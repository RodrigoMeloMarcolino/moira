# ADR 0005 - Use discrete 15-minute appointment slots

## Status

Accepted

## Context

Scheduling must prevent overlapping appointments, including under concurrent booking attempts. Direct interval comparison can become complex and error-prone as the product grows.

Discrete slots simplify conflict detection and let the database enforce consistency.

## Decision

Use discrete 15-minute slots as the minimum occupation unit for the MVP.

When an appointment is created, the system computes occupied slot start times from `start_at` until before `end_at`, using the service duration snapshot.

## Consequences

- Appointment start times must align to 15-minute boundaries.
- Service durations must be compatible with the slot size in the MVP.
- Long appointments occupy multiple rows in `appointment_slots`.
- Availability can be calculated in 15-minute candidate steps.
