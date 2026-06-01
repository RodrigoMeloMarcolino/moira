# ADR 0004 - Reuse customers globally by canonical phone

## Status

Accepted

## Context

Customers may book with multiple providers. For this product, phone/WhatsApp is expected to be a more reliable and practical identifier than email.

The MVP needs a simple customer reuse rule that supports recurring customers without creating provider-specific duplicates by default.

## Decision

Reuse customers globally by canonical phone number in the MVP.

The `customers` table should enforce uniqueness on canonical phone. Email is optional and must not be the primary identity key for customers in the MVP.

When an existing customer is found by phone, the application may update the name with the latest submitted value and fill email only if it is currently empty.

## Consequences

- Phone input must be validated and normalized before lookup or persistence.
- Customer creation and reuse must happen inside appointment creation transactions.
- A customer can have appointments with multiple providers.
- Provider-specific relationship data should not be stored directly on the global customer record in the MVP.
