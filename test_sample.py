import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from hypothesis import given
from hypothesis.strategies import text

import XMLinDICOM

@given(text(min_size=5))
def test_store_load(s):
    XMLinDICOM.makeFile(s, "sr.dcm")
    output = XMLinDICOM.loadSR("sr.dcm").ContentSequence[0].TextValue
    assert s == output
