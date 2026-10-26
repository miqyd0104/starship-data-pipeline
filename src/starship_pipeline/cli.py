"""One command for a reviewer demo; another for live or cached ingestion."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
from pathlib import Path

import requests
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from .demo import fixture
from .pipeline import run_pipeline
from .source import DataQualityError, SwapiClient

LOG = logging.getLogger("starship_pipeline")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="API → MongoDB → SQLite with verified pilot links."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser(
        "demo", help="Run synthetic data with an in-memory MongoDB substitute"
    )
    demo.add_argument("--output", type=Path, default=Path("artifacts/demo"))
    live = commands.add_parser(
        "run", help="Use real MongoDB and live SWAPI or an explicit snapshot"
    )
    live.add_argument("--snapshot", type=Path, help="Previously saved source-snapshot.json")
    live.add_argument("--output", type=Path, default=Path("artifacts/live"))
    live.add_argument("--database", default=os.getenv("MONGODB_DATABASE", "starship_portfolio"))
    live.add_argument("--ca-bundle", default=os.getenv("REQUESTS_CA_BUNDLE"))
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    client, api = None, None
    try:
        if args.command == "demo":
            try:
                import mongomock
            except ImportError:
                LOG.error("Install demo dependencies: pip install '.[demo]'")
                return 1
            client = mongomock.MongoClient()
            db = client.portfolio_demo
            people, ships = fixture()
            source, backend = "synthetic-fixture", "mongomock (not a real MongoDB server)"
        else:
            if not args.database or any(c in args.database for c in '/\\. "$*<>:|?'):
                raise DataQualityError("Invalid database name")
            if args.snapshot:
                payload = json.loads(args.snapshot.read_text(encoding="utf-8"))
                people, ships = payload["people"], payload["starships"]
                source = "explicit-local-snapshot"
            else:
                api = SwapiClient(ca_bundle=args.ca_bundle)
                LOG.info("Fetching paginated people and starships from SWAPI")
                people, ships = api.fetch_all("people"), api.fetch_all("starships")
                source = "live-swapi"
            # Credentials are read from the environment and never printed.
            client = MongoClient(
                os.getenv("MONGODB_URI", "mongodb://localhost:27017"), serverSelectionTimeoutMS=5000
            )
            client.admin.command("ping")
            db = client[args.database]
            backend = "real-mongodb"
        report = run_pipeline(db, people, ships, args.output, source, backend)
        print(
            json.dumps(
                {
                    "source": source,
                    "mongo_backend": backend,
                    "counts": report["counts"],
                    "quality": report["quality"],
                    "report": str(args.output / "report.json"),
                },
                indent=2,
            )
        )
        LOG.info("Pipeline completed; MongoDB references and SQL identity parity verified")
        return 0
    except (
        DataQualityError,
        PyMongoError,
        sqlite3.Error,
        requests.RequestException,
        OSError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        # Deliberately omit raw connection errors: they may include a credential URI.
        LOG.error(
            "Pipeline failed (%s). Check source data, TLS and database connectivity.",
            type(exc).__name__,
        )
        return 1
    finally:
        if api is not None:
            api.close()
        if client is not None:
            client.close()


if __name__ == "__main__":
    sys.exit(main())
