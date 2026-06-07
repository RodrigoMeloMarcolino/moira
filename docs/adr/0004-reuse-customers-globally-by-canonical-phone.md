# ADR 0004 - Reuse customers globally by canonical phone

## Status

Accepted

## Context

Customers may book with multiple providers. For this product, phone/WhatsApp is expected to be a more reliable and practical identifier than email.

The MVP needs a simple customer reuse rule that supports recurring customers without creating provider-specific duplicates by default.

## Decision

Reuse customers globally by canonical phone number in the MVP.

The `customers` table should use a single `phone` column for the customer phone
number. This field must store the phone already validated and normalized in
canonical format before lookup or persistence.

The MVP must not add a separate `canonical_phone` column.

The `customers` table should enforce uniqueness on `phone`. Email is optional
and must not be the primary identity key for customers in the MVP.

When an existing customer is found by phone, the application may eventually
update the name with the latest submitted value and fill email only if it is
currently empty.

For the initial public booking implementation, this profile update flow will
not be implemented. The system will reuse the existing customer by canonical
phone and keep the existing global customer data unchanged.

## Consequences

- Phone input must be validated and normalized before lookup or persistence.
- `customers.phone` stores the canonical phone value.
- There is no separate `customers.canonical_phone` column in the MVP.
- Customer creation and reuse must happen inside appointment creation transactions.
- A customer can have appointments with multiple providers.
- Provider-specific relationship data should not be stored directly on the global customer record in the MVP.
- The first public booking flow may discard submitted customer name/email when
  the phone already belongs to an existing customer, because automatic global
  profile updates are intentionally deferred.
