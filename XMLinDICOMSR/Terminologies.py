class TerminologyNotFoundException(Exception):
    pass


class NKPK:
	def __init__(self):
		self.NKPK = dict()
		with open("../Data/Terminologies/prosedyrekoder.csv", "r") as csv:
			for line in csv.readlines():
				lineparsed = line.split(";")
				self.NKPK[lineparsed[0]] = lineparsed[1].replace("\n","")

    def getNKPKDefinition(self, code: str) -> str:
        if not code in self.NKPK:
            raise TerminologyNotFoundException(f"NKPK code not found: {code}")

        return self.NKPK.get(code)


class ICD10:
    def __init__(self):
        self.ICD10 = dict()
        with open("../Data/Terminologies/icd10.csv", "r") as csv:
            for line in csv.readlines():
                lineparsed = line[:-1].split(";")
                self.ICD10[lineparsed[0]] = lineparsed[1]

    def getICD10Definition(self, code: str) -> str:
        if not code in self.ICD10:
            raise TerminologyNotFoundException(f"ICD10 code not found: {code}")

        return self.ICD10.get(code)


class Region:
    def __init__(self):
        self.Region = dict()
        with open("../Data/Terminologies/regionskoder.csv", "r") as csv:
            for line in csv.readlines():
                lineparsed = line[:-1].split(";")
                self.Region[lineparsed[0]] = lineparsed[1]

    def getRegionDefinition(self, code: str) -> str:
        code = str(code)
        if not code in self.Region:
            raise TerminologyNotFoundException(f"Regionskode not found: {code}")

        return self.Region.get(code)
