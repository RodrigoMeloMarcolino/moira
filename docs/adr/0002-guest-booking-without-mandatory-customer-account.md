# ADR 0002 - Guest booking without mandatory customer account

## Status

Accepted

## Context

The MVP must minimize friction for clients booking services through a provider's public link. Requiring a final customer to create an account before booking would make the core flow slower and less attractive for providers and their clients.

## Decision

Final customers will not be required to create an account or log in to book an appointment in the MVP.

The public booking flow will ask only for minimum customer data, such as name, phone/WhatsApp, optional email, and optional notes.

## Consequences

- Public booking endpoints must not require customer authentication.
- Administrative/provider endpoints remain authenticated.
- Sensitive public appointment actions, such as cancellation or rescheduling, must be authorized through appointment-specific secure tokens instead of customer login.
- Customer records can still exist internally for history and relationship tracking without becoming platform users.
