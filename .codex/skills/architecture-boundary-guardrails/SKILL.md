---
name: architecture-boundary-guardrails
description: Enforce architectural boundaries during design, implementation, review, and refactoring. Use when changing application wiring, cache strategies, use cases, shared services, dependency injection, or module layout to prevent mixing multiple domains in one file, replacing use cases with edge wrappers, or creating cascading dependencies across modules.
---

# Architecture Boundary Guardrails

## Overview

Apply this skill before introducing shared services, cache layers, dependency containers, or cross-module orchestration. Keep policies close to the owning application module and keep infrastructure details behind narrow ports.

## Mandatory Checks

Before editing code, answer these questions:

1. Which domain owns this behavior?
2. Is the file being changed carrying rules from more than one domain?
3. Is a new dependency being injected because the use case truly needs it, or because wiring was centralized elsewhere?
4. Will this change make the HTTP layer depend on a helper that bypasses the use case?
5. Can invalidation, serialization, or cache keys live in the owning module instead of a shared registry?

If any answer points to "shared because it was convenient", stop and refactor the design first.

## Guardrails

### 1. Do not centralize domain policies in shared files

Do not create a single shared service that contains cache keys, TTLs, invalidation rules, serializers, or orchestration for unrelated domains.

Prefer:

- one cache-facing application service per domain or use case
- a tiny shared adapter only for generic cache primitives like `get`, `set`, `delete`, `incr`
- domain-specific key rules and payload mapping inside the owning module

### 2. Do not replace a use case with an edge wrapper

Controllers and route dependencies should keep calling the application use case as the main entry point.

Prefer:

- `UseCase(cache_port=..., repository=...)`
- the use case deciding cache read-through, fallback, and invalidation

Avoid:

- route -> cached reader -> use case
- route -> helper service that duplicates use case orchestration

If a wrapper appears necessary, treat that as a signal that the use case API is incomplete.

### 3. Stop dependency cascades early

A dependency cascade exists when one new concern forces many unrelated modules to accept, forward, or know about a service they do not own.

When adding a dependency:

- inject it only into the use cases that need it
- keep constructor signatures narrow
- avoid adding a cross-cutting dependency to a central container unless multiple use cases in the same boundary actually consume it
- prefer dedicated factories per module over one global container that knows every variant

### 4. Keep shared code policy-free

`shared` may contain:

- ports/protocols
- generic adapters
- neutral utilities

`shared` must not contain:

- provider-specific cache keys
- offerings invalidation rules
- availability version semantics
- orchestration that belongs to one public endpoint flow

### 5. Optimize for ownership, not deduplication

Some duplication is acceptable if it preserves module ownership and makes the dependency graph clearer.

Choose small local duplication over:

- a god service
- a registry of domain rules
- indirection that hides who owns behavior

## Refactoring Pattern

When you find mixed concerns, refactor in this order:

1. Identify the owning use case or application service for each behavior.
2. Move cache policy, key building, and payload mapping into that module.
3. Reduce shared code to a generic port or adapter.
4. Rewire routes back to use cases.
5. Re-run tests focused on behavior and invalidation.

## Review Heuristics

Raise a concern immediately when you see:

- one file naming multiple domains in its public API
- a `shared` module importing DTOs or use cases from several business modules
- route dependencies that select between "fresh" and "cached" readers outside the use case
- invalidation logic spread across unrelated modules with a central registry
- a request container growing because a cross-cutting helper became the new orchestration center

## Expected Outcome

After applying this skill:

- each domain owns its cache policy
- use cases remain the application entry points
- shared code stays generic
- dependency injection remains narrow
- adding one new concern does not force unrelated modules to change
