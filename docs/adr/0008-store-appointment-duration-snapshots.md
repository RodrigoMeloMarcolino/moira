# ADR 0008 - Store appointment duration snapshots

## Status

Accepted

## Context

Providers may change a service duration after appointments have already been booked. Existing appointments should not change retroactively when an offering is edited.

## Decision

Store `duration_minutes_snapshot` on each appointment at creation time.

The appointment end time and occupied slots are calculated from the offering duration at the time of booking, then preserved on the appointment.

## Consequences

- Appointment history remains stable even when offerings change.
- Appointment creation must copy the active offering duration into the appointment.
- Availability and rescheduling logic should use the appointment snapshot where historical appointment duration matters.
