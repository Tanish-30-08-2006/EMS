class DeptLocation:
    def __init__(self, dno, dlocation):
        self.dno = dno
        self.dlocation = dlocation

    def get_location_info(self):
        return f"Department {self.dno} is located in {self.dlocation}."