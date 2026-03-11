#!/usr/bin/env python3
"""Local evaluation script for the categorization engine v2.

Usage:
  python scripts/evaluate_statement.py --input data/test_transactions.csv
  python scripts/evaluate_statement.py --input data/test_transactions.csv --true-column true_category

Input CSV must have a 'description' column.
Optionally, include a 'true_category' column for accuracy/F1 metrics.

Output:
  - Table: [Raw] → [Informative] → [Merchant] → [Predicted Category] (Confidence)
  - Metrics (if true_category present): Accuracy, per-class F1, Precision, Recall
"""

import argparse
import csv
import os
import sys
from collections import defaultdict

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from packages.categorization.classifier import TransactionClassifier
from packages.categorization.cleaner import process_description


def run_evaluation(input_path: str, true_column: str | None = None) -> None:
    """Run the evaluation pipeline."""

    # Load CSV
    with open(input_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("❌ No rows found in input file.")
        return

    if "description" not in rows[0]:
        # Try common alternatives
        desc_col = None
        for candidate in [
            "Description",
            "desc",
            "Desc",
            "DESCRIPTION",
            "narration",
            "Narration",
        ]:
            if candidate in rows[0]:
                desc_col = candidate
                break
        if not desc_col:
            print(f"❌ No 'description' column found. Available: {list(rows[0].keys())}")
            return
    else:
        desc_col = "description"

    descriptions = [str(row.get(desc_col, "")) for row in rows]
    true_categories = None
    if true_column and true_column in rows[0]:
        true_categories = [str(row.get(true_column, "")) for row in rows]

    print(f"\n📊 Evaluating {len(descriptions)} transactions from {input_path}")
    print(f"{'─' * 120}")

    # Initialize classifier
    print("🔄 Loading classifier...")
    classifier = TransactionClassifier()

    # Process and classify
    processed = [process_description(d) for d in descriptions]
    results = classifier.predict_batch(descriptions)

    # Print table
    print(f"\n{'#':>4} │ {'Raw (truncated)':40} │ {'Informative':35} │ {'Merchant':20} │ {'Category':25} │ {'Conf':>6}")
    print(f"{'─' * 4}─┼─{'─' * 40}─┼─{'─' * 35}─┼─{'─' * 20}─┼─{'─' * 25}─┼─{'─' * 6}")

    for i, (proc, res) in enumerate(zip(processed, results)):
        raw_trunc = proc.raw[:40].ljust(40)
        info_trunc = proc.informative[:35].ljust(35)
        merch_trunc = proc.merchant_name[:20].ljust(20)
        cat = res["category"][:25].ljust(25)
        conf = f"{res['confidence']:.4f}"
        print(f"{i+1:>4} │ {raw_trunc} │ {info_trunc} │ {merch_trunc} │ {cat} │ {conf:>6}")

    # Metrics (if true categories provided)
    if true_categories:
        print(f"\n{'═' * 80}")
        print("📈 CLASSIFICATION METRICS")
        print(f"{'═' * 80}")

        pred_categories = [r["category"] for r in results]
        correct = sum(1 for t, p in zip(true_categories, pred_categories) if t == p)
        accuracy = correct / len(true_categories) if true_categories else 0.0
        print(f"\n✅ Overall Accuracy: {accuracy:.2%} ({correct}/{len(true_categories)})")

        # Per-class metrics
        classes = sorted(set(true_categories + pred_categories))
        tp: dict[str, int] = defaultdict(int)
        fp: dict[str, int] = defaultdict(int)
        fn: dict[str, int] = defaultdict(int)

        for t, p in zip(true_categories, pred_categories):
            if t == p:
                tp[t] += 1
            else:
                fp[p] += 1
                fn[t] += 1

        print(f"\n{'Category':30} │ {'Precision':>10} │ {'Recall':>10} │ {'F1':>10} │ {'Support':>8}")
        print(f"{'─' * 30}─┼─{'─' * 10}─┼─{'─' * 10}─┼─{'─' * 10}─┼─{'─' * 8}")

        for cls in classes:
            prec = tp[cls] / (tp[cls] + fp[cls]) if (tp[cls] + fp[cls]) > 0 else 0.0
            rec = tp[cls] / (tp[cls] + fn[cls]) if (tp[cls] + fn[cls]) > 0 else 0.0
            f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
            support = tp[cls] + fn[cls]
            if support > 0:
                print(f"{cls[:30]:30} │ {prec:>10.4f} │ {rec:>10.4f} │ {f1:>10.4f} │ {support:>8}")

        # Confusion matrix summary
        print(f"\n{'─' * 60}")
        misclassified = [(t, p) for t, p in zip(true_categories, pred_categories) if t != p]
        if misclassified:
            print(f"\n🔴 Misclassified ({len(misclassified)}):")
            for t, p in misclassified[:20]:
                print(f"   Expected: {t:25} → Predicted: {p}")
            if len(misclassified) > 20:
                print(f"   ... and {len(misclassified) - 20} more")
    else:
        print(f"\n💡 Add a '{true_column or 'true_category'}' column to compute accuracy metrics.")

    # Confidence distribution
    confidences = [r["confidence"] for r in results]
    buckets = {"0.0-0.2": 0, "0.2-0.4": 0, "0.4-0.6": 0, "0.6-0.8": 0, "0.8-1.0": 0}
    bucket_keys = list(buckets.keys())
    for c in confidences:
        idx = min(int(c / 0.2), 4)
        buckets[bucket_keys[idx]] += 1

    print("\n📊 Confidence Distribution:")
    for k, v in buckets.items():
        bar = "█" * (v * 50 // max(len(confidences), 1))
        print(f"   {k}: {v:>4} {bar}")

    print(f"\n✅ Done. Evaluated {len(descriptions)} transactions.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate the categorization engine on a CSV file.")
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Path to CSV file with 'description' column",
    )
    parser.add_argument(
        "--true-column",
        "-t",
        default="true_category",
        help="Column name containing ground truth categories (default: true_category)",
    )
    args = parser.parse_args()
    run_evaluation(args.input, args.true_column)
