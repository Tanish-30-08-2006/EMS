class Project:
    def __init__(self, pno, pname, plocation, dno):
        self.pno = pno
        self.pname = pname
        self.plocation = plocation
        self.dno = dno

    def get_details(self):
        return f"Project {self.pname} is located at {self.plocation}."