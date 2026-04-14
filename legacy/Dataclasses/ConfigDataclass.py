from pydantic_settings import BaseSettings
from typing import Optional
from enum import Enum
from pathlib import PurePath

class DVH(BaseSettings):
	resolution_cgy: int
	gzip_compression_level: int
	basedir: str

class HFEnum(str, Enum):
	OUS = 'OUS'
	HUS = 'HUS'
	SUS = 'SUS'
	SSHF = 'SSHF'
	SIG = 'SIG'
	AAL = 'AAL'
	SOH = 'SOH'
	NLSH = 'NLSH'
	UNN = 'UNN'
	TEST = "Test"
	# Can add autoenum here: https://stackoverflow.com/questions/
	# 66655733/making-an-enum-more-flexible-in-pydantic
	# for more flexible naming later on

class HF(BaseSettings):
	HF: HFEnum

class Logging(BaseSettings):
	log_path: PurePath
	log_level: str

class ConquestBase(BaseSettings):
	aet: str
	server: str
	port: int
	app_dir: Optional[PurePath] = None
	app_exe: Optional[PurePath] = None
	app_dgate: Optional[PurePath] = None
	sql_uri: Optional[str] = None

class Conquest(BaseSettings):
	reg: ConquestBase
	stg: ConquestBase

class RTModel(BaseSettings):
	mappingfile: str
	use_rtrecord: bool
	use_npr: bool

class REDCap(BaseSettings):
	token: str
	uri: str
	certificate: str

class TimeStep(BaseSettings):
	between_sync: int
	for_sigterm: int

class Kodeliste(BaseSettings):
	aes_key: str
	sql_user: str
	sql_pass: str

class ConfigDataclass(BaseSettings):
	hf: HF
	dvh: DVH
	logging: Logging
	conquest: Conquest
	redcap: REDCap
	time_step: TimeStep
	rtmodel: RTModel
	kodeliste: Kodeliste