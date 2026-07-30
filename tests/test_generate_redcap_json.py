"""Generate mock REDCap JSON output from test NPR CSV files.

Uses the real pipeline (interface.get_csv_data + remap/serialize) but patches
out all network dependencies:
  - find_files     → test CSV files
  - sync_kodeliste → deterministic record_id / fodselsdato (no Kodeliste DB)
  - REDCapInterface.export_all → [] (empty REDCap = all rows are new)
  - config.HF      → set per HF under test

Output: tests/TestOutput/redcap_hus.json  /  redcap_ous.json
"""

import json
import pandas as pd
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from norpreg.config import Config
config = Config("OUS")

from module import interface, utils

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

TEST_FILES = {
    "HUS": Path(__file__).parent / "TestData" / "test_npr_hus.csv",
    "OUS": Path(__file__).parent / "TestData" / "test_npr_ous.csv",
}
OUTPUT_DIR = Path(__file__).parent / "TestOutput"

FILTERING = {"only_proton": False, "treatment_start_date": None}


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _mock_sync_kodeliste(df: pd.DataFrame) -> pd.DataFrame:
    """Deterministic kodeliste sync — no DB required.
    record_id: derived from last 6 digits of PersNo.
    fodselsdato: 01-01 of Fodselsar.
    """
    df["record_id"] = df["PersNo"].apply(lambda p: f"T{str(p)[-6:]}" if pd.notna(p) else None)
    df["fodselsdato"] = df["Fodselsar"].apply(
        lambda y: f"{int(y)}-01-01" if pd.notna(y) and str(y).strip() else ""
    )
    return df[df["record_id"].notnull()].fillna("")


# ---------------------------------------------------------------------------
# Parametrised test
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("hf", ["HUS", "OUS"])
def test_generate_redcap_json(hf):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    mock_config = MagicMock()
    mock_config.HF = hf

    with (
        patch("module.interface.config", mock_config),
        patch("module.interface.find_files", return_value=[str(TEST_FILES[hf])]),
        patch("module.interface.sync_kodeliste", side_effect=_mock_sync_kodeliste),
        patch("module.interface.REDCapInterface.export_all", return_value=[]),
    ):
        df = interface.get_csv_data(FILTERING, paths=[TEST_FILES[hf]])
        interface.remove_rows_in_redcap(df)

    payload = df.to_dict(orient="records")

    output_file = OUTPUT_DIR / f"redcap_{hf.lower()}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

    # --- assertions ---
    assert output_file.exists()
    assert len(payload) > 0, f"[{hf}] Payload should not be empty"

    for row in payload:
        assert row.get("redcap_repeat_instrument") == "npr", "redcap_repeat_instrument should be 'npr'"
        assert row.get("redcap_repeat_instance") == "new", "redcap_repeat_instance should be 'new'"
        assert row.get("record_id"), "record_id should be set"
        assert row.get("kno"), "kno should be set"

    print(f"[{hf}] {len(payload)} rows written to {output_file}")
