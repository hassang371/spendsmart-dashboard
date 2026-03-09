# RFC-002: Dual-Layer Auth & Tenant Isolation Policy

> **Doc ID:** RFC-002-auth-tenant-isolation
> **Date:** 2026-03-08
> **DRI:** Hassan
> **Status:** Implemented

*Use this short-form RFC for small decisions. Use `rfc.md` for significant architectural changes.*

---

## Problem Statement

Two high-severity security bugs (BUG-002 IDOR in Safe-to-Spend, BUG-032 IDOR in Anomaly detection) were caused by the backend implicitly trusting the client-provided `user_id` parameter or failing to filter database aggregations by `user_id`, under the false assumption that Supabase Row Level Security (RLS) alone provided sufficient protection in the service layer.

## Decision

We are adopting a **Dual-Layer Isolation Model**:
1. **Database Layer:** Supabase RLS remains active as a defense-in-depth safety net.
2. **Service Layer (Mandatory):** The Python backend MUST explicitly verify authorization boundaries. Specifically:
   - The user ID MUST be derived from the verified JWT (via `CurrentUser` dependency), never from path/body parameters for operations acting on "self".
   - ALL database queries affecting or reading multi-tenant tables MUST explicitly include `.eq("user_id", current_user.id)`.

```mermaid
flowchart LR
    A["🔴 Before (Vulnerable)"] -->|Trusts input user_id| B["Route Handler"]
    B -->|Query without .eq()| C["Supabase (Relies solely on RLS)"]
    
    D["✅ After (Dual-Layer)"] -->|Extracts UID from JWT| E["Route Handler"]
    E -->|Explicit .eq('user_id', uid)| F["Supabase (RLS + Explicit Filter)"]
```

## Alternatives Considered

| Option | Why Rejected |
|---|---|
| Rely strictly on RLS | The backend often runs with the `service_role` key (which bypasses RLS) for background tasks, leading to accidental cross-tenant data spillage if code is shared between API and Worker. |
| Custom RBAC Middleware | Too complex for our current multi-tenant needs; enforcing `.eq("user_id")` solves 99% of our current data isolation risks simply. |

## Impact

- **Code Review:** Reviewers MUST block any PR that reads/writes data without an explicit `user_id` query filter.
- **Testing:** All new API routes must include a cross-tenant test (e.g., User A attempting to access User B's resource) to prove the filter is active.
- **Migration:** Existing routes (like BUG-002 and BUG-032) have already been patched to comply.
