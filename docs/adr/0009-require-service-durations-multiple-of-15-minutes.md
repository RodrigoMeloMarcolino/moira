# ADR 0009 - Require service durations to be multiples of 15 minutes in the MVP

## Status

Accepted

## Context

The MVP uses 15-minute discrete slots. Supporting arbitrary durations would add complexity to slot generation, availability calculation, and conflict handling.

## Decision

Provider offering durations must be multiples of 15 minutes in the MVP.

Durations that are not positive multiples of 15 minutes must be rejected during offering creation or update.

## Consequences

- Slot generation remains simple and deterministic.
- Availability calculations can use fixed 15-minute candidate boundaries.
- The product can revisit smaller or more flexible duration increments in a future ADR if needed.
