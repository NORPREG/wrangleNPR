from config import Config
import logging
import requests
import json
import os

"""
This file is responsible for communication with the
REDCap REST API. Both in terms of fetching data and
sendfing data from RTDataModel.
"""

config = Config()
logger = logging.getLogger(__name__ + f" ({config.HF})")

error_message = {
	200: "OK",
	400: "Bad request",
	401: "Unauthorized",
	403: "Forbidden",
	404: "Not found",
	406: "Not acceptable",
	500: "Internal server error",
	501: "Not implemented"
}

# set correct SSL environment for REDCap certificate
# Not enough to have certificate in Windows MMC store "Trusted ROOT Certificate Authorities"

os.environ["SSL_CERT_FILE"] = config.redcap.certificate
os.environ["REQUESTS_CA_BUNDLE"] = config.redcap.certificate

def fetch_study_uids_from_redcap(patient = None) -> list:
	return fetch_field_from_redcap(patient, 'dcm_studies_uid')


def fetch_series_uids_from_redcap(patient = None) -> list:
	return fetch_field_from_redcap(patient, 'dcm_series_uid')


def fetch_md5sum_from_redcap(patient = None) -> str:
	return fetch_field_from_redcap(patient, 'dcm_md5')

def fetch_record_ids() -> list:
	fields = fetch_field_from_redcap(None, "record_id")
	record_ids = sorted({r["record_id"] for r in fields})
	return record_ids

def fetch_field_from_redcap(patient, field_name) -> list:
	fields = {
		'token': config.redcap.token,
		'content': 'record',
		'action': 'export',
		'format': 'json',
		'type': 'flat',
		'csvDelimiter': '',
		# 'records[0]': patient and patient.PatientID or '',
		'fields': field_name,
		'rawOrLabel': 'raw',
		'rawOrLabelHeaders': 'raw',
		'exportCheckboxLabel': 'false',
		'exportSurveyFields': 'false',
		'exportDataAccessGroups': 'false',
		'returnFormat': 'json'
	}

	try:
		r = requests.post(config.redcap.uri, data=fields, verify=True)
		r.raise_for_status()
	except requests.exceptions.HTTPError as err:
		logging.error(f"REDCap API error: {err}")
	else:
		logging.info("Data successfully retrieved from REDCap API")
	return r.json()

def send_json_to_redcap(json_data_model) -> None:
	if isinstance(json_data_model, dict):
		data = "[" + json.dumps(json_data_model) + "]"
	elif isinstance(json_data_model, list):
		data = json.dumps(json_data_model)
	else:
		raise Exception("json_data_model not properly formatted: ", type(json_data_model))

	fields = {
		'token': config.redcap.token,
		'content': 'record',
		'format': 'json',
		'type': 'flat',
		'overwriteBehavior': 'normal',
		'data': data,
	}

	try:
		r = requests.post(config.redcap.uri, data=fields, verify=config.redcap.certificate)
		r.raise_for_status()
	except requests.exceptions.HTTPError as err:
		print(r.text)
		logging.error(f"REDCap API error: {err}; {r.text}")
	else:
		print(r.text)
		logging.info("Data successfully posted to REDCap API")

def delete_patient_instrument(record_ids, instrument, repeat_instance) -> None:
	if isinstance(record_ids, list):
		record_ids = { f"records[{k}]": record_ids[k] for k in range(len(record_ids))}
	else:
		record_ids = {"records[0]": record_ids}

	fields = {
		'token': config.redcap.token,
		'action': 'delete',
		'content': 'record',
		'format': 'json',
		"repeat_instance": repeat_instance,
		'instrument': instrument,
		**record_ids
	}

	try:
		r = requests.post(config.redcap.uri, data=fields, verify=config.redcap.certificate)
		r.raise_for_status()
		print(r.text)
	except requests.exceptions.HTTPError as err:
		print(r.text)
		logging.error(f"REDCap API error: {err}; {r.text}")
	else:
		print(r.text)
		logging.info("Record {record_id} / instrument {instrument} deleted from REDCap")

def get_all_instruments() -> list:
	"""
	Retrieve all instrument/form names from the REDCap project.
	
	Returns:
		List of instrument names (e.g., ['demographics', 'clinical_data', 'lab_results'])
	"""
	fields = {
		'token': config.redcap.token,
		'content': 'metadata',
		'format': 'json',
		'returnFormat': 'json'
	}
	
	try:
		r = requests.post(config.redcap.uri, data=fields)
		r.raise_for_status()
	except requests.exceptions.HTTPError as err:
		logging.error(f"REDCap API error retrieving instruments: {err}")
		return []
	else:
		metadata = r.json()
		# Extract unique instrument names from metadata
		instruments = list(dict.fromkeys([field.get('form_name') for field in metadata if 'form_name' in field]))
		logging.info(f"Retrieved {len(instruments)} instruments from REDCap")
		return instruments

def delete_patient(record_id: str) -> None:
	data = {
		'token':  config.redcap.token,
		'action': 'delete',
		'content': 'record',
		'records[0]': record_id,
		'returnFormat': 'json'
	}

	r = requests.post(config.redcap.uri, data=data)
	return r.json()

def export_all(instruments: list = None, fields: list = None) -> dict:
	"""
	Export records from REDCap, optionally scoped to specific instruments or fields.
	
	Args:
		instruments: List of instrument names to include (e.g., ['demographics', 'clinical_data'])
		fields: List of specific field names to include (e.g., ['record_id', 'first_name', 'age'])
	
	Returns:
		Dictionary of exported records
	"""

	if not isinstance(instruments, list):
		instruments = [instruments]

	export_fields = {
		'token': config.redcap.token,
		'content': 'record',
		'returnFormat': 'json',
		'action': 'export',
		'format': 'json',
		"fields[0]": "record_id",
		'type': 'flat',
	}
	
	# Limit to specific forms/instruments
	if instruments:
		export_fields['forms'] = ','.join(instruments)

	# Limit to specific fields
	if fields:
		export_fields['fields'] = ','.join(fields)

	r = requests.post(config.redcap.uri, data=export_fields)
	r.raise_for_status()

	return r.json()


def export_all_instruments_scoped() -> dict:
	"""
	Export ALL instruments from REDCap, each with only its relevant fields.
	Returns a dictionary where keys are instrument names and values are the exported data.
	
	Returns:
		Dictionary mapping instrument names to their exported records
	"""
	instruments = get_all_instruments()
	if not instruments:
		logging.warning("No instruments found to export")
		return {}
	
	result = {}
	
	for instrument in instruments:
		try:
			logging.info(f"Exporting instrument: {instrument}")
			result[instrument] = export_all(instruments=[instrument])
		except requests.exceptions.HTTPError as err:
			logging.error(f"Failed to export instrument '{instrument}': {err}")
			result[instrument] = []
	
	return result

def is_uid_imported(uid):
	"""Check if study instance UID is in redcap project."""

	fetch_study_uids_from_redcap()
	if uid in fetch_field_from_redcap:
		return True
	else:
		return False