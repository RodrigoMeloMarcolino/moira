# ADR 0014 - Version v1 routes and standard error envelope

## Status

Accepted

## Context

The backend is becoming the API-first scheduling core for the SaaS, public
booking flow, and future agent/channel integrations. The HTTP contract needs a
stable version boundary and a clear split between public customer-facing reads
and authenticated provider administration.

## Decision

Expose the current API only under `/v1`.

Use `/v1/public` for customer-facing public endpoints that do not require
provider authentication. Use `/v1/providers/{provider_id}` and resource-specific
administrative routes for provider-owned operations that require bearer auth.

Return HTTP errors with a consistent envelope:

```json
{
  "error": {
    "code": "provider_not_found",
    "message": "provider not found",
    "details": null
  }
}
```

Validation errors use `validation_error` and include validation details.

Public provider responses do not expose `user_id`.

## Consequences

- Unversioned routes are no longer registered.
- Public clients should use `/v1/public/...`.
- Provider admin clients should use `/v1/...` with bearer tokens.
- Future API changes can be introduced behind a version boundary.
- Error handling is centralized in FastAPI exception handlers instead of being
  shaped ad hoc by each router.
