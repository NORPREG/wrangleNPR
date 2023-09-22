import pydicom as pd
import highdicom as hd
import numpy as np

from pprint import pprint

from pydicom.filereader import dcmread
from pydicom.sr.codedict import codes
from pydicom.uid import generate_uid

from highdicom.sr.content import FindingSite
from highdicom.sr.templates import Measurement, TrackingIdentifier

import xml.dom.minidom
from pprint import pprint
import pathlib

import pydantic
from pydantic_xml import BaseXmlModel, RootXmlModel, attr, element, wrapped
from typing import Optional, List


class MissingDollarSignException(Exception):
    def __init__(self, value, message="Missing dollar sign in price element"):
        self.value = value
        self.message = message
        super().__init__(self.message)


class PriceIsNotFloatException(Exception):
    def __init__(self, value, message="Cannot parse price"):
        self.value = value
        self.message = message
        super().__init__(self.message)


def is_float(string):
    try:
        float(string)
        return True
    except ValueError:
        return False


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


sr = pd.dcmread("../Data/DICOM/sr_withXML.dcm")
xml_doc = sr.ContentSequence[0].TextValue.encode("utf-8")

catalog = CATALOG.from_xml(xml_doc)
print(catalog)
