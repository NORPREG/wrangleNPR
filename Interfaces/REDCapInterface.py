import pydicom

from pprint import pprint
import tempfile

import datetime

from pydicom.filereader import dcmread
from pydicom.sr.codedict import codes
from pydicom.uid import generate_uid, UID

from pprint import pprint
import zlib
import base64

from hypothesis import given
from hypothesis.strategies import text

import pydantic
from pydantic_xml import BaseXmlModel, RootXmlModel, attr, element, wrapped
from typing import Optional, List

mapping = {
	'patientName': '[record_id]',	
}

class REDCapInterface:
   """Use PyCap to send dictionary of parameters. The mapping process is also performed here."""
   pass