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


years = ["2026"]
paths = [ config.paths.npr_input / year for year in years ]

files = list()
for path in paths:
    for file in glob(str(path) + "/*.csv"):
        files.append(file)

# Make list of fields vs instrument
fields = NPR.model_json_schema()["properties"]

# Set data type for CSV parsing
type_mapper = {"string": "string", "number": np.float64}
dtypes = {k: type_mapper.get(v.get("type")) for k,v in fields.items() }

skip_rows = {file: utils.find_skip_rows(file) for file in files}

df_years = [
    pd.read_csv(file, sep=";", decimal=",", skiprows=skip_rows[file], dtype=dtypes)
    for file in files
]

df_npr = pd.concat(df_years)

df_npr = df_npr.rename(columns=utils.mapper[config.HF])

df_npr["Kno"] = df_npr["Kno"].astype("string")


# Check number of patients in NPR
# - How many are already in Kodeliste?
# - How many are new?

print(f"Number of patients in NPR {config.HF} file: ", end="")
print(len(df_npr["PersNo"].unique()))

proton_treatment = ["WEOC00", "WEGX90"]
df_proton_treatment = df_npr.query("Pkode in @proton_treatment")
keep_patients = df_proton_treatment["PersNo"].unique()

# Use all patients now
# df_npr = df_npr.query("PersNo in @keep_patients", inplace=False)
df_npr["BehSerieStart"] = pd.to_datetime(df_npr["BehSerieStart"])
df_npr = df_npr.query("BehSerieStart >= '2026-01-01'", inplace=False)

df_npr["record_id"] = df_npr["PersNo"].apply(utils.fnr_mapper_makenew)
df_npr["Fodselsdato"] = df_npr["PersNo"].apply(KodelisteInterface.get_birthdate)

df_npr = df_npr[df_npr["record_id"].notnull()]
df_npr = df_npr.fillna("")

print(f"Number of unique patients in NPR file: {len(df_npr['record_id'].unique())}")
print(f"The total number of rows is {len(df_npr)}")

df_npr["InnDato"] = pd.to_datetime(df_npr["InnDato"]).dt.strftime("%Y-%m-%d %H:%M%:%S")
df_npr["Utdato"] = pd.to_datetime(df_npr["Utdato"]).dt.strftime("%Y-%m-%d %H:%M%:%S")
df_npr["BehSerieStart"] = pd.to_datetime(df_npr["BehSerieStart"]).dt.strftime("%Y-%m-%d %H:%M%:%S")
df_npr["Fodselsdato"] = pd.to_datetime(df_npr["Fodselsdato"]).dt.strftime("%Y-%m-%d")

df_npr["redcap_repeat_instance"] = "new"
df_npr["redcap_repeat_instrument"] = "npr"

df_npr.columns = map(str.lower, df_npr.columns)
df_npr.drop(["persno", "debitor", "frasted", "tilsted", "pidno", "fodselsar"], axis=1, inplace=True)

# Now get current list & compare
redcap_npr = REDCapInterface.export_all(instruments=["npr"])
redcap_tuples = set(
    (str(row["kno"]), str(row["refvolumid"]), str(row["planuid"]))
    for row in redcap_npr
    if row["redcap_repeat_instrument"] == "npr"
)
print(f"Antall rader i REDCap (npr): {len(redcap_tuples)}")

df_npr["_key"] = list(zip(
    df_npr["kno"].astype(str),
    df_npr["refvolumid"].astype(str),
    df_npr["planuid"].astype(str),
))
df_npr_reduced = df_npr[~df_npr["_key"].isin(redcap_tuples)].drop(columns=["_key"])
df_npr = df_npr.drop(columns=["_key"])

to_redcap = df_npr_reduced.to_dict(orient="records")

# Print number of unique KNO rows
# print number of unique KNO + REFVOLUMID rows
# print total number of rows
pat_rows = len(df_npr_reduced["record_id"].unique())

print("Antall manglende rader etter (kno,refvolumid,planuid) søk: ", len(df_npr_reduced))
print("Antall manglende pasienter etter (kno,refvolumid,planuid) søk: ", pat_rows)

# Convert NPR file DF to indexed dict — key is (kno, refvolumid, planuid)
# Normalize types to str to match REDCap API types
df_npr_for_index = df_npr.copy()
df_npr_for_index["kno"] = df_npr_for_index["kno"].astype(str)
df_npr_for_index["refvolumid"] = df_npr_for_index["refvolumid"].astype(str)
df_npr_for_index["planuid"] = df_npr_for_index["planuid"].astype(str)
npr_dict = df_npr_for_index.set_index(["kno", "refvolumid", "planuid"]).to_dict(orient="index")

print("Number of KNO in all NPR files: ", len(npr_dict))

to_update = list()
updated_patients = set()
checked = 0
is_none = 0

# TODO: Gå andre veien
# Vil helst søke FRA npr_row, så vi vet vi får med alle
# F.eks. endringer som skal propageres riktig vei

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

change_counter = Counter()

print_n_first = 0
idx = 0

for row in redcap_npr:
    if row["redcap_repeat_instrument"] != "npr":
        continue

    checked += 1
    
    key = (str(row["kno"]), str(row["refvolumid"]), str(row["planuid"]))
    npr_row = npr_dict.get(key)

    if npr_row is None:
        is_none += 1
        continue

    # Find ONLY updated fields
    updated = {
        k: parse_strip(v)
        for k, v in npr_row.items()
        if k != "redcap_repeat_instance" and not my_compare(row.get(k), v)
    }

    if updated:
        if idx <= print_n_first and "plantotdose" in updated:
            print("UPDATED field.")
            print("Old:", row)
            print("New:", npr_row)
            print("Updated fields: ", updated)
            idx += 1 # only increment with updated == True

        for updated_field in updated:
            change_counter[updated_field] += 1

        updated["record_id"] = row["record_id"]
        updated["redcap_repeat_instrument"] = "npr"
        updated["redcap_repeat_instance"] = row["redcap_repeat_instance"]

        # Change from "." to "," in str output FOR NOW !!!
        for key in ["gittdose", "plandose", "plantotdose"]:
            if not key in updated:
                continue

            from_str = updated[key]
            to_str = from_str.replace(".", ",")
            updated[key] = to_str

        to_update.append(updated)
        updated_patients.add(row["record_id"])

l1 = len(to_update)
l2 = len(updated_patients)
print(f"Checked {checked} rows; {is_none = }")
print(f"In total, {l1} instruments across {l2} patients needs to be updated")

to_redcap = to_update

n_split = 5
for idx, to_redcap_split in enumerate(utils.split_list(to_redcap, n_split)):
    print(f"Sending a list of {len(to_redcap_split) = } to redcap.... {idx+1} of {n_split}")
    REDCapInterface.send_json_to_redcap(to_redcap_split)
    print("Done!")