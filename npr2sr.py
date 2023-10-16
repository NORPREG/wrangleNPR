from Terminologies import ICD10, NKPK, NPR, Region
from Interfaces import NPRInterface
from Interfaces import DICOMInterface, makeDataset
from pydicom.uid import generate_uid, UID

import pathlib
from pprint import pprint
import xml.dom.minidom
import numpy as np

import tempfile

import argparse


class NothingToOutputException(Exception):
   pass

class NPRVersionNotSupportedException(Exception):
   pass

# Two executables: sr2npr and npr2sr
# npr2sr

parser = argparse.ArgumentParser(description="NPR-XML to DICOM SR encapsulation program")

parser.add_argument("inputFile", type=str, help="Input NPR XML file")
parser.add_argument("-o", "--outputFile", type=str, help="Output DICOM SR file name")
parser.add_argument("-c", "--outputConquest", action="store_true", help="Send directly to Conquest")
parser.add_argument("-v", "--NPRVersion", help="Define NPR version (default 57)")
parser.add_argument("-p", "--parentUID", help="Study UID of parent DICOM dataset")

args = parser.parse_args()

if args.NPRVersion and args.NPRVersion != "57":
   raise NPRVersionNotSupportedException(f"NPR version {args.NPRVersion} not supported.")

if not args.outputFile:
   if not args.outputConquest:
      raise NothingToOutputException("Need an actual output destination (outputFile OR outputConquest)")

   output = generate_uid() + ".dcm"

else:
   output = args.outputFile

with args.inputFile as f:
   # Validate XML before encapsulating to ensure it can be read on the other side
   NPR = NPRInterface(f)
   XMLString = NPR.to_xml()

   parentUID = args.parentUID or generate_uid()
   patients = NPR.getPatients()
   if len(patients) == 1:
      patientName = "Etternavn^Fornavn"
      patientID = patients[0].pasientNr
   else:
      patientName = "Many"
      patientID = "123"

   basicSR = makeDataset(parentUID, patientID, patientName, XMLString) # Returns DicomInterface object
   basicSR.saveFile(output)

   if args.outputConquest:
      """Which Conquest to send to here? Provide list? Local / registry?"""

      conquest = ConquestInterface()
      conquest.sendDS(basicSR)