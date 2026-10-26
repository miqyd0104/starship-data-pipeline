# Contributing

Use Python 3.11 or newer. Create a virtual environment and install `pip install -e '.[dev]'`.
Before opening a pull request, run:

```sh
ruff check .
ruff format --check .
pytest -m 'not integration' --cov=starship_pipeline --cov-fail-under=90
starship-pipeline demo
```

Real-server changes also need `MONGODB_TEST_URI=mongodb://localhost:27017 pytest -m integration`.
The integration test creates and removes only its own UUID-named test database.
Keep unit tests deterministic: use the original synthetic fixtures and mock HTTP, rather than calling SWAPI.
Document changes to the report contract and avoid committing generated databases, credentials, runtime snapshots or personal screen recordings.
