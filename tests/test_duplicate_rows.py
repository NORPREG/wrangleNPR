"""Tests for orchestrator.find_duplicated_rows using TestData JSON fixture.

Fixture: redcap_hus_duplicate_rows.json
  - 13 rows total
  - 1 TUPLE_KEY group with 4 copies (kno=0FI3J4JLFKJ46, instances 10/11/12/13)
  - Expected: keep instance 10, delete 11/12/13 (3 delete descriptors, sorted descending)

interface.get_redcap_rows is mocked to return the fixture data directly.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from norpreg.config import Config
config = Config("OUS")

from module import interface, orchestrator

TESTDATA = Path(__file__).parent / "TestData"
OUTPUT_DIR = Path(__file__).parent / "TestOutput"

DUPLICATE_ROWS_FILE = TESTDATA / "redcap_hus_duplicate_rows.json"


def _load_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture()
def duplicate_fixture():
    return _load_json(DUPLICATE_ROWS_FILE)


@pytest.fixture()
def to_delete(duplicate_fixture):
    npr_rows = [r for r in duplicate_fixture if r.get("redcap_repeat_instrument") == "npr"]
    with patch("module.interface.get_redcap_rows", return_value=npr_rows):
        return orchestrator.find_duplicated_rows()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFindDuplicatedRows:

    def test_returns_nonempty_list(self, to_delete):
        assert len(to_delete) > 0, "Expected at least one row to delete"

    def test_delete_count_equals_duplicates_minus_one_per_group(self, duplicate_fixture, to_delete):
        """For a group of N copies, N-1 should be marked for deletion."""
        from collections import Counter
        from module import tuple_handler

        groups = {}
        for row in duplicate_fixture:
            if row.get("redcap_repeat_instrument") != "npr":
                continue
            key = tuple_handler.make_tuple_key(row)
            groups.setdefault(key, []).append(row)

        expected = sum(len(v) - 1 for v in groups.values() if len(v) > 1)
        assert len(to_delete) == expected, (
            f"Expected {expected} delete descriptors, got {len(to_delete)}"
        )

    def test_sorted_descending_by_repeat_instance(self, to_delete):
        """Delete list must be sorted highest repeat_instance first."""
        instances = [r["redcap_repeat_instance"] for r in to_delete]
        assert instances == sorted(instances, reverse=True), (
            f"Expected descending order, got {instances}"
        )

    def test_keeper_instance_not_in_delete_list(self, duplicate_fixture, to_delete):
        """The lowest repeat_instance of each group must not appear in to_delete."""
        from collections import defaultdict
        from module import tuple_handler

        groups: dict = defaultdict(list)
        for row in duplicate_fixture:
            if row.get("redcap_repeat_instrument") != "npr":
                continue
            key = tuple_handler.make_tuple_key(row)
            groups[key].append(row)

        delete_instances = {r["redcap_repeat_instance"] for r in to_delete}

        for key, rows in groups.items():
            if len(rows) <= 1:
                continue
            keeper_instance = min(int(r["redcap_repeat_instance"]) for r in rows)
            assert keeper_instance not in delete_instances, (
                f"Keeper instance {keeper_instance} for key {key} must not be in delete list"
            )

    def test_delete_descriptors_have_required_fields(self, to_delete):
        """Each delete descriptor must contain record_id, instrument and instance."""
        for row in to_delete:
            assert "record_id" in row
            assert row["redcap_repeat_instrument"] == "npr"
            assert isinstance(row["redcap_repeat_instance"], int)

    def test_no_unique_rows_in_delete_list(self, duplicate_fixture, to_delete):
        """Rows with a unique TUPLE_KEY must never appear in the delete list."""
        from collections import Counter
        from module import tuple_handler

        key_counts = Counter(
            tuple_handler.make_tuple_key(r)
            for r in duplicate_fixture
            if r.get("redcap_repeat_instrument") == "npr"
        )
        unique_keys_by_instance = {
            int(r["redcap_repeat_instance"])
            for r in duplicate_fixture
            if key_counts[tuple_handler.make_tuple_key(r)] == 1
        }
        delete_instances = {r["redcap_repeat_instance"] for r in to_delete}
        overlap = unique_keys_by_instance & delete_instances
        assert not overlap, f"Unique-row instance(s) {overlap} must not be deleted"

    def test_delta_written_to_output(self, to_delete):
        """Delete payload is serialized to TestOutput as a JSON file."""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_file = OUTPUT_DIR / "redcap_hus_duplicate_rows_delta.json"

        output_file.write_text(
            json.dumps(to_delete, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        written = _load_json(output_file)
        assert len(written) == len(to_delete)
        assert all(r["redcap_repeat_instrument"] == "npr" for r in written)
