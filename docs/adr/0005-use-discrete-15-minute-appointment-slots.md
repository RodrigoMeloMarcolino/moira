# ADR 0005 - Use discrete 15-minute appointment slots

## Status

Accepted

## Context

Scheduling must prevent overlapping appointments, including under concurrent booking attempts. Direct interval comparison can become complex and error-prone as the product grows.

Discrete slots simplify conflict detection and let the database enforce consistency.

## Decision

Use discrete 15-minute slots as the minimum occupation unit for the MVP.

When an appointment is created, the system computes occupied slot start times from `start_at` until before `end_at`, using the service duration snapshot.

Weekly availability rules are evaluated in the provider's IANA timezone. Public
available-slot responses and persisted occupied slots use canonical
timezone-aware UTC instants, so comparisons must convert through timezone rules
instead of attaching or removing `tzinfo`.

## Consequences

- Appointment start times must align to 15-minute boundaries.
- Service durations must be compatible with the slot size in the MVP.
- Long appointments occupy multiple rows in `appointment_slots`.
- Availability can be calculated in 15-minute candidate steps.
- Public scheduling clients must send appointment `start_at` with a timezone
  offset; the API returns available starts as UTC/offset-aware datetimes.
