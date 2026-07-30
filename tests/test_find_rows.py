"""Tests for find_new_rows logic using TestData JSON fixtures.

Mocks REDCapInterface.export_all to return data from TestData JSON files
instead of making real API calls.

Scenarios:
  no_changes:      CSV data matches REDCap exactly → nothing to insert (empty df)
  extra_activity:  CSV has 2 extra rows not in REDCap → delta written to TestOutput
"""

import json
import pandas as pd
import pytest
from pathlib import Path
from unittest.mock import patch

from module import interface

TESTDATA = Path(__file__).parent / "TestData"
OUTPUT_DIR = Path(__file__).parent / "TestOutput"

NO_CHANGES_FILE = TESTDATA / "redcap_hus_no_changes.json"
EXTRA_ACTIVITY_FILE = TESTDATA / "redcap_hus_extra_activity.json"


def _load_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_json_as_df(path: Path) -> pd.DataFrame:
    return pd.DataFrame(_load_json(path))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFindRows:

    def test_no_changes(self):
        """When CSV data matches REDCap exactly, all rows should be removed in-place."""
        df = _load_json_as_df(NO_CHANGES_FILE)
        redcap_data = _load_json(NO_CHANGES_FILE)

        with patch("module.interface.REDCapInterface.export_all", return_value=redcap_data):
            interface.remove_rows_in_redcap(df)

        assert len(df) == 0, (
            f"Expected 0 rows after matching REDCap, got {len(df)}"
        )

    def test_extra_activity_delta_count(self):
        """When CSV has rows not in REDCap, remove_rows_in_redcap keeps only the delta."""
        df = _load_json_as_df(EXTRA_ACTIVITY_FILE)
        redcap_data = _load_json(NO_CHANGES_FILE)

        n_extra = len(_load_json(EXTRA_ACTIVITY_FILE)) - len(redcap_data)  # 2

        with patch("module.interface.REDCapInterface.export_all", return_value=redcap_data):
            interface.remove_rows_in_redcap(df)

        assert len(df) == n_extra, (
            f"Expected {n_extra} new rows in delta, got {len(df)}"
        )

    def test_extra_activity_delta_written_to_output(self):
        """Delta rows are written to TestOutput as a JSON file."""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_file = OUTPUT_DIR / "redcap_hus_extra_activity_delta.json"

        df = _load_json_as_df(EXTRA_ACTIVITY_FILE)
        redcap_data = _load_json(NO_CHANGES_FILE)
        n_extra = len(_load_json(EXTRA_ACTIVITY_FILE)) - len(redcap_data)

        with patch("module.interface.REDCapInterface.export_all", return_value=redcap_data):
            interface.remove_rows_in_redcap(df)

        payload = df.to_dict(orient="records")
        output_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

        assert output_file.exists()
        written = _load_json(output_file)
        assert len(written) == n_extra, (
            f"Output file should contain {n_extra} rows, got {len(written)}"
        )

    def test_extra_activity_delta_kno_values(self):
        """Delta rows contain the expected kno values (unique to extra_activity)."""
        df = _load_json_as_df(EXTRA_ACTIVITY_FILE)
        redcap_data = _load_json(NO_CHANGES_FILE)

        no_changes_knos = {r["kno"] for r in redcap_data}

        with patch("module.interface.REDCapInterface.export_all", return_value=redcap_data):
            interface.remove_rows_in_redcap(df)

        for _, row in df.iterrows():
            assert row["kno"] not in no_changes_knos, (
                f"Delta row kno '{row['kno']}' should not be present in REDCap"
            )
