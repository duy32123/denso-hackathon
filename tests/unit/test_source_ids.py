"""Tests for the persisted D1-A source ID allocator (acquisition/video_catalog/source_ids.py).

Iron Law: ids must be allocated by code and persisted, never re-derived from
title/url/order on a rerun (D1-A prompt section 3).
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "acquisition", "video_catalog"))

from source_ids import SourceIdAllocator


class TestSourceIdAllocator(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.registry_path = os.path.join(self.tmp.name, "registry.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_new_url_gets_a_stable_id_shape(self):
        alloc = SourceIdAllocator(self.registry_path)
        sid = alloc.get_or_create("https://www.haascnc.com/video/service/TmjjC7BDDag.html")
        self.assertRegex(sid, r"^SRC_HAAS_\d{4}$")

    def test_same_url_returns_same_id_across_fresh_allocator_instances(self):
        first = SourceIdAllocator(self.registry_path).get_or_create("https://example.com/a")
        second = SourceIdAllocator(self.registry_path).get_or_create("https://example.com/a")
        self.assertEqual(first, second)

    def test_different_urls_get_different_ids(self):
        alloc = SourceIdAllocator(self.registry_path)
        a = alloc.get_or_create("https://example.com/a")
        b = alloc.get_or_create("https://example.com/b")
        self.assertNotEqual(a, b)

    def test_ids_are_sequential_by_first_seen_not_by_sorted_url(self):
        alloc = SourceIdAllocator(self.registry_path)
        first = alloc.get_or_create("https://example.com/z-seen-first")
        second = alloc.get_or_create("https://example.com/a-seen-second")
        self.assertEqual(first, "SRC_HAAS_0001")
        self.assertEqual(second, "SRC_HAAS_0002")

    def test_registry_persists_to_disk(self):
        alloc = SourceIdAllocator(self.registry_path)
        alloc.get_or_create("https://example.com/a")
        with open(self.registry_path, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("https://example.com/a", data["urls"])


if __name__ == "__main__":
    unittest.main()
