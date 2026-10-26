"""All nine extra and three advanced aggregation tasks, run on real MongoDB."""

import json
import os
from pathlib import Path

from pymongo import MongoClient

ROOT = Path(__file__).resolve().parent

# Keep unknown measures null; comma-separated mass values must become numbers.
CLEAN = {
    "$set": {
        key: {
            "$convert": {
                "input": {
                    "$replaceAll": {
                        "input": {"$toString": "$" + field},
                        "find": ",",
                        "replacement": "",
                    }
                },
                "to": "double",
                "onError": None,
                "onNull": None,
            }
        }
        for key, field in [("h", "height"), ("m", "mass")]
    }
}
# Five class records represent unknown species as [] rather than an object.
CLEAN["$set"]["species"] = {
    "$cond": [{"$eq": [{"$type": "$species"}, "object"]}, "$species", {"name": None}]
}
SPECIES = {"$match": {"species.name": {"$ne": None}}}
PIPELINES = {
    "homeworld_counts": [
        {"$group": {"_id": "$homeworld.name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1, "_id": 1}},
    ],
    "tallest_per_species": [
        SPECIES,
        {"$group": {"_id": "$species.name", "height": {"$max": "$h"}}},
        {"$project": {"_id": 0, "species.name": "$_id", "height": 1}},
        {"$sort": {"species.name": 1}},
    ],
    "average_height_by_eye_color": [
        {"$match": {"h": {"$ne": None}}},
        {"$group": {"_id": "$eye_color", "avg_height": {"$avg": "$h"}}},
        {"$sort": {"avg_height": -1, "_id": 1}},
    ],
    "birth_year_counts": [
        {"$match": {"birth_year": {"$nin": [None, "unknown"]}}},
        {"$group": {"_id": "$birth_year", "count": {"$sum": 1}}},
        # The brief does not give a threshold; show years shared by >=2 people.
        {"$match": {"count": {"$gte": 2}}},
        {"$sort": {"count": -1, "_id": 1}},
    ],
    "average_measures_by_gender": [
        {
            "$match": {
                "gender": {"$nin": [None, "unknown"]},
                "h": {"$ne": None},
                "m": {"$ne": None},
            }
        },
        {
            "$group": {
                "_id": "$gender",
                "avg_height": {"$avg": "$h"},
                "avg_mass": {"$avg": "$m"},
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
    ],
    "top_five_homeworlds": [
        {"$group": {"_id": "$homeworld.name", "count": {"$sum": 1}}},
        {"$sort": {"count": -1, "_id": 1}},
        {"$limit": 5},
    ],
    "height_buckets": [
        {"$match": {"h": {"$ne": None}}},
        {
            "$bucket": {
                "groupBy": "$h",
                "boundaries": [0, 150, 170, 190, 10000],
                "default": "outside_range",
                "output": {"count": {"$sum": 1}},
            }
        },
    ],
    "gender_per_species": [
        {
            "$group": {
                "_id": {"species": "$species.name", "gender": "$gender"},
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"_id.species": 1, "_id.gender": 1}},
    ],
    "single_summary": [
        {
            "$group": {
                "_id": None,
                "total": {"$sum": 1},
                "avg_height": {"$avg": "$h"},
                "avg_mass": {"$avg": "$m"},
                "species": {"$addToSet": "$species.name"},
                "homeworlds": {"$addToSet": "$homeworld.name"},
            }
        },
        {
            "$project": {
                "_id": 0,
                "total": 1,
                "avg_height": 1,
                "avg_mass": 1,
                "species_count": {"$size": {"$setDifference": ["$species", [None]]}},
                "homeworld_count": {
                    "$size": {"$setDifference": ["$homeworlds", [None]]}
                },
            }
        },
    ],
    "species_above_global_average": [
        {
            "$facet": {
                "global": [{"$group": {"_id": None, "avg": {"$avg": "$h"}}}],
                "species": [
                    SPECIES,
                    {"$group": {"_id": "$species.name", "avg": {"$avg": "$h"}}},
                ],
            }
        },
        {"$unwind": "$global"},
        {"$unwind": "$species"},
        {"$match": {"$expr": {"$gt": ["$species.avg", "$global.avg"]}}},
        {
            "$project": {
                "_id": 0,
                "species": "$species._id",
                "avg_height": "$species.avg",
                "global_avg": "$global.avg",
            }
        },
        {"$sort": {"avg_height": -1, "species": 1}},
    ],
    "top_three_heaviest_per_species": [
        SPECIES,
        {"$match": {"m": {"$ne": None}}},
        {"$sort": {"m": -1, "name": 1}},
        {
            "$group": {
                "_id": "$species.name",
                "characters": {"$push": {"name": "$name", "mass": "$m"}},
            }
        },
        {"$project": {"characters": {"$slice": ["$characters", 3]}}},
        {"$sort": {"_id": 1}},
    ],
    "species_statistics": [
        SPECIES,
        {
            "$group": {
                "_id": "$species.name",
                "count": {"$sum": 1},
                "avg_height": {"$avg": "$h"},
                "avg_mass": {"$avg": "$m"},
                "tallest_height": {"$max": "$h"},
                "smallest_height": {"$min": "$h"},
                "characters": {"$push": {"name": "$name", "height": "$h"}},
            }
        },
        {
            "$set": {
                "tallest": {
                    "$filter": {
                        "input": "$characters",
                        "as": "c",
                        "cond": {
                            "$and": [
                                {"$ne": ["$$c.height", None]},
                                {"$eq": ["$$c.height", "$tallest_height"]},
                            ]
                        },
                    }
                },
                "smallest": {
                    "$filter": {
                        "input": "$characters",
                        "as": "c",
                        "cond": {
                            "$and": [
                                {"$ne": ["$$c.height", None]},
                                {"$eq": ["$$c.height", "$smallest_height"]},
                            ]
                        },
                    }
                },
            }
        },
        {"$unset": "characters"},
        {"$sort": {"count": -1, "_id": 1}},
    ],
}


def main():
    with MongoClient(
        os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        serverSelectionTimeoutMS=5000,
    ) as client:
        db = client.sparta_week06
        results = {
            name: list(db.characters.aggregate([CLEAN] + stages))
            for name, stages in PIPELINES.items()
        }
        (ROOT / "outputs/aggregations.json").write_text(
            json.dumps(results, indent=2) + "\n"
        )
        # Export equivalent mongosh queries for the original task's tool.
        shell = [
            "// Run: mongosh mongodb://localhost:27017 --file aggregations.js",
            'const lab = db.getSiblingDB("sparta_week06");',
        ]
        for name, stages in PIPELINES.items():
            shell += [
                f'print("{name}");',
                "printjson(lab.characters.aggregate("
                + json.dumps([CLEAN] + stages)
                + ").toArray());",
            ]
        (ROOT / "aggregations.js").write_text("\n".join(shell) + "\n")
        print(
            f"Executed {len(results)} aggregation pipelines on {db.characters.count_documents({})} characters"
        )
        print(json.dumps(results["single_summary"], indent=2))


if __name__ == "__main__":
    main()
