"""Regression test — BUG-018 §Regression Prevention.

Ensures Stage 5's deletion of the unbounded ``inference._MODEL_CACHE``
dict (and its ``load_model`` / ``invalidate_cache`` companions) is not
silently re-introduced. The bounded :class:`TFTModelCache` from
``packages/forecasting/cache.py`` is the canonical replacement.

Refs: docs/bugs/BUG-018-tft-inference-cold-load-no-bounded-cache.md
Refs: docs/rfcs/RFC-004-tft-inference-cache-architecture.md
"""

from __future__ import annotations


def test_legacy_module_cache_dict_is_not_importable():
    """``packages.forecasting.inference._MODEL_CACHE`` must not exist."""
    from packages.forecasting import inference

    assert not hasattr(inference, "_MODEL_CACHE"), (
        "Stage 5 deleted the unbounded module-level _MODEL_CACHE dict; "
        "use TFTModelCache via cache.get_or_load(user_id) instead."
    )


def test_legacy_load_model_shim_is_not_importable():
    """``inference.load_model`` was replaced by ``cache.get_or_load``."""
    from packages.forecasting import inference

    assert not hasattr(inference, "load_model"), "Stage 5 deleted load_model; use cache.get_or_load(user_id)."


def test_legacy_invalidate_cache_shim_is_not_importable():
    """``inference.invalidate_cache`` was replaced by ``cache.evict``."""
    from packages.forecasting import inference

    assert not hasattr(inference, "invalidate_cache"), "Stage 5 deleted invalidate_cache; use cache.evict(user_id)."


def test_bounded_cache_is_importable_from_cache_module():
    """``TFTModelCache`` is importable from ``packages.forecasting.cache``."""
    from packages.forecasting.cache import TFTModelCache

    assert TFTModelCache is not None
    assert hasattr(TFTModelCache, "get_or_load")
    assert hasattr(TFTModelCache, "set_loader")
