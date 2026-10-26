"""Independent live-database checks against Python-calculated source answers."""

import json
import os
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from bson import ObjectId
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parent


def number(value):
    try:
        return float(str(value).replace(",", ""))
    except ValueError:
        return None


def close(actual, expected):
    assert abs(actual - expected) < 1e-8, (actual, expected)


def main():
    report = json.loads((ROOT / "outputs/aggregations.json").read_text())
    raw = json.loads((ROOT / "data/starships.json").read_text())
    people = json.loads((ROOT / "data/pilots.json").read_text())
    with MongoClient(
        os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        serverSelectionTimeoutMS=5000,
    ) as client:
        db = client.sparta_week06
        characters = list(db.characters.find())
        by_id = {c["_id"]: c for c in characters}
        stored = {s["url"]: s for s in db.starships.find()}
        assert len(stored) == len(raw) == 36
        links = 0
        for ship in raw:
            ids = stored[ship["url"]]["pilots"]
            assert all(isinstance(p, ObjectId) for p in ids)
            assert len(ids) == len(ship["pilots"]) == len(set(ids))
            assert {by_id[p]["name"] for p in ids} == {
                people[u]["name"] for u in ship["pilots"]
            }
            links += len(ids)
        for c in characters:
            c["h"], c["m"] = number(c["height"]), number(c["mass"])
        home = Counter(c["homeworld"]["name"] for c in characters)
        expected_home = [
            {"_id": k, "count": v}
            for k, v in sorted(home.items(), key=lambda x: (-x[1], x[0]))
        ]
        assert report["homeworld_counts"] == expected_home
        assert report["top_five_homeworlds"] == expected_home[:5]
        species, eyes, gender, births, breakdown = (
            defaultdict(list),
            defaultdict(list),
            defaultdict(list),
            Counter(),
            Counter(),
        )
        for c in characters:
            s = c["species"]["name"] if isinstance(c.get("species"), dict) else None
            if s is not None:
                species[s].append(c)
            if c["h"] is not None:
                eyes[c["eye_color"]].append(c["h"])
            if (
                c["gender"] not in (None, "unknown")
                and c["h"] is not None
                and c["m"] is not None
            ):
                gender[c["gender"]].append(c)
            if c["birth_year"] not in (None, "unknown"):
                births[c["birth_year"]] += 1
            breakdown[(s, c["gender"])] += 1
        for row in report["tallest_per_species"]:
            heights = [
                c["h"] for c in species[row["species"]["name"]] if c["h"] is not None
            ]
            assert row["height"] == (max(heights) if heights else None)
        for row in report["average_height_by_eye_color"]:
            close(row["avg_height"], statistics.mean(eyes[row["_id"]]))
        assert {r["_id"]: r["count"] for r in report["birth_year_counts"]} == {
            k: v for k, v in births.items() if v >= 2
        }
        for row in report["average_measures_by_gender"]:
            group = gender[row["_id"]]
            assert row["count"] == len(group)
            close(row["avg_height"], statistics.mean(c["h"] for c in group))
            close(row["avg_mass"], statistics.mean(c["m"] for c in group))
        bins = Counter(
            next(
                b
                for b, upper in [(0, 150), (150, 170), (170, 190), (190, 10000)]
                if c["h"] < upper
            )
            for c in characters
            if c["h"] is not None
        )
        assert {r["_id"]: r["count"] for r in report["height_buckets"]} == dict(bins)
        assert {
            (r["_id"].get("species"), r["_id"]["gender"]): r["count"]
            for r in report["gender_per_species"]
        } == dict(breakdown)
        summary = report["single_summary"][0]
        assert summary["total"] == 87 and summary["species_count"] == len(species)
        assert summary["homeworld_count"] == len(home)
        global_avg = statistics.mean(c["h"] for c in characters if c["h"] is not None)
        close(summary["avg_height"], global_avg)
        close(
            summary["avg_mass"],
            statistics.mean(c["m"] for c in characters if c["m"] is not None),
        )
        above = {
            s
            for s, group in species.items()
            if (hs := [c["h"] for c in group if c["h"] is not None])
            and statistics.mean(hs) > global_avg
        }
        assert {r["species"] for r in report["species_above_global_average"]} == above
        for row in report["top_three_heaviest_per_species"]:
            group = sorted(
                (c for c in species[row["_id"]] if c["m"] is not None),
                key=lambda c: (-c["m"], c["name"]),
            )[:3]
            assert row["characters"] == [
                {"name": c["name"], "mass": c["m"]} for c in group
            ]
        for row in report["species_statistics"]:
            group = species[row["_id"]]
            hs = [c["h"] for c in group if c["h"] is not None]
            ms = [c["m"] for c in group if c["m"] is not None]
            assert row["count"] == len(group)
            if hs:
                close(row["avg_height"], statistics.mean(hs))
                assert row["tallest_height"] == max(hs) and row[
                    "smallest_height"
                ] == min(hs)
                for key, extreme in [("tallest", max(hs)), ("smallest", min(hs))]:
                    assert {c["name"] for c in row[key]} == {
                        c["name"] for c in group if c["h"] == extreme
                    }
            if ms:
                close(row["avg_mass"], statistics.mean(ms))
        print(
            f"PASS: all 36 ships and {links} pilot links match the source API by name."
        )
        print("PASS: all 12 aggregation tasks independently checked with Python.")
        print("PASS: live MongoDB IDs are ObjectIds; no unresolved pilot links.")


if __name__ == "__main__":
    main()
