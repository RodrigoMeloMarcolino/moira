# ADR 0007 - Prevent double booking with a database constraint

## Status

Accepted

## Context

Two clients can attempt overlapping bookings at nearly the same time. If the application only checks availability before writing, both requests may see the time as available and create conflicting appointments.

The database must be the final consistency boundary.

## Decision

Prevent double booking in the MVP with a unique database constraint on occupied slots:

```text
UNIQUE(provider_id, slot_start_at)
```

Appointment creation must create the appointment and insert all occupied slots in the same transaction. A unique constraint violation must roll back the whole operation and be translated into a domain/application conflict.

## Consequences

- Overlapping appointments for the same provider cannot occupy the same slot.
- Slot conflict errors should map to HTTP `409 Conflict` in public/API flows.
- Integration tests must cover concurrent and partially overlapping appointment creation against real PostgreSQL.
- Read-time availability remains advisory; write-time constraints enforce correctness.
