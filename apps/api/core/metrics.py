"""Prometheus metric singletons for the SCALE API.

This module stands up the Prometheus subsystem per RFC-004
§Detailed Design 8 + Codex Fix #4. All eleven RFC-004 metrics are
defined here as module-level singletons against a *custom*
``CollectorRegistry`` (NOT the ``prometheus_client.REGISTRY`` global)
so that tests can run in parallel without process-global pollution
and so that the ``GET /metrics/prom`` endpoint can scope its
``generate_latest`` output to exactly RFC-004 series.

Eleven metrics:

1.  ``tft_cache_hits_total`` — Counter
2.  ``tft_cache_misses_total`` — Counter
3.  ``tft_cache_evictions_total{reason}`` — Counter labelled by
    ``reason`` (``lru`` | ``bytes`` | ``ttl`` | ``invalidation``)
4.  ``tft_cache_load_duration_seconds`` — Histogram
5.  ``tft_cache_resident_entries`` — Gauge
6.  ``tft_cache_resident_bytes`` — Gauge
7.  ``tft_cache_pubsub_invalidations_total`` — Counter
8.  ``tft_cache_pubsub_invalidations_skipped_stale_total`` — Counter
9.  ``tft_cache_pubsub_publish_failures_total`` — Counter
10. ``tft_cache_subscriber_reconnects_total`` — Counter
11. ``forecast_warm_outcome_total{result}`` — Counter labelled by
    ``result`` (``ok`` | ``429`` | ``timeout`` | ``error``)

Refs: docs/rfcs/RFC-004-tft-inference-cache-architecture.md §8
Refs: docs/bugs/BUG-018-tft-inference-cold-load-no-bounded-cache.md
"""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

# Custom registry — DO NOT use prometheus_client.REGISTRY (the global
# default). Using a private registry lets tests instantiate fresh
# series without colliding with already-registered names from other
# modules or from a previous test in the same Python process.
REGISTRY: CollectorRegistry = CollectorRegistry()


# 1. Cache hits
tft_cache_hits_total: Counter = Counter(
    "tft_cache_hits_total",
    "Number of TFT model cache hits (recency-promoted).",
    registry=REGISTRY,
)

# 2. Cache misses
tft_cache_misses_total: Counter = Counter(
    "tft_cache_misses_total",
    "Number of TFT model cache misses (triggered a load).",
    registry=REGISTRY,
)

# 3. Evictions by cause
tft_cache_evictions_total: Counter = Counter(
    "tft_cache_evictions_total",
    "TFT model cache evictions, labelled by reason.",
    labelnames=("reason",),
    registry=REGISTRY,
)

# 4. Cold-load latency histogram (seconds)
tft_cache_load_duration_seconds: Histogram = Histogram(
    "tft_cache_load_duration_seconds",
    "Cold-load duration in seconds (download + deserialize + freeze).",
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
    registry=REGISTRY,
)

# 5. Resident entries gauge
tft_cache_resident_entries: Gauge = Gauge(
    "tft_cache_resident_entries",
    "Number of TFT models currently held in cache.",
    registry=REGISTRY,
)

# 6. Resident bytes gauge
tft_cache_resident_bytes: Gauge = Gauge(
    "tft_cache_resident_bytes",
    "Total resident bytes of all cached TFT models.",
    registry=REGISTRY,
)

# 7. Pub-sub invalidations received
tft_cache_pubsub_invalidations_total: Counter = Counter(
    "tft_cache_pubsub_invalidations_total",
    "Number of pub-sub cache-invalidation messages successfully applied.",
    registry=REGISTRY,
)

# 8. Pub-sub invalidations skipped (stale-message guard)
tft_cache_pubsub_invalidations_skipped_stale_total: Counter = Counter(
    "tft_cache_pubsub_invalidations_skipped_stale_total",
    ("Pub-sub invalidations skipped because the incoming " "checkpoint_updated_at was older than the cached entry's."),
    registry=REGISTRY,
)

# 9. Pub-sub publish failures
tft_cache_pubsub_publish_failures_total: Counter = Counter(
    "tft_cache_pubsub_publish_failures_total",
    "Number of times publish_invalidation() failed to publish.",
    registry=REGISTRY,
)

# 10. Subscriber reconnects
tft_cache_subscriber_reconnects_total: Counter = Counter(
    "tft_cache_subscriber_reconnects_total",
    "Number of times the pub-sub subscriber reconnected after disconnect.",
    registry=REGISTRY,
)

# 11. FE-initiated warm outcome (Codex Fix #4)
forecast_warm_outcome_total: Counter = Counter(
    "forecast_warm_outcome_total",
    (
        "Outcome of a frontend-initiated /forecast/warm request, "
        "reported via the /api/v1/metrics/client-event telemetry route."
    ),
    labelnames=("result",),
    registry=REGISTRY,
)

# 12. RFC-003 §3 — log_user_prediction RPC failure counter.
# Incremented when ForecastService.predict catches a non-fatal RPC
# failure during the fire-and-forget INSERT into ``user_predictions``.
forecast_log_insert_failures_total: Counter = Counter(
    "forecast_log_insert_failures_total",
    (
        "Number of times log_user_prediction RPC failed during forecast "
        "logging. Failure is non-fatal — the user still receives the "
        "forecast — but accumulating failures indicate a DB / RPC outage."
    ),
    registry=REGISTRY,
)


__all__ = [
    "REGISTRY",
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
    "forecast_log_insert_failures_total",
]
