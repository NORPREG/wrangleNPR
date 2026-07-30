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

# Last denne før NORPREG-modulene!
from norpreg.config import Config
config = Config("OUS")

from norpreg.Interfaces import REDCapInterface
from norpreg.Interfaces import KodelisteInterface
from norpreg.Dataclasses.NPR.NPRDataclass import NPR

from module import utils, interface, tuple_handler

YEARS = ["2026"]
PATHS = [ config.paths.npr_input / year for year in YEARS ]

ONLY_PROTON = False
treatment_start_date = "2026-01-01"
DROP_COLUMNS = ["persno", "debitor", "frasted", "tilsted", "pidno", "fodselsar"]
RUN_COMPARE_UPDATES = True
RUN_INSERT_NEW_ROWS = False
RUN_REMOVE_REDCAP_DUPLICATES = False
SEND_TO_REDCAP = True

# ============================================================================
# Main functions
# ============================================================================

def find_new_rows():
    filter_args = {
        "only_proton": ONLY_PROTON,
        "treatment_start_date": treatment_start_date
    }

    df_npr = interface.get_csv_data(filtering=args, paths=PATHS)
    interface.remove_rows_in_redcap(df_npr)
    to_redcap = df_npr.to_dict(orient="records")

    pat_rows = df_npr["record_id"].nunique()
    print(f"Antall manglende rader etter (kno,refvolumid,planuid) søk: {len(df_npr)}")
    print(f"Antall manglende pasienter etter (kno,refvolumid,planuid) søk: {pat_rows}")

    return to_redcap

def compare_csv_redcap():
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

    df_npr = get_csv_data()
    npr_records = df_npr.to_dict(orient="records")

    duplicate_npr_keys = tuple_handler.find_duplicate_tuple_keys(npr_records)
    duplicate_redcap_keys = tuple_handler.find_duplicate_tuple_keys(redcap_rows)

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
            key = tuple_handler.make_tuple_key(row)
            if key not in duplicate_redcap_keys:
                continue
            record_id = row.get("record_id")
            dup_by_patient.setdefault(record_id, Counter())[key] += 1

        print("Pasienter med duplikat TUPLE_KEY (record_id -> Counter(TUPLE_KEY)):")
        pprint(list(dup_by_patient.keys()))        

    npr_dict = tuple_handler.build_key_lookup(npr_records, skip_keys=duplicate_npr_keys)

    for row in redcap_rows:
        key = tuple_handler.make_tuple_key(row)
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
            k: utils.parse_strip(v)
            for k, v in npr_row.items()
            if k in row and k != "redcap_repeat_instance" and not utils.my_compare(row.get(k), v)
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
        key = tuple_handler.make_tuple_key(row)
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
                if not utils.my_compare(keeper.get(field), dup.get(field)):
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

if RUN_COMPARE_UPDATES:
    compare_payload = compare_csv_redcap()

    if SEND_TO_REDCAP and compare_payload:
        interface.send_payload(compare_payload)

if RUN_INSERT_NEW_ROWS:
    insert_payload = find_new_rows()
    if SEND_TO_REDCAP and insert_payload:
        interface.send_payload(insert_payload)

if RUN_REMOVE_REDCAP_DUPLICATES:
    """Trenger ikke kjøre denne jevnlig, mer en ad-hoc metode
        for å fjerne dupliserte data"""

    remove_payload = find_duplicated_rows()

    if SEND_TO_REDCAP and remove_payload:
        interface.send_delete_payload(remove_payload)

# TODO: Samle mye kode inn i felles funksjoner
# TODO: Lage en business-logikk på samlet kjøring
# TODO: Sette opp regelmessig kjøring