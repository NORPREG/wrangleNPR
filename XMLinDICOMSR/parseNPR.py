from Definitions import NPR
import Terminologies

import pathlib
from pprint import pprint
from bs4 import BeautifulSoup
import xml.dom.minidom
import numpy as np


class ListStructureAssertionException(Exception):
   pass


class NPRDocument:
   def __init__(self, path: str, encoding: str = "utf-8") -> None:  # Reads them fine with utf-8, crashes with iso-8859-1 even if the source document is the latter...?
      self.path = path
      self.encoding = encoding

      self.xml_doc = pathlib.Path(self.path).read_text().encode(self.encoding)
      self.npr = NPR.MsgHead.from_xml(self.xml_doc)
      self.inst = self.npr.Document.RefDoc.Content.Melding.Institusjon[0]

      self.ICD10 = Terminologies.ICD10()
      self.NKPK = Terminologies.NKPK()
      self.Region = Terminologies.Region()

   def getXML(self) -> str:
      return str(self.npr.to_xml(skip_empty=True))

   def getPatients(self) -> list:
      return [obj.Pasient for obj in self.inst.Objektholder]

   def getPatientNrs(self) -> list:
      return [obj.Pasient.pasientNr for obj in self.inst.Objektholder]

   def getPatient(self, pasientNr: int):
      for objekt in self.inst.Objektholder:
         for medisinskStraling in objekt.medisinskStraling:
            if not medisinskStraling.medisinskStralingID == pasientNr:
               continue

            return medisinskStraling

   def getReferencedVolumes(self, pasientNr: int) -> list:
      # TODO: Sjekk at pasientNr == attr i medisinsk stråling her i stedet for å bruke indeksert patID

      vols = None
      for objekt in self.inst.Objektholder:
         for medisinskStraling in objekt.medisinskStraling:
            if not medisinskStraling.medisinskStralingID == pasientNr:
               continue

            if isinstance(vols, list):
               raise ListStructureAssertionException('medisinskStraling encountered more than one')

            vols = medisinskStraling.referansevolum

      return {v.referansevolumID: v.referansevolumNavn for v in vols}

   def getDoseFractions(self, pasientNr: int) -> dict:
      doseDict = dict()

      structureDict = self.getReferencedVolumes(pasientNr)

      for structureName in structureDict.values():
         doseDict[structureName] = {'plan': list(), 'gitt': list()}

      for objekt in self.inst.Objektholder:
         if not objekt.pasientNr == pasientNr:
            continue

         for medisinskStraling in objekt.medisinskStraling:
            for behandlingsserie in medisinskStraling.behandlingsserie:
               for apparatFremmote in behandlingsserie.ApparatFremmote:
                  for doseBidrag in apparatFremmote.doseBidrag:
                     structureName = structureDict[doseBidrag.referansevolumID]
                     doseDict[structureName]['plan'].append(float(doseBidrag.planDose))
                     doseDict[structureName]['gitt'].append(float(doseBidrag.gittDose))

      return doseDict

   def getDoseTotal(self, pasientNr: int) -> dict:
      doseFractions = self.getDoseFractions(pasientNr)

      for structure, data in doseFractions.items():
         data['gitt'] = np.sum(data['gitt'])
         data['plan'] = np.sum(data['plan'])

      return doseFractions

   def getEpisodes(self, pasientNr: int) -> list:
      # episode id: diagnosis, treatment code
      episodes = list()
      for obj in self.inst.Objektholder:
         if not obj.pasientNr == pasientNr:
            continue

         for episode in obj.episode:
            episodes.append(episode)

      return episodes

   def getDiagnosis(self, pasientNr: int) -> dict:
      diagnoser = set()

      episodes = self.getEpisodes(pasientNr)
      for episode in episodes:
         for tilstand in episode.tilstand:
            for kode in tilstand.kode:
               diagnoser.add(kode.kodeVerdi)

      return {diag: self.ICD10.getICD10Definition(diag) for diag in diagnoser}

   def getProsedyrer(self, pasientNr: int) -> str:
      pass


NPR = NPRDocument("../Data/XML/NPR-TstHelge5.xml")
print(NPR.getDiagnosis())
