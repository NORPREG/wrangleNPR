from functools import lru_cache
from norpreg.Interfaces import REDCapInterface, KodelisteInterface
import time


kodeliste = KodelisteInterface.Kodeliste()

def split_list(alist, wanted_parts=1):
    length = len(alist)
    return [ alist[i*length // wanted_parts: (i+1)*length // wanted_parts] 
             for i in range(wanted_parts) ]

@lru_cache(maxsize=None)
def fnr_mapper_makenew(fnr_in):
    return kodeliste.add_patient(fnr_in)

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
        "UtDato": "UtDato",
        "KNo": "Kno",
        "Maskin": "Machine",
        "RefVolID": "RefVolumId",
        "RefVolNavn": "RefVolumNavn",
        "BehSerieID": "BehSerieId"
    },
    "OUS": {}
}