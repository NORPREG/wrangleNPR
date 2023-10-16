import pydicom
from pydicom.dataset import Dataset
from glob import glob
from pynetdicom import AE, debug_logger
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelMove,
    CTImageStorage,
    RTDoseStorage,
    RTPlanStorage,
    RTStructureSetStorage,
    RTIonPlanStorage,
    BasicTextSRStorage
)

from config import config

class ConfigNotFoundException(Exception):
	pass

class NoDICOMAssociation(Exception):
	pass

class ConquestInterface:
   """ Use data object to send dictionary of parameters"""
   def __init__(self):
   	if not all([k in config for k in ['conquestAE', 'conquestIP', 'conquestPort']]):
			raise ConfigNotFoundException("Please enter 'conquestAE', 'conquestIP' and 'conquestPort' in config.py.")

		# Initialise the Application Entity
		self.ae = AE()
		self.ae.ae_title = config['conquestAE']

		# Add all possible presentation contexts (contices?)
		self.ae.add_requested_context(CTImageStorage)
		self.ae.add_requested_context(RTDoseStorage)
		self.ae.add_requested_context(RTPlanStorage)
		self.ae.add_requested_context(RTStructureSetStorage)
		self.ae.add_requested_context(RTIonPlanStorage)
		self.ae.add_requested_context(BasicTextSRStorage)

	def sendDS(self, ds: Dataset) -> int:
		self.assoc = self.ae.associate(config['conquestIP'], config['conquestPort'])
		if not self.assoc.is_established:
			raise NoDICOMAssociation('Association rejected, aborted or never connected')

	    response = self.assoc.send_c_store(ds)
	    self.assoc.release()
	    return response

	def sendFilePath(self, filePath: str) -> list:
		files = glob(filePath)
		responses = list()

		self.assoc = self.ae.associate(config['conquestIP'], config['conquestPort'])
		if not self.assoc.is_established:
			raise NoDICOMAssociation('Association rejected, aborted or never connected')

	    for file in files:
	        ds = pydicom.dcmread(file)        
	        response = self.assoc.send_c_store(ds)
	        responses.append(response)
	    self.assoc.release()
	    
	    return responses