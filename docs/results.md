# Verified results

The following evidence was produced by actual executions on **26 October 2026**. Source totals are observations, not invariants imposed on future API releases.

## Live public API → real MongoDB → SQLite

[Machine-readable evidence](../examples/live-verification.json)

| Check | Observed outcome |
|---|---|
| Input | Live paginated SWAPI people and starships |
| People | 82 |
| Starships | 36 |
| Pilot relationships | 30 |
| Unresolved pilot ObjectIds | 0 |
| MongoDB `$lookup` | Every ship's returned pilot URL set matched its source |
| SQLite foreign keys | 0 violations |
| Relational identity parity | Every ship/person URL pair matched the source |
| Millennium Falcon | Chewbacca, Han Solo, Lando Calrissian, Nien Nunb |
| Replay | Identical entity counts, source checksum and all ship/pilot identities |

The live run used the existing local MongoDB server and a dedicated `starship_portfolio` database. No classroom database was required. A system CA bundle was explicitly supplied on this Mac; certificate checks remained enabled. The recorded live run is separate from the deterministic CI suite.

## Offline demonstration

[Example demo report](../examples/demo-report.json)

The synthetic fixture produces **3 people, 3 ships, 3 links**, with no unresolved references or foreign key violations. Aurora has two pilots, Horizon shares a pilot, and Relay has no pilots. Its average of known ship lengths is **617.25 metres**. The backend is labelled mongomock in the report; these fixture results are not presented as live SWAPI results.

## Automated verification

[Recorded test output](../examples/test-results.txt)

The initial local verification passed **56 tests**, including the real MongoDB integration test, with **96.20% statement coverage** on Python 3.14.6. GitHub Actions independently runs supported Python versions and a MongoDB 8.0 service; use the current CI status for the latest commit's result.

The tests exercise pagination, cycles, source identity, duplicate names, missing/duplicate pilots, numeric parsing, unknown values, HTTP failures/redirects, retry configuration, stable ObjectIds, empty pilot arrays, stale datasets, SQL parity, changed links, CLI execution, report generation and error redaction.

`ruff check .`, `ruff format --check .`, and wheel/source-distribution builds also passed locally. The wheel is smoke-tested in a fresh environment before publication.

## What these checks establish

They demonstrate that this implementation handles the tested contracts and preserved the observed live relationships. They do not establish production throughput, service-level guarantees, high availability or compatibility with every future upstream schema change. The integration suite uses a small synthetic fixture; the separate live run exercises the full observed API dataset.
