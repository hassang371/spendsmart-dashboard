import os
import json
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client, Client
import torch
from .backends.cloud import CloudBackend
from .training import HypCDTrainer
from .hypcd import HypCDClassifier

# Configuration
load_dotenv()
load_dotenv("apps/web/.env.local")

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
STATE_FILE = "training_state.json"
ANCHOR_FILE = "anchors.pt"


def get_supabase() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("Supabase credentials missing")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def train():
    logger.info("Starting Student Training Loop...")
    supabase = get_supabase()
    state = load_state()
    last_run = state.get("last_run", "1970-01-01T00:00:00Z")

    # Fetch recently categorized/corrected data
    # We look for is_manual=true (User or Teacher) and updated_at > last_run
    logger.info(f"Fetching transactions updated after {last_run}")

    response = (
        supabase.table("transactions")
        .select("id, description, category, merchant_name")
        .eq("is_manual", True)
        .gt("updated_at", last_run)
        .execute()
    )

    transactions = response.data
    if not transactions:
        logger.info("No new training data found.")
        # Still update timestamp? No, wait for data.
        return

    logger.info(f"Found {len(transactions)} new training samples.")

    # Group by category
    labeled_data = {}
    for tx in transactions:
        cat = tx["category"]
        # Use description or merchant? HypCD uses cleaned description.
        # We can pass raw description, HypCD.update_anchors calls clean_description.
        text = tx["description"]
        if cat not in labeled_data:
            labeled_data[cat] = []
        labeled_data[cat].append(text)

    # Initialize backend and trainer
    logger.info("Initializing trainer...")
    backend = CloudBackend()
    trainer = HypCDTrainer(backend=backend, num_classes=11, proj_dim=128)

    # Prepare training data
    all_texts = []
    all_labels = []
    for cat, texts in labeled_data.items():
        label_idx = trainer.classifier.labels.index(cat)
        all_texts.extend(texts)
        all_labels.extend([label_idx] * len(texts))

    labels_tensor = torch.tensor(all_labels)

    # Create batches
    batch_size = 32
    batches = [
        all_texts[i : i + batch_size]
        for i in range(0, len(all_texts), batch_size)
    ]

    # Train
    logger.info(f"Training on {len(all_texts)} samples...")
    num_epochs = 5
    for epoch in range(num_epochs):
        avg_loss = trainer.train_epoch(batches, labels_tensor)
        logger.info(f"Epoch {epoch + 1}/{num_epochs}, Loss: {avg_loss:.4f}")

    # Save State
    new_last_run = datetime.now(timezone.utc).isoformat()
    state["last_run"] = new_last_run
    save_state(state)

    logger.info(f"Training complete. State updated to {new_last_run}")


if __name__ == "__main__":
    train()
