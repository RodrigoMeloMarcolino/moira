# ADR 0010 - Use pragmatic modular architecture

## Status

Accepted

## Context

The backend needs clear separation of concerns without excessive ceremony. FastAPI should handle HTTP concerns, while domain and application rules should remain testable outside the framework.

The livedoc recommends a pragmatic architecture inspired by Clean Architecture, Hexagonal Architecture, tactical DDD, and modularization by domain/feature.

## Decision

Use a pragmatic modular architecture organized by domain modules and layers:

- API routers and dependencies handle HTTP concerns.
- Application use cases orchestrate workflows and transactions.
- Domain code contains central rules, value objects, entities, and pure functions where practical.
- Infrastructure code contains SQLAlchemy models, concrete repositories, unit-of-work implementation, and technical integrations.

Avoid theatrical DDD and unnecessary abstractions. Add boundaries when they protect the domain, improve testability, or reduce meaningful complexity.

## Consequences

- Routers must not contain complex business rules.
- Use cases should be easy to test without HTTP.
- Infrastructure can evolve without forcing domain rules into framework-specific code.
- Future modules should follow the same structure unless an ADR replaces this decision.
