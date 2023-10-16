import datetime
import pydantic
from pydantic_xml import BaseXmlModel, RootXmlModel, attr, element, wrapped
from typing import Optional, List

from Terminologies import NPR

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

   def getBehandlingsSerie(self, pasientNr: int) -> list:
      for obj in self.inst.Objektholder:
         if not obj.pasientNr == pasientNr:
            continue

         if len(obj.medisinskStraling) > 1:
            raise ListStructureAssertionException(
                'medisinskStraling encountered more than one')

         return obj.medisinskStraling[0].behandlingsserie

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

         for behandlingsserie in self.getBehandlingsSerie(pasientNr):
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

   def getBehandlingsSerieNavn(self, pasientNr: int) -> set:
      """Løpenummer som beskriver antall slike behandlinger pasienter har fått + serienavn."""

      serier = set()

      for behandlingsserie in self.getBehandlingsSerie(pasientNr):
         serier.add(behandlingsserie.behandlingsserieNavn)

      return serier

   def getEpisodes(self, pasientNr: int) -> list:
      # episode id: diagnosis, treatment code
      episodes = list()
      for obj in self.inst.Objektholder:
         if not obj.pasientNr == pasientNr:
            continue

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

   def getProsedyrer(self, pasientNr: int) -> dict:
      prosedyrer = set()

      episodes = self.getEpisodes(pasientNr)
      for episode in episodes:
         for tjeneste in episode.tjeneste:
            for tiltak in tjeneste.tiltak:
               for prosedyre in tiltak.prosedyre:
                  for kode in prosedyre.kode:
                     prosedyrer.add(kode.kodeVerdi)

      return {pros: self.NKPK.getNKPKDefinition(pros) for pros in prosedyrer}
