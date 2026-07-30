# Logikk bak WrangleNPR

Hver stråleterapienhet sender regelmessig ut NPR-filer (Norsk Pasientrapport).
Disse har som hovedformål å rapportere all aktivitet for å få tilbakebetalt IFR-milder.
En gevinst bak dette er at slike rapporter utgjør fasiten bak all stråleterapibehandling.

Per 2026-07 sendes disse rapportene ut tre ganger i året. En hyppiere forsendelse (også med delta-rapporter) vil komme.
Det er også mulig, spesielt i registersammenheng, å lage månedlige og ukentlige rappoter.

Filens oppsett er at først ligger metadata (f.eks. rapporteringsperiode, uttaksdato), før selve innholdet med header og selve data.
Metadata er markert med
```
++RTnpr Header Start++
++RTnpr Header End++
```

## Variabler
Følgende variabler er tilgjengelige (se NORPREG-repo for mer detaljer):

| Feltnavn | Beskrivelse | Datatype / kodeverk | Sendes til REDCap | Sendes til kodeliste |
|----------|-------------|---------------------|---|---|
| PIDno | Pseudonymisert nøkkel i Aria | `str` | Nei | Ja |
| PersNo | Fødselsnummer | `str` | Nei | Ja |
| Kjonn | Kjønn | `Literal["1", "2"]` — 1 = Mann, 2 = Kvinne | Ja | Nei |
| Fodselsar | Fødselsår | `str` | Ja | Ja |
| Fodselsdato | Fødselsdato | `str` | Ja | Nei |
| Komm | Kommunenummer | `str` | Ja | Nei |
| Bydel | Bydelsnummer (kun relevant for Oslo) | `str` | Ja | Nei |
| Frasted | Sted (fra) | `str` | Nei | Nei |
| Debitor | Debitor | `str` | Nei | Nei |
| Omsorg | Omsorgsnivå | `Literal["3", "8"]` — 3 = Poliklinisk, 8 = Inneliggende | Ja | Nei |
| TilSted | Sted (til) | `str` | Nei | Nei |
| InnDato | Tidspunkt for start av fraksjon | `datetime` | Ja | Nei |
| UtDato | Tidspunkt for slutt av fraksjon | `datetime` | Ja | Nei |
| Kno | Unik identifikator for oppmøte / behandlingsfraksjon | `str` | Ja | Nei |
| Hdiag | Diagnosekode | ICD-10 | Ja | Nei |
| Pkode | Prosedyrekode | NKPK | Ja | Nei |
| NyPas | Ny pasient — første fraksjon (1) eller ikke (0) | `str` | Ja | Nei |
| BehSerieId | Behandlingsserie ID (global Course ID) | `str` | Ja | Nei |
| BehSerieNavn | Behandlingsserienavn | `str` | Ja | Nei |
| BehSerieStart | Behandlingsserie start | `datetime` | Ja | Nei |
| Intensjon | Behandlingsintensjon, f.eks. kurativ eller palliativ | `str` | Ja | Nei |
| Machine | Unik identifikator for behandlingsmaskinen | `str` | Ja | Nei |
| RefVolumId | Referansevolum ID | `str` | Ja | Nei |
| RefVolumNavn | Referansevolum navn | `str` | Ja | Nei |
| RegionKode | Regionskode | `str` | Ja | Nei |
| RegionNavn | Regionsnavn | `str` | Ja | Nei |
| PlanTotDose | Totalt planlagt dose til primært normeringsvolum | `float` — Gy | Ja | Nei |
| DoseKorr | Dosekorreksjon, legges til ved rebestrålinger | `float` — Gy | Ja | Nei |
| DKMerknad | Dosekorreksjon merknad | `str` | Ja | Nei |
| PlanDose | Planlagt fraksjonsdose til primært normeringsvolum | `float` — Gy | Ja | Nei |
| GittDose | Gitt fraksjonsdose til primært normeringsvolum | `float` — Gy | Ja | Nei |
| PlanUID | Unik identifikator for behandlingsplanen (SOP Instance UID) [ikke implementert for alle HF] | `str` — DICOM (0008,0018) | Ja | Nei |

Ulike stråleterapienheter benytter ulike skrivemetoder, så en mapping mellom dem er nødvendig. Spesielt fjernes kapitalisering under parsing. Registeret benytter Oslo universitetssykehus' skrivemåte.

Ett eksempel er at rapporten fra Haukeland universitetssykehus mappes slik:
```
mapper = {
    "HUS": {
        "UtDato": "UtDato",
        "KNo": "Kno",
        "Maskin": "Machine",
        "RefVolID": "RefVolumId",
        "RefVolNavn": "RefVolumNavn",
        "BehSerieID": "BehSerieId"
    }
}
```
Felles er rekkefølgen.

De ulike enhetene jobber også med å få inn feltet ´PlanUid´ for en angitt behandlingsplan, dette legges til *på slutten* av CSV-raden.

[Detaljer om de ulike variablene finnes her](https://www.fhi.no/he/npr/statistikk-npr/straleterapi/).

I forsendelsestidspunktet vil ikke alle data være komplette. For eksempel vil det for pasienter som er underveis i behandlingen sin bare rapporteres faktisk utført aktivitet, og ikke planlagt aktivitet. Derfor vil ofte ikke statistikken for et år være ferdig før mars/april påfølgende år.

I mange tilfeller utføres det også korreksjoner underveis i behandlingsforløpet, slik at tidligere innsendte data må overskrives ved mottak av nye NPR-rapporter. Eksempel på hyppige oppdaterte felt er (i synkende frekvens)
* plantotdose
* hdiag
* intensjon
* bydel
* omsorg
* komm
* machine
* dosekorr

For hvert helseforetak lagres det CSV-filer. De legges i mapper etter år, slik: < HF > / < år > / *.csv
Dersom det f.eks. rapporteres fra flere behandlingssteder under ett HF kan de ordnes etter én CSV-fil per HF.
Dersom det kommer nye filer med sprikende informasjon bør de gamle filene slettes eller legges under old/.
* TODO: Ønsker funksjonalitet for å vurdere filer etter forsendelsestidspunkt. Dette finnes i filens metadata.

Det er viktig at innholdet i registeret inneholder til en hver tid de sist rapporterte dataene.

### Unikheten i en rad
Hovedorganiseringen skjer etter `Kno`, eller Kontakt ID. Dette betegner én aktivitet for pasienten, angitt av `pkode` (doseplanlegging eller behandlingsfraksjon). Man kan likevel ikke mappe `Kno` mot fraksjoner, siden det under én fraksjon rapporteres for hvert behandlingsvolum `RefVolumNavn` under behandling. I tillegg kan det gis replanlegging med ulik `PlanUid`. I utgangspunktet vil det være en endring i `PlanUid` mellom behandlingsfraksjoner, men det kan ikke garanteres.

Derfor vil en unik rad betegnes av nøkkelen (`Kno`, `RefVolumNavn`, `PlanUid`).
Denne kalles for `TUPLE_KEY` i koden, og benyttes flere ganger.

# Funksjonaliteten i koden
Etter en konfigurasjon (HF, hvilket år det skal letes etter) hentes alle relevante filene ut med ´glob´.
Disse gis til ´pandas´ som lager en ´df´ per fil. Disse settes sammen (`df.concat`) 
Pythonkoden leter etter headerlinjen i forkant av parsing.
Så leses alle variablene inn.

## Synkroniser mot Kodeliste
Se over alle pasientene i CSV, og let etter eksisterende fødselsnummer med `norpreg.KodelisteInterface.check_patient`
* TODO: Se om samme `PIDno` opptrer flere ganger med ulikt fødselsnummer, og dersom det ligger inn et D-nummer må dette oppdateres.
* TODO: Skriv en funksjon som gjør datavask og leter etter slike tilfeller i databasen
* TODO: Sjekk om `PIDno` er lagret i Kodeliste.

## Last inn nye data
Last ut alle data fra CSV inn i en `pandas` dataframe.
Remap dem slik at de følger navnestandard (`remap_to_redcap(df)`)
Last ut alle data fra REDCap. Last dem over i et nytt objekt med alle REDCaps `TUPLE_KEY` rader.
Lag en ny nøkkel i CSV dataframe basert på `TUPLE_KEY`. For hvert nøkkel som er tilstede i begge objektene, fjern dem fra CSV objektet.
Konverter redusert CSV dataframe til en `dict` som kan gis til REDCap API.
Bruk `norpreg.REDCapInterface.send_json_to_redcap(json_data)` for å sende nye rader til KREST.
Dette gjelder også for en enkelt pasient som får komplettert dataene sine (f.eks. ved å gjennomføre flere aktiviteter mellom rapporteringsperioder).

## Overskriv oppdaterte data
Dersom opplysninger endres mellom to innsendinger, må siste versjon benyttes.
Dette skjer ved å først sammenlikne alle rader i ny CSV mot REDCap, først identifisert gjennom `TUPLE_KEY`.
* Oppfyller *alle* kolonner `CSV(TUPLE_KEY) = REDCap(TUPLE_KEY)`?
Dersom det er ulikheter, lages en delta payload som sendes til REDCap. Eksempel:
```
[
    { 
        'record_id': '12dl23kjd',
        'redcap_repeat_instrument': 'npr',
        'redcap_repeat_instance': 45, // identifiserer NPR raden for aktuell pasient
        'plantotdose': 68.0 // var 60.0 i forrige forsendelse
    }
]
```

Merk at dersom en verdi skal slettes (f.eks. bydel til ""), må man i API-kallet sette ```{'overwriteBehavior': 'overwrite'}```.

## Annen datavask

### Dupliserte rader
Det har vært behov for å fjerne dupliserte rader. Dette har manifestert seg gjennom (hittil) to kopier av `TUPLE_KEY` sett på én pasient.
Da har det vært enkelt gjennom REDCap å bekrefte at hele NPR-historikken er duplisert.
Da benyttes en tredje kjøremetodikk for å idenfisere hvem det gjelder, og etter en manuell kontroll via `print`s sendes et kall 
```
norpreg.REDCAPInterface.delete_patient_instrument(record_ids: list, instrument: str, repeat_instance: str)
```