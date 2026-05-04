"""User-intent CRUD service — LLD 010.

Wraps the ``upsert_intent_with_bridge`` SECURITY DEFINER RPC for the
two writes (intent + scheduled_cashflows companion row) and uses the
user-scoped supabase client (RLS-bound) for read paths.

The service is intentionally thin — the RPC owns atomicity. Callers
get back a fully-populated :class:`UserIntent` Pydantic model.

Refs: docs/features/010-user-intents-and-scenario-forecasting.md
      §Component Architecture
      §Intent → scheduled_cashflows Bridge
"""

from __future__ import annotations

from typing import Any

import structlog

from apps.api.domains.forecasting.schemas import (
    IntentCreateRequest,
    IntentType,
    IntentUpdateRequest,
    UserIntent,
)
from packages.forecasting.intent_bridge import (
    intent_to_scheduled_cashflow_row,
    should_have_bridge_row,
)

logger = structlog.get_logger(__name__)


_TABLE = "user_intents"
_RPC = "upsert_intent_with_bridge"


def _to_payload_value(v: Any) -> Any:
    """Coerce dates / UUIDs / enums to JSON-friendly scalars for the RPC."""
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if hasattr(v, "value"):
        return v.value
    return v


def _shape_bridge_payload(intent: UserIntent) -> dict[str, Any]:
    """Build the bridge_row JSON payload for the RPC."""
    row = intent_to_scheduled_cashflow_row(intent)
    return {k: _to_payload_value(v) for k, v in row.items()}


class IntentsService:
    """CRUD + bridge orchestration for ``public.user_intents``.

    Args:
        client: User-scoped Supabase client (the JWT-bearing client per
            LLD 010 §Security Considerations). RLS gates SELECT/INSERT/
            UPDATE; the upsert RPC additionally asserts user_id matches
            ``auth.uid()`` defense-in-depth.
    """

    def __init__(self, client: Any) -> None:
        self.client = client

    # ------------------------------------------------------------------ #
    # Read paths — RLS-bound through the user-scoped supabase client.
    # ------------------------------------------------------------------ #

    def get(self, intent_id: str, *, user_id: str) -> UserIntent | None:
        """Return the intent matching ``intent_id``, or ``None`` if absent.

        Defense-in-depth: explicit user_id filter even though RLS already
        scopes the SELECT.
        """
        resp = self.client.table(_TABLE).select("*").eq("id", intent_id).eq("user_id", user_id).execute()
        rows = resp.data or []
        if not rows:
            return None
        return UserIntent(**rows[0])

    def list(
        self,
        *,
        user_id: str,
        intent_type: IntentType | None = None,
        include_inactive: bool = False,
    ) -> list[UserIntent]:
        """List intents for the user, optionally filtered by type."""
        q = self.client.table(_TABLE).select("*").eq("user_id", user_id)
        if not include_inactive:
            q = q.eq("is_active", True)
        if intent_type is not None:
            q = q.eq("intent_type", intent_type.value)
        resp = q.execute()
        rows = resp.data or []
        return [UserIntent(**row) for row in rows]

    # ------------------------------------------------------------------ #
    # Write paths — atomic via upsert_intent_with_bridge RPC.
    # ------------------------------------------------------------------ #

    def create(self, req: IntentCreateRequest, *, user_id: str) -> UserIntent:
        """Create an intent (+ bridge row when dated) atomically."""
        bridge_needed = req.intent_type in {
            IntentType.INCOME_CHANGE,
            IntentType.PLANNED_LARGE_EXPENSE,
            IntentType.OBLIGATION_CHANGE,
            IntentType.FD_MATURITY,
            IntentType.EXPECTED_BONUS,
        }

        payload: dict[str, Any] = {
            "user_id": user_id,
            "id": None,
            "intent_type": req.intent_type.value,
            "amount": req.amount,
            "amount_delta": req.amount_delta,
            "category_bucket": req.category_bucket,
            "start_date": _to_payload_value(req.start_date),
            "end_date": _to_payload_value(req.end_date),
            "confidence": req.confidence.value,
            "is_recurring": req.is_recurring,
            "rrule_freq": req.rrule_freq,
            "notes": req.notes,
            "is_active": True,
            "should_bridge": bridge_needed,
            "bridge_row": None,
        }

        if bridge_needed:
            # Build a transient UserIntent so we can reuse the bridge
            # serialiser. The id field is unused by the RPC payload —
            # the RPC will set source_rule_id from the just-INSERTed
            # intent's id, not from this transient placeholder.
            from uuid import uuid4

            transient = UserIntent(
                id=uuid4(),
                user_id=user_id,
                intent_type=req.intent_type,
                amount=req.amount,
                amount_delta=req.amount_delta,
                category_bucket=req.category_bucket,
                start_date=req.start_date,
                end_date=req.end_date,
                confidence=req.confidence,
                is_recurring=req.is_recurring,
                rrule_freq=req.rrule_freq,
                notes=req.notes,
                is_active=True,
                created_at="1970-01-01T00:00:00+00:00",
                updated_at="1970-01-01T00:00:00+00:00",
            )
            payload["bridge_row"] = _shape_bridge_payload(transient)

        result = self._invoke_rpc(payload)
        return UserIntent(**result)

    def update(
        self,
        intent_id: str,
        req: IntentUpdateRequest,
        *,
        user_id: str,
    ) -> UserIntent:
        """Apply a PATCH-style partial update + sync the bridge row.

        Fetches the existing intent to know its type (so the bridge
        payload is shaped correctly), merges the patch, then submits to
        the RPC.

        Raises:
            LookupError: When the intent does not exist for this user.
        """
        existing = self.get(intent_id, user_id=user_id)
        if existing is None:
            raise LookupError(f"intent {intent_id} not found")

        merged_amount = req.amount if req.amount is not None else existing.amount
        merged_amount_delta = req.amount_delta if req.amount_delta is not None else existing.amount_delta
        merged_start_date = req.start_date if req.start_date is not None else existing.start_date
        merged_end_date = req.end_date if req.end_date is not None else existing.end_date
        merged_confidence = req.confidence if req.confidence is not None else existing.confidence
        merged_is_active = req.is_active if req.is_active is not None else existing.is_active
        merged_notes = req.notes if req.notes is not None else existing.notes

        bridge_needed = should_have_bridge_row(existing)

        payload: dict[str, Any] = {
            "user_id": user_id,
            "id": intent_id,
            "intent_type": existing.intent_type.value,
            "amount": _maybe(req.amount),
            "amount_delta": _maybe(req.amount_delta),
            "start_date": _to_payload_value(req.start_date) if req.start_date else None,
            "end_date": _to_payload_value(req.end_date) if req.end_date else None,
            "confidence": req.confidence.value if req.confidence else None,
            "notes": req.notes,
            "is_active": req.is_active,
            "should_bridge": bridge_needed,
            "bridge_row": None,
        }

        if bridge_needed:
            merged_intent = UserIntent(
                id=existing.id,
                user_id=existing.user_id,
                intent_type=existing.intent_type,
                amount=merged_amount,
                amount_delta=merged_amount_delta,
                category_bucket=existing.category_bucket,
                start_date=merged_start_date,
                end_date=merged_end_date,
                confidence=merged_confidence,
                is_recurring=existing.is_recurring,
                rrule_freq=existing.rrule_freq,
                notes=merged_notes,
                is_active=merged_is_active,
                created_at=existing.created_at,
                updated_at=existing.updated_at,
            )
            payload["bridge_row"] = _shape_bridge_payload(merged_intent)

        result = self._invoke_rpc(payload)
        return UserIntent(**result)

    def delete(self, intent_id: str, *, user_id: str) -> UserIntent:
        """Soft-delete by setting ``is_active=False`` (cascades to bridge row).

        Hard-delete is reserved for the auth.users CASCADE path.
        """
        return self.update(
            intent_id,
            IntentUpdateRequest(is_active=False),
            user_id=user_id,
        )

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _invoke_rpc(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = self.client.rpc(_RPC, {"payload": payload}).execute()
        except Exception as exc:
            logger.warning("intent_rpc_failed", error=str(exc))
            raise
        if not resp.data:
            raise RuntimeError("upsert_intent_with_bridge returned no data")
        return resp.data


def _maybe(v: Any) -> Any:
    """Pass through ``v`` only when not ``None`` so the RPC's COALESCE
    on UPDATE preserves existing values."""
    return v if v is not None else None
