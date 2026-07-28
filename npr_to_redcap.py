import json
import pandas as pd
from glob import glob
from pprint import pprint
import numpy as np
from datetime import datetime, date
import matplotlib.pyplot as plt
import time
import re
from decimal import Decimal, InvalidOperation
from collections import Counter

from norpreg.config import Config
config = Config("OUS")

from norpreg.Interfaces import REDCapInterface
from norpreg.Interfaces import KodelisteInterface
from norpreg.Dataclasses.NPR.NPRDataclass import NPR

from module import utils

YEARS = ["2026"]
PATHS = [ config.paths.npr_input / year for year in YEARS ]

only_proton = False
treatment_start_date = "2026-01-01"
TUPLE_KEY = ["kno", "refvolumid", "planuid"]
STED_MAPPER = {"RAD": "Radiumhospitalet", "ULL": "Ullevål"}
RUN_COMPARE_UPDATES = True
RUN_INSERT_NEW_ROWS = False
RUN_REMOVE_REDCAP_DUPLICATES = False
SEND_TO_REDCAP = True

# GLOBAL STUFF
# Make list of fields vs instrument

def map_sted(file_name):
    for k,v in STED_MAPPER.items():
        if k in file_name:
            return v
    
    return ""

def find_files():
    """Find the last files for NPR input, given HF in config"""

    files = list()
    for path in PATHS:
        for file in glob(str(path) + "/*.*"):
            files.append(file)

    return files

def get_data_types():
    """Define data types for CSV input"""

    type_mapper = {"string": "string", "number": np.float64}
    fields = NPR.model_json_schema()["properties"]

    dtypes = {k: type_mapper.get(v.get("type")) for k,v in fields.items() }
    return dtypes

def read_csv():
    files = find_files()
    print("Files: ", files)

    dtypes = get_data_types()

    skip_rows = {file: utils.find_skip_rows(file) for file in files}
    df_years = {
        file: pd.read_csv(file, sep=";", decimal=",", skiprows=skip_rows[file], dtype=dtypes)
        for file in files
    }

    for key in df_years:
        df_years[key]["sted"] = map_sted(key)

    df_combined = pd.concat(df_years.values())

    df_combined = df_combined.rename(columns=utils.mapper[config.HF])
    df_combined["Kno"] = df_combined["Kno"].astype("string")
    df_combined["BehSerieStart"] = pd.to_datetime(df_combined["BehSerieStart"])
    
    if not "PlanUID" in df_combined.columns:
        df_combined["PlanUID"] = ""

    return df_combined

def filter_proton(df):
    proton_treatment = ["WEOC00", "WEGX90"]
    df_pkode = df.query("Pkode in @proton_treatment")
    keep_patients = df_pkode["PersNo"].unique()
    df.query("PersNo in @keep_patients", inplace=True)

def filter_treatment_start(df):
    df.query(f"BehSerieStart >= '{treatment_start_date}'", inplace=True)

def sync_kodeliste(df):
    df["record_id"] = df["PersNo"].apply(utils.fnr_mapper_makenew)
    df["fodselsdato"] = df["PersNo"].apply(KodelisteInterface.get_birthdate)
    return df[df["record_id"].notnull()].fillna("")

def serialize_dates(df):
    """Ensure correct date format (between REDCap/SQL and CSV).
        Perform this step AFTER lowering field names"""

    fields_datetime = ["inndato", "utdato", "behseriestart"]
    fields_date = ["fodselsdato"]

    for field in fields_datetime:
        df[field] = pd.to_datetime(df[field]).dt.strftime("%Y-%m-%d %H:%M:%S")

    for field in fields_date:
        df[field] = pd.to_datetime(df[field]).dt.strftime("%Y-%m-%d")

def split_hdiag(df):
    """When hdiag has two values (e.g. metastasis,primary), split them into mdiag and hdiag
        Perform after lowering field names"""

    df["mdiag"] = ""
    hdiag_with_comma = df["hdiag"].astype(str).str.contains(",", na=False)
    hdiag_split = df.loc[hdiag_with_comma, "hdiag"].astype(str).str.split(",", n=1, expand=True)
    df.loc[hdiag_with_comma, "mdiag"] = hdiag_split[0].str.strip()
    df.loc[hdiag_with_comma, "hdiag"] = hdiag_split[1].str.strip()

def remap_to_redcap(df):
    df["redcap_repeat_instance"] = "new"
    df["redcap_repeat_instrument"] = "npr"

    df.columns = map(str.lower, df.columns)
    df.drop(["persno", "debitor", "frasted", "tilsted", "pidno", "fodselsar"], axis=1, inplace=True)

def remove_rows_in_redcap(df):
    """Remove rows from DF already in redcap
        use TUPLE_KEY as uniqueness test"""

    # Now get current list & compare
    redcap_dict = REDCapInterface.export_all(instruments=["npr"])

    redcap_tuples = set(
        tuple(str(row.get(k, "")) for k in TUPLE_KEY)
        for row in redcap_dict
        if row["redcap_repeat_instrument"] == "npr"
    )
    df["_key"] = list(zip(*(df[k].astype(str) for k in TUPLE_KEY)))

    # Remove rows already in REDCap (by TUPLE_KEY) in-place.
    rows_to_drop = df.index[df["_key"].isin(redcap_tuples)]
    df.drop(index=rows_to_drop, inplace=True)
    df.drop(columns=["_key"], inplace=True)

def find_new_rows():
    df_npr = read_csv()

    if only_proton:
        filter_proton(df_npr)

    if treatment_start_date:
        filter_treatment_start(df_npr)
    
    patients_nb = len(df_npr['PersNo'].unique())
    print(f"Number of patients in NPR {config.HF} file: {patients_nb}")

    df_npr = sync_kodeliste(df_npr)
    remap_to_redcap(df_npr)
    serialize_dates(df_npr)

    if config.HF == "HUS":
        split_hdiag(df_npr)
    
    remove_rows_in_redcap(df_npr)
    to_redcap = df_npr.to_dict(orient="records")

    print("\nUten gruppering:")
    pat_rows = df_npr["record_id"].nunique()
    print(f"Antall manglende rader etter (kno,refvolumid,planuid) søk: {len(df_npr)}")
    print(f"Antall manglende pasienter etter (kno,refvolumid,planuid) søk: {pat_rows}")

    print("\nMed gruppering:")
    for file, grp in df_npr.groupby("sted"):
        pat_rows = grp["record_id"].nunique()
        print(f"[{file}] Antall manglende rader etter (kno,refvolumid,planuid) søk: {len(grp)}")
        print(f"[{file}] Antall manglende pasienter etter (kno,refvolumid,planuid) søk: {pat_rows}")

    return to_redcap

def parse_strip(value):
    """Normalize values from DataFrame/REDCap into a canonical string representation."""
    if value is None:
        return ""

    # pd.isna handles np.nan, pd.NA, NaT, etc.
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass

    if isinstance(value, (datetime, date, pd.Timestamp)):
        if isinstance(value, pd.Timestamp):
            if pd.isna(value):
                return ""
            value = value.to_pydatetime()
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M:%S")
        return value.strftime("%Y-%m-%d")

    s = str(value).strip()
    if s == "":
        return ""

    # REDCap and CSV may represent missing values as text literals.
    if s.lower() in {"nan", "none", "null", "nat", "<na>"}:
        return ""

    # Normalize decimal separator before numeric parse.
    s = s.replace(",", ".")

    # For numerics, avoid float precision issues and remove trailing zeros.
    try:
        n = Decimal(s)
        normalized = format(n.normalize(), "f")
        if "." in normalized:
            normalized = normalized.rstrip("0").rstrip(".")
        if normalized in {"-0", "-0.0", ""}:
            normalized = "0"
        return normalized
    except InvalidOperation:
        pass

    return s

def my_compare(s1, s2):
    """Return True when two values are equivalent after normalization."""
    return parse_strip(s1) == parse_strip(s2)

def compare_csv_redcap():
    change_counter = Counter()
    checked = 0
    missing_tuple = 0
    ambiguous_tuple = 0
    to_update = []
    updated_patients = set()

    redcap_rows = [
        row
        for row in REDCapInterface.export_all(instruments=["npr"])
        if row.get("redcap_repeat_instrument") == "npr"
    ]

    df_npr = read_csv()
    if only_proton:
        filter_proton(df_npr)
        
    if treatment_start_date:
        filter_treatment_start(df_npr)

    df_npr = sync_kodeliste(df_npr)
    remap_to_redcap(df_npr)
    serialize_dates(df_npr)
    if config.HF == "HUS":
        split_hdiag(df_npr)

    npr_records = df_npr.to_dict(orient="records")
    npr_key_counts = Counter(tuple(str(r.get(k, "")) for k in TUPLE_KEY) for r in npr_records)
    redcap_key_counts = Counter(tuple(str(r.get(k, "")) for k in TUPLE_KEY) for r in redcap_rows)

    duplicate_npr_keys = {k for k, c in npr_key_counts.items() if c > 1}
    duplicate_redcap_keys = {k for k, c in redcap_key_counts.items() if c > 1}

    """
        Strategy for finding duplicates:
            - Compare all three TUPLE_KEYs, even if no planuid is present
                - In earlier version I only looked at data with k[2] (planuid) present, miss a few that way
            - THEN compare all the data inside the instrument, esp. regionsnavn and inndato
            - When is it neccessary to add planuid? Same kno (treatment contact), 
                same regionsnavn, and DIFFERENT REPLAN NUMBER. Very uncommon
    """

    if duplicate_npr_keys:
        print(f"WARNING: {len(duplicate_npr_keys)} duplicate TUPLE_KEY values found in CSV; skipping these keys in compare.")
    if duplicate_redcap_keys:
        print(f"WARNING: {len(duplicate_redcap_keys)} duplicate TUPLE_KEY values found in REDCap.")

        dup_by_patient = {}
        for row in redcap_rows:
            key = tuple(str(row.get(k, "")) for k in TUPLE_KEY)
            if key not in duplicate_redcap_keys:
                continue
            record_id = row.get("record_id")
            dup_by_patient.setdefault(record_id, Counter())[key] += 1

        print("Pasienter med duplikat TUPLE_KEY (record_id -> Counter(TUPLE_KEY)):")
        pprint(list(dup_by_patient.keys()))        
        # pprint(dict(dup_by_patient))

    npr_dict = {
        tuple(str(r.get(k, "")) for k in TUPLE_KEY): r
        for r in npr_records
        if tuple(str(r.get(k, "")) for k in TUPLE_KEY) not in duplicate_npr_keys
    }

    for row in redcap_rows:
        key = tuple(str(row.get(k, "")) for k in TUPLE_KEY)
        if key in duplicate_npr_keys or key in duplicate_redcap_keys:
            ambiguous_tuple += 1
            continue

        npr_row = npr_dict.get(key)

        if npr_row is None:
            """Row in REDCap but not current CSV set (OK)"""

            missing_tuple += 1
            continue

        # Only compare fields that already exist in REDCap row.
        updated = {
            k: parse_strip(v)
            for k, v in npr_row.items()
            if k in row and k != "redcap_repeat_instance" and not my_compare(row.get(k), v) and k != "sted"
        }

        if not updated:
            continue

        for updated_field in updated:
            change_counter[updated_field] += 1

        # Keep the same existing repeat instance when replacing row content.
        updated["record_id"] = row["record_id"]
        updated["redcap_repeat_instrument"] = "npr"
        updated["redcap_repeat_instance"] = row["redcap_repeat_instance"]

        # REDCap import currently expects comma as decimal separator for these fields.
        for dose_field in ["gittdose", "plandose", "plantotdose"]:
            if dose_field in updated:
                updated[dose_field] = updated[dose_field].replace(".", ",")

        to_update.append(updated)
        updated_patients.add(row["record_id"])

    print(f"Checked {checked} npr rows in REDCap; missing tuple in CSV: {missing_tuple}; ambiguous tuple keys skipped: {ambiguous_tuple}")
    print(f"To update: {len(to_update)} instruments across {len(updated_patients)} patients")

    if change_counter:
        print("Updated field counts:")
        for field, count in change_counter.most_common():
            print(f"  - {field}: {count}")

    return to_update

def find_duplicated_rows():
    """Find all NPR repeat instances in REDCap that share a TUPLE_KEY (duplicates).

    For each duplicate group:
    - Warns if content fields differ between copies.
    - Keeps the lowest repeat_instance, marks the higher ones for deletion.

    Returns a list of delete descriptors sorted by repeat_instance descending
    (highest = rarest instance first, so each batch is smaller than the last).
    """

    SKIP_FIELDS = {"redcap_repeat_instance", "record_id", "redcap_repeat_instrument"}

    redcap_rows = [
        row
        for row in REDCapInterface.export_all(instruments=["npr"])
        if row.get("redcap_repeat_instrument") == "npr"
    ]

    # Group rows by TUPLE_KEY.
    groups = {}
    for row in redcap_rows:
        key = tuple(str(row.get(k, "")) for k in TUPLE_KEY)
        groups.setdefault(key, []).append(row)

    unique_record_ids = set()

    duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}
    print(
        f"Found {len(duplicate_groups)} TUPLE_KEY groups with duplicates "
        f"({sum(len(v) for v in duplicate_groups.values())} total rows)"
    )

    to_delete = []
    content_mismatch_count = 0

    for key, rows in duplicate_groups.items():
        # Sort ascending by repeat_instance; keep lowest, delete the rest.
        try:
            rows_sorted = sorted(rows, key=lambda r: int(r.get("redcap_repeat_instance", 0)))
        except (ValueError, TypeError):
            rows_sorted = rows

        keeper = rows_sorted[0]
        duplicates = rows_sorted[1:]

        # Verify that content fields are identical across all copies.
        differing_fields = set()
        for dup in duplicates:
            for field in keeper:
                if field in SKIP_FIELDS:
                    continue
                if not my_compare(keeper.get(field), dup.get(field)):
                    differing_fields.add(field)
  
        if differing_fields:
            content_mismatch_count += 1
            print(
                f"WARNING: fields differ for TUPLE_KEY {key}: {differing_fields} "
                f"(keeping instance {keeper['redcap_repeat_instance']}, "
                f"deleting {[d['redcap_repeat_instance'] for d in duplicates]})"
            )

        for dup in duplicates:
            to_delete.append({
                "record_id": dup["record_id"],
                "redcap_repeat_instrument": "npr",
                "redcap_repeat_instance": int(dup["redcap_repeat_instance"]),
            })
            unique_record_ids.add(dup["record_id"])

    if content_mismatch_count:
        print(f"\nWARNING: {content_mismatch_count} group(s) had differing field values between duplicates.")

    # Highest repeat_instance first → fewest records per batch initially, growing downward.
    to_delete.sort(key=lambda r: r["redcap_repeat_instance"], reverse=True)

    print(f"\nInstances to delete: {len(to_delete)}")
    instance_counts = Counter(r["redcap_repeat_instance"] for r in to_delete)
    print("Records per repeat_instance (descending):")
    for inst in sorted(instance_counts, reverse=True):
        print(f"  instance {inst}: {instance_counts[inst]} record(s)")

    print(f"\nUnique record IDs: {len(unique_record_ids)} in total")

    return to_delete

def send_delete_payload(payload):
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
        print("Done!")

def send_payload(payload, n_split=5):
    for idx, payload_split in enumerate(utils.split_list(payload, n_split)):
        print(f"Sending list with {len(payload_split)} rows to REDCap... {idx+1}")

        REDCapInterface.send_json_to_redcap(payload_split)
        print("Done!")

if RUN_COMPARE_UPDATES:
    compare_payload = compare_csv_redcap()

    if SEND_TO_REDCAP and compare_payload:
        send_payload(compare_payload)

if RUN_INSERT_NEW_ROWS:
    insert_payload = find_new_rows()
    if SEND_TO_REDCAP and insert_payload:
        send_payload(insert_payload)

if RUN_REMOVE_REDCAP_DUPLICATES:
    """Trenger ikke kjøre denne jevnlig, mer en ad-hoc metode
        for å fjerne dupliserte data"""

    remove_payload = find_duplicated_rows()

    if SEND_TO_REDCAP and remove_payload:
        send_delete_payload(remove_payload)

# TODO: Samle mye kode inn i felles funksjoner
# TODO: Lage en business-logikk på samlet kjøring
# TODO: Sette opp regelmessig kjøring