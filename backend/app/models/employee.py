class Employee:
    # 1. The Constructor (__init__)
    def __init__(self, eno, ename, dob, gender, salary, super_eno, dno):
        self.eno = eno
        self.ename = ename
        self.dob = dob
        self.gender = gender
        self.salary = salary
        self.super_eno = super_eno
        self.dno = dno

    # 2. A Method (Behavior)
    def display_info(self):
        return f"Employee: {self.ename} (ID: {self.eno}) works in Dept: {self.dno}"