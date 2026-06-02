# ADR 0011 - Store provider currency and offering prices in minor units

## Status

Accepted

## Context

Providers can define offerings with optional public prices. The MVP needs a clear
and safe representation for these monetary values before the offering schema
becomes part of the database and API contracts.

The SaaS monetization strategy, such as subscription plans, commissions, billing,
checkout, invoices, or payment provider integration, is not part of this
decision. This ADR only covers prices shown or stored for provider offerings.

Money must not be stored as floating point values because binary floating point
can introduce precision errors in arithmetic, comparisons, serialization, and
display.

## Decision

Store the provider's currency on the provider record using an ISO 4217 currency
code.

For the MVP, providers default to `BRL`.

Store offering prices as integer minor units on the offering record. For `BRL`,
this means cents.

The initial offering field is:

```text
price_cents
```

The provider field is:

```text
currency_code
```

Application code and API contracts must not use floating point numbers to
represent money. Boundaries that receive or display human-readable prices must
convert between formatted currency values and integer minor units explicitly.

Examples:

```text
R$ 50,00 -> price_cents = 5000, provider.currency_code = "BRL"
R$ 49,90 -> price_cents = 4990, provider.currency_code = "BRL"
```

Offering prices may be optional in the MVP. When present, `price_cents` must be
greater than or equal to zero.

## Consequences

- The `providers` table must include `currency_code`.
- The `offerings` table must include `price_cents`.
- Monetary values must be stored as integers, not floats.
- UI and external API layers are responsible for formatting and parsing display
  values such as `R$ 50,00`.
- Offering prices inherit the provider currency instead of storing a currency per
  offering in the MVP.
- Changing a provider currency after offerings exist can make existing prices
  ambiguous and should be restricted or handled by an explicit future rule.
- SaaS monetization remains a separate future decision.
