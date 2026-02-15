"""
Tests for comprehensive training pipeline.

Validates:
- Configuration management
- Checkpoint persistence and recovery
- Distributed training setup
- Data preparation from ingestion_engine
- Hierarchical loss computation
- Integration with forecasting dependencies
"""

import pytest
import torch
import tempfile
import os
import json
from unittest.mock import MagicMock, patch

from packages.categorization.training_pipeline import (
    TrainingConfig,
    CheckpointManager,
    HierarchicalLoss,
    TrainingMonitor,
    HypCDTrainingPipeline,
    create_default_pipeline,
    load_pipeline_from_checkpoint
)
from packages.categorization.backends.cloud import CloudBackend


class TestTrainingConfig:
    """Test training configuration management."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = TrainingConfig()
        assert config.input_dim == 768
        assert config.proj_dim == 128
        assert config.num_classes == 11
        assert config.epochs == 50
        assert config.batch_size == 32
    
    def test_config_serialization(self):
        """Test config save/load."""
        config = TrainingConfig(epochs=100, batch_size=64)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            config.save(temp_path)
            loaded_config = TrainingConfig.load(temp_path)
            
            assert loaded_config.epochs == 100
            assert loaded_config.batch_size == 64
            assert loaded_config.input_dim == 768
        finally:
            os.unlink(temp_path)
    
    def test_config_to_dict(self):
        """Test config conversion to dictionary."""
        config = TrainingConfig()
        config_dict = config.to_dict()
        
        assert isinstance(config_dict, dict)
        assert 'input_dim' in config_dict
        assert 'epochs' in config_dict
    
    def test_config_from_dict(self):
        """Test config creation from dictionary."""
        config_dict = {'epochs': 25, 'batch_size': 16}
        config = TrainingConfig.from_dict(config_dict)
        
        assert config.epochs == 25
        assert config.batch_size == 16
        assert config.input_dim == 768  # Default preserved


class TestCheckpointManager:
    """Test checkpoint persistence and recovery."""
    
    def test_checkpoint_save_load(self):
        """Test saving and loading checkpoints."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CheckpointManager(temp_dir, keep_last_n=2)
            
            # Save checkpoint
            model_state = {'weight': torch.tensor([1.0, 2.0])}
            optimizer_state = {'lr': 0.001}
            config = TrainingConfig()
            metrics = {'loss': 0.5, 'accuracy': 0.85}
            
            path = manager.save(
                epoch=5,
                model_state=model_state,
                optimizer_state=optimizer_state,
                scheduler_state=None,
                config=config,
                metrics=metrics
            )
            
            # Load checkpoint
            checkpoint = manager.load(path)
            
            assert checkpoint['epoch'] == 5
            assert torch.equal(checkpoint['model_state']['weight'], model_state['weight'])
            assert checkpoint['metrics']['accuracy'] == 0.85
    
    def test_latest_checkpoint_tracking(self):
        """Test that latest checkpoint is tracked."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CheckpointManager(temp_dir)
            
            config = TrainingConfig()
            
            # Save multiple checkpoints
            for epoch in range(3):
                manager.save(
                    epoch=epoch,
                    model_state={'epoch': epoch},
                    optimizer_state={},
                    scheduler_state=None,
                    config=config,
                    metrics={'loss': 0.1 * epoch}
                )
            
            # Check latest checkpoint exists
            latest = manager.get_latest_checkpoint()
            assert latest is not None
            
            # Load and verify
            checkpoint = manager.load(latest)
            assert checkpoint['epoch'] == 2  # Last epoch
    
    def test_checkpoint_cleanup(self):
        """Test that old checkpoints are cleaned up."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CheckpointManager(temp_dir, keep_last_n=2)
            config = TrainingConfig()
            
            # Save more checkpoints than keep_last_n
            for epoch in range(5):
                manager.save(
                    epoch=epoch,
                    model_state={'epoch': epoch},
                    optimizer_state={},
                    scheduler_state=None,
                    config=config,
                    metrics={'loss': 0.1}
                )
            
            # Check only last N checkpoints remain
            checkpoints = list(manager.checkpoint_dir.glob("checkpoint_epoch_*.pt"))
            assert len(checkpoints) == 2
    
    def test_best_checkpoint_saved(self):
        """Test that best checkpoint is saved separately."""
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = CheckpointManager(temp_dir)
            config = TrainingConfig()
            
            # Save checkpoint as best
            manager.save(
                epoch=1,
                model_state={'epoch': 1},
                optimizer_state={},
                scheduler_state=None,
                config=config,
                metrics={'accuracy': 0.9},
                is_best=True
            )
            
            best = manager.get_best_checkpoint()
            assert best is not None


class TestHierarchicalLoss:
    """Test hierarchical category-aware loss function."""
    
    def test_loss_computation(self):
        """Test basic loss computation."""
        loss_fn = HierarchicalLoss(num_classes=11, alpha=0.5)
        
        # Create sample predictions and targets
        logits = torch.randn(4, 11)
        targets = torch.tensor([0, 1, 2, 3])
        
        loss = loss_fn(logits, targets)
        
        assert loss.dim() == 0  # Scalar
        assert loss.item() > 0
        assert not torch.isnan(loss)
    
    def test_loss_with_hierarchy(self):
        """Test loss with hierarchy matrix."""
        # Create hierarchy matrix (Food and Restaurants are close)
        hierarchy = torch.eye(11)
        hierarchy[0, 1] = 0.5  # Food close to Restaurants
        hierarchy[1, 0] = 0.5
        
        loss_fn = HierarchicalLoss(num_classes=11, hierarchy_matrix=hierarchy, alpha=0.3)
        
        logits = torch.randn(2, 11)
        targets = torch.tensor([0, 1])
        
        loss = loss_fn(logits, targets)
        assert loss.item() > 0


class TestTrainingMonitor:
    """Test training monitoring."""
    
    def test_epoch_logging(self):
        """Test epoch metric logging."""
        monitor = TrainingMonitor()
        
        train_metrics = {'loss': 0.5}
        val_metrics = {'loss': 0.4, 'accuracy': 0.85}
        
        monitor.log_epoch(0, train_metrics, val_metrics)
        
        assert len(monitor.metrics_history) == 1
        assert monitor.best_metrics['accuracy'] == 0.85
    
    def test_early_stopping(self):
        """Test early stopping detection."""
        monitor = TrainingMonitor()
        
        # Add 15 epochs of stagnant validation accuracy
        for epoch in range(15):
            monitor.log_epoch(
                epoch,
                {'loss': 0.5 - epoch * 0.01},
                {'accuracy': 0.8}  # Not improving
            )
        
        assert monitor.should_stop_early(patience=10, metric='accuracy')
    
    def test_no_early_stopping_when_improving(self):
        """Test that early stopping doesn't trigger when metrics improve."""
        monitor = TrainingMonitor()
        
        # Add epochs with improving accuracy
        for epoch in range(15):
            monitor.log_epoch(
                epoch,
                {'loss': 0.5},
                {'accuracy': 0.8 + epoch * 0.01}  # Improving
            )
        
        assert not monitor.should_stop_early(patience=10, metric='accuracy')
    
    def test_metrics_saving(self):
        """Test metrics history saving."""
        monitor = TrainingMonitor()
        
        monitor.log_epoch(0, {'loss': 0.5}, {'accuracy': 0.8})
        monitor.log_epoch(1, {'loss': 0.4}, {'accuracy': 0.85})
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            monitor.save_metrics(temp_path)
            
            with open(temp_path, 'r') as f:
                saved = json.load(f)
            
            assert len(saved) == 2
            assert saved[0]['epoch'] == 0
            assert saved[1]['epoch'] == 1
        finally:
            os.unlink(temp_path)


class TestTrainingPipeline:
    """Test comprehensive training pipeline."""
    
    def test_pipeline_initialization(self):
        """Test pipeline initialization."""
        config = TrainingConfig(epochs=5, checkpoint_dir=tempfile.mkdtemp())
        pipeline = HypCDTrainingPipeline(config)
        
        assert pipeline.config == config
        assert pipeline.device is not None
        assert pipeline.checkpoint_manager is not None
        assert pipeline.monitor is not None
    
    def test_device_setup_auto(self):
        """Test automatic device selection."""
        config = TrainingConfig(device='auto')
        pipeline = HypCDTrainingPipeline(config)
        
        assert pipeline.device in [
            torch.device('cuda'),
            torch.device('mps'),
            torch.device('cpu')
        ]
    
    def test_model_initialization(self):
        """Test model initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = TrainingConfig(
                checkpoint_dir=temp_dir,
                epochs=1
            )
            pipeline = HypCDTrainingPipeline(config)
            
            pipeline.initialize_model()
            
            assert pipeline.backend is not None
            assert pipeline.classifier is not None
            assert pipeline.trainer is not None
    
    @pytest.mark.slow
    def test_training_epoch(self):
        """Test single training epoch."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = TrainingConfig(
                checkpoint_dir=temp_dir,
                epochs=1,
                batch_size=2
            )
            pipeline = HypCDTrainingPipeline(config)
            pipeline.initialize_model()
            
            # Mock data loader
            texts = ['test1', 'test2', 'test3', 'test4']
            labels = [0, 1, 0, 1]
            
            def mock_data_loader():
                return texts, labels
            
            train_loader, val_loader = pipeline.prepare_data(mock_data_loader)
            
            # Train one epoch
            metrics = pipeline.train_epoch(train_loader, epoch=0)
            
            assert 'loss' in metrics
            assert metrics['loss'] >= 0


class TestPipelineIntegration:
    """Test integration with other packages."""
    
    def test_ingestion_engine_integration(self):
        """Test integration with ingestion_engine data."""
        from packages.ingestion_engine.import_transactions import parse_file
        
        config = TrainingConfig()
        pipeline = HypCDTrainingPipeline(config)
        
        # Verify we can use ingestion_engine functions
        # (Actual parsing would require file)
        assert hasattr(parse_file, '__call__')
    
    def test_forecasting_compatibility(self):
        """Test compatibility with forecasting package."""
        from packages.forecasting.dataset import prepare_training_data
        
        config = TrainingConfig()
        pipeline = HypCDTrainingPipeline(config)
        
        # Verify forecasting functions exist
        assert hasattr(prepare_training_data, '__call__')
    
    def test_create_default_pipeline(self):
        """Test factory function for default pipeline."""
        with tempfile.TemporaryDirectory() as temp_dir:
            pipeline = create_default_pipeline(
                checkpoint_dir=temp_dir,
                epochs=10
            )
            
            assert isinstance(pipeline, HypCDTrainingPipeline)
            assert pipeline.config.epochs == 10
    
    def test_load_from_checkpoint(self):
        """Test loading pipeline from checkpoint."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create and save checkpoint
            config = TrainingConfig(checkpoint_dir=temp_dir, epochs=5)
            manager = CheckpointManager(temp_dir)
            
            manager.save(
                epoch=2,
                model_state={'test': 'state'},
                optimizer_state={},
                scheduler_state=None,
                config=config,
                metrics={'loss': 0.3}
            )
            
            checkpoint_path = manager.get_latest_checkpoint()
            
            # Load pipeline
            loaded_config = TrainingConfig.load_from_checkpoint(checkpoint_path)
            assert loaded_config.epochs == 5


class TestProductionReadiness:
    """Test production-ready features."""
    
    def test_logging_configuration(self):
        """Test that logging is properly configured."""
        import logging
        
        logger = logging.getLogger('packages.categorization.training_pipeline')
        assert logger.level == logging.INFO
    
    def test_checkpoint_recovery(self):
        """Test recovery from checkpoint after interruption."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = TrainingConfig(checkpoint_dir=temp_dir)
            manager = CheckpointManager(temp_dir)
            
            # Simulate interrupted training
            manager.save(
                epoch=10,
                model_state={'epoch': 10},
                optimizer_state={'step': 100},
                scheduler_state=None,
                config=config,
                metrics={'loss': 0.2}
            )
            
            # Resume
            checkpoint = manager.load()
            assert checkpoint['epoch'] == 10
            assert checkpoint['optimizer_state']['step'] == 100
    
    def test_model_export(self):
        """Test model export for production."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = TrainingConfig(checkpoint_dir=temp_dir)
            pipeline = HypCDTrainingPipeline(config)
            pipeline.initialize_model()
            
            export_path = os.path.join(temp_dir, 'model.pt')
            pipeline.export_model(export_path)
            
            assert os.path.exists(export_path)
            
            # Verify exported model can be loaded
            exported = torch.load(export_path, map_location='cpu')
            assert 'classifier' in exported
            assert 'config' in exported


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
