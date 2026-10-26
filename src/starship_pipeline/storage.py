"""Repeatable MongoDB loading and independent relational validation."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from bson import ObjectId

from .source import DataQualityError

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS people (
  source_url TEXT PRIMARY KEY, name TEXT NOT NULL,
  height_cm REAL CHECK(height_cm >= 0), mass_kg REAL CHECK(mass_kg >= 0)
);
CREATE TABLE IF NOT EXISTS models (
  model_id TEXT PRIMARY KEY, model TEXT NOT NULL,
  manufacturer_attribution TEXT NOT NULL, length_m REAL CHECK(length_m >= 0)
);
CREATE TABLE IF NOT EXISTS starships (
  source_url TEXT PRIMARY KEY, name TEXT NOT NULL,
  model_id TEXT NOT NULL REFERENCES models(model_id)
);
CREATE TABLE IF NOT EXISTS starship_pilots (
  starship_url TEXT NOT NULL REFERENCES starships(source_url),
  person_url TEXT NOT NULL REFERENCES people(source_url),
  PRIMARY KEY (starship_url, person_url)
);
"""


def load_mongo(db, people: list[dict], ships: list[dict]) -> None:
    """Upsert by source identity; retain ObjectIds on subsequent runs.

    Data-quality validation happens before this function. Standalone MongoDB
    writes are not a transaction; a transport failure is recovered by rerunning.
    Unexpected stale records are detected by verify_mongo, never silently deleted.
    """
    db.people.create_index("source_url", unique=True)
    db.starships.create_index("source_url", unique=True)
    for person in people:
        db.people.update_one({"source_url": person["source_url"]}, {"$set": person}, upsert=True)
    ids = {p["source_url"]: p["_id"] for p in db.people.find()}
    for ship in ships:
        document = dict(ship)
        document["pilots"] = [ids[url] for url in ship["pilot_urls"]]
        db.starships.update_one({"source_url": ship["source_url"]}, {"$set": document}, upsert=True)


def verify_mongo(db, people: list[dict], ships: list[dict]) -> list[dict]:
    stored_people = list(db.people.find())
    stored_ships = list(db.starships.find())
    if {p["source_url"] for p in stored_people} != {p["source_url"] for p in people} or {
        s["source_url"] for s in stored_ships
    } != {s["source_url"] for s in ships}:
        raise DataQualityError("Stored dataset differs from this source; use a separate database")
    by_id = {p["_id"]: p for p in stored_people}
    expected = {s["source_url"]: s for s in ships}
    for ship in stored_ships:
        ids = ship["pilots"]
        if not all(isinstance(p, ObjectId) and p in by_id for p in ids):
            raise DataQualityError("Invalid or dangling MongoDB pilot ID")
        resolved = [by_id[p]["source_url"] for p in ids]
        if resolved != expected[ship["source_url"]]["pilot_urls"]:
            raise DataQualityError("Pilot identity mismatch")
    rows = list(
        db.starships.aggregate(
            [
                {
                    "$lookup": {
                        "from": "people",
                        "localField": "pilots",
                        "foreignField": "_id",
                        "as": "details",
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "name": 1,
                        "source_url": 1,
                        "pilot_names": "$details.name",
                        "pilot_sources": "$details.source_url",
                    }
                },
                {"$sort": {"source_url": 1}},
            ]
        )
    )
    for row in rows:
        if set(row["pilot_sources"]) != set(expected[row["source_url"]]["pilot_urls"]):
            raise DataQualityError("MongoDB lookup did not resolve every pilot")
        row["pilot_names"] = sorted(row["pilot_names"])
        row["pilot_sources"] = sorted(row["pilot_sources"])
    return rows


def export_sql(people: list[dict], ships: list[dict], path: Path) -> dict:
    """Normalise the analytical projection; verify SQL links against source URLs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as sql, sql:
        sql.executescript(SCHEMA)
        for person in people:
            sql.execute(
                """INSERT INTO people VALUES (?, ?, ?, ?)
                ON CONFLICT(source_url) DO UPDATE SET name=excluded.name,
                height_cm=excluded.height_cm, mass_kg=excluded.mass_kg""",
                (person["source_url"], person["name"], person["height_cm"], person["mass_kg"]),
            )
        for ship in ships:
            # A model specification is identified by its exact source description,
            # manufacturer attribution and length; equal model names can differ.
            spec = (ship["model"], ship["manufacturer"], ship["length_m"])
            model_id = hashlib.sha256(json.dumps(spec).encode()).hexdigest()
            sql.execute("INSERT OR IGNORE INTO models VALUES (?, ?, ?, ?)", (model_id, *spec))
            sql.execute(
                """INSERT INTO starships VALUES (?, ?, ?) ON CONFLICT(source_url)
                DO UPDATE SET name=excluded.name, model_id=excluded.model_id""",
                (ship["source_url"], ship["name"], model_id),
            )
            sql.execute("DELETE FROM starship_pilots WHERE starship_url=?", (ship["source_url"],))
            sql.executemany(
                "INSERT INTO starship_pilots VALUES (?, ?)",
                [(ship["source_url"], p) for p in ship["pilot_urls"]],
            )
        violations = sql.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise DataQualityError("SQL foreign key check failed")
        actual_pairs = set(sql.execute("SELECT starship_url, person_url FROM starship_pilots"))
        expected_pairs = {(s["source_url"], p) for s in ships for p in s["pilot_urls"]}
        actual_ships = {r[0] for r in sql.execute("SELECT source_url FROM starships")}
        actual_people = {r[0] for r in sql.execute("SELECT source_url FROM people")}
        if (
            actual_pairs != expected_pairs
            or actual_ships != {s["source_url"] for s in ships}
            or actual_people != {p["source_url"] for p in people}
        ):
            raise DataQualityError("SQLite export contains stale or mismatched records")
        return {
            "people": len(actual_people),
            "starships": len(actual_ships),
            "pilot_links": len(actual_pairs),
            "foreign_key_violations": len(violations),
            "identity_parity": True,
        }
