"""
Comprehensive Training Pipeline for HypCDClassifier

Features:
- BERT-768 CloudBackend architecture
- End-to-end data ingestion integration
- Distributed training with device management
- Checkpoint persistence and recovery
- Hierarchical category-aware loss functions
- Production-ready monitoring and logging
- Resume from interruption capability
- Compatible with forecasting and ingestion_engine packages
"""

import os
import json
import logging
import torch
import torch.nn as nn
import torch.distributed as dist
from torch.utils.data import DataLoader, Dataset
from torch.nn.parallel import DistributedDataParallel as DDP
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, asdict
import numpy as np
from tqdm import tqdm

from .hypcd import HypCDClassifier, HyperbolicProjector, HypFFN
from .backends.cloud import CloudBackend
from .backends.base import BackendBase
from .training import HypCDTrainer
from .clustering import HierarchyExtractor
from .cleaner import TextAugmenter
from geoopt import PoincareBall

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@dataclass
class TrainingConfig:
    """Configuration for training pipeline."""
    # Model architecture
    input_dim: int = 768  # BERT base
    hidden_dim: int = 256
    proj_dim: int = 128
    num_classes: int = 11
    
    # Training hyperparameters
    epochs: int = 50
    batch_size: int = 32
    learning_rate: float = 1e-4
    weight_decay: float = 1e-5
    warmup_steps: int = 100
    
    # Loss weights
    lambda_distance: float = 0.5
    lambda_angle: float = 0.3
    lambda_hierarchy: float = 0.2
    
    # Data augmentation
    augmentation_prob: float = 0.3
    
    # Checkpointing
    checkpoint_dir: str = "checkpoints"
    checkpoint_frequency: int = 5  # Save every N epochs
    keep_last_n: int = 3  # Keep only last N checkpoints
    
    # Distributed training
    distributed: bool = False
    world_size: int = 1
    local_rank: int = 0
    
    # Device management
    device: str = "auto"  # auto, cpu, cuda, mps
    mixed_precision: bool = True
    
    # Data ingestion
    data_source: str = "supabase"  # supabase, csv, json
    min_samples_per_class: int = 10
    validation_split: float = 0.1
    
    # Monitoring
    log_frequency: int = 10  # Log every N batches
    validate_frequency: int = 1  # Validate every N epochs
    
    # Resume training
    resume_from: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert config to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, config_dict: Dict) -> 'TrainingConfig':
        """Create config from dictionary."""
        return cls(**config_dict)
    
    def save(self, path: str):
        """Save config to JSON file."""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, path: str) -> 'TrainingConfig':
        """Load config from JSON file."""
        with open(path, 'r') as f:
            return cls.from_dict(json.load(f))

    @classmethod
    def load_from_checkpoint(cls, checkpoint_path: str) -> 'TrainingConfig':
        """Load config from a serialized training checkpoint."""
        checkpoint = torch.load(checkpoint_path, map_location='cpu')
        config_data = checkpoint.get('config', {})
        if isinstance(config_data, TrainingConfig):
            return config_data
        if isinstance(config_data, dict):
            return cls.from_dict(config_data)
        return cls()


class TransactionDataset(Dataset):
    """Dataset for transaction categorization."""
    
    def __init__(
        self,
        texts: List[str],
        labels: List[int],
        backend: BackendBase,
        augment: bool = False,
        augmenter: Optional[TextAugmenter] = None
    ):
        self.texts = texts
        self.labels = labels
        self.backend = backend
        self.augment = augment
        self.augmenter = augmenter or TextAugmenter()
    
    def __len__(self) -> int:
        return len(self.texts)
    
    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, int, str]:
        text = self.texts[idx]
        label = self.labels[idx]
        
        # Apply augmentation if enabled
        if self.augment:
            text = self.augmenter.augment(text)
        
        # Get embedding from backend
        embedding = self.backend.embed(text)
        
        return embedding, label, text


class HierarchicalLoss(nn.Module):
    """
    Hierarchical category-aware loss function.
    
    Incorporates taxonomy structure into the loss computation,
    penalizing predictions that violate hierarchical relationships.
    """
    
    def __init__(
        self,
        num_classes: int,
        hierarchy_matrix: Optional[torch.Tensor] = None,
        alpha: float = 0.5
    ):
        super().__init__()
        self.num_classes = num_classes
        self.alpha = alpha
        
        # If hierarchy matrix not provided, use identity (no hierarchy)
        if hierarchy_matrix is None:
            hierarchy_matrix = torch.eye(num_classes)
        
        self.register_buffer('hierarchy_matrix', hierarchy_matrix)
        self.ce_loss = nn.CrossEntropyLoss()
    
    def forward(
        self,
        logits: torch.Tensor,
        targets: torch.Tensor
    ) -> torch.Tensor:
        """
        Compute hierarchical loss.
        
        Args:
            logits: Model predictions (batch, num_classes)
            targets: Ground truth labels (batch,)
            
        Returns:
            Combined loss value
        """
        # Standard cross-entropy
        ce_loss = self.ce_loss(logits, targets)
        
        # Hierarchical penalty
        # Penalize predictions that are far in the hierarchy
        probs = torch.softmax(logits, dim=-1)
        batch_size = targets.size(0)
        
        hierarchical_penalty = 0.0
        for i in range(batch_size):
            target_class = targets[i].item()
            # Get hierarchy distances for this target
            hier_distances = self.hierarchy_matrix[target_class]
            # Weight probabilities by hierarchy distance
            weighted_probs = probs[i] * (1.0 + hier_distances)
            hierarchical_penalty += weighted_probs.sum()
        
        hierarchical_penalty = hierarchical_penalty / batch_size
        
        # Combine losses
        total_loss = (1 - self.alpha) * ce_loss + self.alpha * hierarchical_penalty
        
        return total_loss


class CheckpointManager:
    """Manages checkpoint persistence and recovery."""
    
    def __init__(self, checkpoint_dir: str, keep_last_n: int = 3):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.keep_last_n = keep_last_n
        self.metadata_file = self.checkpoint_dir / "checkpoint_metadata.json"
    
    def save(
        self,
        epoch: int,
        model_state: Dict,
        optimizer_state: Dict,
        scheduler_state: Optional[Dict],
        config: TrainingConfig,
        metrics: Dict,
        is_best: bool = False
    ) -> str:
        """Save checkpoint."""
        checkpoint = {
            'epoch': epoch,
            'model_state': model_state,
            'optimizer_state': optimizer_state,
            'scheduler_state': scheduler_state,
            'config': config.to_dict(),
            'metrics': metrics,
            'timestamp': datetime.now().isoformat()
        }
        
        # Save checkpoint
        checkpoint_path = self.checkpoint_dir / f"checkpoint_epoch_{epoch}.pt"
        torch.save(checkpoint, checkpoint_path)
        
        # Save best checkpoint separately
        if is_best:
            best_path = self.checkpoint_dir / "best_checkpoint.pt"
            torch.save(checkpoint, best_path)
        
        # Save latest checkpoint
        latest_path = self.checkpoint_dir / "latest_checkpoint.pt"
        torch.save(checkpoint, latest_path)
        
        # Update metadata
        self._update_metadata(epoch, str(checkpoint_path), metrics)
        
        # Clean old checkpoints
        self._cleanup_old_checkpoints()
        
        logger.info(f"Checkpoint saved: {checkpoint_path}")
        return str(checkpoint_path)
    
    def load(self, checkpoint_path: Optional[str] = None) -> Dict:
        """Load checkpoint."""
        if checkpoint_path is None:
            # Load latest checkpoint
            checkpoint_path = self.checkpoint_dir / "latest_checkpoint.pt"
        else:
            checkpoint_path = Path(checkpoint_path)
        
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
        
        checkpoint = torch.load(checkpoint_path, map_location='cpu')
        logger.info(f"Checkpoint loaded: {checkpoint_path}")
        return checkpoint
    
    def _update_metadata(self, epoch: int, path: str, metrics: Dict):
        """Update checkpoint metadata."""
        metadata = self._load_metadata()
        metadata['checkpoints'] = metadata.get('checkpoints', [])
        metadata['checkpoints'].append({
            'epoch': epoch,
            'path': path,
            'metrics': metrics,
            'timestamp': datetime.now().isoformat()
        })
        
        with open(self.metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def _load_metadata(self) -> Dict:
        """Load checkpoint metadata."""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        return {}
    
    def _cleanup_old_checkpoints(self):
        """Remove old checkpoints, keeping only last N."""
        checkpoints = sorted(
            self.checkpoint_dir.glob("checkpoint_epoch_*.pt"),
            key=lambda x: x.stat().st_mtime
        )
        
        if len(checkpoints) > self.keep_last_n:
            for checkpoint in checkpoints[:-self.keep_last_n]:
                checkpoint.unlink()
                logger.info(f"Removed old checkpoint: {checkpoint}")
    
    def get_latest_checkpoint(self) -> Optional[str]:
        """Get path to latest checkpoint."""
        latest = self.checkpoint_dir / "latest_checkpoint.pt"
        if latest.exists():
            return str(latest)
        return None
    
    def get_best_checkpoint(self) -> Optional[str]:
        """Get path to best checkpoint."""
        best = self.checkpoint_dir / "best_checkpoint.pt"
        if best.exists():
            return str(best)
        return None


class TrainingMonitor:
    """Monitors training progress and logs metrics."""
    
    def __init__(self, log_frequency: int = 10):
        self.log_frequency = log_frequency
        self.metrics_history = []
        self.best_metrics = {}
    
    def log_batch(
        self,
        epoch: int,
        batch: int,
        total_batches: int,
        loss: float,
        learning_rate: float
    ):
        """Log batch-level metrics."""
        if batch % self.log_frequency == 0:
            logger.info(
                f"Epoch [{epoch}] Batch [{batch}/{total_batches}] "
                f"Loss: {loss:.4f} LR: {learning_rate:.6f}"
            )
    
    def log_epoch(
        self,
        epoch: int,
        train_metrics: Dict,
        val_metrics: Optional[Dict] = None
    ):
        """Log epoch-level metrics."""
        metrics = {
            'epoch': epoch,
            'train': train_metrics,
            'validation': val_metrics,
            'timestamp': datetime.now().isoformat()
        }
        self.metrics_history.append(metrics)
        
        # Update best metrics
        if val_metrics:
            for key, value in val_metrics.items():
                if key not in self.best_metrics or value > self.best_metrics[key]:
                    self.best_metrics[key] = value
        
        logger.info(f"Epoch [{epoch}] Train: {train_metrics}")
        if val_metrics:
            logger.info(f"Epoch [{epoch}] Val: {val_metrics}")
        logger.info(f"Best metrics: {self.best_metrics}")
    
    def save_metrics(self, path: str):
        """Save metrics history to file."""
        with open(path, 'w') as f:
            json.dump(self.metrics_history, f, indent=2)
    
    def should_stop_early(
        self,
        patience: int = 10,
        metric: str = 'val_accuracy'
    ) -> bool:
        """Check if training should stop early."""
        if len(self.metrics_history) < patience:
            return False
        
        # Check if metric has improved in last N epochs
        recent_metrics = [
            m.get('validation', {}).get(metric, 0)
            for m in self.metrics_history[-patience:]
        ]
        
        return all(m <= recent_metrics[0] for m in recent_metrics[1:])


class HypCDTrainingPipeline:
    """
    Comprehensive training pipeline for HypCDClassifier.
    
    Integrates with forecasting and ingestion_engine packages,
    supports distributed training, and handles checkpoint recovery.
    """
    
    def __init__(self, config: TrainingConfig):
        self.config = config
        self.device = self._setup_device()
        self.backend = None
        self.classifier = None
        self.trainer = None
        self.checkpoint_manager = CheckpointManager(
            config.checkpoint_dir,
            config.keep_last_n
        )
        self.monitor = TrainingMonitor(config.log_frequency)
        
        # Setup distributed training if enabled
        if config.distributed:
            self._setup_distributed()
    
    def _setup_device(self) -> torch.device:
        """Setup compute device."""
        if self.config.device == "auto":
            if torch.cuda.is_available():
                device = torch.device("cuda")
            elif torch.backends.mps.is_available():
                device = torch.device("mps")
            else:
                device = torch.device("cpu")
        else:
            device = torch.device(self.config.device)
        
        logger.info(f"Using device: {device}")
        return device
    
    def _setup_distributed(self):
        """Setup distributed training."""
        if not dist.is_initialized():
            dist.init_process_group(
                backend='nccl' if torch.cuda.is_available() else 'gloo',
                world_size=self.config.world_size,
                rank=self.config.local_rank
            )
        
        # Set device for distributed training
        if torch.cuda.is_available():
            torch.cuda.set_device(self.config.local_rank)
            self.device = torch.device(f"cuda:{self.config.local_rank}")
    
    def initialize_model(self, resume_from: Optional[str] = None):
        """Initialize model and trainer."""
        # Initialize backend
        self.backend = CloudBackend()
        
        # Initialize classifier
        self.classifier = HypCDClassifier(
            backend=self.backend,
            num_classes=self.config.num_classes,
            proj_dim=self.config.proj_dim,
            backend_type='cloud'
        )
        
        # Move to device
        self.classifier.to(self.device)
        
        # Wrap in DDP if distributed
        if self.config.distributed:
            self.classifier = DDP(
                self.classifier,
                device_ids=[self.config.local_rank]
            )
        
        # Initialize trainer
        self.trainer = HypCDTrainer(
            projector=self.classifier.embedder.projector,
            manifold=self.classifier.manifold,
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
        )
        
        # Resume from checkpoint if specified
        if resume_from:
            self._resume_from_checkpoint(resume_from)
    
    def _resume_from_checkpoint(self, checkpoint_path: str):
        """Resume training from checkpoint."""
        checkpoint = self.checkpoint_manager.load(checkpoint_path)
        
        # Load model state
        model_state = checkpoint['model_state']
        self.classifier.load_state_dict(model_state)
        
        # Load optimizer state
        optimizer_state = checkpoint['optimizer_state']
        self.trainer.optimizer.load_state_dict(optimizer_state)
        
        # Load scheduler state if available
        if checkpoint.get('scheduler_state'):
            self.trainer.scheduler.load_state_dict(checkpoint['scheduler_state'])
        
        start_epoch = checkpoint['epoch'] + 1
        logger.info(f"Resumed from checkpoint: {checkpoint_path}, starting epoch {start_epoch}")
        
        return start_epoch
    
    def prepare_data(
        self,
        data_loader_fn: Callable[[], Tuple[List[str], List[int]]]
    ) -> Tuple[DataLoader, Optional[DataLoader]]:
        """
        Prepare data loaders.
        
        Args:
            data_loader_fn: Function that returns (texts, labels)
            
        Returns:
            Train and validation data loaders
        """
        # Load data
        texts, labels = data_loader_fn()
        
        # Validate minimum samples per class
        unique_labels = set(labels)
        for label in unique_labels:
            count = sum(1 for l in labels if l == label)
            if count < self.config.min_samples_per_class:
                logger.warning(
                    f"Class {label} has only {count} samples, "
                    f"minimum recommended is {self.config.min_samples_per_class}"
                )
        
        # Split into train/validation
        if self.config.validation_split > 0:
            split_idx = int(len(texts) * (1 - self.config.validation_split))
            train_texts, val_texts = texts[:split_idx], texts[split_idx:]
            train_labels, val_labels = labels[:split_idx], labels[split_idx:]
        else:
            train_texts, val_texts = texts, []
            train_labels, val_labels = labels, []
        
        # Create datasets
        train_dataset = TransactionDataset(
            train_texts,
            train_labels,
            self.backend,
            augment=True,
            augmenter=TextAugmenter(train_texts)
        )
        
        # Create data loaders
        train_loader = DataLoader(
            train_dataset,
            batch_size=self.config.batch_size,
            shuffle=True,
            num_workers=4,
            pin_memory=True
        )
        
        val_loader = None
        if val_texts:
            val_dataset = TransactionDataset(
                val_texts,
                val_labels,
                self.backend,
                augment=False
            )
            val_loader = DataLoader(
                val_dataset,
                batch_size=self.config.batch_size,
                shuffle=False,
                num_workers=4,
                pin_memory=True
            )
        
        logger.info(f"Train samples: {len(train_texts)}, Val samples: {len(val_texts)}")
        
        return train_loader, val_loader
    
    def train_epoch(self, train_loader: DataLoader, epoch: int) -> Dict:
        """Train for one epoch."""
        self.classifier.train()
        total_loss = 0.0
        num_batches = 0
        
        progress_bar = tqdm(train_loader, desc=f"Epoch {epoch}")
        for batch_idx, (embeddings, labels, texts) in enumerate(progress_bar):
            # Move to device
            embeddings = embeddings.to(self.device)
            labels = labels.to(self.device)
            
            # Forward pass
            self.trainer.optimizer.zero_grad()
            
            # Get hyperbolic embeddings
            hyp_embeddings = self.classifier.embedder.projector(embeddings)
            
            # Get predictions
            logits = self.classifier.classifier(hyp_embeddings)
            
            # Compute loss (using hierarchical loss)
            criterion = HierarchicalLoss(
                self.config.num_classes,
                alpha=self.config.lambda_hierarchy
            )
            loss = criterion(logits, labels)
            
            # Backward pass
            loss.backward()
            self.trainer.optimizer.step()
            
            # Update metrics
            total_loss += loss.item()
            num_batches += 1
            
            # Log batch metrics
            self.monitor.log_batch(
                epoch,
                batch_idx,
                len(train_loader),
                loss.item(),
                self.trainer.optimizer.param_groups[0]['lr']
            )
            
            # Update progress bar
            progress_bar.set_postfix({'loss': loss.item()})
        
        avg_loss = total_loss / num_batches if num_batches > 0 else 0.0
        return {'loss': avg_loss}
    
    def validate(self, val_loader: DataLoader) -> Dict:
        """Validate model."""
        self.classifier.eval()
        total_loss = 0.0
        correct = 0
        total = 0
        
        with torch.no_grad():
            for embeddings, labels, texts in val_loader:
                # Move to device
                embeddings = embeddings.to(self.device)
                labels = labels.to(self.device)
                
                # Forward pass
                hyp_embeddings = self.classifier.embedder.projector(embeddings)
                logits = self.classifier.classifier(hyp_embeddings)
                
                # Compute loss
                criterion = HierarchicalLoss(self.config.num_classes)
                loss = criterion(logits, labels)
                
                # Compute accuracy
                predictions = torch.argmax(logits, dim=-1)
                correct += (predictions == labels).sum().item()
                total += labels.size(0)
                
                total_loss += loss.item()
        
        avg_loss = total_loss / len(val_loader) if len(val_loader) > 0 else 0.0
        accuracy = correct / total if total > 0 else 0.0
        
        return {'loss': avg_loss, 'accuracy': accuracy}
    
    def train(
        self,
        data_loader_fn: Callable[[], Tuple[List[str], List[int]]],
        resume_from: Optional[str] = None
    ) -> Dict:
        """
        Run complete training pipeline.
        
        Args:
            data_loader_fn: Function that loads training data
            resume_from: Path to checkpoint to resume from
            
        Returns:
            Training metrics
        """
        # Initialize model
        self.initialize_model(resume_from)
        
        # Prepare data
        train_loader, val_loader = self.prepare_data(data_loader_fn)
        
        # Determine starting epoch
        start_epoch = 0
        if resume_from:
            checkpoint = self.checkpoint_manager.load(resume_from)
            start_epoch = checkpoint['epoch'] + 1
        
        best_val_accuracy = 0.0
        
        # Training loop
        for epoch in range(start_epoch, self.config.epochs):
            logger.info(f"Starting epoch {epoch}/{self.config.epochs}")
            
            # Train
            train_metrics = self.train_epoch(train_loader, epoch)
            
            # Validate
            val_metrics = None
            if val_loader and epoch % self.config.validate_frequency == 0:
                val_metrics = self.validate(val_loader)
            
            # Log metrics
            self.monitor.log_epoch(epoch, train_metrics, val_metrics)
            
            # Save checkpoint
            is_best = val_metrics and val_metrics.get('accuracy', 0) > best_val_accuracy
            if is_best:
                best_val_accuracy = val_metrics['accuracy']
            
            if epoch % self.config.checkpoint_frequency == 0 or is_best:
                self.checkpoint_manager.save(
                    epoch,
                    self.classifier.state_dict(),
                    self.trainer.optimizer.state_dict(),
                    None,  # scheduler state
                    self.config,
                    {**train_metrics, **(val_metrics or {})},
                    is_best
                )
            
            # Check early stopping
            if self.monitor.should_stop_early(patience=10):
                logger.info("Early stopping triggered")
                break
        
        # Save final metrics
        self.monitor.save_metrics(
            os.path.join(self.config.checkpoint_dir, 'metrics_history.json')
        )
        
        logger.info("Training completed!")
        return self.monitor.best_metrics
    
    def export_model(self, export_path: str):
        """Export trained model for production."""
        model_state = {
            'classifier': self.classifier.state_dict(),
            'config': self.config.to_dict(),
            'timestamp': datetime.now().isoformat()
        }
        torch.save(model_state, export_path)
        logger.info(f"Model exported to: {export_path}")


def create_default_pipeline(
    checkpoint_dir: str = "checkpoints",
    epochs: int = 50,
    distributed: bool = False
) -> HypCDTrainingPipeline:
    """Create training pipeline with default configuration."""
    config = TrainingConfig(
        checkpoint_dir=checkpoint_dir,
        epochs=epochs,
        distributed=distributed,
        batch_size=32 if not distributed else 16,
        learning_rate=1e-4
    )
    return HypCDTrainingPipeline(config)


def load_pipeline_from_checkpoint(checkpoint_path: str) -> HypCDTrainingPipeline:
    """Load training pipeline from checkpoint."""
    checkpoint = torch.load(checkpoint_path, map_location='cpu')
    config = TrainingConfig.from_dict(checkpoint['config'])
    config.resume_from = checkpoint_path
    
    pipeline = HypCDTrainingPipeline(config)
    return pipeline
