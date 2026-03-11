from typing import Dict, List, Optional

import structlog
import torch
import torch.nn as nn
import torch.nn.functional as F
from geoopt import PoincareBall

from .cleaner import clean_description
from .rules import KeywordMatcher

logger = structlog.get_logger()

# Confidence threshold for categorization.
# Predictions below this score are stored as suggested_category
# and the transaction is left as "Uncategorized" for user review.
# Tune after running real data through the classifier.
CONFIDENCE_THRESHOLD: float = 0.90


class HyperbolicProjector(nn.Module):
    """
    Three-layer projector per HypCD paper Section 3.5:
    Layer 1: Euclidean MLP | Layer 2: Feature Clipping | Layer 3: ExpMap

    Critical: Feature clipping prevents gradient explosion near Poincaré boundary.
    """

    def __init__(
        self,
        input_dim: int = 768,
        hidden_dim: int = 256,
        output_dim: int = 128,
        clip_factor: float = 0.98,
    ):
        """
        Initialize hyperbolic projector.

        Args:
            input_dim: Input dimension (e.g., 768 for BERT)
            hidden_dim: Hidden layer dimension (paper uses 256)
            output_dim: Output dimension (paper projects to 128)
            clip_factor: Clipping boundary (must be < 1.0 for stability)
        """
        super().__init__()

        # Layer 1: Euclidean MLP (768 → 256 → 128)
        self.mlp = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, output_dim),
        )

        # Layer 2: Feature clipping (critical for stability)
        self.clip_factor = clip_factor

        # Layer 3: Poincaré ball manifold
        self.manifold = PoincareBall(c=1.0)

    def clip_features(self, h: torch.Tensor) -> torch.Tensor:
        """
        Clip features to prevent boundary violations.

        Per Section 3.5.2: "We clip the feature magnitude to 0.98 before
        applying the exponential map to ensure numerical stability."

        Args:
            h: Euclidean features from MLP

        Returns:
            Clipped features with norm < clip_factor
        """
        norm = torch.norm(h, dim=-1, keepdim=True)

        # Scale features that exceed clip_factor
        scale = torch.where(
            norm > self.clip_factor,
            self.clip_factor / (norm + 1e-8),  # Add epsilon for stability
            torch.ones_like(norm),
        )

        return h * scale

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Project Euclidean embeddings to hyperbolic space.

        Args:
            x: Euclidean embeddings (batch_size, input_dim)

        Returns:
            Hyperbolic embeddings on Poincaré ball (batch_size, output_dim)
        """
        # Layer 1: Euclidean MLP
        h = self.mlp(x)

        # Layer 2: Feature Clipping (CRITICAL)
        h_clipped = self.clip_features(h)

        # Layer 3: Exponential Map to Poincaré ball
        z_hyp = self.manifold.expmap0(h_clipped)

        return z_hyp


class HyperbolicEmbedder:
    """
    Hyperbolic space embedder using BERT/DistilBERT and Poincaré ball.

    Updated to use backend architecture and explicit hyperbolic projector.
    """

    def __init__(self, backend: Optional["BackendBase"] = None, proj_dim: int = 128):
        """
        Initialize the hyperbolic embedder.

        Args:
            backend: Backend for Euclidean embeddings (Cloud or Mobile)
            proj_dim: Projected dimension for hyperbolic space (default: 128)
        """
        # Initialize backend if not provided
        if backend is None:
            from .backends.cloud import CloudBackend

            backend = CloudBackend()

        self.backend = backend
        self.proj_dim = proj_dim

        # Initialize hyperbolic projector
        self.projector = HyperbolicProjector(input_dim=backend.dim, hidden_dim=256, output_dim=proj_dim).to(
            backend.device
        )

    @property
    def device(self):
        return self.backend.device

    def embed(self, text: str) -> torch.Tensor:
        """Embed a single text string into hyperbolic space."""
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: List[str]) -> torch.Tensor:
        """
        Embed multiple text strings into hyperbolic space.

        Args:
            texts: List of text strings to embed.

        Returns:
            Tensor of hyperbolic embeddings on the Poincaré ball.
        """
        # Get Euclidean embeddings from backend
        euclidean = self.backend.embed_batch(texts)

        # Project to hyperbolic space
        hyperbolic = self.projector(euclidean)

        return hyperbolic

    def distance(self, p1: torch.Tensor, p2: torch.Tensor) -> torch.Tensor:
        return self.projector.manifold.dist(p1, p2)


class HypLinear(nn.Module):
    """
    Hyperbolic linear layer using Möbius algebra.

    Per Section 3.6.1: Implements Möbius matrix-vector multiplication
    W ⊗ x ⊕ b via tangent space operations.
    """

    def __init__(self, in_features: int, out_features: int, manifold):
        """
        Initialize hyperbolic linear layer.

        Args:
            in_features: Input dimension
            out_features: Output dimension
            manifold: PoincaréBall manifold
        """
        super().__init__()
        self.manifold = manifold
        self.in_features = in_features
        self.out_features = out_features

        # Euclidean parameters (applied in tangent space)
        self.weight = nn.Parameter(torch.Tensor(out_features, in_features))
        self.bias = nn.Parameter(torch.Tensor(out_features))

        # Initialize
        nn.init.xavier_uniform_(self.weight)
        nn.init.zeros_(self.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Möbius Matrix-Vector Multiplication: W ⊗ x ⊕ b

        Computed via:
        1. Map x to tangent space at origin
        2. Apply Euclidean linear transform in tangent space
        3. Map back to Poincaré ball

        Args:
            x: Input on Poincaré ball (batch, in_features)

        Returns:
            Output on Poincaré ball (batch, out_features)
        """
        # Convert to tangent space at origin
        x_tan = self.manifold.logmap0(x)

        # Euclidean matmul in tangent space
        out_tan = F.linear(x_tan, self.weight, self.bias)

        # Map back to manifold
        return self.manifold.expmap0(out_tan)


class HypFFN(nn.Module):
    """
    Hyperbolic Feed-Forward Network (Section 3.6.1).

    Two-layer hyperbolic classifier with activation in tangent space.
    Replaces centroid-based classification with learned Möbius layers.
    """

    def __init__(self, dim: int, num_classes: int, manifold):
        """
        Initialize hyperbolic FFN.

        Args:
            dim: Input dimension (e.g., 128 from projector)
            num_classes: Number of output categories
            manifold: PoincaréBall manifold
        """
        super().__init__()
        self.manifold = manifold

        # Two hyperbolic linear layers
        self.fc1 = HypLinear(dim, dim // 2, manifold)
        self.fc2 = HypLinear(dim // 2, num_classes, manifold)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through hyperbolic FFN.

        Args:
            x: Hyperbolic embeddings (batch, dim)

        Returns:
            Class logits in hyperbolic space (batch, num_classes)
        """
        # First hyperbolic linear layer
        x = self.fc1(x)

        # Activation in tangent space (ReLU)
        x_tan = self.manifold.logmap0(x)
        x_tan = F.relu(x_tan)
        x = self.manifold.expmap0(x_tan)

        # Second hyperbolic linear layer
        x = self.fc2(x)

        return x


class HypCDClassifier:
    """
    Hyperbolic Contrastive Learning Classifier with dual-path support.

    Updated to use:
    - Backend architecture (Cloud BERT or Mobile DistilBERT)
    - HyperbolicProjector with feature clipping
    - HypFFN classifier (replacing centroids)
    - HyperbolicKMeans for GCD
    """

    def __init__(
        self,
        backend: Optional["BackendBase"] = None,
        num_classes: int = 11,
        proj_dim: int = 128,
    ):
        """
        Initialize HypCD classifier.

        Args:
            backend: Pre-initialized backend (defaults to CloudBackend)
            num_classes: Number of output categories
            proj_dim: Projected dimension for hyperbolic space
        """
        # Initialize backend (mobile deferred to mobile phase)
        if backend is None:
            from .backends.cloud import CloudBackend

            backend = CloudBackend()

        self.backend = backend
        self.num_classes = num_classes
        self.proj_dim = proj_dim
        self.manifold = PoincareBall(c=1.0)

        # Initialize embedder with projector
        self.embedder = HyperbolicEmbedder(backend=backend, proj_dim=proj_dim)

        # Initialize classifier (HypFFN)
        self.classifier = HypFFN(dim=proj_dim, num_classes=num_classes, manifold=self.manifold).to(backend.device)

        # Category labels
        self.labels = [
            "Food",
            "Transport",
            "Utilities",
            "Salary",
            "Shopping",
            "Entertainment",
            "Health",
            "Education",
            "Finance",
            "People",
            "Misc",
        ]

        self.rule_matcher = KeywordMatcher()
        self.anchors = self._initialize_anchors()

        # Load checkpoint if available (global base or env override)
        self._load_checkpoint()

    def _load_checkpoint(self) -> None:
        """Load global base checkpoint at startup.

        Priority:
          1. HYPCD_CHECKPOINT_PATH env var (explicit override)
          2. AdapterManager: Supabase Storage models/global/base_model.pt
          3. checkpoints/global/base_model.pt (local dev)
          4. Silent skip (random init — first run)
        """
        import os

        from packages.categorization.adapter_manager import AdapterManager

        explicit = os.getenv("HYPCD_CHECKPOINT_PATH")
        if explicit:
            try:
                state = torch.load(explicit, map_location=self.backend.device, weights_only=True)
                self.load_state_dict(state)
                logger.info("checkpoint_loaded", source="env_var", path=explicit)
                return
            except Exception as e:
                logger.warning("checkpoint_load_failed", path=explicit, error=str(e))

        mgr = AdapterManager()
        state = mgr.load_global_base()
        if state:
            try:
                self.load_state_dict(state)
                logger.info("checkpoint_loaded", source="global_base")
            except Exception as e:
                logger.warning("checkpoint_load_failed", source="global_base", error=str(e))
        else:
            logger.debug("checkpoint_not_found", note="using_random_init")

    def to(self, device: torch.device | str):
        self.embedder.projector = self.embedder.projector.to(device)
        self.classifier = self.classifier.to(device)
        if hasattr(self.backend, "model"):
            self.backend.model = self.backend.model.to(device)
        if hasattr(self.backend, "_device"):
            self.backend._device = torch.device(device)
        return self

    def train(self):
        self.embedder.projector.train()
        self.classifier.train()
        return self

    def eval(self):
        self.embedder.projector.eval()
        self.classifier.eval()
        return self

    def state_dict(self) -> Dict[str, Dict[str, torch.Tensor]]:
        return {
            "projector": self.embedder.projector.state_dict(),
            "classifier": self.classifier.state_dict(),
        }

    def load_state_dict(self, state: Dict[str, Dict[str, torch.Tensor]]):
        if "projector" in state:
            self.embedder.projector.load_state_dict(state["projector"])
        if "classifier" in state:
            self.classifier.load_state_dict(state["classifier"])

    def _initialize_anchors(self) -> Dict[str, torch.Tensor]:
        seed_phrases = {
            "Food": [
                "swiggy order",
                "zomato payment",
                "restaurant bill",
                "blinkit grocery delivery",
                "zepto quick delivery",
                "bigbasket grocery order",
                "dunzo delivery",
                "eatfit healthy meal",
                "dominos pizza order",
                "cafe coffee purchase",
            ],
            "Transport": [
                "uber ride payment",
                "ola cab trip",
                "rapido bike taxi",
                "metro card recharge",
                "irctc train ticket",
                "indigo flight booking",
                "petrol pump payment",
                "fastag toll recharge",
                "makemytrip travel booking",
                "redbus bus ticket",
            ],
            "Utilities": [
                "electricity bill payment",
                "water bill payment",
                "airtel mobile recharge",
                "jio prepaid recharge",
                "act fibernet broadband",
                "tata power electricity",
                "vodafone postpaid bill",
                "bwssb water payment",
                "gas cylinder booking",
                "broadband monthly bill",
            ],
            "Salary": [
                "salary credited account",
                "monthly payroll credit",
                "salary transfer neft",
                "payroll deposit",
                "stipend payment credited",
                "wages monthly income",
                "salary for the month",
                "income transfer received",
            ],
            "Shopping": [
                "amazon purchase order",
                "flipkart product order",
                "myntra fashion purchase",
                "nykaa beauty products",
                "meesho clothing order",
                "croma electronics",
                "decathlon sports equipment",
                "ajio fashion sale",
                "retail store purchase",
                "online shopping payment",
            ],
            "Entertainment": [
                "netflix monthly subscription",
                "spotify premium",
                "jiocinema subscription plan",
                "sonyliv monthly",
                "hotstar disney subscription",
                "youtube premium",
                "bookmyshow movie ticket",
                "play pass monthly",
                "music streaming subscription",
                "movie rental payment",
            ],
            "Health": [
                "pharmacy medicine purchase",
                "hospital bill payment",
                "clinic doctor consultation",
                "1mg medicine order",
                "netmeds pharmacy delivery",
                "cult.fit gym membership",
                "healthifyme subscription",
                "apollo pharmacy",
                "lab test diagnostics",
                "medical expense payment",
            ],
            "Education": [
                "udemy online course",
                "unacademy subscription",
                "byju learning app payment",
                "coursera course fee",
                "tuition fee payment",
                "college exam fee",
                "physics wallah subscription",
                "upgrad course",
                "book purchase education",
                "simplilearn certification",
            ],
            "Finance": [
                "loan emi debit",
                "insurance premium payment",
                "mutual fund sip",
                "zerodha brokerage",
                "groww investment",
                "cred credit card",
                "bajaj finance emi",
                "tax payment",
                "upstox trading",
                "fd deposit bank",
            ],
            "People": [
                "transfer to friend",
                "sent money family",
                "upi transfer personal",
                "gift payment friend",
                "reimbursement colleague",
                "money sent contact",
                "personal payment received",
                "family expense split",
            ],
        }

        anchors: Dict[str, torch.Tensor] = {}
        for category, phrases in seed_phrases.items():
            # Use embedder (projector output) so anchors are in the same hyperbolic space
            # as predict_batch embeddings (proj_dim, not backend dim)
            embedded = self.embedder.embed_batch(phrases)
            anchors[category] = embedded.mean(dim=0, keepdim=True)
        return anchors

    def update_anchors(self, labeled_texts: Dict[str, List[str]]) -> None:
        for category, texts in labeled_texts.items():
            valid = [clean_description(str(t)) for t in texts if str(t).strip()]
            valid = [t for t in valid if t]
            if not valid:
                continue
            embedded = self.embedder.embed_batch(valid)
            self.anchors[category] = embedded.mean(dim=0, keepdim=True)

    def _classify_novel(self, embedding: torch.Tensor) -> dict:
        """Route low-confidence embedding through anchor-based GCD (§3.7.2).

        Uses pre-computed category anchors as proxy centroids.
        Finds nearest anchor by hyperbolic distance.
        """
        from .clustering import HierarchyExtractor

        extractor = HierarchyExtractor(self.manifold)
        norm_val = extractor.compute_norm(embedding).item()

        # Stack anchor embeddings — shape (K, D)
        anchor_keys = list(self.anchors.keys())
        anchor_vecs = torch.cat([self.anchors[k] for k in anchor_keys], dim=0)

        # Hyperbolic distances from this embedding to each anchor
        dists = self.manifold.dist(
            embedding.unsqueeze(0).expand(len(anchor_keys), -1),
            anchor_vecs,
        )

        min_idx = dists.argmin().item()
        confidence = torch.exp(-dists[min_idx]).item()

        return {
            "category": anchor_keys[min_idx],
            "confidence": max(confidence, 0.05),
            "norm": norm_val,
        }

    def predict(self, text: str) -> dict:
        """
        Single transaction classification.

        Args:
            text: Transaction description

        Returns:
            Dictionary with category, confidence, embedding
        """
        return self.predict_batch([text])[0]

    def predict_batch(self, texts: list) -> list:
        """
        Batch classification.

        Args:
            texts: List of transaction descriptions

        Returns:
            List of prediction dictionaries
        """
        results: list[dict] = [None] * len(texts)
        model_texts: list[str] = []
        model_indices: list[int] = []

        for i, text in enumerate(texts):
            cleaned = clean_description(str(text))
            candidate = cleaned or str(text)
            rule_category = self.rule_matcher.predict(candidate)
            if rule_category:
                embedding = self.embedder.embed_batch([candidate])[0]
                from .clustering import HierarchyExtractor

                _extractor = HierarchyExtractor(self.manifold)
                norm_val = _extractor.compute_norm(embedding).item()
                results[i] = {
                    "category": rule_category,
                    "confidence": 1.0,
                    "embedding": embedding,
                    "is_novel": False,
                    "depth": "macro" if norm_val < 0.5 else "micro",
                    "norm": norm_val,
                    "path": "keyword_rule",
                }
            else:
                model_texts.append(candidate)
                model_indices.append(i)

        if not model_texts:
            return results

        # Get hyperbolic embeddings for non-rule texts
        embeddings = self.embedder.embed_batch(model_texts)

        # Some tests monkeypatch geoopt and may yield non-tensor embeddings.
        if not isinstance(embeddings, torch.Tensor):
            for model_i, target_i in enumerate(model_indices):
                results[target_i] = {
                    "category": "Misc",
                    "confidence": 0.0,
                    "embedding": embeddings,
                    "is_novel": False,
                    "depth": "macro",
                    "norm": 0.0,
                    "path": "hypffn",
                }
            return results

        # Ensure embeddings is 2D
        if embeddings.dim() == 1:
            embeddings = embeddings.unsqueeze(0)

        # Classify with HypFFN
        with torch.no_grad():
            logits = self.classifier(embeddings)

            # Get softmax in tangent space
            logits_tan = self.manifold.logmap0(logits)
            probs = F.softmax(logits_tan, dim=-1)

            confidences, indices = probs.max(dim=-1)

            # Ensure 1D tensors for iteration
            if confidences.dim() == 0:
                confidences = confidences.unsqueeze(0)
                indices = indices.unsqueeze(0)

        # Import hierarchy extractor once for all results
        from .clustering import HierarchyExtractor

        _extractor = HierarchyExtractor(self.manifold)

        # Build results
        for model_i, (idx, conf) in enumerate(zip(indices, confidences)):
            target_i = model_indices[model_i]
            candidate = model_texts[model_i].lower()
            embedding = embeddings[model_i]

            # §3.7.1 confidence threshold — route novel to GCD
            if conf.item() < CONFIDENCE_THRESHOLD:
                novel = self._classify_novel(embedding)
                results[target_i] = {
                    "category": novel["category"],
                    "confidence": novel["confidence"],
                    "embedding": embedding,
                    "is_novel": True,
                    "depth": "boundary",
                    "norm": novel["norm"],
                    "path": "novel_cluster",
                }
                continue

            predicted = self.labels[idx.item()]

            # §3.1 Salary guardrail
            if predicted == "Salary" and not any(
                token in candidate for token in ["salary", "payroll", "stipend", "credited", "wage"]
            ):
                predicted = "Misc"

            # §3.8 Hierarchy norm extraction
            norm_val = _extractor.compute_norm(embedding).item()
            depth = "macro" if norm_val < 0.5 else "micro"

            results[target_i] = {
                "category": predicted,
                "confidence": conf.item(),
                "embedding": embedding,
                "is_novel": False,
                "depth": depth,
                "norm": norm_val,
                "path": "hypffn",
            }

        return results

    def discover_categories(self, texts: list, n_clusters: int = 5, confidence_threshold: float = 0.7) -> list:
        """
        Discover novel categories using GCD.

        Args:
            texts: Unlabeled transaction descriptions
            n_clusters: Number of novel clusters to discover
            confidence_threshold: Threshold for novel detection

        Returns:
            List of discovered category dictionaries
        """
        from .clustering import HyperbolicKMeans

        # Get embeddings
        embeddings = self.embedder.embed_batch(texts)

        # Cluster
        kmeans = HyperbolicKMeans(n_clusters=n_clusters, manifold=self.manifold)
        kmeans.fit(embeddings)

        # Get labels and confidence
        labels, confidence, is_known = kmeans.predict(embeddings, confidence_threshold=confidence_threshold)

        # Build results
        discovered = []
        for k in range(n_clusters):
            mask = labels == k
            cluster_texts = [texts[i] for i in range(len(texts)) if mask[i]]
            cluster_conf = confidence[mask].mean().item()

            discovered.append(
                {
                    "cluster_id": k,
                    "centroid": kmeans.centroids[k],
                    "sample_texts": cluster_texts[:5],  # Top 5 examples
                    "confidence": cluster_conf,
                    "count": mask.sum().item(),
                }
            )

        return discovered

    def extract_hierarchy(self) -> dict:
        """
        Extract taxonomy from classifier embeddings.

        Returns:
            Taxonomy dictionary with macro/micro categories
        """
        from .clustering import HierarchyExtractor

        # Get class embeddings from classifier
        # Use classifier's output layer weights as centroids
        with torch.no_grad():
            # Get second layer weights
            weights = self.classifier.fc2.weight  # (num_classes, dim//2)
            # Project to full dimension
            centroids = self.classifier.fc1.manifold.expmap0(torch.matmul(weights, self.classifier.fc1.weight))

        extractor = HierarchyExtractor(self.manifold)
        taxonomy = extractor.build_taxonomy(centroids, self.labels)

        return taxonomy


# Legacy class for backward compatibility
class HypCDClassifierLegacy(HypCDClassifier):
    """Legacy classifier with anchor-based prediction."""

    pass  # Inherits from new implementation but could be extended for backward compat
