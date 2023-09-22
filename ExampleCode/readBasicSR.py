import pydicom as pd
import highdicom as hd
import numpy as np

from pydicom.filereader import dcmread
from pydicom.sr.codedict import codes
from pydicom.uid import generate_uid

from highdicom.sr.content import FindingSite
from highdicom.sr.templates import Measurement, TrackingIdentifier

sr = pd.dcmread("../Data/DICOM/sr_basic.dcm")
print(sr)