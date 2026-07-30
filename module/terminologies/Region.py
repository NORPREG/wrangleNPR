class TerminologyNotFoundException(Exception):
    pass


class Region:
    def __init__(self):
        self.Region = dict()
        with open("Data/Terminologies/regionskoder.csv", "r") as csv:
            for line in csv.readlines():
                lineparsed = line[:-1].split(";")
                self.Region[lineparsed[0]] = lineparsed[1]

    def getRegionDefinition(self, code: str) -> str:
        code = str(code)
        if not code in self.Region:
            raise TerminologyNotFoundException(f"Regionskode not found: {code}")

        return self.Region.get(code)
