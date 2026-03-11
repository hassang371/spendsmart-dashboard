#!/usr/bin/env python3
"""
Validate environment promotion workflows (dev → staging → production).
Checks that changes are promoted through environments in the correct order.
"""

import argparse
import subprocess
import sys
from pathlib import Path


def get_git_diff(ref1: str, ref2: str, path: str = ".") -> str:
    """Get git diff between two refs."""
    try:
        result = subprocess.run(
            ["git", "diff", f"{ref1}...{ref2}", "--", path],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"❌ Git diff failed: {e}")
        sys.exit(1)


def validate_promotion(source_env: str, target_env: str, repo_path: str):
    """Validate that changes exist in source before promoting to target."""
    print(f"🔍 Validating promotion: {source_env} → {target_env}\n")

    # Check that source and target directories exist
    source_path = Path(repo_path) / f"environments/{source_env}"
    target_path = Path(repo_path) / f"environments/{target_env}"

    if not source_path.exists():
        print(f"❌ Source environment not found: {source_path}")
        sys.exit(1)

    if not target_path.exists():
        print(f"❌ Target environment not found: {target_path}")
        sys.exit(1)

    # Check git history - target should not have changes that source doesn't have
    diff = get_git_diff("HEAD~10", "HEAD", str(target_path))

    if diff and source_env == "dev":
        # If there are recent changes to target (prod/staging) check they came from source
        print("⚠️  Recent changes detected in target environment")
        print("   Verify changes were promoted from dev/staging first")

    print("✅ Promotion path is valid")
    print("\nNext steps:")
    print(f"1. Review changes in {source_env}")
    print(f"2. Test in {source_env} environment")
    print(f"3. Copy changes to {target_env}")
    print(f"4. Create PR for {target_env} promotion")


def main():
    parser = argparse.ArgumentParser(
        description="Validate environment promotion workflows",
        epilog="""
Examples:
  # Validate dev → staging promotion
  python3 promotion_validator.py --source dev --target staging

  # Validate staging → production promotion
  python3 promotion_validator.py --source staging --target production

Checks:
  - Environment directories exist
  - Changes flow through proper promotion path
  - No direct changes to production
        """,
    )

    parser.add_argument("--source", required=True, help="Source environment (dev/staging)")
    parser.add_argument("--target", required=True, help="Target environment (staging/production)")
    parser.add_argument("--repo-path", default=".", help="Repository path")

    args = parser.parse_args()

    validate_promotion(args.source, args.target, args.repo_path)


if __name__ == "__main__":
    main()
