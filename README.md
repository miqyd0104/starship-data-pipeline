<p align="center"><img src="docs/assets/banner.svg" alt="Star Wars Starship ETL — Python, MongoDB and SQL" /></p>

<p align="center"><a href="https://github.com/miqyd0104/starship-data-pipeline/actions/workflows/ci.yml"><img src="https://github.com/miqyd0104/starship-data-pipeline/actions/workflows/ci.yml/badge.svg" alt="Original tests and full demo" /></a> <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&amp;logoColor=white" alt="Python 3.10 or newer" /> <img src="https://img.shields.io/badge/MongoDB-ObjectId%20referencing-47A248" alt="MongoDB ObjectId referencing" /></p>

# Star Wars Starship ETL

### Python API integration · MongoDB referencing · advanced aggregation · relational SQL

A practical data engineering project that collects **36 Star Wars starships**, replaces their pilot URLs with references to existing MongoDB character documents, and proves those references point to the right people. It includes error handling, **15 unit tests**, **12 aggregation tasks**, an independent verification script and an optional SQLite export.

**By [Syed Miqdad Hamdani](https://github.com/miqyd0104).** This repository contains the original Star Wars project on its own, so the code and evidence can be reviewed without browsing a training-notes repository. The original executable files and dependencies are preserved; the README, presentation guide, setup and CI are tailored for this standalone repository. [Code checksums](docs/original-code-checksums.json) record that correspondence.

[Run the project](#quick-start) · [Read the code](starships.py) · [Presentation script](WALKTHROUGH.md) · [Architecture](docs/architecture.md) · [Verified results](outputs/results.json)

## What it demonstrates

- **API integration:** follow every SWAPI page, check counts and reject duplicate results.
- **MongoDB data modelling:** resolve pilot names against the supplied character collection and store actual BSON ObjectIds.
- **Reliable imports:** validate references before ship writes, use a unique source URL index and upsert ships on reruns.
- **Data analysis:** clean numeric strings and answer 12 additional aggregation questions.
- **Testing:** exercise successful and failing cases with mongomock and mocked HTTP, then verify against real MongoDB.
- **Relational modelling:** export starships, model specifications, manufacturers, characters and film relationships into SQLite tables with foreign keys.

This is a learning and portfolio project with executable evidence. It does not claim production deployment, high availability or a transaction spanning MongoDB and SQL.

## Verified results

| Check | Result |
|---|---:|
| Imported starships | **36** |
| Characters in the supplied snapshot | **87** |
| Pilot links | **30** |
| Ships with listed pilots | **15** |
| Unresolved pilot links | **0** |
| Extra / advanced aggregation tasks | **12** |
| Unit tests | **15 passing** |
| SQLite foreign key violations | **0** |

The Millennium Falcon links to **Chewbacca, Han Solo, Lando Calrissian and Nien Nunb**. A character may pilot several ships, so 30 links does not mean 30 unique people. Ships with no listed pilots are retained.

These are the original project's results. Its 87-character snapshot is a different dataset from SWAPI's current people endpoint. The importer resolves pilot URLs to names and matches those names to this snapshot; it does not replace it with a new people download.

Evidence: [pilot lookup results](outputs/results.json) · [independent verification](outputs/verification.txt) · [unit tests](outputs/unit-tests.txt) · [aggregation answers](outputs/aggregations.json) · [SQL results](outputs/sql-results.json).

## Quick start

Requires **Python 3.10+** and a running **MongoDB server**. The local verification used Python 3.14. CI checks Python 3.11–3.13 and runs the original demo against real MongoDB.

```sh
git clone https://github.com/miqyd0104/starship-data-pipeline.git
cd starship-data-pipeline
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run_demo.py
```

`run_demo.py` runs the **same original demonstration**: seed the included character snapshot, import the saved starship data, execute all aggregations, independently verify the results, export SQL and run all 15 tests. It uses saved API responses, so it needs **no live API connection**, but it **does need a real MongoDB server**. The final output should include:

```text
Ran 15 tests ...
OK
ALL DEMO STEPS PASSED. MongoDB: sparta_week06; 36 ships, 30 valid pilot links.
```

### Need a local MongoDB server?

If you do not already have one, the optional Docker Compose setup uses MongoDB 7.0 on **localhost:27018**, avoiding an existing server on port 27017:

```sh
docker compose up -d --wait
# macOS / Linux
export MONGODB_URI='mongodb://localhost:27018'
# Windows PowerShell: $env:MONGODB_URI = 'mongodb://localhost:27018'
python run_demo.py
```

With no environment variable, the original scripts use `mongodb://localhost:27017`. They write to **`sparta_week06`**; the name is preserved from the original project. Credentials belong in the environment, never in source files. `.env.example` is a template, not an automatically loaded configuration file.

## The original three functions

All three are in [starships.py](starships.py):

| Function | Responsibility |
|---|---|
| `get_starships(api)` | Follow `next` links, collect the ships and reject cycles, duplicates or incomplete totals |
| `get_pilot_ids(pilot_urls, characters, api)` | Retrieve each pilot's name, require exactly one matching character and return its ObjectId; cache repeated URLs |
| `replace_pilots_and_insert(ships, db, api)` | Copy the ship data, replace pilot URLs with IDs, validate the whole relationship batch and upsert by unique source URL |

`SwapiClient` handles verified HTTPS requests, connection/read timeouts and bounded GET retries with backoff. `SnapshotClient` exposes the same interface for the included saved responses. Comments and docstrings explain the implementation.

The character collection does not contain person API URLs, so **exact names are the bridge**. Missing or ambiguous matches fail explicitly. This is a declared limitation of the original design. A production system would usually retain stable external person identifiers.

## Run the steps individually

From the repository root:

```sh
python starships.py --offline --seed-snapshot
python aggregations.py
python verify.py
python sql_extension.py
python -m unittest discover -s tests -v
```

To download current SWAPI starships and pilot responses while using the supplied 87-character projection:

```sh
python starships.py --seed-snapshot
```

The original program expects 36 ships and fails clearly if the API's total changes. Live mode refreshes `data/starships.json` and `data/pilots.json`; offline mode is explicit, with no silent fallback. If a Python installation needs a system trust bundle, the original client uses `/etc/ssl/cert.pem` when available and keeps certificate verification enabled.

If you already have the original `star_wars.characters` collection, omit `--seed-snapshot` to use it. A fresh reviewer should use the supplied snapshot. Avoid switching character sources within a populated project database if their IDs differ. Use a clean MongoDB environment when comparing different source datasets.

## See the relationships in MongoDB Compass

Connect to the same MongoDB server as the scripts. Open `sparta_week06.characters` and `sparta_week06.starships`. A ship's `pilots` field contains an array of character ObjectIds.

In Compass's Mongosh tab, this query shows the four Falcon pilots:

```javascript
db.getSiblingDB("sparta_week06").starships.aggregate([
  {$match: {name: "Millennium Falcon"}},
  {$lookup: {from: "characters", localField: "pilots", foreignField: "_id", as: "pilot_details"}},
  {$project: {_id: 0, name: 1, pilot_names: "$pilot_details.name"}}
]).toArray()
```

`$lookup` matches the array of pilot IDs to character `_id` values. Several pilots return in the result array without requiring `$unwind`. [Saved shell evidence](outputs/mongosh-referencing.txt) is included.

## Twelve aggregation tasks

[aggregations.py](aggregations.py) defines and executes the pipelines. [aggregations.js](aggregations.js) contains the equivalent original Mongosh queries.

| Task | Output key |
|---|---|
| Character counts by homeworld, descending | `homeworld_counts` |
| Tallest height for each known species | `tallest_per_species` |
| Average known height by eye colour | `average_height_by_eye_color` |
| Birth years shared by at least two characters | `birth_year_counts` |
| Average height and mass by gender | `average_measures_by_gender` |
| Top five homeworlds by character count | `top_five_homeworlds` |
| Height ranges using `$bucket` | `height_buckets` |
| Species / gender breakdown | `gender_per_species` |
| A single summary document | `single_summary` |
| Species above the global average height | `species_above_global_average` |
| Three heaviest characters per species | `top_three_heaviest_per_species` |
| Species counts, averages and tallest/smallest characters | `species_statistics` |

Unknown measures become null rather than zero. Commas are removed before numeric conversion. Five empty species lists are normalised to unknown within the pipeline. Height buckets are lower-inclusive and upper-exclusive: `[0,150)`, `[150,170)`, `[170,190)` and `[190,10000)`. Unknown heights are excluded.

Gender averages use records with both known height and mass; null/`unknown` gender is excluded, while the source category `n/a` is retained. Other averages independently ignore unknown measures. Species extrema include ties. The named `unknown` homeworld remains a source category. The birth-year threshold is explicitly `count >= 2`. “Most populous homeworld” refers to character counts in the sample.

Run the shell versions after the import, using your server's URI:

```sh
mongosh mongodb://localhost:27017 --quiet --file aggregations.js
mongosh mongodb://localhost:27017 --quiet --file referencing.js
```

The referencing script reuses the existing Falcon rather than adding an accidental 37th ship.

## Optional relational SQL extension

[sql_extension.py](sql_extension.py) connects to SQLite, creates the [schema](schema.sql), loads the records and checks foreign keys. It produces the local file `outputs/starships-3nf.sqlite3`, which is intentionally excluded from Git.

The original schema uses **eight tables**: `characters`, `models`, `manufacturers`, `model_manufacturers`, `starships`, `starship_pilots`, `films` and `starship_films`. Junction tables represent many-to-many relationships. Character and film entities are identity projections; the export does not remodel every character attribute.

Model specifications are separated from ship rows. The design assumes a model identifies one specification and rejects conflicting definitions. It treats commas in the manufacturer field as organisation separators; that assumption needs review with other datasets. Unknown measures and crew ranges stay as source text rather than invented numbers. [SQL evidence](outputs/sql-results.json) records 36 ships, 30 pilot links and zero foreign key violations.

## Testing and verification

- **Original 15 unit tests:** pagination, incomplete/duplicate downloads, cycles, pilot matches, missing/ambiguous names, ObjectIds, empty/multiple pilot arrays, caching, repeat runs, HTTP errors, retry settings and SQL relationships.
- **Real MongoDB:** `run_demo.py` executes `$lookup` and all 12 aggregations on a real server. GitHub Actions repeats the complete demo to check reruns.
- **Independent verification:** `verify.py` recalculates aggregation answers in Python and compares each ship's pilot names to the saved person responses.
- **Source preservation:** [checksums](docs/original-code-checksums.json) confirm that the original Python, JavaScript, SQL and requirements files were copied unchanged.

The project contains **15 original unit tests**, with full real-database verification performed by the demo runner.

## Files to open when presenting

Start with **`starships.py` → `README.md` → `tests/test_starships.py` → `run_demo.py` → Compass → `schema.sql` → `sql_extension.py` → `outputs/sql-results.json`**.

The [read-aloud walkthrough](WALKTHROUGH.md) pairs each screen with a short explanation. [Architecture and design limits](docs/architecture.md) give the deeper technical context.

## Data and license

The included files are the original project's public Star Wars data snapshots and a minimal 87-character projection. They exclude original MongoDB IDs, private training notes, trainer messages and unrelated film text. [Provenance and source hashes](data/provenance.json) are retained.

Technical references: [SWAPI documentation](https://swapi.dev/documentation) and [MongoDB `$lookup`](https://www.mongodb.com/docs/manual/reference/operator/aggregation/lookup/). Code: [MIT](LICENSE). This code license does not relicense upstream data, Star Wars names or trademarks.
