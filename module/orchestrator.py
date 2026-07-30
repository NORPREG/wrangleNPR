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

from norpreg.Interfaces import REDCapInterface
from norpreg.Interfaces import KodelisteInterface
from norpreg.Dataclasses.NPR.NPRDataclass import NPR

from module import utils, interface, tuple_handler

def find_duplicated_rows() -> list[dict]:
    """Find all NPR repeat instances in REDCap that share a TUPLE_KEY (duplicates).

    For each duplicate group keeps the lowest repeat_instance and marks the
    higher ones for deletion.

    Returns a list of delete descriptors sorted by repeat_instance descending
    (highest first, so each send_delete_payload batch is smaller than the last).
    """

    SKIP_FIELDS = {"redcap_repeat_instance", "record_id", "redcap_repeat_instrument"}

    redcap_rows = interface.get_redcap_rows("npr")

    groups: dict[tuple, list[dict]] = {}
    for row in redcap_rows:
        key = tuple_handler.make_tuple_key(row)
        groups.setdefault(key, []).append(row)

    duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}

    to_delete: list[dict] = []

    for key, rows in duplicate_groups.items():
        try:
            rows_sorted = sorted(rows, key=lambda r: int(r.get("redcap_repeat_instance", 0)))
        except (ValueError, TypeError):
            rows_sorted = rows

        keeper = rows_sorted[0]
        duplicates = rows_sorted[1:]

        # Warn if content differs between copies.
        # This should not happen, since the compare_csv_redcap function
        # updates any mismatches
         
        differing_fields = set()
        for dup in duplicates:
            for field in keeper:
                if field in SKIP_FIELDS:
                    continue
                if not utils.my_compare(keeper.get(field), dup.get(field)):
                    differing_fields.add(field)

        if differing_fields:
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

    to_delete.sort(key=lambda r: r["redcap_repeat_instance"], reverse=True)
    return to_delete

def compare_csv_redcap() -> list[dict]:
    """Strategy for finding duplicates:
        - Compare all three TUPLE_KEYs, even if no planuid is present
            - In earlier version I only looked at data with k[2] (planuid) present, miss a few that way
        - THEN compare all the data inside the instrument, esp. regionsnavn and inndato
        - When is it neccessary to add planuid? Same kno (treatment contact), 
            same regionsnavn, and DIFFERENT REPLAN NUMBER. Very uncommon
    """

    checked = 0
    missing_tuple = 0
    ambiguous_tuple = 0
    to_update = []
    updated_patients = set()

    redcap_rows = interface.get_redcap_rows("npr")

    df_npr = interface.get_csv_data()
    npr_records = df_npr.to_dict(orient="records")

    duplicate_npr_keys = tuple_handler.find_duplicate_tuple_keys(npr_records)
    duplicate_redcap_keys = tuple_handler.find_duplicate_tuple_keys(redcap_rows)

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

    print(f"Checked {checked} NPR rows in REDCap; missing tuple in CSV: {missing_tuple}; ambiguous tuple keys skipped: {ambiguous_tuple}")
    print(f"To update: {len(to_update)} instruments across {len(updated_patients)} patients")

    if change_counter:
        print("Updated field counts:")
        for field, count in change_counter.most_common():
            print(f"  - {field}: {count}")

    return to_update

def find_new_rows(only_proton, treatment_start_date, paths):
    df_npr = interface.get_csv_data(only_proton, treatment_start_date, paths=PATHS)
    interface.remove_rows_in_redcap(df_npr)
    to_redcap = df_npr.to_dict(orient="records")

    pat_rows = df_npr["record_id"].nunique()
    print(f"Antall manglende rader etter (kno,refvolumid,planuid) søk: {len(df_npr)}")
    print(f"Antall manglende pasienter etter (kno,refvolumid,planuid) søk: {pat_rows}")

    return to_redcap