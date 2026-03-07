class Dependent:
    def __init__(self, eno, dependent_name, gender, dob, relationship):
        self.eno = eno
        self.dependent_name = dependent_name
        self.gender = gender
        self.dob = dob
        self.relationship = relationship

    def __str__(self):
        return f"{self.dependent_name} ({self.relationship} of Employee {self.eno})"