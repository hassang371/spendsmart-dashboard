"""Model Registry — manages adapter checkpoints in Supabase Storage.

v2: Saves the lightweight Linear Adapter to the 'models' bucket,
    tracking version history for ML-1 feature.
"""

import io
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

import structlog

from supabase import Client

logger = structlog.get_logger()


@dataclass
class ModelVersion:
    version_id: str
    user_id: str
    created_at: str
    metrics: Dict[str, Any]
    storage_path: str


def save_version(
    client: Client,
    user_id: str,
    adapter_state_dict: Dict[str, Any],
    metrics: Optional[Dict[str, Any]] = None,
    correction_count_delta: int = 0,
) -> ModelVersion:
    """Save a new model version to Supabase Storage and atomically update
    user_model_metadata via the upsert_model_metadata RPC.
    """
    import torch

    version_id = f"v_{int(datetime.now().timestamp())}"
    storage_path = f"{user_id}/{version_id}/adapter.pt"

    buffer = io.BytesIO()
    torch.save(adapter_state_dict, buffer)
    buffer.seek(0)

    try:
        client.storage.from_("models").upload(
            storage_path,
            buffer.read(),
            file_options={"content-type": "application/octet-stream"},
        )
        logger.info("model_saved", user_id=user_id, version_id=version_id)
    except Exception as e:
        logger.error("model_save_failed", error=str(e))
        raise

    # Atomically update user_model_metadata (url + timestamp + count increment).
    # Non-fatal: if the RPC fails, the adapter is still saved to Storage.
    try:
        client.rpc(
            "upsert_model_metadata",
            {
                "p_user_id": user_id,
                "p_adapter_url": storage_path,
                "p_count_delta": correction_count_delta,
            },
        ).execute()
        logger.info(
            "user_model_metadata_updated",
            user_id=user_id,
            storage_path=storage_path,
            count_delta=correction_count_delta,
        )
    except Exception as e:
        logger.error(
            "user_model_metadata_rpc_failed",
            user_id=user_id,
            storage_path=storage_path,
            error=str(e),
        )

    return ModelVersion(
        version_id=version_id,
        user_id=user_id,
        created_at=datetime.utcnow().isoformat(),
        metrics=metrics or {},
        storage_path=storage_path,
    )


def load_latest(client: Client, user_id: str) -> Optional[Dict[str, Any]]:
    """Load the latest adapter state dict for a user from Supabase Storage."""
    try:
        # List files in the user's directory
        files = client.storage.from_("models").list(user_id)
        if not files:
            return None

        # Filter for directories (versions) that match our "v_TIMESTAMP" naming
        versions = [f["name"] for f in files if f.get("name", "").startswith("v_")]
        if not versions:
            return None

        # Sort sequentially so latest is last
        versions.sort()
        latest_version = versions[-1]

        storage_path = f"{user_id}/{latest_version}/adapter.pt"

        # Download bytes
        response = client.storage.from_("models").download(storage_path)

        import torch

        buffer = io.BytesIO(response)
        # Using weights_only=False since we trust our own bucket or set weights_only=True if torch>=2.0
        # Passing weights_only=True is safer.
        state_dict = torch.load(buffer, map_location="cpu", weights_only=True)

        return state_dict
    except Exception as e:
        logger.error("load_latest_failed", user_id=user_id, error=str(e))
        return None
