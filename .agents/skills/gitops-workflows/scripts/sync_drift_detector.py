#!/usr/bin/env python3
"""
Detect configuration drift between Git and Kubernetes cluster.
Supports both ArgoCD and Flux CD deployments.
"""

import argparse
import sys
import subprocess
import json
from typing import List, Optional

try:
    from kubernetes import client, config
except ImportError:
    print("⚠️  'kubernetes' library not found. Install with: pip install kubernetes")
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("⚠️  'pyyaml' library not found. Install with: pip install pyyaml")
    sys.exit(1)


def run_command(cmd: List[str]) -> tuple:
    """Run shell command and return output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout, None
    except subprocess.CalledProcessError as e:
        return None, e.stderr


def check_argocd_drift(app_name: Optional[str] = None):
    """Check drift using ArgoCD CLI."""
    print("🔍 Checking ArgoCD drift...\n")

    cmd = ["argocd", "app", "diff"]
    if app_name:
        cmd.append(app_name)
    else:
        # Get all apps
        stdout, err = run_command(["argocd", "app", "list", "-o", "json"])
        if err:
            print(f"❌ Failed to list apps: {err}")
            return

        apps = json.loads(stdout)
        for app in apps:
            app_name = app["metadata"]["name"]
            check_single_app_drift(app_name)
        return

    check_single_app_drift(app_name)


def check_single_app_drift(app_name: str):
    """Check drift for single ArgoCD application."""
    stdout, err = run_command(["argocd", "app", "diff", app_name])

    if err and "no differences" not in err.lower():
        print(f"❌ {app_name}: Error checking drift")
        print(f"   {err}")
        return

    if not stdout or "no differences" in (stdout + (err or "")).lower():
        print(f"✅ {app_name}: No drift detected")
    else:
        print(f"⚠️  {app_name}: Drift detected")
        print(f"   Run: argocd app sync {app_name}")


def check_flux_drift(namespace: str = "flux-system"):
    """Check drift using Flux CLI."""
    print("🔍 Checking Flux drift...\n")

    # Check kustomizations
    stdout, err = run_command(
        [
            "flux",
            "get",
            "kustomizations",
            "-n",
            namespace,
            "--status-selector",
            "ready=false",
        ]
    )

    if stdout:
        print("⚠️  Out-of-sync Kustomizations:")
        print(stdout)
    else:
        print("✅ All Kustomizations synced")

    # Check helmreleases
    stdout, err = run_command(
        [
            "flux",
            "get",
            "helmreleases",
            "-n",
            namespace,
            "--status-selector",
            "ready=false",
        ]
    )

    if stdout:
        print("\n⚠️  Out-of-sync HelmReleases:")
        print(stdout)
    else:
        print("✅ All HelmReleases synced")


def main():
    parser = argparse.ArgumentParser(
        description="Detect configuration drift between Git and cluster",
        epilog="""
Examples:
  # Check ArgoCD drift
  python3 sync_drift_detector.py --argocd

  # Check specific ArgoCD app
  python3 sync_drift_detector.py --argocd --app my-app

  # Check Flux drift
  python3 sync_drift_detector.py --flux

Requirements:
  - argocd CLI (for ArgoCD mode)
  - flux CLI (for Flux mode)
  - kubectl configured
        """,
    )

    parser.add_argument("--argocd", action="store_true", help="Check ArgoCD drift")
    parser.add_argument("--flux", action="store_true", help="Check Flux drift")
    parser.add_argument("--app", help="Specific ArgoCD application name")
    parser.add_argument("--namespace", default="flux-system", help="Flux namespace")

    args = parser.parse_args()

    if not args.argocd and not args.flux:
        print("❌ Specify --argocd or --flux")
        sys.exit(1)

    try:
        if args.argocd:
            check_argocd_drift(args.app)
        if args.flux:
            check_flux_drift(args.namespace)

    except KeyboardInterrupt:
        print("\n\nInterrupted")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
