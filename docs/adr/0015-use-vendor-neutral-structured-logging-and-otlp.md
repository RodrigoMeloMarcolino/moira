# ADR 0015 - Use vendor-neutral structured logging and OTLP

## Status

Accepted

## Context

Moira needs useful logs for its critical booking, authentication, provider
signup, cache, database, and HTTP flows. The logs must also be consumable by
Grafana Loki or another distributed logging backend without coupling business
modules to one vendor.

Plain text messages and provider-specific SDK calls from use cases would make
queries inconsistent, complicate correlation, and force application changes
when the operational backend changes.

The OpenTelemetry Logs Data Model defines portable concepts for timestamps,
severity, body, event name, resource identity, trace context, and attributes.
Grafana Loki supports native OTLP ingestion, directly or through an
OpenTelemetry Collector.

Moira is also expected to expose metrics for Prometheus in a future stage. Logs
and metrics must share stable service identity and cardinality discipline
without being collapsed into one cross-cutting service.

## Decision

Use Python's standard `logging` module as the API used by application and
infrastructure code.

Define a canonical structured event contract aligned with the OpenTelemetry
Logs Data Model:

- timestamp;
- severity text and number;
- body;
- event name;
- resource attributes;
- event attributes;
- optional trace and span ids when tracing is introduced.

Keep logging setup and exporters in the shared infrastructure observability
adapter. Domain code remains unaware of logging. Use cases own their event names
and business attributes but do not know exporters, endpoints, credentials,
Grafana, or Loki.

Support these exporters:

- structured JSON Lines to `stdout`, always enabled in the MVP;
- OTLP/HTTP, optionally enabled alongside `stdout`.

Use an OpenTelemetry Collector or Grafana Alloy as the recommended routing
boundary. The collector selects Loki, Grafana Cloud, Elastic, Datadog,
CloudWatch, or another destination. Do not add a vendor-specific logging SDK to
business modules.

OTLP export must use asynchronous batching and a bounded queue. Remote exporter
failure is fail-open: it must not fail requests or readiness, and `stdout`
remains available. Invalid local configuration fails at startup when OTLP was
explicitly enabled.

Promote only stable, low-cardinality resource attributes such as service name,
namespace, and environment to Loki labels. Keep request ids, correlation ids,
domain entity ids, routes, and event names as structured metadata.

Never log credentials, authentication tokens, passwords, personal data, full
payloads, connection URLs, idempotency keys, SQL parameters, or cache values.

Treat future Prometheus metrics as a separate observability signal and adapter.
Logging lives under `observability/logging`; future metric providers and the
`/metrics` endpoint will live under `observability/metrics`. They may share
stable service resource identity, but not event orchestration or domain policy.

Prometheus labels must remain low-cardinality. Request ids, correlation ids,
trace/span ids, entity ids, slugs, raw paths, exception messages, and arbitrary
user values must never become metric labels.

The Prometheus client/export path, endpoint security, histogram buckets, and
initial metric catalog require a separate specification and ADR before metrics
are implemented.

## Consequences

- Grafana Loki is supported without becoming an application dependency.
- Another backend can be selected by changing exporter or collector
  configuration rather than business code.
- JSON `stdout` remains suitable for container runtimes and log agents.
- OTLP adds infrastructure dependencies and requires pinned versions and
  contract tests because the OpenTelemetry Python logs SDK is still evolving.
- Export failures can lose remote log records when the bounded queue is full;
  this degradation must be diagnosed locally and monitored later with metrics.
- Deployments must choose either direct OTLP export or collection of `stdout`
  for a given backend to avoid duplicate ingestion.
- Cardinality rules are part of the operational contract and must be covered by
  configuration review and tests.
- Adding Prometheus later does not require changing the logging event contract.
- A separate metrics adapter avoids turning shared observability code into a
  registry of policies owned by unrelated domains.

## References

- [OpenTelemetry Logs Data Model](https://opentelemetry.io/docs/specs/otel/logs/data-model/)
- [OpenTelemetry Python logging instrumentation](https://opentelemetry.io/docs/languages/python/instrumentation/#logs)
- [Grafana Loki OTLP ingestion](https://grafana.com/docs/loki/latest/send-data/otel/)
- [Prometheus metric and label naming](https://prometheus.io/docs/practices/naming/)
