"""End-to-end test for compare logic: CSV vs mock REDCap (changed information).

Pipeline:
  test_npr_hus.csv  →  get_csv_data (mocked)  →  compare with redcap_hus_changed_information.json
                                                   (mocked as REDCap export)
                                                ↓
                                      TestOutput/redcap_hus_changed_information_delta.json

The fixture redcap_hus_changed_information.json is identical to redcap_hus_no_changes.json
except that 10 rows have komm='4321' instead of '1234'.  The CSV source has the correct value
'1234', so the compare should produce a delta of 10 rows that need updating in REDCap.
"""

import json
import pandas as pd
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from norpreg.config import Config
config = Config("OUS")

from module import interface, utils, tuple_handler

TESTDATA = Path(__file__).parent / "TestData"
OUTPUT_DIR = Path(__file__).parent / "TestOutput"

HUS_CSV = TESTDATA / "test_npr_hus.csv"
CHANGED_INFO_FILE = TESTDATA / "redcap_hus_changed_information.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def _mock_sync_kodeliste(df: pd.DataFrame) -> pd.DataFrame:
    df["record_id"] = df["PersNo"].apply(lambda p: f"T{str(p)[-6:]}" if pd.notna(p) else None)
    df["fodselsdato"] = df["Fodselsar"].apply(
        lambda y: f"{int(y)}-01-01" if pd.notna(y) and str(y).strip() else ""
    )
    return df[df["record_id"].notnull()].fillna("")


def _compare_csv_with_redcap(csv_records: list[dict], redcap_rows: list[dict]) -> list[dict]:
    """Find CSV records that differ from their REDCap counterpart (by TUPLE_KEY).

    Mirrors the compare_csv_redcap logic in wrange_npr.py.
    Returns a list of update dicts, each containing only changed fields plus
    record_id / redcap_repeat_instrument / redcap_repeat_instance.
    """
    redcap_npr = [r for r in redcap_rows if r.get("redcap_repeat_instrument") == "npr"]

    duplicate_csv_keys = tuple_handler.find_duplicate_tuple_keys(csv_records)
    duplicate_redcap_keys = tuple_handler.find_duplicate_tuple_keys(redcap_npr)
    csv_lookup = tuple_handler.build_key_lookup(csv_records, skip_keys=duplicate_csv_keys)

    to_update = []
    for row in redcap_npr:
        key = tuple_handler.make_tuple_key(row)
        if key in duplicate_csv_keys or key in duplicate_redcap_keys:
            continue

        csv_row = csv_lookup.get(key)
        if csv_row is None:
            continue

        updated = {
            k: utils.parse_strip(v)
            for k, v in csv_row.items()
            if k in row
            and k != "redcap_repeat_instance"
            and not utils.my_compare(row.get(k), v)
        }

        if not updated:
            continue

        updated["record_id"] = row["record_id"]
        updated["redcap_repeat_instrument"] = "npr"
        updated["redcap_repeat_instance"] = row["redcap_repeat_instance"]
        to_update.append(updated)

    return to_update


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCompareRows:

    @pytest.fixture(autouse=True)
    def _csv_records(self):
        """Run the full CSV pipeline once and expose csv_records to all tests."""
        mock_config = MagicMock()
        mock_config.HF = "HUS"

        with (
            patch("module.interface.config", mock_config),
            patch("module.interface.find_files", return_value=[str(HUS_CSV)]),
            patch("module.interface.sync_kodeliste", side_effect=_mock_sync_kodeliste),
        ):
            df = interface.get_csv_data(
                only_proton=False, treatment_start_date=None, paths=[HUS_CSV]
            )

        self.csv_records = df.to_dict(orient="records")
        self.redcap_data = _load_json(CHANGED_INFO_FILE)

    def test_compare_detects_changed_rows(self):
        """compare logic finds rows where CSV and REDCap differ."""
        delta = _compare_csv_with_redcap(self.csv_records, self.redcap_data)
        assert len(delta) > 0, "Expected at least one changed row"

    def test_compare_changed_field_is_komm(self):
        """All detected changes are in the 'komm' field."""
        delta = _compare_csv_with_redcap(self.csv_records, self.redcap_data)
        for row in delta:
            changed_fields = {k for k in row if k not in {"record_id", "redcap_repeat_instrument", "redcap_repeat_instance"}}
            assert changed_fields == {"komm"}, (
                f"Expected only 'komm' to change, got {changed_fields}"
            )

    def test_compare_corrected_value_is_from_csv(self):
        """Delta rows contain the CSV value for komm, not the REDCap value."""
        delta = _compare_csv_with_redcap(self.csv_records, self.redcap_data)
        csv_komm_values = {r["komm"] for r in self.csv_records}
        for row in delta:
            assert row["komm"] in csv_komm_values, (
                f"Delta komm='{row['komm']}' not found in CSV values {csv_komm_values}"
            )

    def test_compare_delta_has_repeat_instance_from_redcap(self):
        """Delta rows carry the REDCap repeat_instance (not 'new') so updates target the right record."""
        delta = _compare_csv_with_redcap(self.csv_records, self.redcap_data)
        for row in delta:
            assert row["redcap_repeat_instance"] != "new", (
                "Delta row should carry the existing REDCap repeat_instance"
            )
            assert isinstance(row["redcap_repeat_instance"], int), (
                f"repeat_instance should be int, got {type(row['redcap_repeat_instance'])}"
            )

    def test_compare_delta_written_to_output(self):
        """Delta is serialized to TestOutput as a JSON file."""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_file = OUTPUT_DIR / "redcap_hus_changed_information_delta.json"

        delta = _compare_csv_with_redcap(self.csv_records, self.redcap_data)

        output_file.write_text(
            json.dumps(delta, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

        assert output_file.exists()
        written = _load_json(output_file)
        assert len(written) == len(delta)
        assert all("komm" in row for row in written)
