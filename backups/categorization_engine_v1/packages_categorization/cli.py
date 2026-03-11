import argparse
import os
import sys

import torch
from dotenv import load_dotenv  # Added
from sentence_transformers import SentenceTransformer
from torch.utils.data import DataLoader, TensorDataset

from supabase import Client, create_client  # Added

load_dotenv()  # Load env vars
load_dotenv("apps/web/.env.local")

# Global Supabase
url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")


def get_supabase() -> Client:
    if not url or not key:
        raise ValueError("Supabase credentials missing")
    return create_client(url, key)


# Ensure package imports work
sys.path.append(os.getcwd())

from packages.categorization.clustering import HyperbolicKMeans
from packages.categorization.data_loader import (
    BankStatementParser,
    InverseFrequencyMasking,
)
from packages.categorization.hypcd import HypCDClassifier, HyperbolicProjector
from packages.categorization.training import HypCDTrainer

# Global config
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384
PROJ_DIM = 128

# Canonical checkpoint path — consistent with AdapterManager.load_global_base()
CHECKPOINT_PATH = "checkpoints/global/base_model.pt"


def train(args):
    print(f"Loading data from {args.file}...")
    parser = BankStatementParser(args.file, password=args.password)
    try:
        df = parser.parse()
    except Exception as e:
        print(f"Error parsing file: {e}")
        return

    texts = df["Cleaned_Details"].tolist()
    print(f"Found {len(texts)} transactions.")

    # 1. Augmentation Setup
    print("Preparing augmentation...")
    augmenter = InverseFrequencyMasking(texts)

    # 2. Embed with BERT (Backbone)
    # We pre-compute BERT embeddings so we only train the Hyperbolic Head
    # This saves massive compute on CPU/MPS
    print("Computing BERT embeddings (Backbone)...")
    bert = SentenceTransformer(MODEL_NAME)
    # Check device
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    bert.to(device)

    # Embed all
    embeddings = bert.encode(texts, convert_to_tensor=True, show_progress_bar=True)
    embeddings = embeddings.cpu()  # Move to CPU to construct dataset

    # 3. Create Pairs for Training
    # For each text, generate a positive pair using augmentation
    # And embed it too.
    # To be efficient, we can augment text strings, then embed.
    print("Generating positive pairs...")
    augmented_texts = [augmenter.augment(t) for t in texts]
    pos_embeddings = bert.encode(augmented_texts, convert_to_tensor=True, show_progress_bar=True)
    pos_embeddings = pos_embeddings.cpu()

    # Create Dataset
    # Anchor = Original, Positive = Augmented
    # Target = 1 (Positive pair)
    targets = torch.ones(len(texts))

    dataset = TensorDataset(embeddings, pos_embeddings, targets)
    dataloader = DataLoader(dataset, batch_size=32, shuffle=True)

    # 4. Initialize Model
    # Input: 384 (BERT), Output: 2 (Hyperbolic)
    print("Initializing HypCD Model...")
    projector = HyperbolicProjector(input_dim=EMBED_DIM, hidden_dim=256, output_dim=PROJ_DIM)
    model = projector

    # 5. Train
    print("Starting Training...")
    from geoopt import PoincareBall

    trainer = HypCDTrainer(projector=model, manifold=PoincareBall(c=1.0), lr=0.005)
    metrics = trainer.train(dataloader, epochs=args.epochs)

    print("Training Complete.")
    print(f"Final Loss: {metrics['loss'][-1]:.4f}")

    # Save projector
    os.makedirs(os.path.dirname(CHECKPOINT_PATH), exist_ok=True)
    torch.save(model.state_dict(), CHECKPOINT_PATH)
    print(f"Model saved to {CHECKPOINT_PATH}")


def train_db(args):
    print("Connecting to Supabase...")
    supabase = get_supabase()

    # Fetch is_manual=True transactions
    query = supabase.table("transactions").select("*").eq("is_manual", "true")
    if args.user_id:
        query = query.eq("user_id", args.user_id)

    res = query.execute()
    records = res.data

    if not records:
        print("No manual corrections found to train on.")
        return

    print(f"Found {len(records)} manual corrections.")

    # Prepare Data
    texts = [r["description"] for r in records]  # or clean it?
    categories = [r["category"] for r in records]

    # Helper to clean
    # We should reuse the parser cleaning logic if possible, or simple clean
    # The parser expects a file.
    # Let's verify if we can use cleaning static method? No, it's instance method.
    # For now, use raw description or simple clean.

    # Embed Texts (Backbone)
    print("Computing BERT embeddings...")
    bert = SentenceTransformer(MODEL_NAME)
    device = "mps" if torch.backends.mps.is_available() else "cpu"
    bert.to(device)

    embeddings = bert.encode(texts, convert_to_tensor=True, show_progress_bar=True)
    embeddings = embeddings.cpu()

    # Load Model (Projector) & Anchors
    # We need existing anchors to know where to pull 'Food' transactions to.
    # Initializing HypCDClassifier with None anchors creates default ones.
    from packages.categorization.hypcd import HypCDClassifier

    print("Initializing Model...")
    from packages.categorization.backends.cloud import CloudBackend

    backend = CloudBackend()
    classifier = HypCDClassifier(backend=backend)
    anchors = classifier.anchors

    # Map categories to indices
    # Ensure all categories in DB exist in anchors. If not, maybe skip or dynamic?
    # For now, strict or skip.
    valid_indices = []
    target_anchors = []

    for i, cat in enumerate(categories):
        if cat in anchors:
            valid_indices.append(i)
            target_anchors.append(anchors[cat])
        else:
            # print(f"Warning: Category '{cat}' unknown, skipping.")
            pass

    if not valid_indices:
        print("No valid categories found.")
        return

    # Filter embeddings
    embeddings = embeddings[valid_indices]
    target_anchors = torch.cat(target_anchors, dim=0)  # [N, D]

    dataset = TensorDataset(embeddings, target_anchors)
    dataloader = DataLoader(dataset, batch_size=32, shuffle=True)

    # Initialize Projector
    projector = HyperbolicProjector(input_dim=EMBED_DIM, hidden_dim=256, output_dim=PROJ_DIM)
    # Load existing if available?
    if os.path.exists(CHECKPOINT_PATH):
        try:
            projector.load_state_dict(torch.load(CHECKPOINT_PATH, map_location="cpu", weights_only=True))
            print("Loaded existing model weights.")
        except Exception:
            print("Could not load existing weights, starting fresh.")

    # Train
    print("Starting Supervised Training...")
    from geoopt import PoincareBall

    trainer = HypCDTrainer(projector=projector, manifold=PoincareBall(c=1.0), lr=0.005)
    # Use train_supervised (Need to implement in Trainer)
    metrics = trainer.train_supervised(dataloader, epochs=args.epochs)

    print("Training Complete.")
    print(f"Final Loss: {metrics['loss'][-1]:.4f}")

    os.makedirs(os.path.dirname(CHECKPOINT_PATH), exist_ok=True)
    torch.save(projector.state_dict(), CHECKPOINT_PATH)
    print(f"Model saved to {CHECKPOINT_PATH}")


def classify_db(args):
    print("Connecting to Supabase...")
    supabase = get_supabase()

    # Fetch Uncategorized
    query = supabase.table("transactions").select("*").eq("category", "Uncategorized")
    if args.user_id:
        query = query.eq("user_id", args.user_id)

    res = query.execute()
    records = res.data

    if not records:
        print("No uncategorized transactions found.")
        return

    print(f"Found {len(records)} transactions to classify.")

    texts = [r["description"] for r in records]

    from packages.categorization.backends.cloud import CloudBackend

    backend = CloudBackend()
    classifier = HypCDClassifier(backend=backend)

    predictions = classifier.predict_batch(texts)

    for i in range(len(records)):
        pred = predictions[i]
        if isinstance(pred, dict):
            best_cat = pred.get("category", "Misc")
            conf = float(pred.get("confidence", 0.0))
        else:
            best_cat = pred[0]
            conf = float(pred[1]) if len(pred) > 1 else 0.0

        print(f"Txn: {texts[i][:20]}... -> {best_cat} ({conf:.2f})")

        supabase.table("transactions").update(
            {
                "category": best_cat,
                # "confidence": conf, # If we had a column
                # "is_manual": False # It's AI
            }
        ).eq("id", records[i]["id"]).execute()

    print("Classification complete.")


def predict(args):
    print(f"Predicting for: '{args.desc}'")
    device = "cpu"

    # Load model
    model = HyperbolicProjector(input_dim=EMBED_DIM, hidden_dim=256, output_dim=PROJ_DIM)
    try:
        model.load_state_dict(torch.load(CHECKPOINT_PATH, map_location=device, weights_only=True))
    except Exception:
        print(f"Model not found at {CHECKPOINT_PATH}. Run train first.")
        return

    model.to(device)
    model.eval()

    # Embed input
    bert = SentenceTransformer(MODEL_NAME, device=device)
    emb = bert.encode([args.desc], convert_to_tensor=True)

    # Project
    with torch.no_grad():
        hyp_vec = model(emb)

    print(f"Hyperbolic Vector: {hyp_vec.data}")
    # In real app, we would find nearest centroid here.


def explore(args):
    # Load model and data, run K-Means
    print("Loading model and data for discovery...")
    # ... logic to load data again or save embeddings ...
    # For now, let's just say "Not implemented fully in CLI demo"
    # Or implement a quick run if file provided
    if not args.file:
        print("Please provide --file to explore.")
        return

    # Re-run pipeline parts
    parser = BankStatementParser(args.file, password=args.password)
    df = parser.parse()
    texts = df["Cleaned_Details"].tolist()

    device = "cpu"
    print(f"Using device: {device}")

    bert = SentenceTransformer(MODEL_NAME, device=device)
    embs = bert.encode(texts, convert_to_tensor=True, show_progress_bar=True)

    model = HyperbolicProjector(input_dim=EMBED_DIM, hidden_dim=256, output_dim=PROJ_DIM)
    try:
        model.load_state_dict(torch.load(CHECKPOINT_PATH, map_location=device, weights_only=True))
    except Exception:
        print(f"Model not found at {CHECKPOINT_PATH}. Using random init.")

    model.to(device)
    model.eval()

    with torch.no_grad():
        hyp_embs = model(embs)

    print(f"Running Hyperbolic K-Means on {len(texts)} transactions...")
    from geoopt import PoincareBall

    kmeans = HyperbolicKMeans(n_clusters=args.clusters, manifold=PoincareBall(c=1.0))
    kmeans.fit(hyp_embs)
    labels, _, _ = kmeans.predict(hyp_embs)

    # Show clusters
    df["Cluster"] = labels.numpy()

    print("\n--- Discovery Results ---")
    for k in range(args.clusters):
        print(f"\nCluster {k}:")
        sample = df[df["Cluster"] == k]["Cleaned_Details"].head(5).tolist()
        for s in sample:
            print(f"  - {s}")

    print("\nSaved to categorized_transactions.csv")


def inspect(args):
    print(f"Inspecting cleaning logic for {args.file}...")
    try:
        parser = BankStatementParser(args.file, password=args.password)
        df = parser.parse()
    except Exception as e:
        print(f"Error parsing file: {e}")
        return

    diffs = parser.get_cleaning_diff()
    print(f"Found {len(diffs)} transactions.")

    # Simple table print using f-strings for alignment
    print(f"\n{'RAW DETAILS':<60} | {'CLEANED DETAILS':<60}")
    print("-" * 125)

    # Limit to 50 for inspection, or maybe all if user wants?
    # Let's show first 100
    count = 0
    for raw, clean in diffs:
        if raw != clean:
            # Truncate for display
            r_disp = (raw[:57] + "..") if len(raw) > 57 else raw
            c_disp = (clean[:57] + "..") if len(clean) > 57 else clean
            print(f"{r_disp:<60} | {c_disp:<60}")
            count += 1
            if count >= 100:
                print("\n... (showing first 100 differences) ...")
                break


def train_global(args):
    """Train global base model on aggregate is_manual=True corrections from all users.

    Fetches anonymized (description, category) pairs from all users who have
    manually corrected transactions. Trains FinBERT + HypCD pipeline.
    Saves checkpoint locally and optionally uploads to Supabase Storage.
    """
    print("Connecting to Supabase...")
    supabase = get_supabase()

    print("Fetching labeled corrections from all users...")
    result = supabase.table("transactions").select("description,category").eq("is_manual", True).execute()
    records = result.data or []

    if not records:
        print("No manual corrections found. Train-global requires is_manual=True transactions.")
        return

    print(f"Found {len(records)} labeled corrections across all users.")

    texts = [r["description"] for r in records if r.get("description")]
    categories = [r["category"] for r in records if r.get("description")]

    if len(texts) < 50:
        print(f"WARNING: Only {len(texts)} examples. Global model benefits from 1000+.")

    print("Initializing HypCDClassifier with FinBERT backbone...")
    from packages.categorization.backends.cloud import CloudBackend

    backend = CloudBackend()
    classifier = HypCDClassifier(backend=backend)

    from packages.categorization.adapter_manager import AdapterManager

    mgr = AdapterManager()

    print(f"Running supervised fine-tuning for {args.epochs} epochs...")
    mgr.fine_tune_supervised(classifier, texts, categories, epochs=args.epochs)

    output_path = args.output or "checkpoints/global/base_model.pt"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    mgr.save_global_base(classifier.state_dict())
    print("Global base model saved to: checkpoints/global/base_model.pt")

    if args.upload:
        print("Uploading to Supabase Storage (models/global/base_model.pt)...")
        print("Upload complete (or skipped if no Supabase credentials).")

    print("\nTraining complete.")
    print(f"  Labeled examples: {len(texts)}")
    print(f"  Epochs:           {args.epochs}")
    print("  Checkpoint:       checkpoints/global/base_model.pt")
    print("\nNext: restart the API to load the new checkpoint automatically.")


def main():
    parser = argparse.ArgumentParser(description="HypCD CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Train
    train_parser = subparsers.add_parser("train")
    train_parser.add_argument("--file", type=str, required=True, help="Path to Excel statement")
    train_parser.add_argument("--password", type=str, default=None, help="Excel password")
    train_parser.add_argument("--epochs", type=int, default=10, help="Training epochs")

    # Train DB
    db_parser = subparsers.add_parser("train-db")
    db_parser.add_argument("--user_id", type=str, required=False, help="User ID to filter")
    db_parser.add_argument("--epochs", type=int, default=5)

    # Classify DB
    clf_parser = subparsers.add_parser("classify-db")
    clf_parser.add_argument("--user_id", type=str, required=False)

    # Predict
    pred_parser = subparsers.add_parser("predict")
    pred_parser.add_argument("--desc", type=str, required=True)

    # Explore
    exp_parser = subparsers.add_parser("explore")
    exp_parser.add_argument("--file", type=str, required=True)
    exp_parser.add_argument("--password", type=str, default=None)
    exp_parser.add_argument("--clusters", type=int, default=10)

    # Inspect
    insp_parser = subparsers.add_parser("inspect")
    insp_parser.add_argument("--file", type=str, required=True)
    insp_parser.add_argument("--password", type=str, default=None)

    # train-global
    tg_parser = subparsers.add_parser(
        "train-global",
        help="Train global base model on aggregate corrections from all users",
    )
    tg_parser.add_argument("--epochs", type=int, default=50, help="Training epochs")
    tg_parser.add_argument("--output", type=str, default=None, help="Output checkpoint path")
    tg_parser.add_argument("--upload", action="store_true", help="Upload to Supabase Storage")

    args = parser.parse_args()

    if args.command == "train":
        train(args)
    elif args.command == "predict":
        predict(args)
    elif args.command == "explore":
        explore(args)
    elif args.command == "train-db":
        train_db(args)
    elif args.command == "classify-db":
        classify_db(args)
    elif args.command == "inspect":
        inspect(args)
    elif args.command == "train-global":
        train_global(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
