"""Unit tests for CSV reading and type parsing via module/utils.py.

Tests run against both HUS and OUS test files and verify:
- Schema-derived dtype / parse_dates logic (get_data_types)
- Column mapping per HF (utils.mapper)
- Datetime parsing after rename
- split_hdiag behaviour
"""

import numpy as np
import pandas as pd
import pytest
from pathlib import Path

from norpreg.config import Config
config = Config("OUS")

from module import utils

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_FILES = {
    "HUS": Path(__file__).parent / "TestData" / "test_npr_hus.csv",
    "OUS": Path(__file__).parent / "TestData" / "test_npr_ous.csv",
}

CANONICAL_DATETIME_COLS = ["InnDato", "UtDato", "BehSerieStart"]
CANONICAL_NUMERIC_COLS  = ["PlanTotDose", "PlanDose", "GittDose"]
CANONICAL_STRING_COLS   = ["Kno", "PersNo", "PIDno", "Pkode", "Hdiag"]
EXPECTED_ROW_COUNT = {"HUS": 11, "OUS": 10}


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def read_csv_for_hf(hf: str) -> pd.DataFrame:
    dtypes, parse_dates = utils.get_data_types()
    csv_path = TEST_FILES[hf]
    skip_rows = utils.find_skip_rows(str(csv_path))
    df = pd.read_csv(csv_path, sep=";", decimal=",", skiprows=skip_rows, dtype=dtypes)
    df = df.rename(columns=utils.mapper[hf])
    for col in parse_dates:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col])
    return df


# ---------------------------------------------------------------------------
# utils.get_data_types()
# ---------------------------------------------------------------------------

class TestGetDataTypes:

    def test_returns_two_element_tuple(self):
        result = utils.get_data_types()
        assert isinstance(result, tuple) and len(result) == 2

    def test_parse_dates_contains_datetime_fields(self):
        _, parse_dates = utils.get_data_types()
        for field in CANONICAL_DATETIME_COLS:
            assert field in parse_dates, f"'{{field}}' should be in parse_dates"

    def test_datetime_fields_excluded_from_dtypes(self):
        dtypes, parse_dates = utils.get_data_types()
        for field in parse_dates:
            assert field not in dtypes, f"'{{field}}' appears in both dtypes and parse_dates"

    def test_numeric_fields_mapped_to_float64(self):
        dtypes, _ = utils.get_data_types()
        for field in CANONICAL_NUMERIC_COLS:
            assert dtypes.get(field) == np.float64, f"'{{field}}' should map to float64"

    def test_string_fields_mapped_to_string(self):
        dtypes, _ = utils.get_data_types()
        for field in CANONICAL_STRING_COLS:
            assert dtypes.get(field) == "string", f"'{{field}}' should map to string"

    def test_no_unmapped_non_transfer_fields(self):
        from norpreg.Dataclasses.NPR.NPRDataclass import NPR
        transfer_only = {
            k for k, v in NPR.model_json_schema()["properties"].items()
            if v.get("transfer_only")
        }
        dtypes, _ = utils.get_data_types()
        unmapped = [k for k, v in dtypes.items() if v is None and k not in transfer_only]
        assert unmapped == [], f"Non-transfer fields with no dtype mapping: {unmapped}"


# ---------------------------------------------------------------------------
# CSV reading -- parametrised over both HF values
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hf", ["HUS", "OUS"])
class TestReadCsv:

    @pytest.fixture
    def df(self, hf):
        return read_csv_for_hf(hf)

    def test_file_exists(self, hf, df):
        assert TEST_FILES[hf].exists()

    def test_row_count(self, hf, df):
        expected = EXPECTED_ROW_COUNT[hf]
        assert len(df) == expected, f"[{hf}] Expected {expected} rows, got {len(df)}"

    def test_canonical_columns_present(self, hf, df):
        all_canonical = CANONICAL_DATETIME_COLS + CANONICAL_NUMERIC_COLS + CANONICAL_STRING_COLS
        missing = [c for c in all_canonical if c not in df.columns]
        assert missing == [], f"[{hf}] Missing columns after rename: {missing}"

    def test_datetime_columns_are_datetime_dtype(self, hf, df):
        for col in CANONICAL_DATETIME_COLS:
            assert pd.api.types.is_datetime64_any_dtype(df[col]), \
                f"[{hf}] '{col}' should be datetime64"

    def test_datetime_columns_have_no_nat(self, hf, df):
        for col in CANONICAL_DATETIME_COLS:
            assert df[col].notna().all(), f"[{hf}] '{col}' contains NaT"

    def test_numeric_columns_are_float(self, hf, df):
        for col in CANONICAL_NUMERIC_COLS:
            assert pd.api.types.is_float_dtype(df[col]), f"[{hf}] '{col}' should be float64"

    def test_dose_values_are_positive(self, hf, df):
        for col in CANONICAL_NUMERIC_COLS:
            assert (df[col] > 0).all(), f"[{hf}] All values in '{col}' should be > 0"

    def test_string_columns_are_string_dtype(self, hf, df):
        for col in CANONICAL_STRING_COLS:
            assert pd.api.types.is_string_dtype(df[col]), f"[{hf}] '{col}' should be string"

    def test_kno_has_no_nulls(self, hf, df):
        assert df["Kno"].notna().all(), f"[{hf}] Kno should have no null values"

    def test_persno_is_consistent(self, hf, df):
        assert df["PersNo"].nunique() == 1, f"[{hf}] Expected 1 unique PersNo"


# ---------------------------------------------------------------------------
# split_hdiag
# ---------------------------------------------------------------------------

class TestSplitHdiag:

    def _lowercased(self, hf: str) -> pd.DataFrame:
        df = read_csv_for_hf(hf)
        df.columns = pd.Index(map(str.lower, df.columns))
        return df

    def test_rows_with_comma_are_split(self):
        """Rows where Hdiag contains a comma get split: first code -> mdiag, rest -> hdiag.
        Rows without comma are untouched (mdiag stays empty)."""
        df = self._lowercased("HUS")
        had_comma = df["hdiag"].str.contains(",", na=False).copy()
        utils.split_hdiag(df)

        assert not df["hdiag"].str.contains(",", na=False).any(), \
            "No commas should remain in hdiag after split"
        if had_comma.any():
            assert (df.loc[had_comma, "mdiag"] != "").all(), \
                "Rows that had a comma should have a non-empty mdiag"
        assert (df.loc[~had_comma, "mdiag"] == "").all(), \
            "Rows without comma should keep mdiag empty"

    def test_ous_single_hdiag_unchanged(self):
        """OUS data has single-value Hdiag -- split_hdiag should be a no-op."""
        df = self._lowercased("OUS")
        original_hdiag = df["hdiag"].copy()
        utils.split_hdiag(df)
        assert (df["mdiag"] == "").all(), "mdiag should be empty when Hdiag has no comma"
        pd.testing.assert_series_equal(df["hdiag"], original_hdiag)

    def test_mixed_only_comma_rows_affected(self):
        """When only some rows have a comma, only those rows are modified."""
        df = self._lowercased("OUS")
        df.loc[0, "hdiag"] = "C500,C341"
        utils.split_hdiag(df)
        assert df.loc[0, "mdiag"] == "C500"
        assert df.loc[0, "hdiag"] == "C341"
        assert (df.loc[1:, "mdiag"] == "").all()
