-- backend/app/database/tenant_template.sql
-- This template is executed within the context of a specific tenant schema.
-- The search_path is assumed to be already set by the ConnectionFactory.
-- 1. Department Table
CREATE TABLE department (
    dno INT PRIMARY KEY,
    dname VARCHAR(50) NOT NULL UNIQUE,
    mgr_eno INT,
    mgrstartdate DATE
);
-- 2. Project Table
CREATE TABLE project (
    pno INT PRIMARY KEY,
    pname VARCHAR(50) NOT NULL,
    plocation VARCHAR(50),
    dno INT REFERENCES department(dno)
);
-- 3. Employee Table 
CREATE TABLE employee (
    eno INT PRIMARY KEY,
    ename VARCHAR(50) NOT NULL,
    dob DATE,
    gender CHAR(1) CHECK (gender IN ('M', 'F')),
    salary DECIMAL(10, 2) CHECK (salary > 0),
    super_eno INT REFERENCES employee(eno),
    dno INT REFERENCES department(dno)
);
-- 4. Dept_Locations
CREATE TABLE dept_locations (
    dno INT REFERENCES department(dno),
    dlocation VARCHAR(50),
    PRIMARY KEY (dno, dlocation)
);
-- 5. Works_On
CREATE TABLE works_on (
    eno INT REFERENCES employee(eno),
    pno INT REFERENCES project(pno),
    hours DECIMAL(5, 1),
    PRIMARY KEY (eno, pno)
);
-- 6. Dependent
CREATE TABLE dependent (
    eno INT REFERENCES employee(eno),
    dependent_name VARCHAR(50),
    gender CHAR(1),
    dob DATE,
    relationship VARCHAR(20),
    PRIMARY KEY (eno, dependent_name)
);
-- 7. Audit Log
CREATE TABLE audit_log (
    log_id SERIAL PRIMARY KEY,
    table_name VARCHAR(50) NOT NULL,
    operation VARCHAR(10) NOT NULL,
    old_data JSONB,
    new_data JSONB,
    changed_at TIMESTAMP DEFAULT NOW()
);
-- 8. Audit Trigger Function
CREATE OR REPLACE FUNCTION fn_audit_log_changes() RETURNS TRIGGER AS $$ BEGIN IF (TG_OP = 'DELETE') THEN
INSERT INTO audit_log (table_name, operation, old_data, new_data)
VALUES (TG_TABLE_NAME, 'DELETE', to_jsonb(OLD), NULL);
RETURN OLD;
ELSIF (TG_OP = 'UPDATE') THEN
INSERT INTO audit_log (table_name, operation, old_data, new_data)
VALUES (
        TG_TABLE_NAME,
        'UPDATE',
        to_jsonb(OLD),
        to_jsonb(NEW)
    );
RETURN NEW;
ELSIF (TG_OP = 'INSERT') THEN
INSERT INTO audit_log (table_name, operation, old_data, new_data)
VALUES (TG_TABLE_NAME, 'INSERT', NULL, to_jsonb(NEW));
RETURN NEW;
END IF;
RETURN NULL;
END;
$$ LANGUAGE plpgsql;
-- 9. Attach Triggers to all Tables
CREATE TRIGGER trg_audit_department
AFTER
INSERT
    OR
UPDATE
    OR DELETE ON department FOR EACH ROW EXECUTE FUNCTION fn_audit_log_changes();
CREATE TRIGGER trg_audit_employee
AFTER
INSERT
    OR
UPDATE
    OR DELETE ON employee FOR EACH ROW EXECUTE FUNCTION fn_audit_log_changes();
CREATE TRIGGER trg_audit_project
AFTER
INSERT
    OR
UPDATE
    OR DELETE ON project FOR EACH ROW EXECUTE FUNCTION fn_audit_log_changes();
CREATE TRIGGER trg_audit_dept_locations
AFTER
INSERT
    OR
UPDATE
    OR DELETE ON dept_locations FOR EACH ROW EXECUTE FUNCTION fn_audit_log_changes();
CREATE TRIGGER trg_audit_works_on
AFTER
INSERT
    OR
UPDATE
    OR DELETE ON works_on FOR EACH ROW EXECUTE FUNCTION fn_audit_log_changes();
CREATE TRIGGER trg_audit_dependent
AFTER
INSERT
    OR
UPDATE
    OR DELETE ON dependent FOR EACH ROW EXECUTE FUNCTION fn_audit_log_changes();