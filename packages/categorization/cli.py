import argparse
import sys
import os
import torch
from torch.utils.data import DataLoader, TensorDataset
from sentence_transformers import SentenceTransformer
from supabase import create_client, Client  # Added
from dotenv import load_dotenv  # Added

load_dotenv()  # Load env vars
load_dotenv("apps/web/.env.local")

# Global Supabase
url = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get(
    "NEXT_PUBLIC_SUPABASE_ANON_KEY"
)


def get_supabase() -> Client:
    if not url or not key:
        raise ValueError("Supabase credentials missing")
    return create_client(url, key)


# Ensure package imports work
sys.path.append(os.getcwd())

from packages.categorization.data_loader import (
    BankStatementParser,
    InverseFrequencyMasking,
)
from packages.categorization.hyperbolic_nn import HyperbolicProjector
from packages.categorization.trainer import HypCDTrainer
from packages.categorization.discovery import HyperbolicKMeans
from packages.categorization.hypcd import HypCDClassifier  # Added to top level

# Global config
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384
PROJ_DIM = 2  # Visualization friendly, but maybe 32 better for perf
HIDDEN_DIM = 16
OUTPUT_DIM = 2  # If optimizing for 2D visualization


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
    pos_embeddings = bert.encode(
        augmented_texts, convert_to_tensor=True, show_progress_bar=True
    )
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
    projector = HyperbolicProjector(EMBED_DIM, PROJ_DIM)
    # We might want a deeper network or just projector for visualization
    # Let's use HypFFN wrapping the projector logic?
    # Our HypFFN assumes input is on manifold.
    # Let's create a wrapper that does: BERT_Emb -> Projector -> HypFFN (optional)
    # For simple HypCD, Projector is enough to map to ball.
    # But we want to train it. Trainer expects 'model(x)'.

    # If we pass BERT embeddings to model, model should be Projector.
    model = projector

    # 5. Train
    print("Starting Training...")
    trainer = HypCDTrainer(model, lr=0.005)
    metrics = trainer.train(dataloader, epochs=args.epochs)

    print("Training Complete.")
    print(f"Final Loss: {metrics['loss'][-1]:.4f}")

    # Save projector
    torch.save(model.state_dict(), "hypcd_model.pt")
    print("Model saved to hypcd_model.pt")


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
    projector = HyperbolicProjector(EMBED_DIM, PROJ_DIM)
    # Load existing if available?
    if os.path.exists("hypcd_model.pt"):
        try:
            projector.load_state_dict(torch.load("hypcd_model.pt", map_location="cpu"))
            print("Loaded existing model weights.")
        except:
            print("Could not load existing weights, starting fresh.")

    # Train
    print("Starting Supervised Training...")
    trainer = HypCDTrainer(projector, lr=0.005)
    # Use train_supervised (Need to implement in Trainer)
    metrics = trainer.train_supervised(dataloader, epochs=args.epochs)

    print("Training Complete.")
    print(f"Final Loss: {metrics['loss'][-1]:.4f}")

    torch.save(projector.state_dict(), "hypcd_model.pt")
    print("Model saved to hypcd_model.pt")


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
    model = HyperbolicProjector(EMBED_DIM, PROJ_DIM)
    try:
        model.load_state_dict(torch.load("hypcd_model.pt", map_location=device))
    except:
        print("Model not found. Run train first.")
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

    model = HyperbolicProjector(EMBED_DIM, PROJ_DIM)
    try:
        model.load_state_dict(torch.load("hypcd_model.pt", map_location=device))
    except:
        print("Model not found. Using random init.")

    model.to(device)
    model.eval()

    with torch.no_grad():
        hyp_embs = model(embs)

    print(f"Running Hyperbolic K-Means on {len(texts)} transactions...")
    kmeans = HyperbolicKMeans(n_clusters=args.clusters)
    labels = kmeans.fit_predict(hyp_embs)

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


def main():
    parser = argparse.ArgumentParser(description="HypCD CLI")
    subparsers = parser.add_subparsers(dest="command")

    # Train
    train_parser = subparsers.add_parser("train")
    train_parser.add_argument(
        "--file", type=str, required=True, help="Path to Excel statement"
    )
    train_parser.add_argument(
        "--password", type=str, default=None, help="Excel password"
    )
    train_parser.add_argument("--epochs", type=int, default=10, help="Training epochs")

    # Train DB
    db_parser = subparsers.add_parser("train-db")
    db_parser.add_argument(
        "--user_id", type=str, required=False, help="User ID to filter"
    )
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
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
