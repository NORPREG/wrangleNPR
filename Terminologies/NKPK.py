class TerminologyNotFoundException(Exception):
    pass


class NKPK:
    def __init__(self):
        self.NKPK = dict()
        with open("Data/Terminologies/prosedyrekoder.csv", "r") as csv:
            for line in csv.readlines():
                lineparsed = line.split(";")
                self.NKPK[lineparsed[0]] = lineparsed[1].replace("\n", "")

    def getNKPKDefinition(self, code: str) -> str:
        if not code in self.NKPK:
            raise TerminologyNotFoundException(f"NKPK code not found: {code}")

        return self.NKPK.get(code)
