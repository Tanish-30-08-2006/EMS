SET search_path TO "202401465", public;
-- 1. Create a formal schema for the project
CREATE SCHEMA IF NOT EXISTS company_ems;

-- 2. Tell the database to use this schema for all following commands
SET search_path TO company_ems;

-- 1. Department Table (Parent of Employee)
CREATE TABLE department (
    dno INT PRIMARY KEY,
    dname VARCHAR(50) NOT NULL UNIQUE,
    mgr_eno INT, -- We will link this to Employee later
    mgrstartdate DATE
);

-- 2. Project Table (Independent)
CREATE TABLE project (
    pno INT PRIMARY KEY,
    pname VARCHAR(50) NOT NULL,
    plocation VARCHAR(50),
    dno INT REFERENCES 
    department(dno)
);

-- 3. Employee Table 
CREATE TABLE employee (
    eno INT PRIMARY KEY,
    ename VARCHAR(50) NOT NULL,
    dob DATE,
    gender CHAR(1) CHECK (gender IN ('M', 'F')),
    salary DECIMAL(10, 2) CHECK (salary > 0),
    super_eno INT REFERENCES employee(eno), -- Self-referencing link
    dno INT REFERENCES department(dno)
);

-- 4. Dept_Locations (Links to Department)
CREATE TABLE dept_locations (
    dno INT REFERENCES department(dno),
    dlocation VARCHAR(50),
    PRIMARY KEY (dno, dlocation)
);

-- 5. Works_On (Links Employee to Project)
CREATE TABLE works_on (
    eno INT REFERENCES employee(eno),
    pno INT REFERENCES project(pno),
    hours DECIMAL(5, 1),
    PRIMARY KEY (eno, pno)
);

-- 6. Dependent (Links to Employee)
CREATE TABLE dependent (
    eno INT REFERENCES employee(eno),
    dependent_name VARCHAR(50),
    gender CHAR(1),
    dob DATE,
    relationship VARCHAR(20),
    PRIMARY KEY (eno, dependent_name)
);