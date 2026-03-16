# BUG-003: Setu AA Integration - CORS Error Hiding Authentication Failure

## Meta
- **Status:** Resolved
- **Date:** 2026-03-16
- **Component:** API (Aggregator Domain)
- **Severity:** High (Blocked Account Linking)

## Symptom
When the frontend attempted to link an account via `/api/v1/aggregator/accounts/link`, the browser blocked the response with a CORS policy error (`No 'Access-Control-Allow-Origin' header is present`).

## Root Cause
The CORS error was a secondary symptom.
1. The `SetuProvider` was using an invalid authentication flow for the v2 Sandbox (sending `client_id` and `client_secret` directly as headers).
2. The Setu Sandbox API rejected the request with a `401 Unauthorized` (`INVALID_CREDENTIALS`).
3. `httpx` raised an `HTTPStatusError` during `raise_for_status()`.
4. This exception was unhandled and propagated all the way up through the FastAPI middleware stack.
5. Because it was an unhandled exception rather than a normal response or a FastAPI `HTTPException`, Starlette's `CORSMiddleware` did not intercept the response to add `Access-Control-Allow-Origin` headers.
6. The browser received a 500 error without CORS headers and interpreted it as a CORS violation.

## Investigation
- Backend logs revealed the `401 Unauthorized` error from Setu, indicating the real issue was authentication.
- Setu documentation confirmed that the v2 API requires an OAuth2 `client_credentials` flow to obtain a JWT Bearer token from `auth-v2.setu.co`.
- Furthermore, all Setu v2 API calls require the `x-product-instance-id` header in addition to the Bearer token, and endpoints must use the `/v2/` prefix.

## Solution Implementations
1. **Error Handling & CORS Fix:** Added `_handle_setu_error` interceptor to catch `httpx.HTTPStatusError` exceptions and re-raise them as FastAPI `HTTPException`. This ensures the error response passes through normal exception handlers where `CORSMiddleware` correctly decorates it with `Access-Control-Allow-Origin` headers.
2. **Auth Flow Fix:** Rewrote `SetuProvider` (`apps/api/domains/aggregator/providers/setu.py`) to correctly implement the two-step OAuth2 Bearer token flow, including token caching to minimize redundant auth requests.
3. **Config Updates:** Added `SETU_AUTH_URL` and `SETU_PRODUCT_INSTANCE_ID` to `apps/api/core/config.py` and updated `.env` values.

## Verification
- Verified Token generation against `https://auth-v2.setu.co/realms/setu/protocol/openid-connect/token` returns 200 OK.
- Verified `/v2/consents` creation with Bearer token & `x-product-instance-id` returns 201 Created.
- All 5 aggregator domain tests (`test_router.py`) pass successfully.
