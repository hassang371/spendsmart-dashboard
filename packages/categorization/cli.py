"""Categorization CLI v2 — classify, evaluate, and manage adapters.

Usage:
  python -m packages.categorization.cli classify "Swiggy food order"
  python -m packages.categorization.cli batch data/test.csv
  python -m packages.categorization.cli info
"""
import argparse
import csv
import sys
import os

sys.path.append(os.getcwd())

from packages.categorization.classifier import TransactionClassifier
from packages.categorization.cleaner import process_description
from packages.categorization.constants import Category


def classify_cmd(args):
    """Classify one or more transaction descriptions."""
    classifier = TransactionClassifier()

    for text in args.texts:
        processed = process_description(text)
        result = classifier.predict(text)

        print(f"\n{'─' * 60}")
        print(f"  Raw:         {processed.raw}")
        print(f"  Informative: {processed.informative}")
        print(f"  Merchant:    {processed.merchant_name}")
        print(f"  Tx Type:     {processed.transaction_type}")
        print(f"  Category:    {result['category']}")
        print(f"  Confidence:  {result['confidence']:.4f}")


def batch_cmd(args):
    """Classify a CSV file of transactions."""
    classifier = TransactionClassifier()

    with open(args.input, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Find description column
    desc_col = None
    for candidate in ["description", "Description", "desc", "narration", "Narration", "DESCRIPTION"]:
        if candidate in rows[0]:
            desc_col = candidate
            break

    if not desc_col:
        print(f"❌ No description column found. Available: {list(rows[0].keys())}")
        return

    descriptions = [str(row.get(desc_col, "")) for row in rows]
    results = classifier.predict_batch(descriptions)

    print(f"\n{'#':>4} │ {'Description':40} │ {'Category':25} │ {'Conf':>6}")
    print(f"{'─' * 4}─┼─{'─' * 40}─┼─{'─' * 25}─┼─{'─' * 6}")

    for i, (desc, res) in enumerate(zip(descriptions, results)):
        d = desc[:40].ljust(40)
        c = res["category"][:25].ljust(25)
        print(f"{i+1:>4} │ {d} │ {c} │ {res['confidence']:.4f}")

    print(f"\n✅ Classified {len(descriptions)} transactions.")


def info_cmd(args):
    """Display classifier info."""
    classifier = TransactionClassifier()

    print(f"\n📊 Classifier Info")
    print(f"{'─' * 40}")
    print(f"  Model:      {classifier._model_name}")
    print(f"  Dim:        {classifier.embedding_dim}")
    print(f"  Threshold:  {classifier.confidence_threshold}")
    print(f"  Categories: {len(classifier._category_names)}")
    print(f"\n  Categories:")
    for cat in sorted(classifier._category_names):
        print(f"    - {cat}")


def main():
    parser = argparse.ArgumentParser(description="Categorization CLI v2")
    sub = parser.add_subparsers(dest="command")

    # classify
    p_classify = sub.add_parser("classify", help="Classify transaction descriptions")
    p_classify.add_argument("texts", nargs="+", help="Transaction description(s)")
    p_classify.set_defaults(func=classify_cmd)

    # batch
    p_batch = sub.add_parser("batch", help="Classify a CSV file")
    p_batch.add_argument("input", help="Path to CSV file")
    p_batch.set_defaults(func=batch_cmd)

    # info
    p_info = sub.add_parser("info", help="Display classifier info")
    p_info.set_defaults(func=info_cmd)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
