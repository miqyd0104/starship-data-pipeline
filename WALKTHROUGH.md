# Explain and demonstrate this project

This guide follows the original project's three stages: import and referencing, documentation/testing/verification, then the optional SQL extension. Allow about five minutes. Read the quoted paragraphs; the instructions tell you what to show.

## Open these files

| File | Purpose during the demonstration |
|---|---|
| `starships.py` | The original three functions, HTTP client and pilot lookup |
| `README.md` | Setup, results, assumptions and documentation |
| `tests/test_starships.py` | The original 15 unit tests and mocking |
| `run_demo.py` | Run the original complete demonstration |
| `schema.sql` | Optional relational schema |
| `sql_extension.py` | SQLite connection, table loading and foreign key checks |
| `outputs/sql-results.json` | Recorded SQL counts and Falcon pilot join |

Keep MongoDB Compass connected to the same server as the scripts. Open `sparta_week06.characters`, `sparta_week06.starships` and the Mongosh tab. No notes repository is needed.

## 1. Introduce the project

**Show:** `starships.py`.

“This project collects all 36 Star Wars starships, connects their pilots to existing character documents in MongoDB, and verifies that those references point to the correct people.”

“It also includes error handling, documentation, 15 unit tests, 12 additional aggregation tasks and an optional relational SQL extension.”

## 2. Explain the three functions

**Show:** `get_starships` in `starships.py`. Use Find to search its name.

“The first function is get_starships. The API sends its data across several pages. This function follows each next-page link until there are no more pages, then checks the result count and unique ship URLs.”

“That helps catch missing pages, repeated pages and duplicate ships.”

**Show:** `get_pilot_ids`.

“The second function takes a ship's pilot URLs and retrieves each person's name. It finds that name in the characters collection and returns the matching ObjectId.”

“An ObjectId is MongoDB's unique identifier for a document. Storing the ID links to an existing character instead of copying that character's details onto every ship.”

“The supplied character collection has names but no API person URLs, so exact names are the bridge. The function requires exactly one match. Missing or ambiguous matches raise an error instead of guessing. A shared cache avoids resolving the same pilot URL repeatedly.”

**Show:** `replace_pilots_and_insert`.

“The third function copies the ship information, replaces pilot URLs with character IDs, and saves the ships. It checks all pilot matches before starting the ship writes.”

“Ships are identified by their unique source URL. An upsert means update an existing ship, otherwise insert it. A repeated import therefore updates the same ships instead of creating duplicates.”

“Ships with no pilots are still saved with an empty pilot list.”

## 3. Show error handling, comments and the README

**Show:** `SwapiClient` near the top of `starships.py`.

“The HTTP client uses connection and read timeouts, checks for failed HTTP responses, and retries selected temporary failures a limited number of times with backoff. HTTPS certificate verification stays enabled.”

“Data checks reject duplicate or incomplete downloads, missing pilots and ambiguous character matches.”

**Show:** a function docstring, then `README.md`.

“Comments and docstrings explain the implementation. The README includes installation, run instructions, results, data assumptions and links to verification evidence.”

## 4. Show the tests and run the demo

**Show:** `tests/test_starships.py`.

“The 15 unit tests use mongomock for a temporary database and mocked HTTP responses. They check pagination, failure cases, pilot references, multiple or empty pilot lists, caching, repeat runs and SQL relationships.”

“Mocks check the function behaviour without relying on a live API. Separate checks exercise the actual MongoDB operations.”

**Action:** open `run_demo.py` and click Run in PyCharm. Select this repository's `.venv/bin/python` interpreter. Alternatively run `python run_demo.py` in an activated terminal.

“This is the original demo runner. It uses the included API snapshots so the presentation does not depend on the website responding, but it still writes to and queries a real MongoDB server.”

“It imports the ships, runs all 12 aggregation tasks, independently verifies the results, creates the SQL export and runs the 15 tests. It stops if a step fails.”

**Wait for:** `ALL DEMO STEPS PASSED` and exit code 0.

“The result is 36 starships, 87 characters and 30 valid pilot links, with no unresolved links. Fifteen ships have listed pilots. All 15 unit tests passed, and exit code zero means the complete run finished successfully.”

“Thirty links is a count of connections, not necessarily thirty different people; one character can pilot more than one ship.”

## 5. Demonstrate the MongoDB relationships

**Show:** Compass → `sparta_week06` → `characters` and `starships`.

“These are the stored records. The original database name is preserved. Each ship's pilots array contains references to character IDs.”

**Action:** paste this into the Compass Mongosh tab and run it:

```javascript
db.getSiblingDB("sparta_week06").starships.aggregate([
  {$match: {name: "Millennium Falcon"}},
  {$lookup: {from: "characters", localField: "pilots", foreignField: "_id", as: "pilot_details"}},
  {$project: {_id: 0, name: 1, pilot_names: "$pilot_details.name"}}
]).toArray()
```

“The lookup matches the ship's pilot IDs to the characters collection's ID field and returns the matching people.”

“The Millennium Falcon correctly returns Chewbacca, Han Solo, Lando Calrissian and Nien Nunb. Because pilots is an array, the lookup can match several characters without an unwind stage.”

**Fallback:** show `outputs/mongosh-referencing.txt`. Say “This is the saved output from the MongoDB lookup” rather than calling the file a live query.

## 6. Briefly show the extra analysis

**Show:** `aggregations.py` or `outputs/aggregations.json`.

“The 12 additional pipelines cover grouping, averages, ranking, height buckets, composite keys and comparisons against the global average.”

“Measurements arrive as strings, so the pipelines remove commas and convert usable values to numbers. Unknown measurements become null, not zero.”

“The independent verifier calculates expected answers with ordinary Python and compares them with MongoDB's results.”

You do not need to explain all 12 pipelines individually. Choose homeworld counts as a simple grouping example, or height buckets to explain range boundaries.

## 7. Show the optional SQL extension

**Show:** `schema.sql`.

“The SQL extension uses SQLite, a relational database that runs locally without a separate database server.”

“There are eight tables. Ship, model, manufacturer and character facts are separated, and linking tables represent pilots, model manufacturers and film appearances.”

“A ship can have several pilots and a person can pilot several ships, so a junction table represents that many-to-many relationship.”

“The design assumes one model name identifies one specification; conflicting definitions are rejected. Manufacturer commas are treated as organisation separators, which is an explicit assumption for this dataset.”

**Show:** `sqlite3.connect` and `PRAGMA foreign_key_check` in `sql_extension.py`.

“The loader opens the SQL connection, creates the tables, inserts or updates the records and checks that foreign keys point to valid records.”

**Show:** `outputs/sql-results.json`.

“The export has 36 ships, 87 character identities and 30 pilot links. There are zero foreign key violations, and the SQL join returns the same four Falcon pilots.”

## 8. Finish

“The project demonstrates API extraction, transforming links into MongoDB references, repeatable imports, aggregation, testing and relational data modelling. The code and evidence are all available in this standalone repository.”

## Questions to prepare for

**Why match names?** The original supplied character collection has no SWAPI person URLs. The code requires one exact match and fails on ambiguity. Retaining external person IDs would be an improvement for another design.

**Does a rerun add more ships?** No. Ship URLs are unique and the importer upserts. Unexpected extra ships cause verification to fail instead of being silently deleted.

**What if a database write fails?** Pilot matching is checked before ship writes, but standalone MongoDB writes are not an atomic batch. An interrupted load may be partial; rerunning completes the upserts. No cross-database transaction is claimed.

**Does the demo call the live API?** `run_demo.py` uses saved responses and real MongoDB. `python starships.py --seed-snapshot` fetches fresh starship and pilot responses while keeping the supplied 87-character snapshot.

**Why SQLite instead of SQLAlchemy?** SQLite is the database. SQLAlchemy is an optional library. This original implementation uses Python's built-in `sqlite3` connection.

**What does the SQL model cover?** Starship fields and relationships, plus character and film identities. It is not a complete relational remodel of every character attribute.
