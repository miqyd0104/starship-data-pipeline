"""Optional 3NF extension using SQLite and enforced foreign keys."""

import json
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MODEL_FIELDS = [
    "cost_in_credits",
    "length",
    "max_atmosphering_speed",
    "crew",
    "passengers",
    "cargo_capacity",
    "consumables",
    "hyperdrive_rating",
    "MGLT",
    "starship_class",
]
SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS characters (
    character_id TEXT PRIMARY KEY, name TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS models (
    model TEXT PRIMARY KEY,
    cost_in_credits TEXT, length TEXT, max_atmosphering_speed TEXT,
    crew TEXT, passengers TEXT, cargo_capacity TEXT, consumables TEXT,
    hyperdrive_rating TEXT, MGLT TEXT, starship_class TEXT
);
CREATE TABLE IF NOT EXISTS manufacturers (name TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS model_manufacturers (
    model TEXT REFERENCES models(model),
    manufacturer TEXT REFERENCES manufacturers(name),
    PRIMARY KEY (model, manufacturer)
);
CREATE TABLE IF NOT EXISTS starships (
    starship_url TEXT PRIMARY KEY, name TEXT NOT NULL,
    model TEXT NOT NULL REFERENCES models(model), created TEXT, edited TEXT
);
CREATE TABLE IF NOT EXISTS starship_pilots (
    starship_url TEXT REFERENCES starships(starship_url),
    character_id TEXT REFERENCES characters(character_id),
    PRIMARY KEY (starship_url, character_id)
);
CREATE TABLE IF NOT EXISTS films (film_url TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS starship_films (
    starship_url TEXT REFERENCES starships(starship_url),
    film_url TEXT REFERENCES films(film_url),
    PRIMARY KEY (starship_url, film_url)
);
"""


def export_sql(db, destination):
    """All starship fields, character identity, and three many-to-many relations.

    Assumption: model identifies a specification; reject conflicting definitions.
    Manufacturer commas delimit organisations in this API snapshot. Unknown
    measures stay source text, rather than being misleadingly changed to zero.
    """
    definitions = {}
    ships = list(db.starships.find())
    for ship in ships:
        spec = tuple(ship.get(f) for f in MODEL_FIELDS)
        definition = (spec, ship["manufacturer"])
        if ship["model"] in definitions and definitions[ship["model"]] != definition:
            raise ValueError("Conflicting specifications for the same model")
        definitions[ship["model"]] = definition
    with sqlite3.connect(destination) as sql:
        sql.executescript(SCHEMA)
        for character in db.characters.find():
            sql.execute(
                "INSERT INTO characters VALUES (?, ?) ON CONFLICT(character_id) "
                "DO UPDATE SET name=excluded.name",
                (str(character["_id"]), character["name"]),
            )
        for model, (spec, manufacturers) in definitions.items():
            columns = ", ".join(MODEL_FIELDS)
            updates = ", ".join(f"{f}=excluded.{f}" for f in MODEL_FIELDS)
            marks = ", ".join("?" for _ in range(len(MODEL_FIELDS) + 1))
            sql.execute(
                f"INSERT INTO models (model, {columns}) VALUES ({marks}) "
                f"ON CONFLICT(model) DO UPDATE SET {updates}",
                (model, *spec),
            )
            sql.execute("DELETE FROM model_manufacturers WHERE model=?", (model,))
            for name in {n.strip() for n in manufacturers.split(",")}:
                sql.execute("INSERT OR IGNORE INTO manufacturers VALUES (?)", (name,))
                sql.execute(
                    "INSERT INTO model_manufacturers VALUES (?, ?)", (model, name)
                )
        for ship in ships:
            sql.execute(
                "INSERT INTO starships VALUES (?, ?, ?, ?, ?) ON CONFLICT(starship_url) "
                "DO UPDATE SET name=excluded.name, model=excluded.model, "
                "created=excluded.created, edited=excluded.edited",
                (
                    ship["url"],
                    ship["name"],
                    ship["model"],
                    ship.get("created"),
                    ship.get("edited"),
                ),
            )
            sql.execute(
                "DELETE FROM starship_pilots WHERE starship_url=?", (ship["url"],)
            )
            sql.executemany(
                "INSERT INTO starship_pilots VALUES (?, ?)",
                [(ship["url"], str(p)) for p in ship["pilots"]],
            )
            sql.execute(
                "DELETE FROM starship_films WHERE starship_url=?", (ship["url"],)
            )
            for film in ship.get("films", []):
                sql.execute("INSERT OR IGNORE INTO films VALUES (?)", (film,))
                sql.execute(
                    "INSERT INTO starship_films VALUES (?, ?)", (ship["url"], film)
                )
        violations = sql.execute("PRAGMA foreign_key_check").fetchall()
        if violations:
            raise ValueError(violations)
        tables = [
            "characters",
            "models",
            "manufacturers",
            "model_manufacturers",
            "starships",
            "starship_pilots",
            "films",
            "starship_films",
        ]
        counts = {
            t: sql.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables
        }
        pilots = sql.execute("""SELECT s.name, c.name FROM starships s
            JOIN starship_pilots p USING (starship_url)
            JOIN characters c USING (character_id)
            WHERE s.name = 'Millennium Falcon' ORDER BY c.name""").fetchall()
        return {
            "counts": counts,
            "foreign_key_violations": violations,
            "falcon_pilots": pilots,
        }


if __name__ == "__main__":
    from pymongo import MongoClient

    with MongoClient(
        os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        serverSelectionTimeoutMS=5000,
    ) as client:
        result = export_sql(
            client.sparta_week06, ROOT / "outputs/starships-3nf.sqlite3"
        )
    (ROOT / "schema.sql").write_text(SCHEMA)
    (ROOT / "outputs/sql-results.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
