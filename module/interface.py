from glob import glob
import pandas as pd

from norpreg.config import Config
config = Config("OUS")

from norpreg.Interfaces import REDCapInterface
from norpreg.Interfaces import KodelisteInterface

from module import utils, tuple_handler

HF_WITH_SPLIT_HDIAG = ["HUS"]

## REDCAP HANDLING

def send_delete_payload(payload: dict) -> None:
    """Delete repeat instances one repeat_instance value at a time, highest first."""
    instance_groups = {}
    for item in payload:
        instance_groups.setdefault(item["redcap_repeat_instance"], []).append(item["record_id"])

    for instance in sorted(instance_groups, reverse=True):
        record_ids = instance_groups[instance]
        print(f"Deleting repeat_instance={instance} for {len(record_ids)} record(s): {record_ids}")
        
        REDCapInterface.delete_patient_instrument(
            record_ids=record_ids,
            instrument="npr",
            repeat_instance=instance,
        )

def send_payload(payload: dict, n_split: int = 5) -> None:
    for idx, payload_split in enumerate(utils.split_list(payload, n_split)):
        print(f"Sending list with {len(payload_split)} rows to REDCap... {idx+1}")
        REDCapInterface.send_json_to_redcap(payload_split)

def remove_rows_in_redcap(df):
    """Remove rows from DF already in redcap
        use TUPLE_KEY as uniqueness test"""

    # Now get current list & compare
    redcap_dict = REDCapInterface.export_all(instruments=["npr"])

    redcap_tuples = set(
        tuple_handler.make_tuple_key(row)
        for row in redcap_dict
        if row["redcap_repeat_instrument"] == "npr"
    )
    df["_key"] = df.apply(lambda row: tuple_handler.make_tuple_key(row.to_dict()), axis=1)

    # Remove rows already in REDCap (by TUPLE_KEY) in-place.
    rows_to_drop = df.index[df["_key"].isin(redcap_tuples)]
    df.drop(index=rows_to_drop, inplace=True)
    df.drop(columns=["_key"], inplace=True)

## KODELISTE SQL HANDLING

def sync_kodeliste(df: pd.DataFrame) -> pd.DataFrame:
    df["record_id"] = df.apply(
        lambda row: utils.fnr_mapper_makenew(row["PersNo"], row["PIDno"]),
        axis=1
    )

    df["fodselsdato"] = df["PersNo"].apply(KodelisteInterface.get_birthdate)

    record_ids = df[df["record_id"].notnull()].fillna("")

    return record_ids

## CSV HANDLING

def find_files(paths):
    """Find all NPR input files under the given list of directory paths."""
    files = []
    for path in paths:
        for file in glob(str(path) + "/*.*"):
            files.append(file)
    return files

def read_csv(paths):
    """Read the NPR CSV files. Do some light parsing."""

    files = find_files(paths)

    # Find data types and date columns from NPR Pydantic schema
    dtypes, parse_dates = utils.get_data_types()

    # Skip header row
    skip_rows = {file: utils.find_skip_rows(file) for file in files}

    # Read all the CSV files contained in target folder
    df_perfile = [
        pd.read_csv(file, sep=";", decimal=",", skiprows=skip_rows[file], dtype=dtypes)
        for file in files
    ]

    df_combined = pd.concat(df_perfile)

    # Map NPR column names to common convention (must happen before datetime parsing
    # so that column names match the schema field names in parse_dates)
    df_combined = df_combined.rename(columns=utils.mapper[config.HF])

    # Convert datetime columns now that names match the Pydantic schema
    for col in parse_dates:
        if col in df_combined.columns:
            df_combined[col] = pd.to_datetime(df_combined[col])
    
    # Not all NPR files have this column -- yet
    if not "PlanUID" in df_combined.columns:
        df_combined["PlanUID"] = ""

    return df_combined

def get_csv_data(filtering, paths):
    """Get NPR CSV data, perform filtering & mapping"""

    df_npr_csv = read_csv(paths)

    if filtering['only_proton']:
        utils.filter_proton(df_npr_csv)

    if filtering['treatment_start_date']:
        utils.filter_treatment_start(df_npr_csv)
    
    df_npr_csv = sync_kodeliste(df_npr_csv)
    utils.remap_to_redcap(df_npr_csv)
    utils.serialize_dates(df_npr_csv)

    if config.HF in HF_WITH_SPLIT_HDIAG:
        utils.split_hdiag(df_npr_csv)
    
    return df_npr_csv