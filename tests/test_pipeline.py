"""Contract tests use original synthetic data, never the public network."""

import copy
import json
import sqlite3
from contextlib import closing
from unittest.mock import Mock

import mongomock
import pytest
import requests
from bson import ObjectId

from starship_pipeline.cli import main
from starship_pipeline.demo import fixture
from starship_pipeline.pipeline import run_pipeline
from starship_pipeline.source import DataQualityError, SwapiClient, canonical_url
from starship_pipeline.storage import export_sql, load_mongo, verify_mongo
from starship_pipeline.transform import number, prepare


@pytest.fixture
def prepared():
    return prepare(*fixture())


@pytest.fixture
def db():
    return mongomock.MongoClient().test


@pytest.mark.parametrize(
    "value,expected",
    [("1,200", 1200), ("34.5", 34.5), ("0", 0), ("unknown", None), ("n/a", None), (None, None)],
)
def test_number(value, expected):
    assert number(value) == expected


@pytest.mark.parametrize("value", ["nan", "inf", "-1", "many", True])
def test_invalid_numbers(value):
    with pytest.raises(DataQualityError):
        number(value)


def test_canonical_identity():
    assert (
        canonical_url("http://swapi.dev/api/people/1", "people")
        == "https://swapi.dev/api/people/1/"
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.test/api/people/1/",
        "file:///api/people/1/",
        "https://user:secret@swapi.dev/api/people/1/",
        "https://swapi.dev/api/people/1/?x=1",
        "https://swapi.dev/api/people/1/#x",
        "https://swapi.dev/api/people/not-an-id/",
    ],
)
def test_reject_unexpected_identity(url):
    with pytest.raises(DataQualityError):
        canonical_url(url, "people")


def test_prepare_does_not_mutate_source():
    raw = fixture()
    before = copy.deepcopy(raw)
    prepare(*raw)
    assert raw == before


def test_names_are_not_identity():
    people, ships = fixture()
    people[1]["name"] = people[0]["name"]
    clean_people, clean_ships = prepare(people, ships)
    assert len(clean_people) == 3
    assert len(clean_ships[0]["pilot_urls"]) == 2


@pytest.mark.parametrize(
    "change",
    [
        "missing_pilot",
        "duplicate_pilot",
        "duplicate_person",
        "duplicate_ship",
        "empty_name",
        "bad_pilots",
    ],
)
def test_bad_batch_rejected(change):
    people, ships = fixture()
    if change == "missing_pilot":
        ships[0]["pilots"].append("https://swapi.dev/api/people/99999/")
    elif change == "duplicate_pilot":
        ships[0]["pilots"].append(ships[0]["pilots"][0])
    elif change == "duplicate_person":
        people.append(people[0])
    elif change == "duplicate_ship":
        ships.append(ships[0])
    elif change == "empty_name":
        people[0]["name"] = " "
    else:
        ships[0]["pilots"] = "not a list"
    with pytest.raises(DataQualityError):
        prepare(people, ships)


def test_empty_batch_rejected():
    with pytest.raises(DataQualityError):
        prepare([], [])


def test_pagination():
    api = SwapiClient()
    api.get = Mock(
        side_effect=[
            {
                "count": 2,
                "next": "https://swapi.dev/api/people/?page=2",
                "results": [fixture()[0][0]],
            },
            {"count": 2, "next": None, "results": [fixture()[0][1]]},
        ]
    )
    assert len(api.fetch_all("people")) == 2
    assert api.get.call_count == 2


@pytest.mark.parametrize("case", ["cycle", "partial", "duplicate", "changed_count", "bad_count"])
def test_invalid_pagination(case):
    api = SwapiClient()
    person = fixture()[0][0]
    page = {"count": 2, "next": None, "results": [person]}
    if case == "cycle":
        page["next"] = "http://swapi.dev/api/people/"
    if case == "duplicate":
        page["results"] = [person, person]
    if case == "bad_count":
        page["count"] = True
    if case == "changed_count":
        page["next"] = "https://swapi.dev/api/people/?page=2"
        api.get = Mock(side_effect=[page, {"count": 3, "results": [], "next": None}])
    else:
        api.get = Mock(return_value=page)
    with pytest.raises(DataQualityError):
        api.fetch_all("people")


def test_http_contract():
    session = Mock()
    session.get.return_value.status_code = 200
    session.get.return_value.json.return_value = {"count": 0}
    api = SwapiClient(session=session)
    assert api.get("http://swapi.dev/api/people/") == {"count": 0}
    session.get.assert_called_once_with(
        "https://swapi.dev/api/people/", timeout=(5, 30), allow_redirects=False
    )
    session.get.return_value.raise_for_status.assert_called_once()
    api.close()
    session.close.assert_called_once()


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.test/api/people/",
        "https://swapi.dev/api/people/?page=bad",
        "https://swapi.dev/api/people/?page=2&host=evil",
    ],
)
def test_http_url_contract(url):
    api = SwapiClient()
    with pytest.raises(DataQualityError):
        api.get(url)


def test_redirect_rejected():
    session = Mock()
    session.get.return_value.status_code = 302
    with pytest.raises(DataQualityError):
        SwapiClient(session).get("https://swapi.dev/api/people/")


def test_http_error_propagates():
    session = Mock()
    session.get.return_value.status_code = 503
    session.get.return_value.raise_for_status.side_effect = requests.HTTPError()
    with pytest.raises(requests.HTTPError):
        SwapiClient(session).get("https://swapi.dev/api/people/")


def test_retry_settings():
    retry = SwapiClient().session.get_adapter("https://").max_retries
    assert retry.total == 3
    assert retry.allowed_methods == {"GET"}
    assert 429 in retry.status_forcelist


def test_idempotent_objectids_and_empty_pilots(db, prepared):
    people, ships = prepared
    load_mongo(db, people, ships)
    original = {p["source_url"]: p["_id"] for p in db.people.find()}
    load_mongo(db, people, ships)
    assert db.starships.count_documents({}) == 3
    assert original == {p["source_url"]: p["_id"] for p in db.people.find()}
    assert all(isinstance(i, ObjectId) for i in db.starships.find_one({"name": "Aurora"})["pilots"])
    assert db.starships.find_one({"name": "Relay"})["pilots"] == []
    rows = verify_mongo(db, people, ships)
    assert next(r for r in rows if r["name"] == "Aurora")["pilot_names"] == [
        "Ari Vale",
        "Mira Chen",
    ]


def test_dangling_id_rejected(db, prepared):
    load_mongo(db, *prepared)
    db.starships.update_one({"name": "Aurora"}, {"$set": {"pilots": [ObjectId()]}})
    with pytest.raises(DataQualityError):
        verify_mongo(db, *prepared)


def test_wrong_existing_pilot_rejected(db, prepared):
    load_mongo(db, *prepared)
    wrong = db.people.find_one({"name": "Sol Reed"})["_id"]
    db.starships.update_one({"name": "Horizon"}, {"$set": {"pilots": [wrong]}})
    with pytest.raises(DataQualityError):
        verify_mongo(db, *prepared)


def test_stale_mongo_records_rejected(db, prepared):
    load_mongo(db, *prepared)
    db.people.insert_one({"source_url": "extra", "name": "Unexpected"})
    with pytest.raises(DataQualityError):
        verify_mongo(db, *prepared)


def test_bad_batch_performs_no_writes(db, tmp_path):
    people, ships = fixture()
    ships[0]["pilots"] = ["https://swapi.dev/api/people/99999/"]
    with pytest.raises(DataQualityError):
        run_pipeline(db, people, ships, tmp_path, "test", "mongomock")
    assert db.people.count_documents({}) == 0
    assert db.starships.count_documents({}) == 0


def test_sql_idempotency_and_parity(prepared, tmp_path):
    path = tmp_path / "db.sqlite3"
    for _ in range(2):
        result = export_sql(*prepared, path)
    assert result == {
        "people": 3,
        "starships": 3,
        "pilot_links": 3,
        "foreign_key_violations": 0,
        "identity_parity": True,
    }
    with closing(sqlite3.connect(path)) as sql:
        assert sql.execute("SELECT COUNT(*) FROM starship_pilots").fetchone()[0] == 3


def test_changed_links_replaced_in_both_databases(db, prepared, tmp_path):
    people, ships = prepared
    load_mongo(db, people, ships)
    path = tmp_path / "db.sqlite3"
    export_sql(people, ships, path)
    ships[0]["pilot_urls"] = []
    load_mongo(db, people, ships)
    verify_mongo(db, people, ships)
    assert export_sql(people, ships, path)["pilot_links"] == 1


def test_full_report(db, tmp_path):
    report = run_pipeline(db, *fixture(), tmp_path, "synthetic-fixture", "mongomock")
    assert report["counts"] == {"people": 3, "starships": 3, "pilot_links": 3}
    assert report["analytics"]["average_known_length_m"] == 617.25
    assert report["quality"]["sql_identity_parity"]
    saved = json.loads((tmp_path / "report.json").read_text())
    assert saved == report
    assert all("_id" not in row for row in saved["starship_pilots"])


def test_demo_cli(tmp_path, capsys):
    assert main(["demo", "--output", str(tmp_path)]) == 0
    assert json.loads(capsys.readouterr().out)["counts"]["starships"] == 3


def test_cli_error_redacts_details(tmp_path, caplog):
    missing = tmp_path / "password-secret.json"
    assert main(["run", "--snapshot", str(missing)]) == 1
    assert "password-secret" not in caplog.text


def test_cli_invalid_database(caplog):
    assert main(["run", "--database", "bad.name"]) == 1
    assert "failed" in caplog.text


def test_cli_snapshot_with_real_client_substitute(tmp_path, monkeypatch):
    from starship_pipeline import cli

    people, ships = fixture()
    snapshot = tmp_path / "source.json"
    snapshot.write_text(json.dumps({"people": people, "starships": ships}))
    client = mongomock.MongoClient()
    client.admin.command = Mock(return_value={"ok": 1})
    monkeypatch.setattr(cli, "MongoClient", Mock(return_value=client))
    assert main(["run", "--snapshot", str(snapshot), "--output", str(tmp_path / "out")]) == 0
    assert (
        json.loads((tmp_path / "out/report.json").read_text())["source"]
        == "explicit-local-snapshot"
    )


def test_cli_live_with_mocked_source(tmp_path, monkeypatch):
    from starship_pipeline import cli

    api = Mock()
    api.fetch_all.side_effect = fixture()
    monkeypatch.setattr(cli, "SwapiClient", Mock(return_value=api))
    client = mongomock.MongoClient()
    client.admin.command = Mock(return_value={"ok": 1})
    monkeypatch.setattr(cli, "MongoClient", Mock(return_value=client))
    assert main(["run", "--output", str(tmp_path)]) == 0
    api.close.assert_called_once()


def test_changed_dataset_in_sql_rejected(prepared, tmp_path):
    people, ships = prepared
    path = tmp_path / "db.sqlite3"
    export_sql(people, ships, path)
    with pytest.raises(DataQualityError):
        export_sql(people, ships[:2], path)


def test_bad_json_object():
    session = Mock()
    session.get.return_value.status_code = 200
    session.get.return_value.json.return_value = []
    with pytest.raises(DataQualityError):
        SwapiClient(session).get("https://swapi.dev/api/people/")
