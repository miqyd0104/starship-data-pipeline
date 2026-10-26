"""Orchestrate a complete, verifiable run and publish a small JSON manifest."""

from __future__ import annotations

import hashlib
import json
import statistics
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

from .storage import export_sql, load_mongo, verify_mongo
from .transform import prepare


def run_pipeline(
    db, raw_people: list[dict], raw_ships: list[dict], output: Path, source: str, backend: str
) -> dict:
    start = perf_counter()
    people, ships = prepare(raw_people, raw_ships)
    load_mongo(db, people, ships)
    lookup = verify_mongo(db, people, ships)
    output.mkdir(parents=True, exist_ok=True)
    sql = export_sql(people, ships, output / "starships.sqlite3")
    lengths = [s["length_m"] for s in ships if s["length_m"] is not None]
    # Deterministic, source-derived metrics give a second check on the stored join.
    analytics = {
        "ships_with_pilots": sum(bool(s["pilot_urls"]) for s in ships),
        "ships_without_pilots": sum(not s["pilot_urls"] for s in ships),
        "unique_pilots": len({p for s in ships for p in s["pilot_urls"]}),
        "known_lengths": len(lengths),
        "average_known_length_m": statistics.mean(lengths) if lengths else None,
        "longest_ships": [
            {"name": s["name"], "length_m": s["length_m"]}
            for s in sorted(
                (s for s in ships if s["length_m"] is not None),
                key=lambda s: (-s["length_m"], s["name"]),
            )[:5]
        ],
    }
    checksum = hashlib.sha256(
        json.dumps({"people": people, "ships": ships}, sort_keys=True).encode()
    ).hexdigest()
    report = {
        "schema_version": 1,
        "source": source,
        "mongo_backend": backend,
        "finished_at_utc": datetime.now(UTC).isoformat(),
        "duration_seconds": round(perf_counter() - start, 3),
        "source_projection_sha256": checksum,
        "counts": {
            "people": len(people),
            "starships": len(ships),
            "pilot_links": sum(len(s["pilot_urls"]) for s in ships),
        },
        "quality": {
            "unresolved_pilot_links": 0,
            "mongo_lookup_verified": True,
            "sql_identity_parity": sql["identity_parity"],
            "sql_foreign_key_violations": sql["foreign_key_violations"],
        },
        "analytics": analytics,
        "starship_pilots": lookup,
    }
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    # Runtime snapshot is intentionally local; it is not bundled with the package.
    (output / "source-snapshot.json").write_text(
        json.dumps({"people": raw_people, "starships": raw_ships}, indent=2) + "\n",
        encoding="utf-8",
    )
    return report
