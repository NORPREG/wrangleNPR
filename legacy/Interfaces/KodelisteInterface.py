from sqlalchemy import String
from sqlalchemy_utils.types.encrypted.encrypted_type import AesEngine
from sqlmodel import create_engine, Session, select, exists
from datetime import datetime, date
import os

from module.Dataclasses.KodelisteDataclass import (
	Registry,
	Patient,
)

from module.Tools import encryption

from config import Config
import logging

config = Config()

logger = logging.getLogger(__name__ + f" ({config.HF})")

def get_birthdate(fnr: str) -> date:
	if len(fnr) != 11 or not fnr.isdigit():
		raise ValueError("Ugyldig fødselsnummer")

	day = int(fnr[0:2])
	month = int(fnr[2:4])
	year = int(fnr[4:6])
	individ = int(fnr[6:9])

	# D-nummer (dag +40)
	if day > 40:
		day -= 40

	# H-nummer (måned +40)
	if month > 40:
		month -= 40

	# Bestem århundre
	if 0 <= individ <= 499:
		century = 1900
	elif 500 <= individ <= 749 and 54 <= year <= 99:
		century = 1800
	elif 500 <= individ <= 999 and 0 <= year <= 39:
		century = 2000
	elif 900 <= individ <= 999 and 40 <= year <= 99:
		century = 1900
	else:
		raise ValueError("Ugyldig kombinasjon av individnummer og år")

	full_year = century + year

	return date(full_year, month, day)

def get_id_type(fnr: str) -> str:
	"""Identifies the correct ID number type for a given ID number.

	Args:
		fnr (str): ID number (fødselsnummer)

	Returns:
		str: ID number type (FNR, HNR, DNR, FHNR)
	"""
	if len(fnr) != 11 or not fnr.isdigit():
		return ValueError("Ugyldig fødselsnummer")

	day = int(fnr[0:2])
	month = int(fnr[2:4])

	day_adjusted = day > 40
	month_adjusted = month > 40

	if int(fnr[0]) >= 8:
		return "FHNR"

	elif day_adjusted:
		return "DNR"

	elif month_adjusted:
		return "HNR"

	else:
		return "FNR"

class Kodeliste:
	def __init__(self):
		login = f"{config.kodeliste.sql_user}:{config.kodeliste.sql_pass}"
		mysql_uri = f"mysql+pymysql://{login}@localhost/kodeliste"
		self.engine = create_engine(mysql_uri)

	def add_registry(self, name):
		"""Only performed to configure the database"""

		this_registry = Registry(name=name)
		with Session(self.engine) as session:
			session.add(this_registry)
			session.commit()

	def initialize_registry_list(self):
		"""Only performed to configure the database"""

		self.add_registry("NORPREG")
		for xxx in ["OUS", "HUS", "AAL", "NLSH", "SIG", "SOH", "SSHF", "SUS", "UNN", "Test"]:
			self.add_registry(f"KREST-{xxx}")

	def get_registry_id(self):
		""" Get the registry ID from config for correct DB interface

		Returns:
			_type_: Registry ID (KREST-XXX)
		"""
		krest_name = f"KREST-{config.HF}"
		with Session(self.engine) as session:
			statement = select(Registry).where(Registry.name == krest_name)
			results = session.exec(statement)
			return results.one().id

	def check_patient(self, id_number: str):
		with Session(self.engine) as session:
			statement = select(Patient)
			results = session.exec(statement)
			for result in results.fetchall():
				if encryption.decrypt(result.id_number_aes) == id_number:
					# print(f"Patient exists with {result.patient_key = }")
					return result.patient_key
			return None

	def add_patient(self, id_number: str, ois_patient_id: str = None, epj_patient_id: str = None) -> str:
		"""Add a patient to the Kodeliste database. Check if exists

		Args:
			id_number (str): Fødselsnummer
			ois_patient_id (str, optional): ID for OIS (Aria / Mosaiq). Defaults to None.
			epj_patient_id (str, optional): ID for EPJ (often NPR ID). Defaults to None.

		Returns:
			str: pseudonymized patient key, new or old (previously generated)
		"""

		id_type = get_id_type(id_number)
		
		# First check if patient exists
		with Session(self.engine) as session:
			statement = select(Patient)
			results = session.exec(statement)
			for result in results.fetchall():
				if encryption.decrypt(result.id_number_aes) == id_number:
					# print(f"Patient exists with {result.patient_key = }")
					return result.patient_key
		
		# Add the Patient object
		try:
			birth_date = get_birthdate(id_number).isoformat()
		except Exception as e:
			print(f"Cannot parse {id_number[:6] = } as birth_date!")
			print(e)
			birth_date = ""
			exit(0)

		this_patient = Patient(
			patient_key = os.urandom(15).hex()[:7],
			dt_added=datetime.now(),
			birth_date_aes=encryption.encrypt(birth_date),
			id_number_aes = encryption.encrypt(id_number),
			# ois_patient_id=ois_patient_id,
			# epj_patient_id=epj_patient_id,
			fk_registry_id=self.get_registry_id(),
			id_type = id_type,
		)

		with Session(self.engine) as session:
			session.add(this_patient)
			session.commit()
			session.refresh(this_patient)

		return str(this_patient.patient_key)

	def get_fnr(self, patient_key: str) -> str:
		"""Return the decrypted id_number of patient_key."

		Args:
			patient_key (str): Pseudonymized patient key

		Returns:
			str: ID number (fødselsnummer)
		"""
		with Session(self.engine) as session:
			statement = select(Patient).where(Patient.patient_key == patient_key)
			results = session.exec(statement)

			try:
				id_number_aes = results.one().id_number_aes
				return encryption.decrypt(id_number_aes)
			except:
				return None

	def get_fnrs(self, patient_keys: list) -> list:
		"""get_fnrs Get decrypted id numbers for all in patient_keys

		Args:
			patient_keys (list): List if pseudonymized patient keys

		Returns:
			list: Patient ID numbers (fødselsnumre)
		"""
		return [ self.get_fnr(patient_key) for patient_key in patient_keys ]

	def no_dt_for_key(self, patient_key: str) -> bool:
		"""Check whether patient has dt_added key (ad hoc function)

		Args:
			patient_key (str): Pseudonymized patient key

		Returns:
			bool: has dt_added
		"""
		with Session(self.engine) as session:
			statement = select(
				exists().where(
					Patient.patient_key == patient_key,
					Patient.dt_added.is_(None),
				)
			)
			return session.exec(statement).one()
		