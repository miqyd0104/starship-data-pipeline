"""Extract SWAPI starships, resolve pilots, and load MongoDB references."""

import argparse
import copy
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import requests
from pymongo import MongoClient
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parent
API = "https://swapi.dev/api/"


class SwapiClient:
    """Reusable HTTP client with bounded retries, timeouts and verified TLS."""

    def __init__(self):
        self.session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        if Path("/etc/ssl/cert.pem").exists():
            self.session.verify = "/etc/ssl/cert.pem"

    def get(self, url):
        # Resolve only links on the expected API; never follow arbitrary pilot URLs.
        parsed = urlparse(url)
        if parsed.hostname != "swapi.dev" or not parsed.path.startswith("/api/"):
            raise ValueError(f"Unexpected API URL: {url}")
        url = parsed._replace(scheme="https").geturl()
        response = self.session.get(url, timeout=(5, 30))
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise TypeError("Expected a JSON object")
        return payload


def get_starships(api):
    """Follow every page and reject duplicate or incomplete downloads."""
    url, seen, ships, expected = API + "starships/", set(), [], None
    while url:
        if url in seen:
            raise ValueError("Pagination cycle detected")
        seen.add(url)
        page = api.get(url)
        if expected is None:
            expected = page["count"]
        ships.extend(page["results"])
        url = page["next"]
    if len(ships) != expected or len({s["url"] for s in ships}) != expected:
        raise ValueError("Incomplete or duplicate starship results")
    return ships


def get_pilot_ids(pilot_urls, characters, api, cache=None):
    """Map API people to exactly one existing character, retaining ObjectIds.

    Class characters have no API URL, so the API person's exact name is the
    bridge. Missing/ambiguous matches fail rather than silently losing a pilot.
    """
    cache = cache if cache is not None else {}
    ids = []
    for url in pilot_urls:
        if url not in cache:
            name = api.get(url)["name"]
            matches = list(characters.find({"name": name}, {"_id": 1}))
            if len(matches) != 1:
                raise ValueError(f"Expected one character for {name}: {len(matches)}")
            cache[url] = matches[0]["_id"]
        ids.append(cache[url])
    if len(set(ids)) != len(ids):
        raise ValueError("Duplicate pilot references")
    return ids


def replace_pilots_and_insert(ships, db, api):
    """Validate all relationships before writes, then upsert by stable API URL."""
    cache, documents = {}, []
    for ship in ships:
        document = copy.deepcopy(ship)
        document["pilots"] = get_pilot_ids(ship["pilots"], db.characters, api, cache)
        documents.append(document)
    db.starships.create_index("url", unique=True)
    for document in documents:
        db.starships.replace_one({"url": document["url"]}, document, upsert=True)
    return len(documents)


def pilot_lookup(db):
    """An array localField matches multiple character IDs without unwind."""
    return list(
        db.starships.aggregate(
            [
                {
                    "$lookup": {
                        "from": "characters",
                        "localField": "pilots",
                        "foreignField": "_id",
                        "as": "pilot_details",
                    }
                },
                {
                    "$project": {
                        "_id": 0,
                        "name": 1,
                        "url": 1,
                        "pilots": 1,
                        "pilot_names": "$pilot_details.name",
                    }
                },
                {"$sort": {"name": 1}},
            ]
        )
    )


class SnapshotClient:
    """Explicit offline mode using previously downloaded public API responses."""

    def __init__(self, people):
        self.people = people

    def get(self, url):
        return self.people[url]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument(
        "--seed-snapshot",
        action="store_true",
        help="Use included character projection instead of the class database",
    )
    args = parser.parse_args()
    if args.offline:
        ships = json.loads((ROOT / "data/starships.json").read_text())
        api = SnapshotClient(json.loads((ROOT / "data/pilots.json").read_text()))
    else:
        api = SwapiClient()
        ships = get_starships(api)
        people = {
            u: api.get(u) for u in sorted({u for s in ships for u in s["pilots"]})
        }
        (ROOT / "data/starships.json").write_text(json.dumps(ships, indent=2) + "\n")
        (ROOT / "data/pilots.json").write_text(json.dumps(people, indent=2) + "\n")
        api = SnapshotClient(people)
    if len(ships) != 36:
        raise ValueError(f"Assignment expects 36 starships; got {len(ships)}")
    with MongoClient(
        os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        serverSelectionTimeoutMS=5000,
    ) as client:
        client.admin.command("ping")
        # Use a dedicated project database; retain source character ObjectIds.
        db = client["sparta_week06"]
        if args.seed_snapshot:
            source = json.loads((ROOT / "data/characters.json").read_text())
            for character in source:
                db.characters.update_one(
                    {"name": character["name"]}, {"$set": character}, upsert=True
                )
        else:
            source = list(client.star_wars.characters.find())
            if len(source) != 87:
                raise ValueError(
                    "Expected 87 class characters; use --seed-snapshot for the included data"
                )
            for character in source:
                db.characters.replace_one(
                    {"_id": character["_id"]}, character, upsert=True
                )
        inserted = replace_pilots_and_insert(ships, db, api)
        rows = pilot_lookup(db)
        if len(rows) != 36 or any(
            len(r["pilots"]) != len(r["pilot_names"]) for r in rows
        ):
            raise ValueError("Lookup integrity failed")
        falcon = next(r for r in rows if r["name"] == "Millennium Falcon")
        if set(falcon["pilot_names"]) != {
            "Chewbacca",
            "Han Solo",
            "Lando Calrissian",
            "Nien Nunb",
        }:
            raise ValueError("Falcon pilot check failed")
        report = {
            "starships": inserted,
            "characters": len(source),
            "pilot_links": sum(len(r["pilots"]) for r in rows),
            "unresolved_links": 0,
            "ships_with_pilots": sum(bool(r["pilots"]) for r in rows),
            "lookup": [{k: v for k, v in r.items() if k != "pilots"} for r in rows],
        }
        (ROOT / "outputs/results.json").write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps({k: v for k, v in report.items() if k != "lookup"}, indent=2))
        print("Millennium Falcon:", ", ".join(sorted(falcon["pilot_names"])))


if __name__ == "__main__":
    main()
