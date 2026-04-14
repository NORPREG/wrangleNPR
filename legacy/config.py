from pathlib import Path
from module.Dataclasses.ConfigDataclass import ConfigDataclass
import tomlkit

CONFIG_DIR = "D:/Brokers/Config/DICOMBroker"

def get_config_object(path):
	config_obj_str = open(path.with_suffix(".toml"), "r").read()
	config_obj_dict = tomlkit.parse(config_obj_str)
	config_obj = ConfigDataclass(**config_obj_dict)
	return config_obj

class Singleton(type):
	_instances = {}
	def __call__(cls, *args, **kwargs):
		if cls not in cls._instances:
			cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
		return cls._instances[cls]

class Config(metaclass=Singleton):
	ALLOWED_HF = {
		'OUS': 'Oslo universitetssykehus',
		'HUS': 'Haukeland universitetssykehus',
		'SUS': 'Stavanger universitetssykehus',
		'SSHF': 'Sørlandet sykehus',
		'SIG': 'Sykehuset i Gjøvik',
		'AAL': 'Ålesund sjukehus',
		'SOH': 'St. Olavs Hospital',
		'NLSH': 'Nordlandssykehuset Bodø',
		'UNN': 'UNN Tromsø',
		'Test': 'Testsykehuset',
	}
	
	def __init__(self, HF = None):
		if HF:
			assert HF in self.ALLOWED_HF
			self.HF = HF
		else:
			self.HF = "Test"

		assert self.HF
		self.path = Path(CONFIG_DIR) / self.HF
		self.config_object = get_config_object(self.path)

	@property
	def hf(self):
		return self.config_object.hf

	@property
	def dvh(self):
		return self.config_object.dvh

	@property
	def logging(self):
		return self.config_object.logging

	@property
	def conquest(self):
		return self.config_object.conquest

	@property
	def redcap(self):
		return self.config_object.redcap

	@property
	def time_step(self):
		return self.config_object.time_step

	@property
	def rtmodel(self):
		return self.config_object.rtmodel

	@property
	def kodeliste(self):
		return self.config_object.kodeliste
	