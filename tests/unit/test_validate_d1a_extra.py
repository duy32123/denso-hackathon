"""D1-A checks not already covered by knowflow_contracts.validate_bundle:
split leakage, checksum format, transcript timestamp bounds, and referenced
artifact existence (D1-A prompt section 14).
"""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "acquisition", "validation"))

from validate_d1a_extra import (
    check_no_split_leakage,
    check_sha256_format,
    check_transcript_bounds,
)


class TestSplitLeakage(unittest.TestCase):
    def test_flags_a_source_id_present_in_both_dev_and_holdout(self):
        errors = check_no_split_leakage(dev_ids={"A", "B"}, holdout_ids={"B", "C"})
        self.assertTrue(any("B" in e for e in errors))

    def test_no_errors_when_splits_are_disjoint(self):
        errors = check_no_split_leakage(dev_ids={"A", "B"}, holdout_ids={"C", "D"})
        self.assertEqual(errors, [])


class TestSha256Format(unittest.TestCase):
    def test_rejects_wrong_length(self):
        errors = check_sha256_format({"x": "abc123"})
        self.assertTrue(errors)

    def test_accepts_valid_64_char_hex(self):
        errors = check_sha256_format({"x": "a" * 64})
        self.assertEqual(errors, [])

    def test_ignores_null_hash(self):
        errors = check_sha256_format({"x": None})
        self.assertEqual(errors, [])


class TestTranscriptBounds(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, utterances):
        path = os.path.join(self.tmp.name, "raw.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"utterances": utterances}, f)
        return path

    def test_flags_utterance_end_ms_past_duration(self):
        path = self._write([{"start_ms": 0, "end_ms": 5000, "text": "hi"}])
        errors = check_transcript_bounds(path, duration_ms=4000)
        self.assertTrue(errors)

    def test_flags_start_not_less_than_end(self):
        path = self._write([{"start_ms": 1000, "end_ms": 1000, "text": "hi"}])
        errors = check_transcript_bounds(path, duration_ms=4000)
        self.assertTrue(errors)

    def test_passes_when_within_bounds(self):
        path = self._write([{"start_ms": 0, "end_ms": 1000, "text": "hi"}])
        errors = check_transcript_bounds(path, duration_ms=4000)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
