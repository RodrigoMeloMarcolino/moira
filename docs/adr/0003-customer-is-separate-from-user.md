# ADR 0003 - Customer is separate from User

## Status

Accepted

## Context

The platform has two distinct people concepts:

- Users: authenticated actors who access the provider/admin side of the platform.
- Customers: final clients who book services with providers.

Treating customers as users would mix platform identity and commercial relationship data, and would add login, permissions, and ownership concepts to a flow that should stay low-friction.

## Decision

Customer and User are separate concepts.

Customers are not authenticated users in the MVP. They do not have passwords, sessions, JWTs, roles, permissions, or ownership over internal provider resources.

## Consequences

- Authorization for provider operations must be based on authenticated users/providers, not customer IDs.
- Customers may be reused across providers through appointments.
- Customer-provider relationships are inferred from appointments in the MVP.
- Public cancellation and rescheduling must use appointment-specific tokens, not customer authentication.
