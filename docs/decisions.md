# Technical decisions

## Stable identities over name matching

The classroom exercise originally used names to bridge an API and a preloaded character collection. A public tool should not require that private setup. This version downloads people directly from SWAPI and uses canonical resource URLs as keys. Two people can share a name without creating an ambiguous relationship.

HTTP and HTTPS variants normalise to the same identity, with one trailing slash. Resource IDs and types are validated, and unrelated domains or embedded credentials are rejected. HTTP request redirects are not followed. Default certificate verification remains enabled; a custom CA bundle can be supplied explicitly.

## Original synthetic fixtures for a frictionless demo

A reviewer should be able to run the project without a MongoDB service or external API. Three fictional ships and three fictional people exercise multiple pilots, a shared pilot, no pilots, an unknown measure and a comma-separated number. Their SWAPI-shaped IDs are test identities, not claims about actual API records.

The report clearly distinguishes this mongomock run from a real MongoDB run. Real-server integration tests validate BSON IDs, unique indexes and `$lookup`. No class datasets or Slack instructions are published.

## Repeatability without silent deletion

Unique source indexes and upserts preserve MongoDB IDs. Every incoming ship replaces its current pilot arrays. The SQL loader replaces each incoming ship's junction rows inside a transaction. Replaying the same source preserves entity and relationship counts.

This is an upsert import, not a destructive full snapshot synchroniser. Removed entities and unexpected local additions are detected as a mismatch rather than deleted. Use separate databases/output directories for different datasets. Unreferenced old model specifications may remain after specification changes; model garbage collection is deliberately outside scope.

## Normalise only what the application needs

The SQL projection keeps people, model specifications, ships and pilot connections in separate tables. Every non-key attribute describes its table's entity; relationships use a composite-key junction table. It demonstrates third-normal-form modelling for this declared projection.

Manufacturer attribution is retained as raw text. A comma is not assumed to be a reliable business-entity delimiter. Heights, masses and lengths are optional non-negative numbers; unknown values become null. Crew ranges, film descriptions and unrelated fields are excluded rather than coerced into misleading values.

## Failures are visible

Retries are restricted to GET requests, with three retries and backoff for selected transient status codes and rate limiting. Connection/read timeouts are five/thirty seconds. Those are per-request limits, not a wall-clock SLA; `Retry-After` may extend a rate-limited run. Permanent HTTP errors are not hidden by an automatic snapshot fallback.

Data-quality checks happen before MongoDB writes. A later connectivity failure can leave a partial MongoDB load; rerunning completes idempotent writes. SQLite exports use a transaction, but no cross-database atomicity or exactly-once guarantee is claimed.

## Evidence over decorative claims

Tests cover success cases and meaningful failure paths. A separate integration test exercises a real MongoDB server. SQL pair comparisons verify identities, not just equal row counts. The local full-API run and its replay are documented separately from CI, which never depends on the public API.
