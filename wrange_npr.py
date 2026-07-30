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

from module import utils, interface, tuple_handler, orchestrator

YEARS = ["2026"]
PATHS = [ config.paths.npr_input / year for year in YEARS ]
ONLY_PROTON = False
TREATMENT_START_DATE = "2026-01-01"

RUN_COMPARE_UPDATES = True
RUN_INSERT_NEW_ROWS = False
RUN_REMOVE_REDCAP_DUPLICATES = False
SEND_TO_REDCAP = True


if RUN_COMPARE_UPDATES:
    compare_payload = orchestrator.compare_csv_redcap()

    if SEND_TO_REDCAP and compare_payload:
        interface.send_payload(compare_payload)

if RUN_INSERT_NEW_ROWS:
    insert_payload = orchestrator.find_new_rows(ONLY_PROTON, TREATMENT_START_DATE, PATHS)
    if SEND_TO_REDCAP and insert_payload:
        interface.send_payload(insert_payload)

if RUN_REMOVE_REDCAP_DUPLICATES:
    """Trenger ikke kjøre denne jevnlig, mer en ad-hoc metode
        for å fjerne dupliserte data"""

    remove_payload = orchestrator.find_duplicated_rows()

    if SEND_TO_REDCAP and remove_payload:
        interface.send_delete_payload(remove_payload)

# TODO: Lage en business-logikk på samlet kjøring
# TODO: Sette opp regelmessig kjøring