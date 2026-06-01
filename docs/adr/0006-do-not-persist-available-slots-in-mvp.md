# ADR 0006 - Do not persist available slots in the MVP

## Status

Accepted

## Context

Persisting every available slot would create unnecessary data volume and make availability changes harder to reason about.

The MVP only needs to persist facts that represent confirmed occupation of the agenda.

## Decision

Do not pre-generate or persist available slots in the MVP.

Available start times will be calculated dynamically from provider availability rules, selected service duration, existing occupied slots, and future blocking/exception rules when those are introduced.

Only occupied slots are persisted in `appointment_slots`.

## Consequences

- Availability reads must calculate candidates dynamically.
- Availability reads are useful for UX but are not the final consistency guarantee.
- Appointment creation must still rely on database constraints to prevent conflicts.
- Changes to provider availability do not require rewriting pre-generated slot rows.
