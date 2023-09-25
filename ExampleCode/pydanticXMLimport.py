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


"""
MODEL:
<?xml version="1.0" encoding="UTF-8"?>
<CATALOG>
  <PLANT>
    <COMMON>Bloodroot</COMMON>
    <BOTANICAL>Sanguinaria canadensis</BOTANICAL>
    <ZONE>4</ZONE>
    <LIGHT>Mostly Shady</LIGHT>
    <PRICE>$2.44</PRICE>
    <AVAILABILITY>031599</AVAILABILITY>
  </PLANT>
</CATALOG>
"""


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


xml_doc = pathlib.Path("../Data/XML/plant_catalog.xml").read_text().encode("utf-8")

catalog = CATALOG.from_xml(xml_doc)
print(catalog)


