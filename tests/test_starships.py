"""Behaviour tests: API pagination, failure paths and MongoDB reference handling."""

import copy
import unittest
from unittest.mock import Mock

import mongomock
import requests
from bson import ObjectId

from sql_extension import export_sql
from starships import (
    SnapshotClient,
    SwapiClient,
    get_pilot_ids,
    get_starships,
    pilot_lookup,
    replace_pilots_and_insert,
)


class StarshipTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().lab
        self.han = ObjectId()
        self.chewie = ObjectId()
        self.db.characters.insert_many(
            [
                {"_id": self.han, "name": "Han Solo"},
                {"_id": self.chewie, "name": "Chewbacca"},
            ]
        )
        self.api = SnapshotClient(
            {
                "https://swapi.dev/api/people/14/": {"name": "Han Solo"},
                "https://swapi.dev/api/people/13/": {"name": "Chewbacca"},
            }
        )
        self.ship = {
            "name": "Millennium Falcon",
            "url": "https://swapi.dev/api/starships/10/",
            "model": "YT-1300",
            "manufacturer": "CEC",
            "length": "34.37",
            "pilots": list(self.api.people),
        }

    def test_all_pages(self):
        api = Mock()
        api.get.side_effect = [
            {"count": 2, "results": [{"url": "a"}], "next": "page2"},
            {"count": 2, "results": [{"url": "b"}], "next": None},
        ]
        self.assertEqual(len(get_starships(api)), 2)
        self.assertEqual(api.get.call_count, 2)

    def test_incomplete_download(self):
        api = Mock()
        api.get.return_value = {"count": 2, "results": [], "next": None}
        with self.assertRaises(ValueError):
            get_starships(api)

    def test_duplicate_ships(self):
        api = Mock()
        api.get.return_value = {
            "count": 2,
            "results": [{"url": "a"}, {"url": "a"}],
            "next": None,
        }
        with self.assertRaises(ValueError):
            get_starships(api)

    def test_pagination_cycle(self):
        api = Mock()
        api.get.return_value = {
            "count": 2,
            "results": [],
            "next": "https://swapi.dev/api/starships/",
        }
        with self.assertRaises(ValueError):
            get_starships(api)

    def test_real_objectids_and_source_unchanged(self):
        original = copy.deepcopy(self.ship)
        replace_pilots_and_insert([self.ship], self.db, self.api)
        stored = self.db.starships.find_one()
        self.assertEqual(stored["pilots"], [self.han, self.chewie])
        self.assertTrue(all(isinstance(p, ObjectId) for p in stored["pilots"]))
        self.assertEqual(self.ship, original)

    def test_rerun_does_not_duplicate(self):
        for _ in range(2):
            replace_pilots_and_insert([self.ship], self.db, self.api)
        self.assertEqual(self.db.starships.count_documents({}), 1)

    def test_no_pilots_still_retains_ship(self):
        self.ship["pilots"] = []
        replace_pilots_and_insert([self.ship], self.db, self.api)
        self.assertEqual(pilot_lookup(self.db)[0]["pilot_names"], [])

    def test_multiple_pilots_lookup(self):
        replace_pilots_and_insert([self.ship], self.db, self.api)
        self.assertEqual(
            set(pilot_lookup(self.db)[0]["pilot_names"]), {"Han Solo", "Chewbacca"}
        )

    def test_missing_pilot_aborts_before_ship_writes(self):
        self.db.characters.delete_one({"name": "Han Solo"})
        with self.assertRaises(ValueError):
            replace_pilots_and_insert([self.ship], self.db, self.api)
        self.assertEqual(self.db.starships.count_documents({}), 0)

    def test_ambiguous_name_rejected(self):
        self.db.characters.insert_one({"name": "Han Solo"})
        with self.assertRaises(ValueError):
            get_pilot_ids(self.ship["pilots"], self.db.characters, self.api)

    def test_shared_pilot_cached(self):
        api = Mock(wraps=self.api)
        cache = {}
        for _ in range(2):
            get_pilot_ids(self.ship["pilots"], self.db.characters, api, cache)
        self.assertEqual(api.get.call_count, 2)

    def test_untrusted_host_rejected(self):
        api = SwapiClient()
        with self.assertRaises(ValueError):
            api.get("https://example.com/api/people/1/")

    def test_http_failure_propagates(self):
        api = SwapiClient()
        api.session = Mock()
        api.session.get.return_value.raise_for_status.side_effect = requests.HTTPError(
            "503"
        )
        with self.assertRaises(requests.HTTPError):
            api.get("https://swapi.dev/api/starships/")

    def test_bounded_get_retries(self):
        retry = SwapiClient().session.get_adapter("https://").max_retries
        self.assertEqual(retry.total, 3)
        self.assertIn(429, retry.status_forcelist)
        self.assertEqual(set(retry.allowed_methods), {"GET"})

    def test_sql_relationships(self):
        replace_pilots_and_insert([self.ship], self.db, self.api)
        result = export_sql(self.db, ":memory:")
        self.assertEqual(result["counts"]["starship_pilots"], 2)
        self.assertEqual(result["foreign_key_violations"], [])
        self.assertEqual(len(result["falcon_pilots"]), 2)


if __name__ == "__main__":
    unittest.main()
