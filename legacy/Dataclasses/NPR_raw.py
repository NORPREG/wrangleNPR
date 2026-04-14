from typing_extensions import Annotated
from pydantic import BaseModel, PlainSerializer, BeforeValidator, Field

from typing import Optional, List, Literal
from datetime import datetime

class NPR(BaseModel):    
    redcap_repeat_instance: str = Field('new', json_schema_extra={"transfer_only": True})
    redcap_repeat_instrument: str = Field('npr', json_schema_extra={"transfer_only": True})
    record_id: Optional[str] = Field(None, title="Pasientnøkkel i NORPREG", json_schema_extra={"transfer_only": True})

    InnDato: datetime = Field(None, title="Tidspunkt for start av fraksjon")
    UtDato: datetime = Field(None, title="Tidspunkt for slutt av fraksjon")
    Omsorg: Literal["3", "8"] = Field(None, title="Omsorgsnivå") # 3 = Poliklinisk; 8 = Inneliggende
    Kno: str = Field(None, title="Kontakt ID")
    Pkode: str = Field(None, title="Prosedyrekode")
    Intensjon: str = Field(None, title="Intensjon")
    Machine: str = Field(None, title="Maskin ID")
    RefVolumId: str = Field(None, title="Referansevolum ID")
    RefVolumNavn: str = Field(None, title="Referansevolum Navn")
    RegionKode: str = Field(None, title="Regionskode")
    RegionNavn: str = Field(None, title="Regionsnavn")
    PlanTotDose: float = Field(None, title="Totalt planlagt dose [Gy]")
    DoseKorr: float = Field(None, title="Dosekorreksjon [Gy]")
    DKMerknad: str = Field(None, title="Dosekorreksjon merknad")
    PlanDose: float = Field(None, title="Planlagt fraksjonskode [Gy]")
    GittDose: float = Field(None, title="Gitt fraksjonsdose [Gy]")
    PlanUID: str = Field(None, title="Plan UID")
    PIDno: str = Field(None, title="Pseudonymisert nøkkel i Aria", json_schema_extra={"document_only": True})
    PersNo: str = Field(None, title="Fødselsnummer", json_schema_extra={"document_only": True})
    Kjonn: Literal["1", "2"] = Field(None, title="Kjønn") # 1 mann, 2 kvinne
    Fodselsar: str = Field(None, title="Fødselsår", json_schema_extra={"document_only": True})
    Fodselsdato: str = Field(None, title="Fødselsdato")
    Komm: str = Field(None, title="Kommunenummer")
    Bydel: str = Field(None, title="Bydelsnummer", description="Kun relevant for Oslo")
    Hdiag: str = Field(None, title="Diagnosekode (ICD10)")
    NyPas: str = Field(None, title="Ny pasient?")
    BehSerieId: str = Field(None, title="Behandlingsserie ID", description="Benyttes som global Course ID") # DENNE ER COURSE ID FOR RESTEN
    BehSerieNavn: str = Field(None, title="Behandlingsserienavn")
    BehSerieStart: datetime = Field(None, title="Behandlingserie start")