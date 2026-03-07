class Department:
    # 1. The Constructor (__init__)
    def __init__(self, dno, dname, mgr_eno, mgrstartdate):
        self.dno = dno
        self.dname = dname
        self.mgr_eno = mgr_eno
        self.mgrstartdate = mgrstartdate

    # 2. A Method (Behavior)
    def __str__(self):
        return f"Department: {self.dname} (ID: {self.dno})"