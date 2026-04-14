import json
import pandas as pd
from glob import glob
from pprint import pprint
import numpy as np
from datetime import datetime, date
import matplotlib.pyplot as plt

from norpreg.config import Config
config = Config("OUS")

from norpreg.Interfaces import REDCapInterface
from norpreg.Interfaces import KodelisteInterface
from norpreg.Dataclasses.NPR.NPRDataclass import NPR

from module import utils

years = ["2026"]
paths = [ config.npr.basedir / year for year in years ]

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

print(f"Number of patients in NPR {config.HF}:")
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

print(f"Now we have in total {len(df_npr['record_id'].unique()) = } patients to push")
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
redcap_kno = list(set(row["kno"] for row in redcap_npr if row["redcap_repeat_instrument"] == "npr"))

df_npr_reduced = df_npr.query("kno not in @redcap_kno", inplace=False)

rows_kno = len(df_npr_reduced)

to_redcap = df_npr_reduced.to_dict(orient="records")

print("Alle behandlinger 2026, ikke i REDCap:")
print(f"{rows_kno = }")
print("Unike pasienter, ikke i REDCap:")
pat_rows = len(df_npr_reduced["record_id"].unique())
print(pat_rows)

"""
#weekly = df_npr_reduced.groupby(pd.Grouper(key="behseriestart", freq="W-MON")).count()
df_npr_reduced["behseriestart"] = pd.to_datetime(df_npr_reduced["behseriestart"])
weekly = df_npr_reduced.set_index("behseriestart").resample("W-MON").count()
plt.plot(weekly.index, weekly.values)
plt.show()
"""

n_split = 50
for idx, to_redcap_split in enumerate(utils.split_list(to_redcap, n_split)):
    print(f"Sending a list of {len(to_redcap_split) = } to redcap.... {idx+1} of {n_split}")
    REDCapInterface.send_json_to_redcap(to_redcap_split)
    print("Done!")