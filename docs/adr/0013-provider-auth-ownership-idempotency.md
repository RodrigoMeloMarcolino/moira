# ADR 0013 - Provider auth, ownership, and booking idempotency

## Status

Accepted

## Context

The scheduling core already supports provider signup, public catalog reads,
availability, public booking, and double-booking protection through occupied
slots. Administrative endpoints still need provider authentication and basic
tenant isolation before the backend can be treated as an API-first core.

Public booking also needs a minimal retry-safe contract so clients can safely
repeat a request after a network timeout without creating duplicate
appointments.

## Decision

Use bearer access tokens for provider authentication in the MVP. Tokens are JWTs
signed with HS256 using the configured application secret, issued and verified
through a PyJWT-based infrastructure adapter, and contain the user id as the
subject.

Administrative use cases receive the authenticated provider id and validate
ownership before mutating or reading provider-owned resources.

For public booking, support an optional `Idempotency-Key` header. The system
stores the key and a deterministic payload fingerprint on the appointment. A
retry with the same provider, key, and payload returns the original appointment.
A retry with the same provider and key but a different payload returns a conflict.

## Consequences

- Customers remain unauthenticated in the MVP.
- Public catalog and public booking endpoints do not require bearer tokens.
- Administrative endpoints return unauthorized when the token is missing or
  invalid.
- Cross-provider administrative access is rejected as forbidden.
- Double-booking protection remains enforced by the database constraint on
  appointment slots.
- Idempotency is intentionally limited to public booking for now.
