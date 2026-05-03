"""Test that ``GET /metrics/prom`` returns Prometheus exposition with
all eleven RFC-004 metric series enumerated by name.

Refs: docs/rfcs/RFC-004-tft-inference-cache-architecture.md §8
Refs: docs/plans/2026-04-17-prediction-engine-v1-master.md Stage 10
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.main import app

REQUIRED_METRICS = (
    "tft_cache_hits_total",
    "tft_cache_misses_total",
    "tft_cache_evictions_total",
    "tft_cache_load_duration_seconds",
    "tft_cache_resident_entries",
    "tft_cache_resident_bytes",
    "tft_cache_pubsub_invalidations_total",
    "tft_cache_pubsub_invalidations_skipped_stale_total",
    "tft_cache_pubsub_publish_failures_total",
    "tft_cache_subscriber_reconnects_total",
    "forecast_warm_outcome_total",
)


def test_metrics_prom_exposes_all_eleven_rfc004_metrics():
    with TestClient(app) as tc:
        resp = tc.get("/metrics/prom")
    assert resp.status_code == 200
    content_type = resp.headers["content-type"]
    assert content_type.startswith("text/plain")
    body = resp.text
    missing = [m for m in REQUIRED_METRICS if m not in body]
    assert not missing, f"Missing metric series in /metrics/prom: {missing}"
