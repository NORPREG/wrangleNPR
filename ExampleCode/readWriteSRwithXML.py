import pydicom as pd
import highdicom as hd
import numpy as np

from pprint import pprint

from pydicom.filereader import dcmread
from pydicom.sr.codedict import codes
from pydicom.uid import generate_uid

from pprint import pprint

import pydantic
from pydantic_xml import BaseXmlModel, RootXmlModel, attr, element, wrapped
from typing import Optional, List


def is_float(string: str) -> bool:
    try:
        float(string)
        return True
    except ValueError:
        return False


class MissingDollarSignException(Exception):
    def __init__(self, value: str, message: str ="Missing dollar sign in price element"):
        self.value = value
        self.message = message
        super().__init__(self.message)


class PriceIsNotFloatException(Exception):
    def __init__(self, value: str, message: str ="Cannot parse price"):
        self.value = value
        self.message = message
        super().__init__(self.message)


class PLANT(BaseXmlModel):
    """ Base XML Model for the inner <PLANT/> element. """

    COMMON: str = element()
    BOTANICAL: str = element()
    ZONE: str = element()
    LIGHT: str = element()
    PRICE: str = element()
    AVAILABILITY: int = element()

    @pydantic.field_validator("PRICE")
    @classmethod
    def price_valid(cls, value):
        if not value[0] == "$":
            raise MissingDollarSignException(value)

        if not is_float(value[1:]):
            raise PriceIsNotFloatException(value)

        return value


class CATALOG(BaseXmlModel):
    """ Base XML Model for the outer <CATALOG/> element."""

    PLANT: List[PLANT]


def write():
    sr = pd.dcmread("../Data/DICOM/sr_basic.dcm")

    sr.PatientID = "1234567890"
    sr.SOPInstanceUID = generate_uid()
    sr.StudyInstanceUID = generate_uid()
    sr.SeriesInstanceUID = generate_uid()

    sr.ContentSequence[0].ConceptNameCodeSequence[0].CodeValue = "111781"
    sr.ContentSequence[0].ConceptNameCodeSequence[0].CodeMeaning = "External Data Source"

    # Read XML and strip newlines
    # Don't change encoding
    xml_doc = "".join(open("../Data/XML/plant_catalog.xml", "r").readlines())
    sr.ContentSequence[0].TextValue = xml_doc

    sr.save_as("../Data/DICOM/sr_withXML.dcm")


def read():
    sr = pd.dcmread("../Data/DICOM/sr_withXML.dcm")
    xml_doc = sr.ContentSequence[0].TextValue.encode("utf-8")

    catalog = CATALOG.from_xml(xml_doc)
    print(catalog)
    print(sr)


def main():
    write()
    read()


if __name__ == "__main__":
    main()
