import pydicom as pd
import highdicom as hd
import numpy as np

from pprint import pprint

from pydicom.filereader import dcmread
from pydicom.sr.codedict import codes
from pydicom.uid import generate_uid

from highdicom.sr.content import FindingSite
from highdicom.sr.templates import Measurement, TrackingIdentifier

sr = pd.dcmread("../Data/DICOM/sr_basic.dcm")

xml_doc = "".join(open("../Data/XML/plant_catalog.xml", "r").readlines())

print(repr(xml_doc))

sr.ContentSequence[0].TextValue = xml_doc

print(sr)

sr.save_as("../Data/DICOM/sr_withXML.dcm")
