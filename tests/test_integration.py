"""Real-server proof for MongoDB $lookup, indexes and BSON references."""

import os
import uuid

import pytest
from pymongo import MongoClient

from starship_pipeline.demo import fixture
from starship_pipeline.pipeline import run_pipeline


@pytest.mark.integration
def test_real_mongo_lookup_and_repeat_run(tmp_path):
    uri = os.getenv("MONGODB_TEST_URI")
    if not uri:
        pytest.skip("Set MONGODB_TEST_URI to run real MongoDB integration checks")
    name = "portfolio_test_" + uuid.uuid4().hex
    with MongoClient(uri, serverSelectionTimeoutMS=5000) as client:
        client.admin.command("ping")
        try:
            db = client[name]
            first = run_pipeline(db, *fixture(), tmp_path, "integration-fixture", "real-mongodb")
            ids = {p["source_url"]: p["_id"] for p in db.people.find()}
            second = run_pipeline(db, *fixture(), tmp_path, "integration-fixture", "real-mongodb")
            assert first["counts"] == second["counts"]
            assert ids == {p["source_url"]: p["_id"] for p in db.people.find()}
            assert second["quality"]["mongo_lookup_verified"]
            assert db.starships.index_information()["source_url_1"]["unique"]
        finally:
            # Only the UUID-named disposable test database created above is removed.
            client.drop_database(name)
