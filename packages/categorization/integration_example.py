"""
Integration Example: Training Pipeline with Forecasting and Ingestion Engine

This script demonstrates how to:
1. Load transaction data from the ingestion_engine
2. Preprocess and categorize transactions using HypCD
3. Export the trained model
4. Use the model in forecasting workflows
"""

import os
import sys
from datetime import datetime
from typing import List, Dict, Tuple
import torch

# Add packages to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from packages.categorization.training_pipeline import (
    HypCDTrainingPipeline,
    TrainingConfig,
    create_default_pipeline
)
from packages.categorization.hypcd import HypCDClassifier
from packages.categorization.backends.cloud import CloudBackend

# Import from ingestion_engine
from packages.ingestion_engine.import_transactions import (
    parse_file,
    clean_transactions,
    validate_and_convert_csv
)

# Import from forecasting
from packages.forecasting.dataset import prepare_training_data
from packages.forecasting.inference import forecast_future_spending


def load_transactions_from_csv(file_path: str) -> Tuple[List[str], List[int]]:
    """
    Load and preprocess transaction data from CSV.
    
    Args:
        file_path: Path to transaction CSV file
        
    Returns:
        Tuple of (descriptions, categories)
    """
    print(f"Loading transactions from {file_path}...")
    
    # Parse file using ingestion_engine
    transactions = parse_file(file_path)
    print(f"Loaded {len(transactions)} transactions")
    
    # Extract descriptions and categories
    descriptions = []
    categories = []
    
    # Category mapping
    category_to_idx = {
        'Food': 0,
        'Restaurants': 1,
        'Groceries': 2,
        'Transport': 3,
        'Entertainment': 4,
        'Shopping': 5,
        'Health': 6,
        'Utilities': 7,
        'Travel': 8,
        'Education': 9,
        'Other': 10
    }
    
    for txn in transactions:
        # Get description
        description = txn.get('description', '')
        if not description:
            continue
        
        # Get category
        category = txn.get('category', 'Other')
        category_idx = category_to_idx.get(category, 10)
        
        descriptions.append(description)
        categories.append(category_idx)
    
    print(f"Processed {len(descriptions)} valid transactions")
    return descriptions, categories


def train_hypcd_model(
    data_loader_fn,
    checkpoint_dir: str = "checkpoints",
    epochs: int = 20,
    resume_from: str = None
) -> HypCDClassifier:
    """
    Train HypCD classifier.
    
    Args:
        data_loader_fn: Function that returns (texts, labels)
        checkpoint_dir: Directory to save checkpoints
        epochs: Number of training epochs
        resume_from: Path to checkpoint to resume from
        
    Returns:
        Trained HypCDClassifier
    """
    print(f"Initializing training pipeline...")
    print(f"Checkpoint directory: {checkpoint_dir}")
    print(f"Epochs: {epochs}")
    
    # Create pipeline
    pipeline = create_default_pipeline(
        checkpoint_dir=checkpoint_dir,
        epochs=epochs
    )
    
    # Train
    print("Starting training...")
    best_metrics = pipeline.train(data_loader_fn, resume_from=resume_from)
    
    print(f"Training complete! Best metrics: {best_metrics}")
    
    # Export model
    export_path = os.path.join(checkpoint_dir, 'hypcd_model.pt')
    pipeline.export_model(export_path)
    print(f"Model exported to: {export_path}")
    
    return pipeline.classifier


def categorize_transactions(
    classifier: HypCDClassifier,
    descriptions: List[str],
    backend: CloudBackend
) -> List[Dict]:
    """
    Categorize new transactions using trained classifier.
    
    Args:
        classifier: Trained HypCDClassifier
        descriptions: List of transaction descriptions
        backend: CloudBackend for embeddings
        
    Returns:
        List of categorized transactions
    """
    print(f"Categorizing {len(descriptions)} transactions...")
    
    results = []
    for desc in descriptions:
        # Get embedding
        embedding = backend.embed(desc)
        
        # Classify
        category_idx, confidence = classifier.predict_with_confidence(embedding)
        
        # Map back to category name
        idx_to_category = {
            0: 'Food', 1: 'Restaurants', 2: 'Groceries',
            3: 'Transport', 4: 'Entertainment', 5: 'Shopping',
            6: 'Health', 7: 'Utilities', 8: 'Travel',
            9: 'Education', 10: 'Other'
        }
        category = idx_to_category.get(category_idx, 'Other')
        
        results.append({
            'description': desc,
            'category': category,
            'category_idx': category_idx,
            'confidence': confidence
        })
    
    return results


def prepare_forecast_data(
    categorized_transactions: List[Dict],
    output_path: str = "forecast_data.json"
) -> str:
    """
    Prepare data for forecasting pipeline.
    
    Args:
        categorized_transactions: List of categorized transactions
        output_path: Path to save forecast data
        
    Returns:
        Path to saved forecast data
    """
    print(f"Preparing forecasting data...")
    
    # Convert to format expected by forecasting
    forecast_data = []
    for txn in categorized_transactions:
        forecast_data.append({
            'description': txn['description'],
            'category': txn['category'],
            'category_confidence': txn['confidence'],
            'timestamp': datetime.now().isoformat()
        })
    
    # Save
    import json
    with open(output_path, 'w') as f:
        json.dump(forecast_data, f, indent=2)
    
    print(f"Forecast data saved to: {output_path}")
    return output_path


def run_forecast(
    data_path: str,
    forecast_days: int = 30
) -> Dict:
    """
    Run forecasting on categorized data.
    
    Args:
        data_path: Path to forecast data
        forecast_days: Number of days to forecast
        
    Returns:
        Forecast results
    """
    print(f"Running {forecast_days}-day forecast...")
    
    # Load data
    import json
    with open(data_path, 'r') as f:
        data = json.load(f)
    
    # Prepare training data
    prepared_data = prepare_training_data(data)
    
    # Run inference (mock - replace with actual forecast call)
    # forecast_results = forecast_future_spending(prepared_data, forecast_days)
    
    print("Forecast complete!")
    
    return {
        'forecast_days': forecast_days,
        'data_points': len(prepared_data),
        'timestamp': datetime.now().isoformat()
    }


def main():
    """Main integration workflow."""
    print("=" * 60)
    print("HypCD Training Pipeline Integration Example")
    print("=" * 60)
    
    # Step 1: Load training data
    print("\n[Step 1] Loading Training Data")
    print("-" * 40)
    
    # Example: Load from CSV
    # texts, labels = load_transactions_from_csv("data/transactions.csv")
    
    # For demo: Use mock data
    mock_texts = [
        "Starbucks coffee downtown",
        "Grocery store purchase",
        "Uber ride to airport",
        "Netflix subscription",
        "Electric bill payment"
    ]
    mock_labels = [0, 2, 3, 4, 7]  # Food, Groceries, Transport, Entertainment, Utilities
    
    def mock_data_loader():
        return mock_texts, mock_labels
    
    print(f"Using {len(mock_texts)} sample transactions for demo")
    
    # Step 2: Train model
    print("\n[Step 2] Training HypCD Classifier")
    print("-" * 40)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        classifier = train_hypcd_model(
            mock_data_loader,
            checkpoint_dir=temp_dir,
            epochs=5  # Demo with fewer epochs
        )
        
        # Step 3: Categorize new transactions
        print("\n[Step 3] Categorizing New Transactions")
        print("-" * 40)
        
        new_transactions = [
            "Coffee shop purchase",
            "Gas station fill up",
            "Movie theater tickets"
        ]
        
        backend = CloudBackend()
        categorized = categorize_transactions(classifier, new_transactions, backend)
        
        print("\nCategorization Results:")
        for txn in categorized:
            print(f"  {txn['description'][:30]:<30} -> {txn['category']:<15} (confidence: {txn['confidence']:.2f})")
        
        # Step 4: Prepare forecast data
        print("\n[Step 4] Preparing Forecast Data")
        print("-" * 40)
        
        forecast_path = os.path.join(temp_dir, "forecast_data.json")
        prepare_forecast_data(categorized, forecast_path)
        
        # Step 5: Run forecast
        print("\n[Step 5] Running Forecast")
        print("-" * 40)
        
        forecast_results = run_forecast(forecast_path, forecast_days=30)
        print(f"Forecast prepared: {forecast_results}")
    
    print("\n" + "=" * 60)
    print("Integration Complete!")
    print("=" * 60)


if __name__ == "__main__":
    import tempfile
    main()
