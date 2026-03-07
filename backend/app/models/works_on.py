class WorksOn:
    # The Constructor
    def __init__(self, eno, pno, hours):
        self.eno = eno      # Link to Employee
        self.pno = pno      # Link to Project
        self.hours = hours  # Data specific to this link

    def get_work_summary(self):
        return f"Employee {self.eno} worked {self.hours} hours on Project {self.pno}."