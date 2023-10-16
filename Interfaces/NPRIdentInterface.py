import datetime
import pydantic
from pydantic_xml import BaseXmlModel, RootXmlModel, attr, element, wrapped
from typing import Optional, List

from Terminologies import NPRIdent

class ListStructureAssertionException(Exception):
   pass

class NPRInterface:
   def __init__(self, path: str, encoding: str = "utf-8") -> None:
      # Reads files fine with utf-8, crashes with iso-8859-1
      # even if the source document is the latter...?
      self.path = path
      self.encoding = encoding

      self.xml_doc = pathlib.Path(self.path).read_text().encode(self.encoding)
      self.npr = NPR.MsgHead.from_xml(self.xml_doc)

   def getXML(self) -> str:
      return str(self.npr.to_xml(skip_empty=True))

   def getPatients(self) -> dict:
      """Returns a dictionary of {patientPID : patientFNR}

      patients = dict()

      for ident in self.npr.Document.RefDoc.Content.Melding.Institusjon[0].PasientIdent:
         patient[ident.pid] = ident.fnr

      return patient