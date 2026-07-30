from functools import lru_cache
import time
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

import numpy as np
import pandas as pd


from norpreg.Interfaces import REDCapInterface, KodelisteInterface
from norpreg.Dataclasses.NPR.NPRDataclass import NPR

from module import tuple_handler

DROP_COLUMNS = ["persno", "debitor", "frasted", "tilsted", "pidno", "fodselsar"]

kodeliste = KodelisteInterface.Kodeliste()

def split_list(alist, wanted_parts=1):
    length = len(alist)
    return [ alist[i*length // wanted_parts: (i+1)*length // wanted_parts] 
             for i in range(wanted_parts) ]

@lru_cache(maxsize=None)
def fnr_mapper_makenew(fnr_in, ois_patient_id):
    return kodeliste.add_patient(fnr_in, ois_patient_id = ois_patient_id)

def get_fields(pyd):
    fields = list()

    schema = pyd.model_json_schema()["properties"]
    for k,v in schema.items():
        if v.get("transfer_only"):
            continue

        fields.append(k)
    
    return fields

def format_date(dateobj):
    if isinstance(dateobj, date):
        return dateobj.isoformat()
    
    return dateobj.isoformat(sep=" ")

def flatten(xss):
    return [x for xs in xss for x in xs]

def find_skip_rows(filename):
    with open(filename, "r") as in_file:
        for idx, line in enumerate(in_file.readlines()):
            if "persno" in line.lower():
                return idx

mapper = {
    "HUS": {
        "Inndato": "InnDato",
        "KNo": "Kno",
        "Maskin": "Machine",
        "RefVolID": "RefVolumId",
        "RefVolNavn": "RefVolumNavn",
        "BehSerieID": "BehSerieId"
    },
    "OUS": {
        "Utdato": "UtDato",
    }
}

def split_hdiag(df):
    """When hdiag has two values (e.g. metastasis,primary), split them into mdiag and hdiag
        Perform after lowering field names"""

    df["mdiag"] = ""
    hdiag_with_comma = df["hdiag"].astype(str).str.contains(",", na=False)
    if not hdiag_with_comma.any():
        return
    hdiag_split = df.loc[hdiag_with_comma, "hdiag"].astype(str).str.split(",", n=1, expand=True)
    hdiag_split.columns = ["mdiag", "hdiag"]
    df.loc[hdiag_with_comma, ["mdiag", "hdiag"]] = hdiag_split.apply(lambda c: c.str.strip())

def get_data_types():
    """Define data types and date columns for CSV input, derived from NPR Pydantic schema.
    Returns (dtypes, parse_dates) where date-time fields are excluded from dtypes
    and collected in parse_dates for pd.read_csv."""

    type_mapper = {"string": "string", "number": np.float64}
    fields = NPR.model_json_schema()["properties"]

    dtypes = {
        k: type_mapper.get(v.get("type"))
        for k, v in fields.items()
        if v.get("format") != "date-time"
    }
    parse_dates = [k for k, v in fields.items() if v.get("format") == "date-time"]
    return dtypes, parse_dates

def filter_proton(df):
    proton_treatment = ["WEOC00", "WEGX90"]
    df_pkode = df.query("Pkode in @proton_treatment")
    keep_patients = df_pkode["PersNo"].unique()
    df.query("PersNo in @keep_patients", inplace=True)

def filter_treatment_start(df, treatment_start_date):
    df.query(f"BehSerieStart >= '{treatment_start_date}'", inplace=True)

def serialize_dates(df):
    """Ensure correct date format (between REDCap/SQL and CSV).
        Perform this step AFTER lowering field names"""

    fields_datetime = ["inndato", "utdato", "behseriestart"]
    fields_date = ["fodselsdato"]

    for field in fields_datetime:
        df[field] = pd.to_datetime(df[field]).dt.strftime("%Y-%m-%d %H:%M:%S")

    for field in fields_date:
        df[field] = pd.to_datetime(df[field]).dt.strftime("%Y-%m-%d")


def remap_to_redcap(df):
    df["redcap_repeat_instance"] = "new"
    df["redcap_repeat_instrument"] = "npr"

    df.columns = map(str.lower, df.columns)
    df.drop(DROP_COLUMNS, axis=1, inplace=True)


def my_compare(s1, s2):
    """Return True when two values are equivalent after normalization."""
    return parse_strip(s1) == parse_strip(s2)

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