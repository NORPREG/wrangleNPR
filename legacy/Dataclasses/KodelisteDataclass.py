import os
from typing import Optional, List, Literal

import sqlalchemy
from sqlalchemy import Column, String
# from sqlalchemy_utils import database_exists, create_database
from sqlmodel import create_engine, Field, Session, SQLModel, select, Relationship
from datetime import date, datetime

from config import Config

config = Config()

# Synced with data_model 2025-11-17

class Registry(SQLModel, table=True):
	id: int = Field(default=None, index=True, primary_key=True)
	name: Optional[str] = None # KREST-XXX, NORPREG
	patients: list["Patient"] = Relationship(back_populates="registry")

class Patient(SQLModel, table=True):
	# patient_key is the registry-wide pseudonymization key for the patient
	patient_key: str = Field(default=None, index=True, primary_key=True)

	fk_registry_id: int = Field(default=None, index=True, foreign_key="registry.id")
	registry: "Registry" = Relationship(back_populates="patients")
	
	dt_added: Optional[datetime] = None
	id_number_aes: Optional[str] = None
	id_type: str
	
	birth_date_aes: Optional[str] = None # Trenger ved FH-nummer spesielt
	ois_patient_id: Optional[str] = None
	epj_patient_id: Optional[str] = None
	npr_patient_id: Optional[str] = None

	id_history: list["IDNumberHistory"] =  Relationship(back_populates="patient")
	addresses: list["Address"] = Relationship(back_populates="patient")
	courses: list["Course"] = Relationship(back_populates="patient")
	
class IDNumberHistory(SQLModel, table=True):
	id: int = Field(default=None, index=True, primary_key=True)

	fk_patient_key: str = Field(default=None, index=True, foreign_key="patient.patient_key")
	patient: "Patient" = Relationship(back_populates="id_history")

	id_number_aes: Optional[str] = None
	id_type: str # Literal["FNR", "DNR", "FHNR", "HNR"]
	dt_added: Optional[datetime] = None

class Address(SQLModel, table=True):
	id: int = Field(default=None, index=True, primary_key=True)

	fk_patient_key: str = Field(default=None, index=True, foreign_key="patient.patient_key")
	patient: "Patient" = Relationship(back_populates="addresses")
	
	dt_added: Optional[datetime] = None
	zip_code_aes: Optional[str] = None
	bydel_aes: Optional[str] = None
	kommune_nr_aes: Optional[str] = None

class Course(SQLModel, table=True):
	id: int = Field(default=None, index=True, primary_key=True)
	fk_patient_key: str = Field(default=None, index=True, foreign_key="patient.patient_key")
	patient: "Patient" = Relationship(back_populates="courses")

	datastatus: list["DataStatus"] = Relationship(back_populates="course")
	dt_added: Optional[datetime] = None
	ois_course_id_aes: Optional[str] = None
	epj_course_id_aes: Optional[str] = None

	map_series_uid: "MapSeriesUID" = Relationship(back_populates="course")
	map_study_uid: "MapStudyUID" = Relationship(back_populates="course")
	map_instance_uid: "MapInstanceUID" = Relationship(back_populates="course")

class DataStatus(SQLModel, table=True):
	id: int = Field(default=None, index=True, primary_key=True)
	fk_course_id: int = Field(default=None, index=True, foreign_key="course.id")
	course: "Course" = Relationship(back_populates="datastatus")
	dt_added: datetime

	epj_status: Optional[str] = None
	dicom_status: Optional[str] = None
	prom_status: Optional[str] = None

class MapSeriesUID(SQLModel, table=True):
	id: int = Field(default=None, index=True, primary_key=True)
	fk_course_id: int = Field(default=None, index=True, foreign_key="course.id")
	course: "Course" = Relationship(back_populates="map_series_uid")

	series_uid_orig: Optional[str] = None
	series_uid_pseudo: Optional[str] = None

class MapStudyUID(SQLModel, table=True):
	id: int = Field(default=None, index=True, primary_key=True)
	fk_course_id: int = Field(default=None, index=True, foreign_key="course.id")
	course: "Course" = Relationship(back_populates="map_study_uid")
	
	study_uid_orig: Optional[str] = None
	study_uid_pseudo: Optional[str] = None

class MapInstanceUID(SQLModel, table=True):
	# Mainly for MR, NM, PlanUID where this is neccessary
	id: int = Field(default=None, index=True, primary_key=True)
	fk_course_id: int = Field(default=None, index=True, foreign_key="course.id")
	course: "Course" = Relationship(back_populates="map_instance_uid")
	
	instance_uid_orig: Optional[str] = None
	instance_uid_pseudo: Optional[str] = None

"""
-> Must be its own database schema

class Study(SQLModel, table=True):
	id: int = Field(default=None, index=True, primary_key=True)

	name: Optional[str] = None
	conquest_name: Optional[str] = None
	description: Optional[str] = None
	contact_person: Optional[str] = None
	institution: Optional[str] = None
	email: Optional[str] = None
	store_until: Optional[date] = None

-> Must be its own database schema

class Export(SQLModel, table=True):
	# One row for each export action (may contain several patients)

	id: int = Field(default=None, index=True, primary_key=True)
	fk_study_id: int = Field(default=None, index=True, foreign_key="study.id")
	fk_registry_id: int = Field(default=None, index=True, foreign_key="registry.id")

	export_date: Optional[date] = None
	contact_person: Optional[str] = None
	institution: Optional[str] = None
	email: Optional[str] = None
	mechanism: Optional[str] = None
	is_pseudo: Optional[bool] = None

-> Must be its own database schema

class PatientExport(SQLModel, table=True):
	# Many-to-many collection of pseudo_keys for a given export action
	# FKs to export.id; patient.patient_key; course.id AND optionally study.id
	# Is it normalized then?

	id: int = Field(default=None, index=True, primary_key=True)
	fk_course_id: int = Field(default=None, index=True, foreign_key="course.id")
	fk_export_id: int = Field(default=None, index=True, foreign_key="export.id")

	pseudo_key: Optional[str] = None
"""

