# A five-minute portfolio walkthrough

## 1. State the engineering problem

“An API can represent pilots as URLs, MongoDB uses ObjectIds, and SQL needs relational keys. This pipeline moves between those representations while proving the relationships still point to the same people.”

## 2. Run it without setup friction

Run `starship-pipeline demo`. Explain that the fixture and mongomock backend make this an offline demonstration, while CI and the recorded live run exercise real MongoDB. Open `artifacts/demo/report.json` and show counts, source/backend, quality checks and pilot names.

## 3. Explain two decisions in code

- In `transform.py`, show canonical source identities and preflight reference validation. Names do not act as keys.
- In `storage.py`, show unique indexes/upserts and the `$lookup`. Explain how repeated imports preserve person IDs and refresh pilot arrays.

## 4. Prove SQL parity

Show the four-table schema in `storage.py` or `docs/architecture.md`. Explain the ship/pilot junction table, foreign keys and exact URL-pair comparison. Equal counts alone would not prove that the right people are connected to the right ships.

## 5. Show evidence and acknowledge limits

Open GitHub Actions for the Python matrix and real MongoDB job. The original verified live run contained 82 people, 36 ships and 30 pilot links. Explain per-request timeouts, bounded retries, null measures, and the absence of a cross-database transaction.

## Questions to be ready for

**How is this different from a simple API script?** It has explicit contracts, stable identities, replayable inputs, idempotent writes, identity checks in both databases, a packaged CLI and automated CI.

**How would you productionise it?** Add a scheduler, secret management, structured monitoring, change/deletion policy, isolated deployment configuration and a transactional or versioned publishing strategy appropriate to the requirements. Those are future extensions, not current features.

**Why not use names as keys?** Names may repeat or change; canonical source resource identities are a better bridge.

**What happens if the API changes?** Invalid structures, inconsistent counts, bad numeric values and missing pilot resources fail visibly. Source totals are observed, not fixed to 36 in code.

**What is the business relevance?** The same pattern applies to CRM contacts and accounts, product/catalog relationships, or supplier records: preserve source identity, validate references and prove correctness after moving between storage models.
