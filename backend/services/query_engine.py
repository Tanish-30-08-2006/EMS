# ==================================================================================================
# /backend/services/query_engine.py
# ==================================================================================================
# THE CORE ENGINE: This file is the "Central nervous system" of the entire application. 
# Its only job is to translate human requests into Database commands (SQL).
# 
# ARCHITECTURAL OVERVIEW:
# 1. TENANCY ISOLATION: 
#    The system uses a 'Shared-Schema, Dedicated-Vault' approach. 
#    While every company technically uses the same database software, their data is 
#    locked behind individual 'Tenant IDs'. This file ensures that a user from 
#    Company A can NEVER see data from Company B.
#
# 2. THE BRIDGE PATTERN:
#    This file acts as a translator. Python is great for users, but SQL is the 
#    native language of data. Functions like 'get_all_employees' handle the 
#    translation seamlessly so the rest of the app doesn't have to worry about SQL.
#
# 3. SAFETY FIRST (SQL INJECTION DEFENSE):
#    We never, ever "Glue" search strings directly into SQL commands. 
#    Instead, we use %s placeholders. This sends the search terms to the database 
#    in a separate, safe bucket, making it impossible for hackers to trick 
#    the system into running unauthorized commands.
#
# 4. TRANSACTION INTEGRITY:
#    When we save data (using '.commit()'), we ensure that either the WHOLE change 
#    is saved, or NONE of it is. This prevents "Partial Data" from corrupting 
#    the company registries if the power goes out or a crash occurs.
#
# Think of this file as a bridge. On one side, we have our Python CLI (the user interface).
# On the other side, we have a massive PostgreSQL Database (the vault where data lives).
# This file handles the heavy lifting of opening connections, finding data, and saving changes.
# ==================================================================================================

# --------------------------------------------------------------------------------------------------
# SYSTEM IMPORTS: The Toolbox
# --------------------------------------------------------------------------------------------------
# We bring in these specialized tools to help the application handle complex tasks.
# Each of these libraries is like a specialist hired to perform one specific job.
# --------------------------------------------------------------------------------------------------
import json                             # To pack audit logs into a single 'JSON' string for the database.
import csv                              # To parse CSV files for bulk employee import.
import os                               # To interact with the operating system for file operations.
from datetime import datetime            # To record the exact moment (Time & Date) that actions occur.
from decimal import Decimal             # To handle money (salaries/billings) without rounding errors.
from tabulate import tabulate           # To turn messy database lists into beautiful, readable tables.
import psycopg2.extras                  # The "Translator" that lets Python talk to the PostgreSQL server.
from psycopg2 import sql                # The "Security Guard" that helps us write safe, injection-proof SQL.
from app.core.connection_factory import ConnectionFactory  # The "Key Maker" for company database vaults.

# --------------------------------------------------------------------------------------------------
# DATA MODELS: Turning "Raw Text" into "Smart Objects"
# --------------------------------------------------------------------------------------------------
# When we get data from the database, it's just a row of text and numbers.
# We import these models so we can turn those rows into "Python Objects".
# This means instead of using indices like row[0], we can say employee.name.
# It makes the code viel more human and easier for developers to read and maintain.
# --------------------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------------------
# DATA MODELS: Turning "Raw Text" into "Smart Objects"
# --------------------------------------------------------------------------------------------------
# When we pull records from the database vault, they are just strings and numbers.
# These models act like blueprints. They take that raw data and build high-level objects.
# This makes the rest of the app much more humanized and easier to work with.
# --------------------------------------------------------------------------------------------------
from app.models.employee import Employee        # The blueprint for an individual worker.
from app.models.department import Department    # The blueprint for an organizational unit.
from app.models.project import Project          # The blueprint for a company initiative.
from app.models.dependent import Dependent      # The blueprint for family members of staff.
from app.models.dept_locations import DeptLocation # The blueprint for office buildings.
from app.models.works_on import WorksOn        # The blueprint for project-staff links.
from app.models.audit_log import AuditLog      # The blueprint for security trail records.

# --------------------------------------------------------------------------------------------------
# SESSION CONTEXT: Remembering "Who is logged in?"
# --------------------------------------------------------------------------------------------------
# This variable acts like a "Sticky Note" on the system's brain.
# It stores the 'Tenant ID' (the unique ID for the company currently using the system).
# Without this, the system wouldn't know which filing cabinet to open!
# --------------------------------------------------------------------------------------------------
CURRENT_TENANT_ID = None

def set_current_tenant(tenant_id):
    """
    THE IDENTITY SWITCH:
    This function is called the moment a company logs in successfully. 
    It takes the unique ID of that company and pins it to our global 'Sticky Note'.
    This is how the system isolated one company's data from another.
    """
    # 1. We use 'global' to tell Python to modify the note defined outside this function.
    global CURRENT_TENANT_ID            
    
    # 2. We overwrite the note with the current company's ID.
    # From this point on, every query will use this ID to find the right vault.
    CURRENT_TENANT_ID = tenant_id       
    
    # 3. Diagnostic Log (Humanized):
    # This helps developers see that the system has successfully "Switched Brains"
    # to the new company workspace context.
    print(f"[ENGINE LOG]: System context locked to Tenant: {tenant_id}")


# ==============================================================================
# SECTION 1: EMPLOYEE MANAGEMENT (The People Database)
# ==============================================================================

def get_all_employees():
    """
    FETCHES EVERY EMPLOYEE: 
    Think of this as walking into the HR room and opening the master registry.
    It looks at every single person currently employed by the company.
    """
    # 1. First, we check if anyone is even logged in.
    if not CURRENT_TENANT_ID: 
        return []

    # 2. We ask our 'ConnectionFactory' to open a door to this specific company's database.
    # The 'with' keyword ensures that the door closes automatically when we are done.
    with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
        
        # 3. We create a 'Cursor'. Think of a cursor as a professional librarian. 
        # You give it a request, and it goes into the aisles to find the data.
        # 'DictCursor' is special: it lets us access data by NAME (like 'ename') instead of just ID.
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            
            # 4. We tell the librarian exactly what to find and how to sort it.
            cur.execute("SELECT * FROM employee ORDER BY eno ASC;")
            
            # 5. 'fetchall()' brings back the entire pile of records that the librarian found.
            rows = cur.fetchall()
            
            # 6. We loop through every raw row and turn it into a high-level 'Employee' object.
            # This makes the data much easier for the CLI (cli_main.py) to work with.
            employee_objects = []
            for r in rows:
                obj = Employee(
                    r['eno'],           # Employee Number
                    r['ename'],         # Name
                    r['dob'],           # Date of Birth
                    r['gender'],        # M/F/O
                    r['salary'],        # Pay scale
                    r['super_eno'],     # Who is their manager?
                    r['dno']            # Which department do they work in?
                )
                employee_objects.append(obj)
            
            return employee_objects


def add_new_employee(e):
    """
    SAVES A NEW PERSON: 
    This is like filling out a 'New Hire' form and filing it away. 
    It takes an Employee Object 'e' and inserts it into the real system records.
    """
    if not CURRENT_TENANT_ID: 
        return False
        
    try:
        # 1. Connect to the company's private space.
        with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
            
            # 2. Get our librarian (Cursor) ready to write.
            with conn.cursor() as cur:
                
                # 3. We use %s placeholders. This is very important! It's like leaving blank spots 
                # on a form to prevent SQL Injection attacks. The database handles the values safely.
                sql_command = """
                    INSERT INTO employee (eno, ename, dob, gender, salary, super_eno, dno) 
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                
                # 4. We 'Execute' the command with the actual data from the object.
                cur.execute(sql_command, (e.eno, e.ename, e.dob, e.gender, e.salary, e.super_eno, e.dno))
            
            # 5. 'Commit' is like clicking the 'Save' button. 
            # If we don't commit, the changes vanish when we close the connection!
            conn.commit()
            
        return True
        
    except Exception as e_err:
        # If anything goes wrong (like a duplicate ID), we catch the error here.
        print(f"[DATABASE ERROR]: {e_err}")
        return False


def get_employee_by_id(eno):
    """
    THE SINGLE SEARCH:
    Finds one specific person using their unique 'Employee Number' (eno).
    """
    if not CURRENT_TENANT_ID: 
        return None

    with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            
            # We look for exactly one person where the eno matches.
            cur.execute("SELECT * FROM employee WHERE eno = %s;", (eno,))
            
            # 'fetchone()' is efficient—it stops searching as soon as it finds the first match.
            r = cur.fetchone()
            
            if r:
                return Employee(r['eno'], r['ename'], r['dob'], r['gender'], r['salary'], r['super_eno'], r['dno'])
            
            return None


def search_employees_by_name(search_term):
    """
    THE NAME SEARCH:
    Finds all employees whose name contains the search term (case-insensitive).
    Uses ILIKE for partial matching — searching 'ali' will find 'Alice' and 'Malik'.
    Returns a list of Employee objects sorted by name.
    """
    if not CURRENT_TENANT_ID:
        return []

    with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT * FROM employee WHERE ename ILIKE %s ORDER BY ename ASC;",
                (f"%{search_term}%",)
            )
            rows = cur.fetchall()
            return [
                Employee(r['eno'], r['ename'], r['dob'], r['gender'],
                         r['salary'], r['super_eno'], r['dno'])
                for r in rows
            ]


def bulk_import_employees(employee_list):
    """
    THE BULK LOADER:
    Accepts a list of Employee objects and inserts them all in a single database
    transaction. If ANY single row fails (duplicate ID, invalid dept, bad data),
    the ENTIRE batch is rolled back — no partial imports ever corrupt the database.
    Returns a tuple: (success_count, error_list)
    - success_count: how many rows were inserted
    - error_list: list of strings describing which rows failed and why
    """
    if not CURRENT_TENANT_ID:
        return 0, ["No active session."]

    errors = []
    success_count = 0

    try:
        with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
            with conn.cursor() as cur:
                for e in employee_list:
                    try:
                        cur.execute(
                            """INSERT INTO employee (eno, ename, dob, gender, salary, super_eno, dno)
                               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                            (e.eno, e.ename, e.dob, e.gender, e.salary, e.super_eno, e.dno)
                        )
                        success_count += 1
                    except Exception as row_error:
                        errors.append(f"Row ENO={e.eno} ({e.ename}): {str(row_error).splitlines()[0]}")
                        conn.rollback()
                        # Re-open cursor after rollback to continue checking remaining rows
                        # but we still won't commit any — full-batch or nothing
                        return success_count, errors
            conn.commit()
        return success_count, errors

    except Exception as batch_error:
        return 0, [f"Batch failed entirely: {str(batch_error)}"]


def delete_employee(eno):
    """
    THE REMOVAL TRIGGER:
    Removes a person from the records permanently. 
    WARNING: This action is final and tracked by the Audit Log.
    """
    if not CURRENT_TENANT_ID: 
        return False
        
    try:
        with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
            with conn.cursor() as cur:
                # Tell the database to purge the record with this specific ID.
                cur.execute("DELETE FROM employee WHERE eno = %s;", (eno,))
            
            # Don't forget to save (Commit)!
            conn.commit()
        return True
    
    except Exception as e:
        print(f"Error purging employee record: {e}")
        return False


def update_employee_salary(eno, new_salary):
    """
    THE PAYROLL ADJUSTER:
    This function modifies the financial record for a specific employee. 
    It is used for raises, bonuses, or contractual adjustments.
    """
    # IDENTITY PROTECTION:
    # Always confirm we are working within a valid company session.
    if not CURRENT_TENANT_ID: 
        return False
        
    try:
        # THE CONNECTION (The Secure Path):
        # Establish a secure data line to the company's private database.
        # 'with' handles the cleanup for us automatically.
        with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
            
            # THE CURSOR (The Data Modifier):
            # We create a librarian (cursor) focused on overwriting existing data.
            # 'psycopg2' manages the communication with the PostgreSQL server.
            with conn.cursor() as cur:
                
                # THE SQL COMMAND (Update Logic):
                # "UPDATE employee" tells the system which table to modify.
                # "SET salary = %s" points to the specific box we want to change.
                # "WHERE eno = %s" acts as a surgical filter—we only want to change ONE person's pay.
                # We use %s to keep the data safe from hackers (SQL Injection prevention).
                sql_update = "UPDATE employee SET salary = %s WHERE eno = %s;"
                
                # THE EXECUTION (Triggering the Change):
                # 'cur.execute' sends the new salary value and the employee ID to the database.
                cur.execute(sql_update, (new_salary, eno))
                
            # THE COMMIT (Finalizing the Deal):
            # Without 'conn.commit', the database won't actually save the new salary.
            # This is our "Confirmation" that the change is intentional and permanent.
            conn.commit()
            
        return True
        
    except Exception as payroll_error:
        # THE FALLBACK:
        # If the salary value is invalid or the connection drops, we catch the error here.
        print(f"[PAYROLL SYSTEM]: Critical error during salary update: {payroll_error}")
        return False


def transfer_employee(eno, new_dno):
    """
    THE DEPARTMENT TRANSFER:
    Moves an employee from their current department to a new one by updating
    the 'dno' field on the employee record. The existing audit trigger fires
    automatically — no extra audit code needed.
    Performs three application-level guards before touching the database:
      Guard 1 — Employee must exist.
      Guard 2 — Target department must exist.
      Guard 3 — Target department must differ from current (no no-op transfers).
    Returns (True, old_dno) on success, (False, error_string) on any failure.
    old_dno is returned so the CLI can display a clear "FROM X TO Y" message.
    """
    if not CURRENT_TENANT_ID:
        return False, "No active session."

    try:
        with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:

                # ── Guard 1: Employee must exist ─────────────────────────────
                cur.execute(
                    "SELECT dno, ename FROM employee WHERE eno = %s;", (eno,))
                emp_row = cur.fetchone()
                if not emp_row:
                    return False, f"No employee found with ID {eno}."

                old_dno = emp_row['dno']
                ename   = emp_row['ename']

                # ── Guard 2: Target department must exist ────────────────────
                cur.execute(
                    "SELECT dname FROM department WHERE dno = %s;", (new_dno,))
                dept_row = cur.fetchone()
                if not dept_row:
                    return False, (f"Department {new_dno} does not exist. "
                                   f"Transfer cancelled.")

                # ── Guard 3: Must be a different department ──────────────────
                if old_dno == new_dno:
                    return False, (f"{ename} is already in Department {new_dno}. "
                                   f"No transfer needed.")

                # ── All guards passed: execute transfer ──────────────────────
                cur.execute(
                    "UPDATE employee SET dno = %s WHERE eno = %s;",
                    (new_dno, eno)
                )

            conn.commit()

        return True, old_dno

    except Exception as transfer_error:
        return False, str(transfer_error)


# ==================================================================================================
# SECTION 2: DEPARTMENT MANAGEMENT (The Organizational Units)
# ==================================================================================================
# This section handles the "Skeleton" of the company: Departments like HR, IT, and Finance.
# It tracks who manages which team and when they started their leadership role.
# ==================================================================================================

def get_all_departments():
    """
    THE STRUCTURE VIEW: 
    This function fetches a complete list of every department in the company.
    It provides a high-level view of how many teams exist in the organization.
    """
    # SESSION GUARD:
    # Ensure a tenant is logged in before we attempt to read their records.
    if not CURRENT_TENANT_ID: 
        return []

    # THE SECURE TUNNEL (The Connection):
    # Establish a private connection to the company's designated storage vault.
    with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
        
        # THE LIBRARIAN (The Dictionary Cursor):
        # We use 'DictCursor' because it's much easier to work with names like 'dname' 
        # than just column numbers. It makes our mapping logic human-readable.
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            
            # THE COMMAND (SQL Query):
            # "SELECT *" means gather all columns (DNO, DNAME, Manager ID, Start Date).
            # "ORDER BY dno ASC" keeps the list logically sorted by their ID number.
            cur.execute("SELECT * FROM department ORDER BY dno ASC;")
            
            # THE FETCH (Gathering the Inventory):
            # 'cur.fetchall' pulls all the found department records out of the database vault
            # and hands them over to the Python environment as a list of rows.
            rows = cur.fetchall()
            
            # THE WRAPPING (Raw Data to Smart Objects):
            # We take each row and turn it into a 'Department' Python object.
            # This allows the rest of the application to treat data like real entities.
            department_registry = []
            
            for r in rows:
                # We build a new Department object for every entry found by the librarian.
                obj = Department(
                    r['dno'],           # The Department's Unique Number (ID)
                    r['dname'],         # The human name of the team (e.g., "RESEARCH")
                    r['mgr_eno'],       # The Employee Number of the person who leads this team
                    r['mgrstartdate']   # The date this person officially became the manager
                )
                department_registry.append(obj)
            
            # Deliver the final list of team objects back to the user.
            return department_registry


def add_new_department(d):
    """
    THE TEAM REGISTRATION:
    This function adds a new department 'd' to the company's organizational map.
    It is the technical way of creating a new division within the system.
    """
    # AUTHENTICATION CHECK:
    # Verify the current company context is active.
    if not CURRENT_TENANT_ID: 
        return False
        
    try:
        # THE BRIDGE (The Connection):
        # Open the data doors to the specific company's database schema.
        with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
            
            # THE WRITING LIBRARIAN (The Cursor):
            # Create a worker who is authorized to write new entries into the 'department' table.
            with conn.cursor() as cur:
                
                # THE PROTECTED COMMAND (SQL Template):
                # We use %s blanks to ensure the department data is handled safely.
                # This protects the system from malicious code (SQL Injection).
                sql_insert = "INSERT INTO department (dno, dname, mgr_eno, mgrstartdate) VALUES (%s, %s, %s, %s)"
                
                # THE EXECUTION (Writing to Disk):
                # 'cur.execute' sends the department details from the object to the database.
                cur.execute(sql_insert, (d.dno, d.dname, d.mgr_eno, d.mgrstartdate))
            
            # THE COMMIT (The Permanent Vault Lock):
            # 'conn.commit' tells the database to permanently save this new department.
            # Until this line runs, the new team isn't officially part of the company.
            conn.commit()
            
        return True
        
    except Exception as creation_error:
        # ERROR LOGGING:
        # If the department number already exists or data is invalid, we capture it here.
        print(f"[SYSTEM LOG]: Could not register new team: {creation_error}")
        return False


def get_department_by_id(dno):
    """
    THE BRANCH LOOKUP:
    Finds one specific department using its unique identification number (dno).
    """
    # PRE-FLIGHT CHECK:
    # Always ensure a session is active.
    if not CURRENT_TENANT_ID: 
        return None

    # THE CONNECTION (Data Portal):
    # Establish a line of communication to the company's database cluster.
    with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
        
        # THE LIBRARIAN (Scanning Cursor):
        # We use 'DictCursor' to make the row data easy to map to our model.
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            
            # THE COMMAND (Targeted Search):
            # "SELECT *" gathers all columns. "WHERE dno = %s" stops at the exact match.
            cur.execute("SELECT * FROM department WHERE dno = %s;", (dno,))
            
            # THE FETCH (Single Row Retrieval):
            # 'cur.fetchone' is optimized for finding a single unique entry.
            row = cur.fetchone()
            
            # MAPPING (Database to Python):
            # If the librarian found the record, we package it in a smart 'Department' object.
            if row:
                return Department(
                    row['dno'], 
                    row['dname'], 
                    row['mgr_eno'], 
                    row['mgrstartdate']
                )
            
            # If no match was found, we return nothing.
            return None


def delete_department(dno):
    """
    THE STRUCTURE PURGE:
    Removes a department permanently from the system registry.
    This is usually used when a department is merged or dissolved.
    """
    # SECURITY GATE:
    # Ensure current authentication before purging data.
    if not CURRENT_TENANT_ID: 
        return False
        
    try:
        # DATA TUNNEL (The Connection):
        # Connect to the private data vault.
        with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
            
            # THE REMOVAL WORKER (The Cursor):
            # Create a librarian focusing on deleting entries.
            with conn.cursor() as cur:
                
                # THE DESTRUCTIVE SQL:
                # "DELETE FROM department" starts the purge process.
                # "WHERE dno = %s" ensures only the targeted department is removed.
                cur.execute("DELETE FROM department WHERE dno = %s;", (dno,))
            
            # THE COMMIT (Finalizing the Purge):
            # Make the deletion permanent on the storage drive.
            conn.commit()
        
        return True
        
    except Exception as purge_error:
        # HANDLING ERRORS:
        # Capture and report issues like "Foreign Key Violations" (e.g., people still work there).
        print(f"[SECURITY ALERT]: Error during department removal: {purge_error}")
        return False


def update_department_manager(dno, mgr_eno):
    """
    THE LEADERSHIP SWAP:
    Assigns a new Employee as the manager of an existing Department.
    This updates the 'mgr_eno' column in the database records.
    """
    # SESSION VERIFICATION:
    # Confirm who is logged in.
    if not CURRENT_TENANT_ID: 
        return False
        
    try:
        # SECURE CONNECTION:
        # Establish the data line.
        with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
            
            # THE CURSOR (The Data Swapper):
            # Create a worker librarian to update existing records.
            with conn.cursor() as cur:
                
                # THE SQL UPDATE (Leadership Change):
                # "UPDATE department" identifies the table.
                # "SET mgr_eno = %s" specifies the new manager's ID.
                # "WHERE dno = %s" targets the specific department we are changing.
                sql_update_mgr = "UPDATE department SET mgr_eno = %s WHERE dno = %s;"
                
                # THE EXECUTION (Applying the Change):
                # 'cur.execute' sends the swap request to the database.
                cur.execute(sql_update_mgr, (mgr_eno, dno))
                
            # THE COMMIT (Saving the Swap):
            # Permanently record the new leadership assignment.
            conn.commit()
            
        return True
        
    except Exception as leadership_error:
        # EXCEPTION CAPTURE:
        # If the manager ID doesn't exist, the database will raise an error here.
        print(f"[OPS ERROR]: Leadership change failed in the database: {leadership_error}")
        return False


def get_payroll_summary():
    """
    THE PAYROLL REPORT:
    Aggregates salary data grouped by department.
    For each department returns: department number, department name,
    headcount (number of employees), total salary bill, average salary,
    highest salary, and lowest salary.
    Returns a list of raw tuples from the database.
    """
    if not CURRENT_TENANT_ID:
        return []

    with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    d.dno,
                    d.dname,
                    COUNT(e.eno)        AS headcount,
                    SUM(e.salary)       AS total_salary,
                    AVG(e.salary)       AS avg_salary,
                    MAX(e.salary)       AS max_salary,
                    MIN(e.salary)       AS min_salary
                FROM department d
                LEFT JOIN employee e ON d.dno = e.dno
                GROUP BY d.dno, d.dname
                ORDER BY total_salary DESC NULLS LAST;
            """)
            return cur.fetchall()


# ==================================================================================================
# SECTION 3: PROJECT MANAGEMENT (The Workflow Database)
# ==================================================================================================
# This section tracks the initiatives and ventures the company is undertaking.
# It records where projects are located and which departments are responsible for them.
# ==================================================================================================

def get_all_projects():
    """
    THE VENTURE TRACKER:
    This function generates a complete, sorted list of every project active in the system.
    It is used by the UI to help supervisors manage workloads and locations.
    """
    # IDENTITY GUARD:
    # Ensure we are operating within a valid company session before fetching any data.
    if not CURRENT_TENANT_ID: 
        return []

    # THE CONNECTION (The Secure Gateway):
    # Establish a private data tunnel to the company's designated database schema.
    # The 'with' keyword ensures the tunnel is safely sealed once we finish.
    with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
        
        # THE CURSOR (The Librarian):
        # We use 'DictCursor' to create a librarian who understands column names.
        # This allows us to use labels like 'pname' instead of just index numbers.
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            
            # THE EXECUTION (The SQL Request):
            # 'cur.execute' is the moment we send our command to the PostgreSQL server.
            # "SELECT *" gathers all project details, and "ORDER BY pno ASC" keeps them organized.
            sql_all_projects = "SELECT * FROM project ORDER BY pno ASC;"
            cur.execute(sql_all_projects)
            
            # THE FETCH (Gathering the Results):
            # 'cur.fetchall' collects every row the librarian found in the project vault.
            # It brings the data back from the database server into our Python environment.
            rows = cur.fetchall()
            
            # DATA MAPPING (Raw Rows to Smart Objects):
            # We transform each raw table row into a professional 'Project' object.
            # This makes the data much more powerful and easier for the UI to display.
            project_registry = []
            
            for r in rows:
                # Build a dedicated Project object for every entry found.
                obj = Project(
                    r['pno'],        # The Unique Project Number (The Identifier)
                    r['pname'],      # The human-readable name of the initiative (e.g., "Product-X")
                    r['plocation'],  # The physical city or office where the project is based
                    r['dno']         # The Department Number that owns this project
                )
                project_registry.append(obj)
            
            # Hand the final list of smart objects back to the system.
            return project_registry


def add_new_project(p):
    """
    THE INITIATIVE STARTER:
    This function takes a 'Project' object 'p' and records it in the database vault.
    It marks the official beginning of a new business venture in the system.
    """
    # SESSION VERIFICATION:
    # Double-check that the company context is correctly set.
    if not CURRENT_TENANT_ID: 
        return False
        
    try:
        # THE BRIDGE (The Connection):
        # Open a secure path to the company's private database storage.
        with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
            
            # THE WRITING CURSOR (The Agent):
            # We create a librarian (cursor) with the authority to add new files to the cabinet.
            with conn.cursor() as cur:
                
                # THE PROTECTED COMMAND (Secure Template):
                # We use %s placeholders to shield the database from SQL Injection attacks.
                # The 'psycopg2' bridge library safely inserts our data into these spots.
                sql_insert_project = "INSERT INTO project (pno, pname, plocation, dno) VALUES (%s, %s, %s, %s)"
                
                # THE EXECUTION (Writing the Data):
                # 'cur.execute' triggers the database to create the new project record.
                cur.execute(sql_insert_project, (p.pno, p.pname, p.plocation, p.dno))
            
            # THE COMMIT (The Permanent Seal):
            # 'conn.commit' is the final "Save" button. It tells the hard drive to keep the data.
            # Without this, the new project would be forgotten the moment we close the connection.
            conn.commit()
            
        return True
        
    except Exception as creation_error:
        # ERROR CAPTURE:
        # If the project number is already taken, the database will throw an error here.
        print(f"[SYSTEM LOG]: Failure during project creation: {creation_error}")
        return False


def get_project_by_id(pno):
    """
    THE TARGETED SEARCH:
    Finds a single project by its unique ID (pno). 
    Used when you want to see the details of one specific initiative.
    """
    # AUTHENTICATION:
    # Confirm the session is active.
    if not CURRENT_TENANT_ID: 
        return None

    # THE SECURE LINE (The Connection):
    # Establish communication with the project storage vault.
    with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
        
        # THE SEARCHING CURSOR (The Librarian):
        # We use 'DictCursor' so we can easily map column names to our Python model.
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            
            # THE COMMAND (Precise SQL):
            # "SELECT *" finds all data. "WHERE pno = %s" ensures we stop at the exact match.
            cur.execute("SELECT * FROM project WHERE pno = %s;", (pno,))
            
            # THE FETCH (Single Row Retrieval):
            # 'cur.fetchone' is used because project numbers are unique—there can only be one.
            row = cur.fetchone()
            
            # THE MAPPING:
            # If found, turn the row into a clean 'Project' object. Otherwise, return 'None'.
            if row:
                return Project(row['pno'], row['pname'], row['plocation'], row['dno'])
            return None


def delete_project(pno):
    """
    THE PROJECT PURGE:
    Removes a project record from the database permanently. 
    This is usually done when a project is completed or cancelled.
    """
    # AUTHORIZATION CHECK:
    # Ensure the user has an active session.
    if not CURRENT_TENANT_ID: 
        return False
        
    try:
        # TUNNEL ACTIVATION (The Connection):
        # Open the secure gate to the database server.
        with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
            
            # THE REMOVAL WORKER (The Cursor):
            # We create a librarian authorized to delete entries from the aisles.
            with conn.cursor() as cur:
                
                # THE DESTRUCTIVE SQL:
                # "DELETE FROM project" marks the target for removal.
                # "WHERE pno = %s" ensures we only remove the specific project intended.
                cur.execute("DELETE FROM project WHERE pno = %s;", (pno,))
            
            # THE COMMIT (Permanent Wipe):
            # Tell the database to finalize the deletion on the physical storage.
            conn.commit()
            
        return True
        
    except Exception as purge_failure:
        # SAFETY LOGGING:
        # Report any issues (like if employees are still assigned to this project).
        print(f"[CRITICAL]: Could not remove project {pno}: {purge_failure}")
        return False


def update_project_location(pno, new_location):
    """
    THE SITE UPDATER:
    Changes the physical location where a project is being managed.
    This modifies the 'plocation' column in the database records.
    """
    # SESSION GUARD:
    # Confirm the company context is active.
    if not CURRENT_TENANT_ID: 
        return False
        
    try:
        # SECURE DATA LINE:
        # Establish a connection to the company vault.
        with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
            
            # THE UPDATING CURSOR (The Modifier):
            # A librarian worker tasked with changing existing data.
            with conn.cursor() as cur:
                
                # THE SQL UPDATE:
                # "UPDATE project" identifies the target table.
                # "SET plocation = %s" points to the new city or building.
                # "WHERE pno = %s" locks the change to ONLY this specific project ID.
                cur.execute("UPDATE project SET plocation = %s WHERE pno = %s;", (new_location, pno))
            
            # THE COMMIT (Saving the Move):
            # Finalize the relocation in the permanent database records.
            conn.commit()
            
        return True
        
    except Exception as move_error:
        # EXCEPTION CAPTURE:
        # Catch any database errors that might occur during the update.
        print(f"[DATABASE ERROR]: Project relocation failed: {move_error}")
        return False


# ==================================================================================================
# SECTION 4: DEPENDENTS (Family & Benefits Registry)
# ==================================================================================================
# This section tracks the family members of employees for insurance and benefits.
# It links every 'Dependent' record to a specific 'Employee' parent record.
# ==================================================================================================

def get_all_dependents():
    """
    THE FAMILY DIRECTORY:
    Fetches a master list of all family members registered in the company system.
    This is essential for HR when managing healthcare and emergency contact info.
    """
    # IDENTITY VERIFICATION:
    # Check if a company session is active.
    if not CURRENT_TENANT_ID: 
        return []

    # THE SECURE GATEWAY (The Connection):
    # Open a private tunnel to the specific company storage.
    with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
        
        # THE LIBRARIAN (The Dictionary Cursor):
        # We use 'DictCursor' so we can read the family data by name (e.g., 'relationship').
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            
            # THE SQL COMMAND (Fetch Everything):
            # "SELECT *" pulls every attribute for every family member.
            cur.execute("SELECT * FROM dependent;")
            
            # THE FETCH (Gathering the Data):
            # 'cur.fetchall' pulls the pile of records back for our Python code to handle.
            rows = cur.fetchall()
            
            # DATA PREPARATION (Rows to Objects):
            # We convert the raw database rows into 'Dependent' objects for a cleaner UI.
            family_registry = []
            
            for r in rows:
                # Create a smart Dependent object for every row in the result pile.
                obj = Dependent(
                    r['eno'],              # Link to the Employee (Parent ID)
                    r['dependent_name'],   # Full name of the family member
                    r['gender'],           # Gender (M/F/O)
                    r['dob'],              # Birthday of the dependent
                    r['relationship']      # Their connection (Spouse, Son, Daughter, etc.)
                )
                family_registry.append(obj)
            
            # Return the organized list of family members.
            return family_registry


def add_new_dependent(d):
    """
    THE FAMILY ENROLLMENT:
    Adds a new family member 'd' to an employee's record. 
    It ensures their benefits and insurance data are properly stored.
    """
    # AUTH CHECK:
    # Only proceed if a tenant is logged in.
    if not CURRENT_TENANT_ID: 
        return False
        
    try:
        # THE DATABASE TUNNEL (The Connection):
        # Establish a secure connection to the company's SQL vault.
        with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
            
            # THE WRITING CURSOR (The Agent):
            # Create a librarian worker authorized to add family records.
            with conn.cursor() as cur:
                
                # THE SQL TEMPLATE (Data Protection):
                # We use %s placeholders to keep the data injection safe and clean.
                sql_insert_dep = """
                    INSERT INTO dependent (eno, dependent_name, gender, dob, relationship) 
                    VALUES (%s, %s, %s, %s, %s)
                """
                
                # THE EXECUTION (Storing the Family Member):
                # 'cur.execute' tells PostgreSQL to create the new dependent entry.
                cur.execute(sql_insert_dep, (d.eno, d.dependent_name, d.gender, d.dob, d.relationship))
            
            # THE COMMIT (Permanent Save):
            # Locking the new family record into the permanent archive.
            conn.commit()
            
        return True
        
    except Exception as enrollment_error:
        # SAFETY CATCH:
        # Log any errors (like if the parent employee ID doesn't exist).
        print(f"[REGISTRY ERROR]: Family enrollment failed: {enrollment_error}")
        return False


def get_dependents_by_eno(eno):
    """
    THE HOUSEHOLD LOOKUP:
    Finds only the family members belonging to one specific Employee (eno).
    """
    # VALIDATION:
    # Ensure current authentication.
    if not CURRENT_TENANT_ID: 
        return []

    # THE SECURE PATH:
    # Connect to the database cluster.
    with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
        
        # THE SEARCHING LIBRARIAN (The Cursor):
        # Using 'DictCursor' for easy mapping to the Python class.
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            
            # THE SQL COMMAND (Filtered Fetch):
            # We filter the search using the Employee ID placeholder.
            cur.execute("SELECT * FROM dependent WHERE eno = %s;", (eno,))
            
            # THE FETCH (Gathering the Family):
            # 'cur.fetchall' gathers everyone who is a dependent of this specific person.
            rows = cur.fetchall()
            
            # Return a list of all matching family members, mapped as smart objects.
            return [Dependent(r['eno'], r['dependent_name'], r['gender'], r['dob'], r['relationship']) for r in rows]


def delete_dependent(eno, name):
    """
    THE REGISTRY CLEANUP:
    Removes a specific family member from the records.
    It requires BOTH the Parent ID and the Name to find the exact unique person.
    """
    # SECURITY GATE:
    # Check session status.
    if not CURRENT_TENANT_ID: 
        return False
        
    try:
        # THE TUNNEL (The Connection):
        # Open a bridge to the database.
        with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
            
            # THE REMOVAL AGENT (The Cursor):
            # Task a librarian worker with erasing the specific family entry.
            with conn.cursor() as cur:
                
                # THE PURGE SQL:
                # "DELETE FROM dependent" removes the row.
                # "WHERE eno = %s AND dependent_name = %s" ensures surgical precision.
                cur.execute("DELETE FROM dependent WHERE eno = %s AND dependent_name = %s;", (eno, name))
            
            # THE COMMIT (Saving the Deletion):
            # Permanently wipe the record from the physical storage disks.
            conn.commit()
            
        return True
        
    except Exception as removal_error:
        # EXCEPTION HANDLING:
        # Report failures during the deletion process.
        print(f"[SECURITY ALERT]: Family removal encountered an error: {removal_error}")
        return False


# ==================================================================================================
# SECTION 5: DEPT LOCATIONS (Office & Facility Registry)
# ==================================================================================================
# This section manages the physical footprint of each department. 
# Since a department can be spread across multiple floors or buildings, 
# this table maps those relationships.
# ==================================================================================================

def get_all_dept_locations():
    """
    THE FACILITY DIRECTORY:
    This function generates a master list of every office and building attached to a department. 
    It provides a clear map of where the company's teams are physically located.
    """
    # IDENTITY PROTECTION:
    # Always confirm we are in a valid company session.
    if not CURRENT_TENANT_ID: 
        return []

    # THE SECURE TUNNEL (The Connection):
    # Establish a private data line to the company's designated database vault.
    with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
        
        # THE LIBRARIAN (The Dictionary Cursor):
        # We use 'DictCursor' so we can refer to data by column names like 'dlocation'.
        # This makes the mapping logic much more intuitive for humans.
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            
            # THE COMMAND (SQL Query):
            # 'cur.execute' sends our request to gather every location record in the system.
            # "SELECT *" means "Give me everything in the dept_locations table."
            sql_all_locations = "SELECT * FROM dept_locations;"
            cur.execute(sql_all_locations)
            
            # THE FETCH (Gathering the Inventory):
            # 'cur.fetchall' pulls all the found location rows out of the database vault.
            rows = cur.fetchall()
            
            # THE WRAPPING (Raw Data to Smart Objects):
            # We take each raw row and turn it into a 'DeptLocation' Python object.
            # This allows the rest of the app to treat data like real entities.
            location_registry = []
            
            for r in rows:
                # Build a new Department Location object for every entry.
                obj = DeptLocation(
                    r['dno'],        # The Department's ID number
                    r['dlocation']   # The name of the building or city
                )
                location_registry.append(obj)
            
            # Return the finalized list of facility objects.
            return location_registry


def add_dept_location(loc):
    """
    THE FACILITY REGISTRATION:
    This function adds a new building or floor 'loc' to a department's portfolio.
    It marks the official expansion of a team into a new physical space.
    """
    # AUTHENTICATION:
    # Verify the current company context is active.
    if not CURRENT_TENANT_ID: 
        return False
        
    try:
        # THE BRIDGE (The Connection):
        # Open the data doors to the company's private SQL vault.
        with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
            
            # THE WRITING LIBRARIAN (The Cursor):
            # Create a worker authorized to record new entries in the directory.
            with conn.cursor() as cur:
                
                # THE PROTECTED COMMAND (Secure SQL):
                # We use %s placeholders to ensure the location data is handled safely.
                # This shields the system from any malicious code injection.
                sql_insert_loc = "INSERT INTO dept_locations (dno, dlocation) VALUES (%s, %s)"
                
                # THE EXECUTION (Triggering the Write):
                # 'cur.execute' sends the new facility details to the database records.
                cur.execute(sql_insert_loc, (loc.dno, loc.dlocation))
            
            # THE COMMIT (Finalizing the Deal):
            # 'conn.commit' tells the database to permanently save this new location.
            # Without this, the record would disappear when the script finishes.
            conn.commit()
            
        return True
        
    except Exception as facility_error:
        # EXCEPTION HANDLING:
        # If the location is already registered for that dept, we catch the error here.
        print(f"[FACILITY LOG]: Could not register new site: {facility_error}")
        return False


def get_locations_by_dno(dno):
    """
    THE SITE LOOKUP:
    Finds every building or floor belonging to one specific Department (dno).
    Useful for seeing the physical reach of a single team.
    """
    # SESSION GUARD:
    # Ensure current authentication before searching.
    if not CURRENT_TENANT_ID: 
        return []

    # THE SECURE PATH (Connection):
    # Establish a line of communication to the database vault.
    with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
        
        # THE SEARCHING CURSOR (The Librarian):
        # Using 'DictCursor' for easy mapping to our Python model.
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            
            # THE COMMAND (Targeted Search):
            # "WHERE dno = %s" ensures we only get results for the requested department.
            cur.execute("SELECT * FROM dept_locations WHERE dno = %s;", (dno,))
            
            # THE FETCH (Retrieval):
            # Pull all matching locations back into our Python environment.
            rows = cur.fetchall()
            
            # Return a list of all matching sites, mapped as smart 'DeptLocation' objects.
            return [DeptLocation(r['dno'], r['dlocation']) for r in rows]


def update_dept_location(dno, old_location, new_location):
    """
    THE FACILITY RELOCATION:
    This function modifies an existing location record if a department moves.
    It swaps out the old building name for the new one in the system.
    """
    # AUTH CHECK:
    # Confirm the session is active.
    if not CURRENT_TENANT_ID: 
        return False
        
    try:
        # THE SECURE DATA LINE:
        # Connect to the private company database.
        with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
            
            # THE UPDATING CURSOR (The Modifier):
            # Task a librarian worker with updating the existing location entry.
            with conn.cursor() as cur:
                
                # THE SQL UPDATE:
                # "UPDATE dept_locations" identifies the table.
                # "SET dlocation = %s" specifies the new building name.
                # "WHERE dno = %s AND dlocation = %s" ensures we hit the exact record.
                sql_update_loc = "UPDATE dept_locations SET dlocation = %s WHERE dno = %s AND dlocation = %s;"
                
                # THE EXECUTION (Applying the Change):
                cur.execute(sql_update_loc, (new_location, dno, old_location))
                
            # THE COMMIT (Saving the Swap):
            # Finalize the relocation in the permanent database drive.
            conn.commit()
            
        return True
        
    except Exception as relocation_error:
        # ERROR LOGGING:
        print(f"[SYSTEM ERROR]: Relocation failed in the database: {relocation_error}")
        return False


def delete_dept_location(dno, location):
    """
    THE SITE REMOVAL:
    Permanently erases a building or floor from a department's list.
    Used when a department shuts down an office or moves entirely.
    """
    # SECURITY GATE:
    # Ensure current authentication status.
    if not CURRENT_TENANT_ID: 
        return False
        
    try:
        # THE DATA TUNNEL (The Connection):
        # Open the secure bridge to the database server.
        with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
            
            # THE REMOVAL AGENT (The Cursor):
            # Create a librarian focusing on deleting entries from the vault.
            with conn.cursor() as cur:
                
                # THE DESTRUCTIVE SQL:
                # "DELETE FROM" initiates the removal process.
                # "WHERE" ensures we delete the correct site for the correct department.
                cur.execute("DELETE FROM dept_locations WHERE dno = %s AND dlocation = %s;", (dno, location))
            
            # THE COMMIT (Finalizing the Purge):
            # Permanently wipe the record from the physical storage disks.
            conn.commit()
            
        return True
        
    except Exception as removal_error:
        # EXCEPTION CAPTURE:
        print(f"[SECURITY]: Facility removal encountered an error: {removal_error}")
        return False


# ==================================================================================================
# SECTION 6: WORKS ON (Staff Project Assignments)
# ==================================================================================================
# This section handles the core logic of staff allocation: who works on what.
# It tracks the 'hours' per week each employee spends on a specific project.
# ==================================================================================================

def get_all_work_records():
    """
    THE ASSIGNMENT MASTER LIST:
    Fetches every record of staff members assigned to projects. 
    This is effectively the 'Timesheet' overview for the entire company.
    """
    # IDENTITY GUARD:
    # Check session status.
    if not CURRENT_TENANT_ID: 
        return []

    # THE SECURE GATEWAY (The Connection):
    # Establish a private connection to the company storage vault.
    with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
        
        # THE LIBRARIAN (The Dictionary Cursor):
        # We use 'DictCursor' so we can refer to 'hours' and 'eno' by name.
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            
            # THE COMMAND (SQL Query):
            # "SELECT *" pulls back every row in the assignments table.
            cur.execute("SELECT * FROM works_on;")
            
            # THE FETCH (Gathering the Data):
            # 'cur.fetchall' collects the rows and brings them into Python.
            rows = cur.fetchall()
            
            # THE WRAPPING (Rows to Objects):
            # Convert raw database output into smart 'WorksOn' assignment objects.
            assignment_registry = []
            
            for r in rows:
                # Build an assignment object for every record found.
                obj = WorksOn(
                    r['eno'],    # The Employee ID
                    r['pno'],    # The Project ID
                    r['hours']   # The number of hours committed per week
                )
                assignment_registry.append(obj)
            
            # Return the finalized list of assignments.
            return assignment_registry


def add_work_record(w):
    """
    THE PROJECT DEPLOYMENT:
    Assigns an employee 'w' to a specific project with a set number of hours. 
    This creates a new link in the company's operational chain.
    """
    # AUTH CHECK:
    # Confirm the company context is active.
    if not CURRENT_TENANT_ID: 
        return False
        
    try:
        # THE BRIDGE (The Connection):
        # Open a secure data line to the company's SQL cluster.
        with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
            
            # THE WRITING CURSOR (The Agent):
            # Create a librarian worker authorized to add to the 'works_on' registry.
            with conn.cursor() as cur:
                
                # THE PROTECTED COMMAND (SQL Template):
                # We use %s blanks to ensure the assignment data is handled safely.
                # This protects against SQL injection and formatting errors.
                sql_insert_work = "INSERT INTO works_on (eno, pno, hours) VALUES (%s, %s, %s)"
                
                # THE EXECUTION (Writing the Assignment):
                # 'cur.execute' sends the employee, project ID, and hours to the database.
                cur.execute(sql_insert_work, (w.eno, w.pno, w.hours))
            
            # THE COMMIT (Finalizing the Work):
            # 'conn.commit' tells the database to permanently save this assignment.
            # Without this, the employee wouldn't be officially on the project.
            conn.commit()
            
        return True
        
    except Exception as assignment_error:
        # ERROR LOGGING:
        # Catch errors like double-assigning or invalid project IDs.
        print(f"[WORKFLOW ERROR]: Project assignment failed: {assignment_error}")
        return False


def get_work_by_eno(eno):
    """
    THE STAFF WORKLOAD LOOKUP:
    Finds all project assignments for one specific person. 
    Useful for checking if an employee is over-committed or under-utilized.
    """
    # SESSION GUARD:
    # Ensure current authentication.
    if not CURRENT_TENANT_ID: 
        return []

    # THE SECURE PATH:
    # Connect to the company database vault.
    with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
        
        # THE SEARCHING LIBRARIAN (The Cursor):
        # Using 'DictCursor' for easy mapping to the Python class.
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            
            # THE COMMAND (Filtered Fetch):
            # "WHERE eno = %s" ensures we only get projects for this specific person.
            cur.execute("SELECT * FROM works_on WHERE eno = %s;", (eno,))
            
            # THE FETCH (Gathering the Evidence):
            # Pull all matching rows back into Python memory.
            rows = cur.fetchall()
            
            # Return a list of all matching work records, mapped as smart objects.
            return [WorksOn(r['eno'], r['pno'], r['hours']) for r in rows]


def delete_work_record(eno, pno):
    """
    THE PROJECT WITHDRAWAL:
    Removes an employee from a specific project. 
    It breaks the link between the person and that initiative in the database.
    """
    # SECURITY GATE:
    # Check session status.
    if not CURRENT_TENANT_ID: 
        return False
        
    try:
        # THE TUNNEL (The Connection):
        # Open a bridge to the database server.
        with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
            
            # THE REMOVAL AGENT (The Cursor):
            # Create a librarian focusing on erasing the work assignment entry.
            with conn.cursor() as cur:
                
                # THE PURGE SQL:
                # "DELETE FROM works_on" initiates the removal.
                # "WHERE eno = %s AND pno = %s" ensures we detach the person from that specific project.
                cur.execute("DELETE FROM works_on WHERE eno = %s AND pno = %s;", (eno, pno))
            
            # THE COMMIT (Finalizing the Withdrawal):
            # Wipe the record from the physical storage drive forever.
            conn.commit()
            
        return True
        
    except Exception as withdrawal_error:
        # EXCEPTION CAPTURE:
        print(f"[SECURITY NOTICE]: Work assignment withdrawal failed: {withdrawal_error}")
        return False

# ==================================================================================================
# SECTION 7: AUDIT LOGS (The 'Eyes' of the System)
# ==================================================================================================
# This section provides a security trail for every action taken in the database.
# It records who changed what, when they did it, and what the data looked like before and after.
# ==================================================================================================

def get_global_logs(limit=50, interval=None):
    """
    THE MASTER TIMELINE:
    Fetches a history of all changes made across every table in the company vault.
    This is the primary tool for administrators to audit system activity.
    
    - limit: How many recent actions to show (prevents overloading the terminal).
    - interval: A time filter like '1 hour' or '7 days' to narrow down the search.
    """
    # IDENTITY GUARD:
    # Always ensure a valid company session is active before accessing sensitive logs.
    if not CURRENT_TENANT_ID: 
        return []

    # THE SECURE GATEWAY (The Connection):
    # Establish a private data tunnel to the company's designated audit storage.
    with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
        
        # THE LIBRARIAN (The Dictionary Cursor):
        # We use 'DictCursor' so we can read the JSON logs and metadata by name.
        # This makes the audit trail much easier to parse in the Python code.
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            
            # THE QUERY BUILDER (Dynamic SQL):
            # We start with a basic request to see the audit trail.
            sql_query = "SELECT * FROM audit_log"
            sql_params = []
            
            # THE TIME FILTER (Interval Logic):
            # If the user requested a specific timeframe (e.g., '24 hours'), we add a filter.
            if interval:
                # We use "NOW() - CAST(%s AS INTERVAL)" to let PostgreSQL do the time math.
                # This ensures we only see the 'Fresh' logs.
                sql_query += " WHERE changed_at > NOW() - CAST(%s AS INTERVAL)"
                sql_params.append(interval)
            
            # THE ORGANIZATION (Sorting and Limiting):
            # We sort by 'changed_at DESC' to show the most recent actions first.
            # We apply a 'LIMIT' to keep the list manageable.
            sql_query += " ORDER BY changed_at DESC LIMIT %s;"
            sql_params.append(limit)
            
            # THE EXECUTION (The SQL Request):
            # 'cur.execute' sends the assembled command and the parameters to the server.
            # Parameters are kept separate for maximum security (Escaping).
            cur.execute(sql_query, tuple(sql_params))
            
            # THE FETCH (Gathering the Evidence):
            # 'cur.fetchall' pulls all the matching audit rows into our Python memory.
            # These rows include timestamps, table names, and JSON data blocks.
            return cur.fetchall()


def get_employee_specific_logs(target_eno, limit=50, interval=None):
    """
    THE TARGETED INVESTIGATION:
    Filters the timeline to show only actions that affected one specific employee.
    It looks deep into the 'old_data' and 'new_data' JSON blocks for the ID.
    """
    # SESSION VERIFICATION:
    # Confirm authentication before performing a deep search.
    if not CURRENT_TENANT_ID: 
        return []

    # THE SECURE PATH (Connection):
    # Open the connection to the company's private database cluster.
    with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
        
        # THE ANALYST CURSOR (The Librarian):
        # Using 'DictCursor' for easy access to the complex JSON log fields.
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            
            # THE DEEP SEARCH SQL (JSON Operations):
            # We use the '@>' operator (The JSON Containment operator).
            # This asks: "Does this JSON blob contain the record {'eno': target_eno}?"
            sql_deep_search = """
                SELECT * FROM audit_log 
                WHERE (old_data @> %s OR new_data @> %s)
            """
            
            # DATA PREPARATION (JSON Conversion):
            # We turn the employee ID into a small JSON string that PostgreSQL can read.
            filter_blob = json.dumps({"eno": int(target_eno)})
            sql_params = [filter_blob, filter_blob]
            
            # OPTIONAL TIME FILTER:
            # Narrow down the search to a specific interval if provided.
            if interval:
                sql_deep_search += " AND changed_at > NOW() - CAST(%s AS INTERVAL)"
                sql_params.append(interval)
            
            # ORDER AND CONSTRAINTS:
            # Sorting by newest first and limiting the results.
            sql_deep_search += " ORDER BY changed_at DESC LIMIT %s;"
            sql_params.append(limit)
            
            # THE EXECUTION:
            # Send the complex JSON search query to the database engine.
            cur.execute(sql_deep_search, tuple(sql_params))
            
            # THE FETCH:
            # Retrieve all matching rows that reference this employee's ID.
            return cur.fetchall()


def get_salary_history(target_eno):
    """
    THE PAY TIMELINE:
    Reads UPDATE records from audit_log for the employee table where the salary
    field is present in both old_data and new_data, filtered to the target employee.
    Uses JSON containment (@>) to locate the correct employee's records and
    CAST to NUMERIC to allow proper arithmetic on the JSONB string values.
    Returns a list of dicts ordered oldest-first:
        {
          'changed_at': datetime,
          'old_salary': float,
          'new_salary': float,
          'direction':  'RAISE' | 'CUT' | 'SAME'
        }
    Returns [] if no session, no employee, or no salary changes recorded.
    """
    if not CURRENT_TENANT_ID:
        return []

    with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            filter_blob = json.dumps({"eno": int(target_eno)})
            cur.execute("""
                SELECT
                    changed_at,
                    (old_data->>'salary')::NUMERIC AS old_salary,
                    (new_data->>'salary')::NUMERIC AS new_salary
                FROM audit_log
                WHERE table_name = 'employee'
                  AND operation   = 'UPDATE'
                  AND (old_data @> %s OR new_data @> %s)
                  AND old_data->>'salary' IS NOT NULL
                  AND new_data->>'salary' IS NOT NULL
                ORDER BY changed_at ASC;
            """, (filter_blob, filter_blob))

            rows = cur.fetchall()
            result = []
            for r in rows:
                old_s = float(r['old_salary']) if r['old_salary'] is not None else 0.0
                new_s = float(r['new_salary']) if r['new_salary'] is not None else 0.0
                if new_s > old_s:
                    direction = "RAISE"
                elif new_s < old_s:
                    direction = "CUT"
                else:
                    direction = "SAME"
                result.append({
                    "changed_at": r['changed_at'],
                    "old_salary": old_s,
                    "new_salary": new_s,
                    "direction":  direction,
                })
            return result


def get_table_specific_logs(table_name, operation=None, limit=50, interval=None):
    """
    THE MODULE FILTER:
    Shows activity for only one specific table (e.g., 'department' or 'project').
    This is useful for spotting patterns within a specific system component.
    """
    # IDENTITY GUARD:
    # Always check the session first.
    if not CURRENT_TENANT_ID: 
        return []

    # THE SECURE GATE (Connection):
    # Establish the data tunnel to the company vault.
    with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
        
        # THE LIBRARIAN (Scanning Cursor):
        # Tasked with gathering records filtered by table name.
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            
            # STARTING POINT (Base Query):
            # Filter specifically for the table the user requested.
            sql_table_filter = "SELECT * FROM audit_log WHERE table_name = %s"
            sql_params = [table_name]
            
            # OPERATION FILTER (Action Type):
            # Optionally filter by INSERT, UPDATE, or DELETE actions.
            if operation:
                sql_table_filter += " AND operation = %s"
                sql_params.append(operation)
            
            # TIME FILTER:
            # Apply an interval constraint if requested.
            if interval:
                sql_table_filter += " AND changed_at > NOW() - CAST(%s AS INTERVAL)"
                sql_params.append(interval)
                
            # SORT AND LIMIT:
            # organizing the output for human consumption.
            sql_table_filter += " ORDER BY changed_at DESC LIMIT %s;"
            sql_params.append(limit)
            
            # THE EXECUTION:
            # Send the multi-part request to the database server.
            cur.execute(sql_table_filter, tuple(sql_params))
            
            # THE FETCH:
            # Gather the resulting history rows back into Python.
            return cur.fetchall()


def get_transfer_history(target_eno):
    """
    THE TRANSFER TRAIL:
    Finds every department change for one specific employee by reading UPDATE
    records from audit_log where the 'dno' field changed between old_data and
    new_data. Returns oldest-first for chronological reading.
    Returns a list of dicts:
        { 'changed_at': datetime, 'old_dno': int, 'new_dno': int }
    Returns [] if no session, no records, or employee was never transferred.
    """
    if not CURRENT_TENANT_ID:
        return []

    with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            filter_blob = json.dumps({"eno": int(target_eno)})
            cur.execute("""
                SELECT
                    changed_at,
                    (old_data->>'dno')::INT AS old_dno,
                    (new_data->>'dno')::INT AS new_dno
                FROM audit_log
                WHERE table_name = 'employee'
                  AND operation   = 'UPDATE'
                  AND (old_data @> %s OR new_data @> %s)
                  AND old_data->>'dno' IS NOT NULL
                  AND new_data->>'dno' IS NOT NULL
                  AND (old_data->>'dno') <> (new_data->>'dno')
                ORDER BY changed_at ASC;
            """, (filter_blob, filter_blob))

            rows = cur.fetchall()
            return [
                {
                    "changed_at": r['changed_at'],
                    "old_dno":    r['old_dno'],
                    "new_dno":    r['new_dno'],
                }
                for r in rows
            ]


def get_operation_summary(interval=None):
    """
    THE OPERATION BREAKDOWN:
    Counts INSERT, UPDATE, DELETE activity grouped by table name.
    Optional interval filter accepts PostgreSQL interval strings like
    '1 hour', '7 days', '30 days'.
    Returns raw tuples: (table_name, operation, count)
    ordered by table name then operation type.
    """
    if not CURRENT_TENANT_ID:
        return []

    with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
        with conn.cursor() as cur:
            if interval:
                cur.execute("""
                    SELECT table_name, operation, COUNT(*) AS cnt
                    FROM audit_log
                    WHERE changed_at > NOW() - CAST(%s AS INTERVAL)
                    GROUP BY table_name, operation
                    ORDER BY table_name ASC, operation ASC;
                """, (interval,))
            else:
                cur.execute("""
                    SELECT table_name, operation, COUNT(*) AS cnt
                    FROM audit_log
                    GROUP BY table_name, operation
                    ORDER BY table_name ASC, operation ASC;
                """)
            return cur.fetchall()


def clear_old_logs(days=30):
    """
    THE ARCHIVE PURGE:
    Deletes logs older than a specific age to save disk space and maintain performance.
    This is part of the system's "Self-Cleaning" routine.
    """
    # SECURITY AUTH:
    # Verify the session is active.
    if not CURRENT_TENANT_ID: 
        return False
        
    try:
        # THE SECURE Path (The Connection):
        # Open a bridge to the database.
        with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
            
            # THE CLEANING CURSOR (The Agent):
            # A librarian tasked with deleting old, expired entries.
            with conn.cursor() as cur:
                
                # THE DESTRUCTIVE SQL (Maintenance Logic):
                # "DELETE FROM audit_log" removes the records.
                # "WHERE changed_at < NOW() - INTERVAL..." targets only the 'Old' stuff.
                sql_purge = "DELETE FROM audit_log WHERE changed_at < NOW() - INTERVAL '%s days';"
                
                # THE EXECUTION (The Purge):
                cur.execute(sql_purge, (days,))
            
            # THE COMMIT (Finalizing the Purge):
            # Permanently wipe the old records from the storage drive.
            conn.commit()
            
        return True
        
    except Exception as maintenance_error:
        # EXCEPTION CAPTURE:
        print(f"[MAINTENANCE ERROR]: Could not clean up history: {maintenance_error}")
        return False


# ==================================================================================================
# SECTION 8: SYSTEM STATISTICS (The Bird's Eye View)
# ==================================================================================================
# This final section provides high-level aggregation and health metrics for the company.
# It gives managers a summary of how much activity is happening in each department or module.
# ==================================================================================================

def get_audit_stats():
    """
    THE HEALTH REPORT:
    Summarizes system activity by counting modifications for each table. 
    It gives a clear picture of which parts of the database are being used the most.
    
    Returns a list of tuples: (table_name, change_count, placeholder).
    """
    # AUTHENTICATION CHECK:
    # Double-check the company session status.
    if not CURRENT_TENANT_ID: 
        return []

    # THE SECURE TUNNEL (The Connection):
    # Establish a private data line to the company's SQL cluster.
    with ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID) as conn:
        
        # THE ANALYTICS CURSOR (The Basic Cursor):
        # We don't need DictCursor here because we are doing custom aggregation math.
        with conn.cursor() as cur:
            
            # THE AGGREGATION SQL (Grouping Logic):
            # "SELECT table_name, COUNT(*)" tells the database to count every row for each table.
            # "GROUP BY table_name" piles the records together by their module name.
            # This is much faster than fetching every log and counting them in Python.
            sql_stats = "SELECT table_name, COUNT(*), 0 FROM audit_log GROUP BY table_name;"
            
            # THE EXECUTION (Triggering the Math):
            # 'cur.execute' sends the aggregation request to the PostgreSQL engine.
            cur.execute(sql_stats)
            
            # THE FETCH (Retrieving the Totals):
            # 'cur.fetchall' pulls the summarized counts back into our system.
            return cur.fetchall()


# ==================================================================================================
# END OF THE QUERY ENGINE (The Heart of the Multi-Tenant EMS)
# ==================================================================================================
# This concludes the database interaction layer. 
# Every function above is designed to be secure, fast, and human-readable.
# ==================================================================================================

