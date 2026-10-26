# Working on this project

This repository preserves the original script-based Star Wars project. Keep changes small, document their purpose, and avoid changing the demonstration into a different application.

Create a virtual environment and install `requirements.txt`. Run:

```sh
python -m unittest discover -s tests -v
ruff check starships.py aggregations.py verify.py sql_extension.py run_demo.py tests/
ruff format --check starships.py aggregations.py verify.py sql_extension.py run_demo.py tests/
# Requires a running MongoDB server:
python run_demo.py
```

The demo writes to `sparta_week06` and creates a local SQLite file under `outputs/`. Use a separate MongoDB server when testing a different dataset. Do not commit environments, credentials or SQLite binaries. If you intentionally change executable code, update the original-code correspondence document so it does not claim unchanged bytes.
