import questionary
from questionary import Style
import sys
import threading 
import time      
import json
import os
import csv
from tabulate import tabulate
import services.query_engine as _qe

from services.query_engine import (
    set_current_tenant, get_employee_by_id, search_employees_by_name, add_new_employee, 
    add_new_department, delete_department, delete_employee, get_all_departments, 
    get_all_employees, update_employee_salary, transfer_employee, get_department_by_id, update_department_manager,
    get_payroll_summary, bulk_import_employees, get_all_projects, add_new_project, 
    get_project_by_id, delete_project, update_project_location, get_all_dependents, 
    add_new_dependent, delete_dependent, get_dependents_by_eno, delete_dept_location, 
    get_locations_by_dno, get_all_work_records, add_work_record, 
    get_work_by_eno, delete_work_record, get_all_dept_locations, 
    add_dept_location, get_global_logs, 
    get_employee_specific_logs, get_table_specific_logs, clear_old_logs, get_audit_stats,
    get_salary_history, get_transfer_history, get_operation_summary
)
from services.data_porter import export_company_data_json, export_company_data_csv

from app.models.employee import Employee 
from app.models.department import Department
from app.models.project import Project
from app.models.dependent import Dependent
from app.models.works_on import WorksOn
from app.models.dept_locations import DeptLocation
from app.models.audit_log import AuditLog

from app.system.provisioning_service import ProvisioningService
from app.core.security import verify_password
from app.core.connection_factory import ConnectionFactory
from app.core.email_service import send_export_email

custom_style = Style([
    ('question', 'fg:#00ffff bold'),
    ('pointer', 'fg:#ff9d00 bold'),
    ('highlighted', 'fg:#ff9d00'),
])


# --- THE BRAIN OF THE USER INTERFACE ---
# This file handles the menus, colors, and button clicks you see in the terminal.

def landing_page():
    """
    THE RECEPTION DESK:
    This is the first screen you see. It lets you Login, Sign Up, or Delete.
    """
    while True:
        # Clear screen for professional entry (ANSI codes)
        print("\033[H\033[J")
        
        # Premium Header (Compact & Organized)
        header_text = [
            ["\033[1;33mCORPORATE ACCESS PORTAL\033[0m"],
            ["\033[1;36mEMPLOYEE MANAGEMENT SYSTEM\033[0m"]
        ]
        print("\n" + tabulate(header_text, tablefmt="fancy_grid", stralign="center"))

        # Choice Menu using 'questionary'
        choice = questionary.select(
            "Welcome to the EMS Portal. Please select an action:",
            choices=[
                "1. Login to Existing Company Space",
                "2. Create a New Company Space (Sign Up)",
                "3. Change Company Password",
                "4. Update Company Email Address",
                "5. Delete My Company Space (Permanent)",
                "6. Exit Application"
            ],
            style=custom_style
        ).ask()
 
        if choice is None:
            sys.exit(0)

        if choice == "1. Login to Existing Company Space":
            # --- THE KEYHOLE ---
            # We ask for name and password to see who is trying to enter.
            company_name = questionary.text("Enter Company Name (or type 'back' to return):").ask()

            if company_name is None: continue
            if not company_name or company_name.lower() in ['back', 'b']: continue
            
            password = questionary.password("Enter Password:").ask()

            if password is None: continue
            if not password or password.lower() in ['back', 'b']: continue

            # We check the 'Public Registry' in the cloud to see if this company exists.
            with ConnectionFactory.get_admin_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT tenant_id, hashed_password FROM public.tenants WHERE company_name = %s", (company_name,))
                    result = cursor.fetchone()
                    
                    if result:
                        tenant_id, hashed_pwd = result
                        # We verify the scrambled password
                        if verify_password(password, hashed_pwd):
                            # SUCCESS! We set the 'Sticky Note' (Tenant ID) so we know who is working.
                            set_current_tenant(tenant_id)
                            questionary.print(f"\n[SUCCESS] Welcome back, {company_name}! Access granted.", style="bold #00ff00")
                            time.sleep(1)
                            main_menu()
                        else:
                            questionary.print("\n[ERROR] Authentication failed: Incorrect password.", style="bold #ff0000")
                            time.sleep(1.5)
                    else:
                        questionary.print(f"\n[ERROR] Company '{company_name}' not found.", style="bold #ff0000")
                        time.sleep(1.5)

        elif choice == "2. Create a New Company Space (Sign Up)":
            questionary.print(
                "\n[REGISTRATION]: Setting up your private workspace.",
                style="bold #00ffff")

            # ── Company name ─────────────────────────────────────────────────
            reg_name = questionary.text(
                "Enter Company Name (or type 'back'):").ask()
            if reg_name is None: continue
            if not reg_name or reg_name.lower() in ['back', 'b']: continue

            # ── Password ─────────────────────────────────────────────────────
            reg_pass = questionary.password("Create Password:").ask()
            if reg_pass is None: continue
            if not reg_pass: continue

            reg_confirm = questionary.password("Confirm Password:").ask()
            if reg_confirm is None: continue
            if not reg_confirm: continue

            if reg_pass != reg_confirm:
                questionary.print(
                    "\n[ERROR] Passwords do not match.",
                    style="bold #ff0000")
                time.sleep(1.5)
                continue

            # ── Email (optional but recommended) ─────────────────────────────
            questionary.print(
                "\n[OPTIONAL] Register a company email for export notifications.",
                style="#888888")
            questionary.print(
                " Press ENTER to skip. You can add one later.",
                style="#888888")
            reg_email_raw = questionary.text(
                "Company Email (ENTER to skip):").ask()
            if reg_email_raw is None: continue
            reg_email = reg_email_raw.strip() if reg_email_raw.strip() else None

            # ── Provision ────────────────────────────────────────────────────
            questionary.print(
                f"\n[SYSTEM]: Building workspace for '{reg_name}'...",
                style="bold #00ffff")

            success, result = ProvisioningService.provision_new_company(
                reg_name, reg_pass, reg_email)

            if success:
                questionary.print(
                    f"\n[SUCCESS] Workspace ready! Tenant ID: {result}",
                    style="bold #00ff00")
                if reg_email:
                    questionary.print(
                        f" Email registered: {reg_email}",
                        style="#888888")
                set_current_tenant(result)
                main_menu()
            else:
                questionary.print(
                    f"\n[ERROR] Provisioning failed: {result}",
                    style="bold #ff0000")
                time.sleep(2)

        elif choice == "3. Change Company Password":
            questionary.print(
                "\n[SECURITY]: Current password required to authorise this change.",
                style="bold #ff9d00"
            )
            ch_company = questionary.text(
                "Enter Company Name (or 'back'):").ask()
            if ch_company is None: continue
            if not ch_company or ch_company.lower() in ['back', 'b']: continue

            ch_current = questionary.password("Enter CURRENT Password:").ask()
            if ch_current is None: continue
            if not ch_current: continue

            ch_new = questionary.password("Enter NEW Password:").ask()
            if ch_new is None: continue
            if not ch_new: continue

            ch_confirm = questionary.password("Confirm NEW Password:").ask()
            if ch_confirm is None: continue
            if not ch_confirm: continue

            success, msg = ProvisioningService.change_company_password(
                ch_company, ch_current, ch_new, ch_confirm
            )
            if success:
                questionary.print(f"\n[SUCCESS] {msg}", style="bold #00ff00")
            else:
                questionary.print(f"\n[ERROR] {msg}", style="bold #ff0000")
            time.sleep(2)

        elif choice == "4. Update Company Email Address":
            questionary.print(
                "\n[ACCOUNT]: Add or update your registered email address.",
                style="bold #00ffff")
            questionary.print(
                " This email will receive exported files.",
                style="#888888")

            ue_name = questionary.text(
                "Enter Company Name (or 'back'):").ask()
            if ue_name is None: continue
            if not ue_name or ue_name.lower() in ['back', 'b']: continue

            ue_pass = questionary.password("Enter Current Password:").ask()
            if ue_pass is None: continue
            if not ue_pass: continue

            ue_email = questionary.text(
                "Enter New Email Address (or 'back'):").ask()
            if ue_email is None: continue
            if not ue_email or ue_email.lower() in ['back', 'b']: continue

            ue_ok, ue_msg = ProvisioningService.update_company_email(
                ue_name, ue_pass, ue_email)

            if ue_ok:
                questionary.print(
                    f"\n[SUCCESS] {ue_msg}", style="bold #00ff00")
            else:
                questionary.print(
                    f"\n[ERROR] {ue_msg}", style="bold #ff0000")
            time.sleep(2)

        elif choice == "5. Delete My Company Space (Permanent)":
            questionary.print("\n[WARNING] THIS ACTION IS PERMANENT AND CANNOT BE UNDONE!", style="bold #ff0000")
            company_name = questionary.text("Enter Company Name to Delete (or type 'back'):").ask()

            if company_name is None: continue
            if not company_name or company_name.lower() in ['back', 'b']: continue
            
            password = questionary.password("Enter Password to Confirm Deletion (or type 'back'):").ask()

            if password is None: continue
            if not password or password.lower() in ['back', 'b']: continue
            
            confirm = questionary.confirm(f"Are you ABSOLUTELY sure you want to delete all data for '{company_name}'?").ask()
            
            if confirm is None: continue
            
            if confirm:
                success, msg = ProvisioningService.delete_company_space(company_name, password)
                if success:
                    questionary.print(f"\n[SUCCESS] {msg}", style="bold #00ff00")
                else:
                    questionary.print(f"\n[ERROR] {msg}", style="bold #ff0000")
                time.sleep(2)
            else:
                questionary.print("\nDeletion cancelled.", style="bold #00ffff")
                time.sleep(1)

        else:
            questionary.print("\nExiting. Thank you for using EMS.", style="bold #ffff00")
            sys.exit()

def main_menu():
    while True:
        # Dashboard Panel for a professional visual frame
        panel = [
            ["\033[1;36mCOMPANY EMPLOYEE DATA MANAGEMENT SYSTEM\033[0m"],
        ]
        print("\n" + tabulate(panel, tablefmt="fancy_grid", stralign="center"))

        # Formal selection with arrow-based indicators
        # NOTE: questionary.Separator() lines are NON-SELECTABLE — the cursor
        # automatically skips over them. This replaces the old box-border
        # strings which were selectable and caused silent dashboard-reloads.
        choice = questionary.select(
            "SELECT MODULE:",
            choices=[
                questionary.Separator("──────────────────────────────────────────"),
                "  EMPLOYEE RECORDS",
                "  DEPARTMENT RECORDS",
                "  PROJECT RECORDS",
                "  EMPLOYEE DEPENDENT RECORDS",
                "  EMPLOYEE PROJECT WORK RECORDS",
                "  DEPARTMENT LOCATION RECORDS",
                questionary.Separator("──────────────────────────────────────────"),
                "  SYSTEM AUDIT TRAIL",
                "  PORTABLE DATA EXPORT (DATA PORTER)",
                "  TERMINATE SESSION",
                questionary.Separator("──────────────────────────────────────────"),
            ],
            style=questionary.Style([
                ('pointer',     'fg:#00ffff bold'),
                ('highlighted', 'fg:#00ffff bold'),
                ('selected',    'fg:#ffffff'),
                ('text',        'fg:#ffffff'),
            ]),
            pointer=" ▶ "
        ).ask()

        if choice is None:
            sys.exit(0)

        # Routing — all existing keywords still match because the choice
        # strings still contain the same keywords. The leading spaces
        # ("  EMPLOYEE RECORDS") still match "EMPLOYEE RECORDS" in choice.
        if "EMPLOYEE RECORDS" in choice:
            employee_hub()
        elif "DEPARTMENT RECORDS" in choice:
            department_hub()
        elif "PROJECT RECORDS" in choice:
            project_hub()
        elif "EMPLOYEE DEPENDENT RECORDS" in choice:
            dependent_hub()
        elif "EMPLOYEE PROJECT WORK RECORDS" in choice:
            work_records_hub()
        elif "DEPARTMENT LOCATION RECORDS" in choice:
            location_hub()
        elif "SYSTEM AUDIT TRAIL" in choice:
            audit_hub()
        elif "PORTABLE DATA EXPORT" in choice:

            export_choice = questionary.select(
                "SELECT EXPORT FORMAT:",
                choices=[
                    questionary.Separator("──────────────────────────────────────────"),
                    "  1. Portable CSV Bundle (7 separate files)",
                    "  2. System Snapshot (JSON)",
                    questionary.Separator("──────────────────────────────────────────"),
                    "  Back to Dashboard",
                ],
                style=custom_style
            ).ask()

            # Guard: cancelled or navigated away
            if export_choice is None:
                continue

            # Guard: back — use EXACT string match to avoid substring bugs
            if "Back to Dashboard" in export_choice:
                continue

            success, result        = False, "No operation performed."
            export_type_label      = ""

            if "1." in export_choice:
                questionary.print(
                    "\n[SYSTEM]: Preparing CSV bundle...",
                    style="bold #00ffff")
                success, result   = export_company_data_csv()
                export_type_label = "CSV Bundle"

            elif "2." in export_choice:
                questionary.print(
                    "\n[SYSTEM]: Generating JSON snapshot...",
                    style="bold #00ffff")
                success, result   = export_company_data_json()
                export_type_label = "JSON Snapshot"

            else:
                # Should never reach here since Separators are non-selectable
                continue

            if success:
                questionary.print("\n" + "="*60, style="#00ffff")
                questionary.print(
                    " SUCCESS: DATA EXPORT COMPLETED",
                    style="bold #00ff00")
                questionary.print("="*60, style="#00ffff")
                questionary.print(
                    f" LOCATION: {result}", style="#00ffff")
                questionary.print("-"*60, style="#00ffff")

                # ── Email option (only for single-file exports) ───────────────
                # CSV produces a folder, not a single file, so it cannot be
                # emailed as an attachment. JSON produces a single .json file.
                can_email = os.path.isfile(result)

                if can_email:
                    want_email = questionary.confirm(
                        "Email this export to your registered company address?",
                        default=False
                    ).ask()

                    if want_email:
                        em_ok, em_data = (
                            ProvisioningService
                            .get_company_email_by_tenant_id(
                                _qe.CURRENT_TENANT_ID)
                        )
                        if em_ok:
                            co_name, co_email = em_data
                            questionary.print(
                                f"\n[EMAIL]: Sending to {co_email}...",
                                style="bold #00ffff")
                            mail_ok, mail_msg = send_export_email(
                                co_email, co_name,
                                result, export_type_label)
                            if mail_ok:
                                questionary.print(
                                    f" [SENT] {mail_msg}",
                                    style="bold #00ff00")
                            else:
                                questionary.print(
                                    f" [ERROR] {mail_msg}",
                                    style="bold #ff0000")
                        else:
                            questionary.print(
                                f" [INFO] {em_data}\n"
                                " Add your email via the landing page "
                                "'Update Company Email Address' option.",
                                style="bold #ff9d00")
                else:
                    questionary.print(
                        " Note: CSV exports produce a folder and cannot "
                        "be emailed directly.\n"
                        " Use JSON export if you need an emailed copy.",
                        style="italic #888888")

                questionary.text(
                    "\n Press ENTER to return to Dashboard...",
                    qmark="").ask()
            else:
                questionary.print(
                    f"\n[ERROR] {result}", style="bold #ff0000")
                time.sleep(3)

        elif "TERMINATE SESSION" in choice:
            questionary.print(
                "DISCONNECTING FROM DATABASE...",
                style="bold #01010E")
            sys.exit()
        
#---------------------------------------------------------EMPLOYEE HUB------------------------------------------------------------#

def employee_hub():
    """
    THE STAFF MODULE:
    Where you manage everyone on your team. You can hire, fire, or change salaries.
    """
    while True:
        # Module Panel for broad POV header
        print("\n" + tabulate([["\033[1;36m EMPLOYEE RECORDS INTERFACE\033[0m"]], tablefmt="fancy_grid", stralign="center"))

        choice = questionary.select(
            "SELECT ACTION:",
            choices=[
                "┌──────────────────────────────────────────┐",
                "│  Search Employee by ID                   │",
                "│  Search Employee by Name                 │",
                "│  Add New Employee                        │",
                "│  Delete Employee                         │",
                "│  View All Employees                      │",
                "│  Update Employee Salary                  │",
                "│  View Salary History                     │",
                "│  Transfer Employee to Department         │",
                "│  Bulk Import from CSV                    │",
                "├──────────────────────────────────────────┤",
                "│  Back to Dashboard                       │",
                "└──────────────────────────────────────────┘"
            ],
            style=custom_style,
            pointer=" ▶ "
        ).ask()

        if choice is None: break


        if "Back to Dashboard" in choice:
            break
        

        #-----------------------------GET EMPLOYEE DETAILS BY ID--------------------------#
        

        if "Search Employee by ID" in choice:
            target_id = questionary.text("Enter Employee ID (or type 'back'):").ask()
            if not target_id or target_id.lower() in ['back', 'b']: continue
            if target_id is None: continue
            
            # Call your existing search function
            emp = get_employee_by_id(target_id)

            if emp:
                # Format for the grid
                f_salary = "{:,.2f}".format(emp.salary)
                mgr = f"\033[90m---\033[0m" if emp.super_eno is None else str(emp.super_eno)
                
                # We put the single employee in a list so tabulate can read it
                row = [[
                    f"\033[1;36m{emp.eno}\033[0m", 
                    f"\033[1m{emp.ename}\033[0m", 
                    str(emp.dob), emp.gender, 
                    f"\033[92m{f_salary}\033[0m", 
                    mgr, 
                    f"\033[93m{emp.dno}\033[0m"
                ]]

                print("\n\033[1m EMPLOYEE MATCH FOUND\033[0m")
                print(tabulate(row, headers=["ID", "NAME", "DOB", "G", "SALARY", "MGR", "DEPT"], tablefmt="fancy_grid"))
            else:
                questionary.print(f"No employee found with ID {target_id}", style="#ff000d")

        #-----------------------------SEARCH EMPLOYEE BY NAME--------------------------#

        elif "Search Employee by Name" in choice:
            search_term = questionary.text("Enter Name to search (or type 'back'):").ask()
            if search_term is None: continue
            if not search_term or search_term.lower() in ['back', 'b']: continue

            results = search_employees_by_name(search_term)

            if results:
                employee_data = []
                for e in results:
                    f_salary = "{:,.2f}".format(e.salary)
                    mgr = f"\033[90m---\033[0m" if e.super_eno is None else str(e.super_eno)
                    employee_data.append([
                        f"\033[1;36m{e.eno}\033[0m",
                        f"\033[1m{e.ename}\033[0m",
                        str(e.dob),
                        e.gender,
                        f"\033[92m{f_salary}\033[0m",
                        mgr,
                        f"\033[93m{e.dno}\033[0m"
                    ])
                print(f"\n\033[1m SEARCH RESULTS FOR: '{search_term.upper()}'\033[0m")
                print(tabulate(employee_data,
                               headers=["ID", "NAME", "DOB", "G", "SALARY", "MGR", "DEPT"],
                               tablefmt="fancy_grid"))
                questionary.print(f" {len(results)} record(s) found.", style="bold #00ffff")
            else:
                questionary.print(f" No employees found matching '{search_term}'.", style="#ff000d")

        #-----------------------------ADD NEW EMPLOYEE------------------------------------#


        elif "Add New Employee" in choice:

            #--------------------collecting the data------------------#

            print("\n[Step 1: Paste Employee Details]")
            print("Format: ID, Name, DOB, Gender, Salary, ManagerID, DeptID")
            print("Example: 102, Tanish, 2006-08-30, M, 60000, None, 1")

            raw_input = questionary.text(">> (or type 'back' to cancel)").ask()

            if raw_input is None: continue
            if not raw_input or raw_input.lower() in ['back', 'b']: continue
            
            data = raw_input.split(",")

            #-------------------building new employee object-----------#

            employee_id = int(data[0].strip())
            name        = data[1].strip()
            dob         = data[2].strip()
            gender      = data[3].strip()
            salary      = float(data[4].strip())
            dept_id     = int(data[6].strip())

            mgr_text = data[5].strip()
            manager_id = None if mgr_text.lower() == "none" else int(mgr_text)

            new_emp_object = Employee(employee_id, name, dob, gender, salary, manager_id, dept_id)

            #--------------saving the new employee in database-------------#

            success = add_new_employee(new_emp_object)
            if success:
                questionary.print(f"The database has been updated , New Employee :{new_emp_object.ename} has ben added","#0026ff")
            else:
                questionary.print(f"Failed to add employee :{new_emp_object.ename}  Check for duplicate ID or invalid Dept ID.","#ec1818")
        
        
        #------------------------------VIEW ALL EMPLOYEES-------------------------------------#


        elif "View All Employees" in choice:
            results = get_all_employees()

            if results:
                employee_data = []
                for e in results:
                    eid = f"\033[1;36m{e.eno}\033[0m"
                    ename = f"\033[1m{e.ename}\033[0m"
                    
                    # --- FIXED: PROPER NUMBER FORMATTING ---
                    # "{:,.2f}" adds commas for thousands and 2 decimal places
                    # This prevents 2.5e+07 and shows 25,000,000.00 instead
                    f_salary = "{:,.2f}".format(e.salary)
                    salary = f"\033[92m{f_salary}\033[0m"
                    
                    dept = f"\033[93m{e.dno}\033[0m"
                    mgr = f"\033[90m---\033[0m" if e.super_eno is None else str(e.super_eno)
                    
                    employee_data.append([eid, ename, str(e.dob), e.gender, salary, mgr, dept])

                print("\n\033[1m CORPORATE EMPLOYEE REGISTRY\033[0m")
                print(tabulate(employee_data, 
                               headers=["ID", "NAME", "DOB", "G", "SALARY", "MGR", "DEPT"], 
                               tablefmt="fancy_grid"))
            else:
                questionary.print("No employees found in the system.", style="#ff000d")

            
        #------------------------------UPDATE EMPLOYEE SALARY------------------------------------------#

        elif "Update Employee Salary" in choice: 
            uid = questionary.text("Enter Employee ID (or 'back'):").ask()

            if uid is None: continue
            if not uid or uid.lower() in ['back', 'b']: continue
            
            new_val = questionary.text("Enter New Salary (or 'back'):").ask()

            if new_val is None: continue
            if not new_val or new_val.lower() in ['back', 'b']: continue
            
            # Call engine
            success = update_employee_salary(int(uid), float(new_val))
            
            if success:
                questionary.print("█" * 40, style="#5f5d5d")
                questionary.print(f"   SUCCESS: Salary set to {new_val}", style="#17798F")
                questionary.print("█" * 40 + "\n", style="#535050")
            else :
                questionary.print(f" No employee found with ID {uid} or database error", "#dfd6d6")
       
        #-----------------------------BULK IMPORT FROM CSV-----------------------------#

        elif "Bulk Import from CSV" in choice:
            print("\n\033[1;36m BULK EMPLOYEE IMPORT FROM CSV\033[0m")
            print("─" * 55)
            print(" CSV FORMAT REQUIRED (with header row):")
            print(" eno, ename, dob, gender, salary, super_eno, dno")
            print(" Example row: 201, Alice Smith, 1990-03-15, F, 55000, None, 2")
            print(" Rules:")
            print("   - Header row MUST be present (first line is skipped)")
            print("   - super_eno can be 'None' if no manager")
            print("   - dob format: YYYY-MM-DD")
            print("   - gender: M or F only")
            print("─" * 55)

            file_path = questionary.text("Enter full path to CSV file (or 'back'):").ask()
            if file_path is None: continue
            if not file_path or file_path.lower() in ['back', 'b']: continue

            file_path = file_path.strip().strip('"').strip("'")

            if not os.path.exists(file_path):
                questionary.print(f" File not found: {file_path}", style="bold #ff0000")
                continue

            # Parse the CSV file
            employee_list = []
            parse_errors = []

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for line_num, row in enumerate(reader, start=2):  # start=2 because row 1 is header
                        try:
                            super_eno_raw = row['super_eno'].strip()
                            super_eno = None if super_eno_raw.lower() == 'none' else int(super_eno_raw)

                            emp = Employee(
                                eno      = int(row['eno'].strip()),
                                ename    = row['ename'].strip(),
                                dob      = row['dob'].strip(),
                                gender   = row['gender'].strip(),
                                salary   = float(row['salary'].strip()),
                                super_eno= super_eno,
                                dno      = int(row['dno'].strip())
                            )
                            employee_list.append(emp)
                        except Exception as parse_err:
                            parse_errors.append(f"  Line {line_num}: {parse_err}")

            except Exception as file_err:
                questionary.print(f" Could not read file: {file_err}", style="bold #ff0000")
                continue

            if parse_errors:
                questionary.print(f"\n PARSE ERRORS in {len(parse_errors)} row(s):", style="bold #ff9d00")
                for pe in parse_errors:
                    print(pe)
                confirm_partial = questionary.confirm(
                    f" {len(employee_list)} valid rows found. Proceed with import of valid rows only?",
                    default=False
                ).ask()
                if not confirm_partial:
                    questionary.print(" Import cancelled.", style="#00ff26")
                    continue

            if not employee_list:
                questionary.print(" No valid rows to import.", style="#ff000d")
                continue

            questionary.print(f"\n[SYSTEM]: Importing {len(employee_list)} employee records...", style="bold #00ffff")

            success_count, db_errors = bulk_import_employees(employee_list)

            if db_errors:
                questionary.print(f"\n IMPORT FAILED — Database rejected the batch:", style="bold #ff0000")
                for de in db_errors:
                    print(f"  {de}")
                questionary.print(" No records were saved (full rollback).", style="#ff9d00")
            else:
                questionary.print("─" * 55, style="#00ffff")
                questionary.print(f"  SUCCESS: {success_count} employee(s) imported.", style="bold #00ff00")
                questionary.print("─" * 55, style="#00ffff")
        
        elif "Delete Employee" in choice:
            target_id = questionary.text("Enter Employee ID to delete (or 'back'):").ask()

            if target_id is None: continue
            if not target_id or target_id.lower() in ['back', 'b']: continue
            
            # --- SAFETY FIRST: CONFIRMATION GUARD ---
            confirm = questionary.confirm(f"⚠️  DANGER: Are you absolutely sure you want to permanently DELETE Employee ID {target_id}?", default=False).ask()
            if confirm:
                success = delete_employee(int(target_id))
                if success:
                    questionary.print(f" Record Purged: Employee {target_id} has been removed.", style="bold #ff0000")
                else:
                    questionary.print(f" Failed: Could not delete Employee {target_id}.", style="bold #ec1818")
            else:
                questionary.print(" Deletion cancelled. Record is safe.", style="#00ff26")

        #─────────────────── VIEW SALARY HISTORY ────────────────────────────

        elif "View Salary History" in choice:
            sh_id = questionary.text(
                "Enter Employee ID to view salary history (or 'back'):").ask()
            if sh_id is None: continue
            if not sh_id or sh_id.lower() in ['back', 'b']: continue

            try:
                sh_eid = int(sh_id)
            except ValueError:
                questionary.print(" Invalid ID — please enter a number.",
                                  style="bold #ff0000")
                continue

            sh_emp = get_employee_by_id(sh_eid)
            if not sh_emp:
                questionary.print(f" No employee found with ID {sh_eid}.",
                                  style="#ff000d")
                continue

            history = get_salary_history(sh_eid)

            print(f"\n\033[1m SALARY HISTORY: "
                  f"{sh_emp.ename.upper()} (ID: {sh_eid})\033[0m")

            if not history:
                questionary.print(
                    " No salary change records found in the audit trail.\n"
                    " This employee's salary has never been updated via the system.",
                    style="#ff9d00")
                questionary.print(
                    f" Current salary on record: "
                    f"\033[92m{float(sh_emp.salary):,.2f}\033[0m",
                    style="bold")
                continue

            hist_rows = []
            for i, entry in enumerate(history, start=1):
                ts    = entry['changed_at'].strftime("%Y-%m-%d  %H:%M:%S")
                old_s = f"\033[91m{entry['old_salary']:>13,.2f}\033[0m"
                new_s = f"\033[92m{entry['new_salary']:>13,.2f}\033[0m"
                diff  = entry['new_salary'] - entry['old_salary']
                if entry['direction'] == "RAISE":
                    arrow = f"\033[92m▲  +{diff:,.2f}\033[0m"
                elif entry['direction'] == "CUT":
                    arrow = f"\033[91m▼  {diff:,.2f}\033[0m"
                else:
                    arrow = f"\033[90m●  unchanged\033[0m"
                hist_rows.append([
                    f"\033[1;36m{i}\033[0m",
                    ts, old_s, new_s, arrow
                ])

            print(tabulate(hist_rows,
                           headers=["#", "CHANGED AT", "OLD SALARY",
                                    "NEW SALARY", "CHANGE"],
                           tablefmt="fancy_grid"))
            questionary.print(
                f" Current salary on record: "
                f"\033[92m{float(sh_emp.salary):,.2f}\033[0m",
                style="bold")

        #─────────────────── TRANSFER EMPLOYEE ──────────────────────────────

        elif "Transfer Employee to Department" in choice:
            print("\n\033[1;36m EMPLOYEE DEPARTMENT TRANSFER\033[0m")
            print("─" * 52)

            tr_id = questionary.text(
                "Enter Employee ID to transfer (or 'back'):").ask()
            if tr_id is None: continue
            if not tr_id or tr_id.lower() in ['back', 'b']: continue

            try:
                tr_eid = int(tr_id)
            except ValueError:
                questionary.print(" Invalid ID — please enter a number.",
                                  style="bold #ff0000")
                continue

            tr_emp = get_employee_by_id(tr_eid)
            if not tr_emp:
                questionary.print(f" No employee found with ID {tr_eid}.",
                                  style="#ff000d")
                continue

            # Show all departments as a reference table
            all_depts_tr = get_all_departments()
            if all_depts_tr:
                dept_ref = []
                for d in all_depts_tr:
                    marker = " ◀ CURRENT" if d.dno == tr_emp.dno else ""
                    dept_ref.append([
                        f"\033[1;36m{d.dno}\033[0m",
                        f"\033[1m{d.dname.upper()}\033[0m{marker}"
                    ])
                print(f"\n Employee : \033[1m{tr_emp.ename}\033[0m  |  "
                      f"Current Dept: \033[93m{tr_emp.dno}\033[0m")
                print(tabulate(dept_ref,
                               headers=["DNO", "DEPARTMENT NAME"],
                               tablefmt="fancy_grid"))

            tr_new_dept = questionary.text(
                "Enter TARGET Department ID (or 'back'):").ask()
            if tr_new_dept is None: continue
            if not tr_new_dept or tr_new_dept.lower() in ['back', 'b']: continue

            try:
                tr_new_dno = int(tr_new_dept)
            except ValueError:
                questionary.print(" Invalid Department ID.",
                                  style="bold #ff0000")
                continue

            confirm_tr = questionary.confirm(
                f"Transfer {tr_emp.ename} from Dept {tr_emp.dno} "
                f"→ Dept {tr_new_dno}?",
                default=False
            ).ask()
            if not confirm_tr:
                questionary.print(" Transfer cancelled. Record unchanged.",
                                  style="#00ff26")
                continue

            tr_success, tr_result = transfer_employee(tr_eid, tr_new_dno)
            if tr_success:
                old_dno = tr_result
                questionary.print("─" * 52, style="#00ffff")
                questionary.print(
                    f"  SUCCESS: {tr_emp.ename} transferred",
                    style="bold #00ff00")
                questionary.print(
                    f"  FROM Dept \033[91m{old_dno}\033[0m"
                    f"  →  TO Dept \033[92m{tr_new_dno}\033[0m",
                    style="bold")
                questionary.print("─" * 52, style="#00ffff")
                questionary.print(
                    " Audit trail updated automatically by the database trigger.",
                    style="italic #888888")
            else:
                questionary.print(f" Transfer Failed: {tr_result}",
                                  style="bold #ff0000")

#---------------------------------------------------------DEPARTMENT HUB----------------------------------------------------------#
def department_hub():
    """
    THE TEAMS MODULE:
    Where you organize the company into departments like 'Research' or 'Marketing'.
    """
    while True:
        # Formal header to maintain broad POV
        print("\n" + tabulate([["\033[1;36mDEPARTMENTAL OPERATIONS INTERFACE\033[0m"]], tablefmt="fancy_grid", stralign="center"))

        choice = questionary.select(
            "SELECT ACTION:",
            choices=[
                "┌──────────────────────────────────────────┐",
                "│  Add New Department                      │",
                "│  Delete Department                       │",
                "│  View All Departments                    │",
                "│  Search Department by ID                 │",
                "│  Update Department Manager               │",
                "│  View Payroll Summary                    │",
                "├──────────────────────────────────────────┤",
                "│  Back to Dashboard                       │",
                "└──────────────────────────────────────────┘"
            ],
            style=custom_style,
            pointer=" ▶ "
        ).ask()

        if choice is None: break
        
        if "Back to Dashboard" in choice:
            break

        #------------------------------ADD NEW DEPARTMENT-------------------------------------------#

        if "Add New Department" in choice:
             
            #-----------------------collecting the data---------------------------# 

            print("\n[Step 1: Paste Department Details]")
            print("Format: DNO, DName, Mgr_ENO, MgrStartDate")
            print("Example: 1, Research, 101, 2024-01-01")

            raw_input = questionary.text(">> (or type 'back' to cancel)").ask()

            if raw_input is None: continue
            if not raw_input or raw_input.lower() in ['back', 'b']: continue
            
            data = raw_input.split(",")

            #----------------------building the department object------------------#

            try:
                new_dept_object = Department(
                    int(data[0].strip()), 
                    data[1].strip(), 
                    int(data[2].strip()), 
                    data[3].strip()
                )

                #-------------------saving the department in database-------------------#

                success = add_new_department(new_dept_object)
                if success:
                    questionary.print(f"The database has been updated! , New Department :{new_dept_object.dname} has ben added","#00ff26")
                else:
                    questionary.print(f"Failed to add department :{new_dept_object.dname}  Check for duplicate ID.","#ff6600")
            except Exception:
                questionary.print(" Format Error: Please follow the DNO, Name, Mgr_ENO, Date pattern.","#ff6600")


        #--------------------------------DELETE DEPARTMENT-----------------------------------#


        elif "Delete Department" in choice:
            val_dno = questionary.text("Enter Department ID to delete (or 'back'):").ask()

            if val_dno is None: continue
            if not val_dno or val_dno.lower() in ['back', 'b']: continue
            
            # --- SAFETY FIRST: CONFIRMATION GUARD ---
            confirm = questionary.confirm(f"⚠️  DANGER: Deleting Dept {val_dno} could orphan employees. Proceed?", default=False).ask()
            if confirm:
                success = delete_department(int(val_dno))
                if success:
                    questionary.print(f" Record Purged: Department {val_dno} removed.", style="bold #ff0000")
                else:
                    questionary.print(f" Failed: Dept {val_dno} may have active employees or sub-records.", style="bold #ec1818")
            else:
                questionary.print(" Deletion cancelled.", style="#00ff26")
        

        #------------------------------VIEW ALL DEPARTMENTS------------------------------------#

      
        elif "View All Departments" in choice:
            # Call  existing function that fetches department objects
            results = get_all_departments()

            if results:
                # 1. Prepare data rows for the Fancy Grid
                dept_data = []
                for d in results:
                    # Apply professional color coding:
                    # Cyan (\033[1;36m) for the Dept ID
                    d_id = f"\033[1;36m{d.dno}\033[0m"
                    # Bold (\033[1m) for the Department Name
                    d_name = f"\033[1m{d.dname.upper()}\033[0m"
                    # Yellow (\033[93m) for the Manager ENO
                    # We handle 'None' check to prevent formatting errors
                    mgr = f"\033[90mVACANT\033[0m" if d.mgr_eno is None else f"\033[93m{d.mgr_eno}\033[0m"
                    
                    dept_data.append([d_id, d_name, mgr])

                # 2. Display the professional registry
                print("\n\033[1m CORPORATE DEPARTMENT REGISTRY\033[0m")
                # 'fancy_grid' provides the double-line border that survives web consoles
                print(tabulate(dept_data, 
                               headers=["DEPT ID", "DEPARTMENT NAME", "MANAGER ID"], 
                               tablefmt="fancy_grid"))
            else:
                # Keep your existing error style for failed searches
                questionary.print("No departments found in the system.", style="#ff000d")
        
        #-------------------------------SEARCH DEPARTMENT----------------------------------------#
          
        elif "Search Department by ID" in choice:
            d_id = questionary.text("Enter Dept ID (or 'back'):").ask()

            if d_id is None: continue
            if not d_id or d_id.lower() in ['back', 'b']: continue
            
            dept = get_department_by_id(d_id)

            if dept:
                # Formatting the single row
                mgr = f"\033[90mVACANT\033[0m" if dept.mgr_eno is None else f"\033[93m{dept.mgr_eno}\033[0m"
                row = [[f"\033[1;36m{dept.dno}\033[0m", f"\033[1m{dept.dname.upper()}\033[0m", mgr]]

                print("\n\033[1m DEPARTMENT MATCH FOUND\033[0m")
                print(tabulate(row, headers=["DEPT ID", "DEPARTMENT NAME", "MANAGER ID"], tablefmt="fancy_grid"))
            else:
                questionary.print(f"No department found with ID {d_id}", style="#ff000d")
        

        #--------------------------UPDATE DEPARTMENT MANAGER-------------------------------#


        elif "Update Department Manager" in choice:

            target_dno = questionary.text("Enter Department ID (DNO) to update (or 'back'):").ask()

            if target_dno is None: continue
            if not target_dno or target_dno.lower() in ['back', 'b']: continue
            
            new_mgr = questionary.text("Enter New Manager ID (Employee ID) (or 'back'):").ask()

            if new_mgr is None: continue
            if not new_mgr or new_mgr.lower() in ['back', 'b']: continue
            
            # Calling the engine function
            success = update_department_manager(int(target_dno), int(new_mgr))
            
            if success:
                questionary.print(f"\n   SUCCESS: Manager for DNO {target_dno} updated", style="#7d85c7\n")
            else:
                questionary.print(" Failed to update. Check if DNO and Employee ID exist.", style="#ff000d")
            
        #-----------------------------PAYROLL SUMMARY-----------------------------#

        elif "View Payroll Summary" in choice:
            results = get_payroll_summary()

            if results:
                summary_data = []
                grand_total = 0

                for row in results:
                    dno, dname, headcount, total_sal, avg_sal, max_sal, min_sal = row

                    # Handle departments that have no employees yet (LEFT JOIN returns NULLs)
                    headcount  = headcount or 0
                    total_sal  = float(total_sal) if total_sal else 0.0
                    avg_sal    = float(avg_sal)   if avg_sal   else 0.0
                    max_sal    = float(max_sal)   if max_sal   else 0.0
                    min_sal    = float(min_sal)   if min_sal   else 0.0

                    grand_total += total_sal

                    summary_data.append([
                        f"\033[1;36m{dno}\033[0m",
                        f"\033[1m{dname.upper()}\033[0m",
                        f"\033[93m{headcount}\033[0m",
                        f"\033[92m{total_sal:>14,.2f}\033[0m",
                        f"\033[92m{avg_sal:>12,.2f}\033[0m",
                        f"\033[92m{max_sal:>12,.2f}\033[0m",
                        f"\033[91m{min_sal:>12,.2f}\033[0m",
                    ])

                print("\n\033[1m CORPORATE PAYROLL SUMMARY BY DEPARTMENT\033[0m")
                print(tabulate(summary_data,
                               headers=["DNO", "DEPARTMENT", "STAFF", "TOTAL SALARY",
                                        "AVG SALARY", "MAX SALARY", "MIN SALARY"],
                               tablefmt="fancy_grid"))
                print(f"\n\033[1;33m  COMPANY-WIDE TOTAL PAYROLL: {grand_total:,.2f}\033[0m")
            else:
                questionary.print(" No department data available.", style="#ff000d")

#----------------------------------------------------------PROJECT HUB------------------------------------------------------------#

def project_hub():
    """
    THE WORK MODULE:
    Track what your company is building. You can assign projects to locations and departments.
    """

    while True:
        # High-visibility header for the Project module
        print("\n" + tabulate([["\033[1;36mPROJECT MANAGEMENT INTERFACE\033[0m"]], tablefmt="fancy_grid", stralign="center"))

        choice = questionary.select(
            "SELECT ACTION:",
            choices=[
                "┌──────────────────────────────────────────┐",
                "│  View All Projects                       │",
                "│  Add New Project                         │",
                "│  Delete Project                          │",
                "│  Search Project by ID                    │",
                "│  Update Project Location                 │",
                "├──────────────────────────────────────────┤",
                "│  Back to Dashboard                       │",
                "└──────────────────────────────────────────┘"
            ],
            style=custom_style,
            pointer=" ▶ "
        ).ask()

        if choice is None: break

        # Navigation handling
        if "Back to Dashboard" in choice:
            break
        #------------------------------VIEW ALL PROJECTS------------------------------------#


        if "View All Projects" in choice:
            # Fetch project objects from query_engine
            results = get_all_projects()
            
            if results:
                # Prepare data rows for the fancy grid
                project_data = []
                for p in results:
                    # Cyan (\033[1;36m) for Project ID to keep it consistent
                    pno = f"\033[1;36m{p.pno}\033[0m"
                    # Bold (\033[1m) for Project Name
                    pname = f"\033[1m{p.pname.upper()}\033[0m"
                    # White/Default for Location
                    loc = p.plocation
                    # Yellow (\033[93m) for Department ID
                    dno = f"\033[93m{p.dno}\033[0m"
                    
                    project_data.append([pno, pname, loc, dno])

                # Header using your clean white style
                print("\n\033[1m🏗️ CURRENT ACTIVE PROJECTS\033[0m")
                
                # 'fancy_grid' ensures the columns stay locked even with long names
                print(tabulate(project_data, 
                               headers=["PNO", "PROJECT NAME", "LOCATION", "DNO"], 
                               tablefmt="fancy_grid"))
            else:
                questionary.print(" No projects found in the system.", style="#ff000d")


        #------------------------------ADD NEW PROJECT------------------------------------#


        elif "Add New Project" in choice:

            #--------------------collecting the data------------------#

            print("\n[Paste Project Details]")
            print("Format: PNO, PName, PLocation, DNO")
            print("Example: 1, ProductX, Ahmedabad, 1")

            raw_input = questionary.text(">> (or type 'back' to cancel)").ask()

            if raw_input is None: continue
            if not raw_input or raw_input.lower() in ['back', 'b']: continue
            
            data = raw_input.split(",")

            #-------------------building new project object-----------#

            try:
                p_id       = int(data[0].strip())
                p_name     = data[1].strip()
                p_loc      = data[2].strip()
                dept_id    = int(data[3].strip())

                new_proj_object = Project(p_id, p_name, p_loc, dept_id)

                #--------------saving the project in database-------------#

                success = add_new_project(new_proj_object)
                
                if success:
                    questionary.print(f" Success: Project '{p_name}' has been launched ", style="#cd3b0e")
                else:
                    questionary.print(f" Failed to add project. Check for duplicate PNO or invalid DNO.", "#ec1818")
            
            except Exception:
                questionary.print(f" Input Error: Please ensure you follow the comma-separated format correctly.", "#ec1818")
        

        #----------------------------------DELETE PROJECT----------------------------------#


        elif "Delete Project" in choice:
            target_pno = questionary.text("Enter Project Number (PNO) to delete (or 'back'):").ask()

            if target_pno is None: continue
            if not target_pno or target_pno.lower() in ['back', 'b']: continue
            
            # --- SAFETY FIRST: CONFIRMATION GUARD ---
            confirm = questionary.confirm(f"⚠️  DANGER: Purging Project {target_pno} will remove all labor records. Proceed?", default=False).ask()
            if confirm:
                success = delete_project(int(target_pno))
                if success:
                    questionary.print(f" Record Removed: Project {target_pno} is no longer in the system.", style="bold #ff0000")
                else:
                    questionary.print(f" Deletion Failed: No project found with PNO {target_pno}.", style="bold #ec1818")
            else:
                questionary.print(" Deletion cancelled.", style="#00ff26")
        

        #--------------------------SEARCH PROJECT BY ID---------------------------------#


        elif "Search Project by ID" in choice:
            # Using questionary for consistent input style
            target_pno = questionary.text("Enter Project Number (PNO) (or 'back'):").ask()

            if target_pno is None: continue
            if not target_pno or target_pno.lower() in ['back', 'b']: continue
            
            result = get_project_by_id(int(target_pno))

            if result:
                # Prepare a single row for the fancy grid
                # Cyan (\033[1;36m) for the ID and Yellow (\033[93m) for Dept
                pno = f"\033[1;36m{result.pno}\033[0m"
                pname = f"\033[1m{result.pname.upper()}\033[0m"
                loc = result.plocation
                dno = f"\033[93m{result.dno}\033[0m"
                
                row = [[pno, pname, loc, dno]]

                print("\n\033[1;36m PROJECT RECORD FOUND\033[0m")
                # Grid ensures borders stay straight in web consoles like Antigravity
                print(tabulate(row, 
                               headers=["PNO", "PROJECT NAME", "LOCATION", "DNO"], 
                               tablefmt="fancy_grid"))
            else:
                questionary.print(f" No project found with PNO: {target_pno}", style="#ff6600")
        
        #--------------------------UPDATE PROJECT LOCATION---------------------------------#


        elif "Update Project Location" in choice:
            target_pno = questionary.text("Enter Project Number (PNO) (or 'back'):").ask()

            if target_pno is None: continue
            if not target_pno or target_pno.lower() in ['back', 'b']: continue
            
            new_loc = questionary.text("Enter New Project Location (or 'back'):").ask()

            if new_loc is None: continue
            if not new_loc or new_loc.lower() in ['back', 'b']: continue
            
            success = update_project_location(int(target_pno), new_loc)
            
            if success:
                # Professional block style for the success message
                questionary.print(f"   SUCCESS: Project {target_pno} moved to {new_loc}", style="#f9f4f5")
            else:
                questionary.print(f" Failed to update. Check if PNO {target_pno} exists.", style="#f1efef")
        
#----------------------------------------------------------DEPENDENT HUB----------------------------------------------------------#

def dependent_hub():
    """
    THE FAMILY MODULE:
    Keep track of employee dependents (like children or spouses) for insurance and benefits.
    """
    while True:
        # Formal header for the Dependent module
        print("\n" + tabulate([["\033[1;36mEMPLOYEE DEPENDENT REGISTRY\033[0m"]], tablefmt="fancy_grid", stralign="center"))

        choice = questionary.select(
            "SELECT ACTION:",
            choices=[
                "┌──────────────────────────────────────────┐",
                "│  View All Dependents                     │",
                "│  Add New Dependent                       │",
                "│  Delete Dependent                        │",
                "│  Search Dependents by Employee ID        │",
                "├──────────────────────────────────────────┤",
                "│  Back to Dashboard                       │",
                "└──────────────────────────────────────────┘"
            ],
            style=custom_style,
            pointer=" ▶ "
        ).ask()

        if choice is None: break

        if "Back to Dashboard" in choice:
            break

        #------------------------------VIEW ALL DEPENDENTS------------------------------------#


        if "View All Dependents" in choice:
            # Fetch all dependent objects
            results = get_all_dependents()
            
            if results:
                # Prepare data rows for the fancy grid
                registry_data = []
                for d in results:
                    # ENO in Orange-Red to match your existing style
                    eno = f"\033[38;5;202m{d.eno}\033[0m"
                    # Bold for names
                    name = f"\033[1m{d.dependent_name}\033[0m"
                    # Magenta for Relationship to distinguish family data
                    relation = f"\033[95m{d.relationship}\033[0m"
                    
                    registry_data.append([eno, name, d.gender, str(d.dob), relation])

                # Display with the locked fancy_grid
                print("\n\033[1m EMPLOYEE DEPENDENT REGISTRY\033[0m")
                print(tabulate(registry_data, 
                               headers=["ENO", "DEPENDENT NAME", "G", "DOB", "RELATIONSHIP"], 
                               tablefmt="fancy_grid"))
            else:
                questionary.print(" No dependent records found.", style="#ff000d")

        #------------------------------ADD NEW DEPENDENT------------------------------------#


        if "Add New Dependent" in choice:

            #--------------------collecting the data------------------#

            print("\n[Step 1: Paste Dependent Details]")
            print("Format: eno, dependent_name, gender, dob, relationship")
            print("Example: 101, Alice, F, 2015-05-20, Daughter")

            raw_input = questionary.text(">> (or type 'back' to cancel)").ask()

            if raw_input is None: continue
            if not raw_input or raw_input.lower() in ['back', 'b']: continue
            
            data = raw_input.split(",")

            #-------------------building new dependent object-----------#

            try:
                # Cleaning and mapping the split data to your names
                val_eno  = int(data[0].strip())
                val_name = data[1].strip()
                val_gen  = data[2].strip()
                val_dob  = data[3].strip()
                val_rel  = data[4].strip()

                new_dep_obj = Dependent(val_eno, val_name, val_gen, val_dob, val_rel)

                #--------------saving the dependent in database-------------#

                success = add_new_dependent(new_dep_obj)
                
                if success:
                    questionary.print(f" Success: {val_name} added for Employee {val_eno}!", style="#e13008")
                else:
                    questionary.print(f" Failed: Check if Employee {val_eno} exists or if record is duplicate.", "#ec1818")
            
            except Exception:
                questionary.print("Input Error: Please use the correct comma-separated format.", "#ec1818")   



        #----------------------------------DELETE DEPENDENT----------------------------------#


        elif "Delete Dependent" in choice:
            # To delete, we need both parts of the primary key
            val_eno = questionary.text("Enter Employee ID (eno) (or 'back'):").ask()

            if val_eno is None: continue
            if not val_eno or val_eno.lower() in ['back', 'b']: continue
            
            val_name = questionary.text("Enter Dependent Name (or 'back'):").ask()

            if val_name is None: continue
            if not val_name or val_name.lower() in ['back', 'b']: continue
            
            # --- SAFETY FIRST: CONFIRMATION GUARD ---
            confirm = questionary.confirm(f"  DANGER: Remove family member '{val_name}' from Employee {val_eno}?", default=False).ask()
            if confirm:
                success = delete_dependent(int(val_eno), val_name)
                if success:
                    questionary.print(f" Record Removed: {val_name} deleted.", style="bold #ff0000")
                else:
                    questionary.print(f" Deletion Failed: No matching record found for {val_name} under ID {val_eno}.", style="bold #ec1818")
            else:
                questionary.print(" Deletion cancelled.", style="#00ff26")
        

        #--------------------------SEARCH DEPENDENTS BY EMPLOYEE ID--------------------------#


        elif "Search Dependents by Employee ID" in choice:
            val_eno = questionary.text("Enter Employee ID (eno) (or 'back'):").ask()

            if val_eno is None: continue
            if not val_eno or val_eno.lower() in ['back', 'b']: continue
            
            # Fetch dependent objects
            results = get_dependents_by_eno(int(val_eno))

            if results:
                # Prepare data rows for the grid
                dependent_data = []
                for d in results:
                    # Bold for name, Magenta for relationship to distinguish from Employee tables
                    d_name = f"\033[1m{d.dependent_name}\033[0m"
                    gender = d.gender
                    dob = str(d.dob)
                    relation = f"\033[95m{d.relationship}\033[0m"
                    
                    dependent_data.append([d_name, gender, dob, relation])

                # Display with the locked fancy_grid
                print(f"\n\033[ DEPENDENTS FOR EMPLOYEE ID: {val_eno}\033[0m")
                print(tabulate(dependent_data, 
                               headers=["DEPENDENT NAME", "G", "DOB", "RELATIONSHIP"], 
                               tablefmt="fancy_grid"))
            else:
                questionary.print(f" No dependent records found for Employee: {val_eno}", style="#ff6600")
      
#-------------------------------------------------------PROJECT WORK HUB----------------------------------------------------------#

def work_records_hub():
    """
    THE TIMESHEET MODULE:
    See exactly who is working on which project and for how many hours.
    """

    while True:
        # Formal header for the Work Assignments module
        print("\n" + tabulate([["\033[1;36mPROJECT ASSIGNMENT & WORK TRACKING\033[0m"]], tablefmt="fancy_grid", stralign="center"))

        choice = questionary.select(
            "SELECT ACTION:",
            choices=[
                "┌──────────────────────────────────────────┐",
                "│  View All Work Records                   │",
                "│  Add New Work Record                     │",
                "│  Delete Work Record                      │",
                "│  Search Work by Employee ID              │",
                "├──────────────────────────────────────────┤",
                "│  Back to Dashboard                       │",
                "└──────────────────────────────────────────┘"
            ],
            style=custom_style,
            pointer=" ▶ "
        ).ask()

        if choice is None: break
    
        if "Back to Dashboard" in choice:
            break

        #------------------------------VIEW ALL WORK RECORDS------------------------------------#


        if "View All Work Records" in choice:
            # Fetch assignment objects from query_engine
            results = get_all_work_records()
            
            if results:
                # Prepare data rows for the fancy grid
                work_data = []
                for w in results:
                    # Cyan (\033[1;36m) for IDs to maintain consistency
                    eno = f"\033[1;36m{w.eno}\033[0m"
                    # Yellow (\033[93m) for Project IDs
                    pno = f"\033[93m{w.pno}\033[0m"
                    # Green (\033[92m) for numeric data like Hours
                    hours = f"\033[92m{w.hours}\033[0m"
                    
                    work_data.append([eno, pno, hours])

                # Header using Purple/Magenta style
                print("\n\033[1;35m PROJECT ASSIGNMENT REGISTRY\033[0m")
                
                # 'fancy_grid' prevents scattered output in web consoles
                print(tabulate(work_data, 
                               headers=["ENO", "PNO", "HOURS WORKED"], 
                               tablefmt="fancy_grid"))
            else:
                questionary.print(" No work records found.", style="#ff000d")

        #------------------------------ADD NEW WORK RECORD------------------------------------#


        elif "Add New Work Record" in choice:
            
            #--------------------collecting the data------------------#

            print("\n[Step 1: Paste Work Assignment Details]")
            print("Format: eno, pno, hours")
            print("Example: 101, 1, 32.5")

            raw_input = questionary.text(">> (or type 'back' to cancel)").ask()

            if raw_input is None: continue
            if not raw_input or raw_input.lower() in ['back', 'b']: continue
            
            data = raw_input.split(",")

            #-------------------building new WorksOn object-----------#

            try:
                # Cleaning and mapping the split data to your names
                val_eno   = int(data[0].strip())
                val_pno   = int(data[1].strip())
                val_hours = float(data[2].strip())

                new_work_obj = WorksOn(val_eno, val_pno, val_hours)

                #--------------saving the record in database-------------#

                success = add_work_record(new_work_obj)
                
                if success:
                    questionary.print(f" Success: Work record for Employee {val_eno} on Project {val_pno} added!", style="#00ff26")
                else:
                    questionary.print(f"Failed: Check if both Employee {val_eno} and Project {val_pno} exist.", "#ec1818")
            
            except Exception:
                questionary.print(" Input Error: Please use the correct comma-separated format.", "#ec1818")

        
       #----------------------------------DELETE WORK RECORD----------------------------------#


        elif "Delete Work Record" in choice:

            # We need both IDs to target a unique assignment
            val_eno = questionary.text("Enter Employee ID (eno) (or 'back'):").ask()

            if val_eno is None: continue
            if not val_eno or val_eno.lower() in ['back', 'b']: continue
            
            val_pno = questionary.text("Enter Project Number (pno) (or 'back'):").ask()

            if val_pno is None: continue
            if not val_pno or val_pno.lower() in ['back', 'b']: continue
            
            # --- SAFETY FIRST: CONFIRMATION GUARD ---
            confirm = questionary.confirm(f"⚠️  DANGER: Remove Employee {val_eno} from Project {val_pno}?", default=False).ask()
            if confirm:
                success = delete_work_record(int(val_eno), int(val_pno))
                if success:
                    questionary.print(f" Assignment Removed: Employee {val_eno} is no longer on Project {val_pno}.", style="bold #ff0000")
                else:
                    questionary.print(f" Deletion Failed: No matching record found for Employee {val_eno} on Project {val_pno}.", style="bold #ec1818")
            else:
                questionary.print(" Deletion cancelled.", style="#00ff26")


        #--------------------------SEARCH WORK BY EMPLOYEE ID--------------------------#


        elif "Search Work by Employee ID" in choice:
            val_eno = questionary.text("Enter Employee ID (eno) (or 'back'):").ask()

            if val_eno is None: continue
            if not val_eno or val_eno.lower() in ['back', 'b']: continue
            
            results = get_work_by_eno(int(val_eno))

            if results:
                # Prepare rows for the grid
                # Since we search by ENO, we only show PNO and Hours
                work_data = []
                for w in results:
                    # Yellow for Project ID to keep contrast
                    pno = f"\033[93m{w.pno}\033[0m"
                    # Green for Hours worked
                    hours = f"\033[92m{w.hours}\033[0m"
                    work_data.append([pno, hours])

                # Header using your preferred brown/earth tone
                print(f"\n\033[38;5;95m📂 WORK ASSIGNMENTS FOR EMPLOYEE: {val_eno}\033[0m")
                
                # Fancy grid prevents column shifting in web consoles
                print(tabulate(work_data, 
                               headers=["PROJECT NO (PNO)", "HOURS WORKED"], 
                               tablefmt="fancy_grid"))
            else:
                questionary.print(f" No work assignments found for Employee: {val_eno}", style="#ff6600")

#------------------------------------------------------DEPARTMENT LOCATION HUB-----------------------------------------------------#

def location_hub():
    """
    THE LOCATION MODULE:
    Keep track of which office buildings or cities your departments are located in.
    """

    while True:
        # Formal header for the Location module
        print("\n" + tabulate([["\033[1;36mCORPORATE OFFICE & LOCATION REGISTRY\033[0m"]], tablefmt="fancy_grid", stralign="center"))

        choice = questionary.select(
            "SELECT ACTION:",
            choices=[
                "┌──────────────────────────────────────────┐",
                "│  View All Department Locations           │",
                "│  Add New Department Location             │",
                "│  Delete Department Location              │",
                "│  Search Locations by Department ID       │",
                "├──────────────────────────────────────────┤",
                "│  Back to Dashboard                       │",
                "└──────────────────────────────────────────┘"
            ],
            style=custom_style,
            pointer=" ▶ "
        ).ask()

        if choice is None: break

        if "Back to Dashboard" in choice:
            break   


        #------------------------------VIEW ALL LOCATIONS------------------------------------#


        elif "View All Department Locations" in choice:
            # Fetch location objects from query_engine
            results = get_all_dept_locations()
            
            if results:
                # Prepare data rows for the fancy grid
                location_data = []
                for loc in results:
                    # Cyan (\033[1;36m) for the Department ID to match your Hub style
                    d_id = f"\033[1;36m{loc.dno}\033[0m"
                    # White for the physical location string
                    office = loc.dlocation
                    
                    location_data.append([d_id, office])

                # Header using your Teal/Cyan preference
                print("\n\033[1;36m CORPORATE OFFICE REGISTRY\033[0m")
                
                # 'fancy_grid' provides a double-line cage for the data
                print(tabulate(location_data, 
                               headers=["DEPT ID", "OFFICE LOCATION"], 
                               tablefmt="fancy_grid"))
            else:
                questionary.print(" No department locations found.", style="#ff000d")

        #------------------------------ADD NEW LOCATION------------------------------------#


        elif "Add New Department Location" in choice:

            #--------------------collecting the data------------------#

            print("\n[Step 1: Paste Location Details]")
            print("Format: dno, dlocation")
            print("Example: 1, Ahmedabad")

            raw_input = questionary.text(">> (or type 'back' to cancel)").ask()

            if raw_input is None: continue
            if not raw_input or raw_input.lower() in ['back', 'b']: continue
            
            data = raw_input.split(",")

            #-------------------building new DeptLocation object-----------#

            try:
                # Cleaning and mapping the split data to your names
                val_dno = int(data[0].strip())
                val_loc = data[1].strip()

                new_loc_obj = DeptLocation(val_dno, val_loc)

                #--------------saving the record in database-------------#

                success = add_dept_location(new_loc_obj)
                
                if success:
                    questionary.print(f" Success: New location '{val_loc}' added for Department {val_dno}!", style="#00ff26")
                else:
                    questionary.print(f" Failed: Check if Department {val_dno} exists.", "#ec1818")
            
            except Exception:
                questionary.print(" Input Error: Please use the correct comma-separated format.", "#ec1818")


       #------------------------------DELETE DEPARTMENT LOCATION--------------------------------#


        elif "Delete Department Location" in choice:

            # Need both to identify which specific office to remove
            val_dno = questionary.text("Enter Department ID (dno) (or 'back'):").ask()

            if val_dno is None: continue
            if not val_dno or val_dno.lower() in ['back', 'b']: continue
            
            val_loc = questionary.text("Enter Location Name to delete (or 'back'):").ask()

            if val_loc is None: continue
            if not val_loc or val_loc.lower() in ['back', 'b']: continue
            
            # --- SAFETY FIRST: CONFIRMATION GUARD ---
            confirm = questionary.confirm(f"  DANGER: Remove Office '{val_loc}' from Department {val_dno}?", default=False).ask()
            if confirm:
                success = delete_dept_location(int(val_dno), val_loc)
                if success:
                    questionary.print(f" Record Removed: Office '{val_loc}' for Dept {val_dno} deleted.", style="bold #ff0000")
                else:
                    questionary.print(f" Deletion Failed: No mapping found for {val_loc} under DNO {val_dno}.", style="#ec1818")
            else:
                questionary.print(" Deletion cancelled.", style="#00ff26")


        #--------------------------SEARCH LOCATIONS BY DEPARTMENT ID--------------------------#


        elif "Search Locations by Department ID" in choice:

            # Using questionary for consistent input style
            val_dno = questionary.text("Enter Department ID (dno):").ask()

            if val_dno is None: continue
            results = get_locations_by_dno(int(val_dno))

            if results:
                # Prepare data rows for the fancy grid
                location_data = []
                for loc in results:
                    # Cyan (\033[1;36m) for the Department ID
                    d_id = f"\033[1;36m{loc.dno}\033[0m"
                    # Standard text for the location name
                    office = loc.dlocation
                    
                    location_data.append([d_id, office])

                # Header using your preferred earth-tone/brown
                print(f"\n\033[38;5;95m OFFICE SITES FOR DEPARTMENT: {val_dno}\033[0m")
                
                # 'fancy_grid' locks the layout to prevent scattering in web consoles
                print(tabulate(location_data, 
                               headers=["DEPT ID", "OFFICE LOCATION"], 
                               tablefmt="fancy_grid"))
            else:
                questionary.print(f" No office locations found for Department: {val_dno}", style="#ff6600")

#---------------------------------------------------------AUDIT LOG HUB-------------------------------------------------------------#

def display_audit_table(logs):
    """Hardened display function with Grid structure and Professional Colors."""
    if not logs:
        questionary.print("\n No matching activity found for this filter.", style="bold #ff9d00")
        return

    for log in logs:
        # 1. Professional Header (Cyan)
        timestamp = log['changed_at'].strftime("%Y-%m-%d %H:%M:%S")
        print("\n" + "="*85)
        # Using ANSI colors directly for the header
        header = f"\033[1;36m EVENT: {log['operation']} | TABLE: {log['table_name'].upper()} | TIME: {timestamp}\033[0m"
        print(header)
        
        # 2. Extract and Sort Keys
        old_data = log['old_data'] or {}
        new_data = log['new_data'] or {}
        all_keys = sorted(set(old_data.keys()) | set(new_data.keys()))
        
        # 3. Build Table Rows with Color Logic
        table_data = []
        for key in all_keys:
            old_val = old_data.get(key, "---")
            new_val = new_data.get(key, "---")
            
            # If data changed, we color Old as Red and New as Green
            if str(old_val) != str(new_val):
                # \033[91m is Red, \033[92m is Green, \033[0m resets color
                colored_old = f"\033[91m{old_val}\033[0m"
                colored_new = f"\033[92m{new_val}\033[0m"
                table_data.append(["\033[93m>>\033[0m", f"\033[1m{key.upper()}\033[0m", colored_old, colored_new])
            else:
                table_data.append(["", key.upper(), str(old_val), str(new_val)])

        # 4. Use 'grid' format for the professional 'box' look
        print(tabulate(table_data, 
                       headers=["", "ATTRIBUTE", "BEFORE", "AFTER"], 
                       tablefmt="grid"))


def audit_hub():
    """
    THE SECURITY CAMERA ROOM:
    This is the most powerful part of the system. It tracks every single 'INSERT', 'UPDATE', and 'DELETE'
    accountably so you always know WHO changed WHAT and WHEN.
    """
    while True:
        # High-impact header for the Security entrance
        print("\n" + tabulate([["\033[1;36mSYSTEM AUDIT & SECURITY CONTROL CENTER\033[0m"]], tablefmt="fancy_grid", stralign="center"))

        main_choice = questionary.select(
            "SELECT SECURITY MODULE:",
            choices=[
                "1. Global Activity Feed (Company-Wide)",
                "2. Employee Investigation (Specific Person)",
                "3. Table-Specific Analysis",
                "4. Operation Breakdown (INSERT/UPDATE/DELETE counts)",
                "5. System Maintenance & Health",
                "Back to Dashboard"
            ],
            style=custom_style,
            pointer=" ▶ "
        ).ask()
 
        if main_choice is None:
            break
 
        if "Back to Dashboard" in main_choice:
            break
        
        if "1. Global Activity Feed" in main_choice:
            global_audit_menu()
            
        elif "2. Employee Investigation" in main_choice:
            employee_audit_menu()
            
        elif "3. Table-Specific Analysis" in main_choice:
            table_audit_menu()

        elif "4. Operation Breakdown" in main_choice:
            operation_summary_menu()
            
        elif "5. System Maintenance & Health" in main_choice:
            maintenance_menu()

#------------------------------------------GLOBAL AUDIT MENU-------------------------------#

def global_audit_menu():
    while True:
        print("\n" + tabulate([["\033[1;36mGLOBAL ACTIVITY FEED: COMPANY-WIDE OVERSIGHT\033[0m"]], tablefmt="fancy_grid", stralign="center"))

        choice = questionary.select(
            "SELECT PARAMETERS:",
            choices=[
                "[A] Last 'N' Actions (Count-based)",
                "[B] Time-Window View (Dynamic Interval)",
                "Back to Audit Panel"
            ],
            style=custom_style,
            pointer=" ▶ "
        ).ask()

        if choice is None: break

        if "Back to Audit Panel" in choice:
            break

        if "[A] Last 'N' Actions" in choice:
            try:
                n_input = questionary.text("Enter the number of recent actions (or 'back'):").ask()
                if n_input is None: continue
                if not n_input or n_input.lower() in ['back', 'b']: continue
                limit = int(n_input)
                
                print(f"\n\033[1;33m[SYSTEM]: Fetching last {limit} company-wide actions...\033[0m")
                
                logs = get_global_logs(limit=limit)
                display_audit_table(logs) 
            except ValueError:
                questionary.print("Invalid input! Please enter a whole number.", style="fg:#ff0000")

        elif "[B] Time-Window View" in choice:
            print("\n\033[1;37mInterval Examples: '1 hour', '30 minutes', '2 days', '1 week'\033[0m")
            interval = questionary.text("Enter the time window (or 'back'):").ask()
            if interval is None: continue
            if not interval or interval.lower() in ['back', 'b']: continue
            
            print(f"\n\033[1;33m[SYSTEM]: Fetching actions from the last {interval}...\033[0m")

            logs = get_global_logs(interval=interval)
            display_audit_table(logs)
#----------------------------------------EMPLOYEE AUDIT MENU--------------------------------#

def employee_audit_menu():
    while True:
        print("\n" + tabulate([["\033[1;36mSECURITY AUDIT: PERSONNEL INVESTIGATION\033[0m"]], tablefmt="fancy_grid", stralign="center"))
        
        target_id = questionary.text("Enter Employee ID to investigate (or type 'back'):").ask()
        
        if target_id is None: break
        if not target_id or target_id.lower() in ['back', 'b']:
            break
            
        try:
            eid = int(target_id)
        except ValueError:
            print("\033[1;31mInvalid ID. Please enter a numeric value.\033[0m")
            continue

        print("\n" + tabulate([[f"\033[1;33mINVESTIGATING EMPLOYEE: {eid}\033[0m"]], tablefmt="fancy_grid", stralign="center"))
        
        choice = questionary.select(
            "SELECT INVESTIGATION CRITERIA:",
            choices=[
                "[A] Last 'N' Actions for this ID",
                "[B] Time-Window View for this ID",
                "[C] Salary History",
                "[D] Transfer History",
                "Change Employee ID / Back"
            ],
            style=custom_style,
            pointer=" ▶ "
        ).ask()

        if choice is None: continue

        if "Change Employee ID / Back" in choice:
            continue

        if "[A] Last 'N' Actions" in choice:
            try:
                n_input = questionary.text(f"How many recent actions for Employee {eid}? (or 'back'):").ask()
                if n_input is None: continue
                if not n_input or n_input.lower() in ['back', 'b']: continue
                n = int(n_input)
                logs = get_employee_specific_logs(target_eno=eid, limit=n)
                display_audit_table(logs)
            except ValueError:
                print("\033[1;31mError: Please enter a valid number.\033[0m")

        elif "[B] Time-Window View" in choice:
            interval = questionary.text(f"Enter time window for Employee {eid} (or 'back'):").ask()
            if interval is None: continue
            if not interval or interval.lower() in ['back', 'b']: continue
            logs = get_employee_specific_logs(target_eno=eid, interval=interval)
            display_audit_table(logs)

        elif "[C] Salary History" in choice:
            print(f"\n\033[1;33m[SYSTEM]: Fetching Salary History for Employee {eid}...\033[0m")
            history = get_salary_history(eid)
            
            if not history:
                questionary.print(" No salary change records found.", style="#ff9d00")
                continue
                
            hist_rows = []
            for i, entry in enumerate(history, start=1):
                ts    = entry['changed_at'].strftime("%Y-%m-%d  %H:%M:%S")
                old_s = f"\033[91m{entry['old_salary']:>13,.2f}\033[0m"
                new_s = f"\033[92m{entry['new_salary']:>13,.2f}\033[0m"
                diff  = entry['new_salary'] - entry['old_salary']
                if entry['direction'] == "RAISE":
                    arrow = f"\033[92m▲  +{diff:,.2f}\033[0m"
                elif entry['direction'] == "CUT":
                    arrow = f"\033[91m▼  {diff:,.2f}\033[0m"
                else:
                    arrow = f"\033[90m●  unchanged\033[0m"
                hist_rows.append([f"\033[1;36m{i}\033[0m", ts, old_s, new_s, arrow])
                
            print(tabulate(hist_rows, headers=["#", "CHANGED AT", "OLD SALARY", "NEW SALARY", "CHANGE"], tablefmt="fancy_grid"))

        elif "[D] Transfer History" in choice:
            print(f"\n\033[1;33m[SYSTEM]: Fetching Transfer History for Employee {eid}...\033[0m")
            transfers = get_transfer_history(eid)
            
            if not transfers:
                questionary.print(" No department transfer records found.", style="#ff9d00")
                continue
                
            t_rows = []
            for i, entry in enumerate(transfers, start=1):
                ts = entry['changed_at'].strftime("%Y-%m-%d  %H:%M:%S")
                t_rows.append([
                    f"\033[1;36m{i}\033[0m",
                    ts,
                    f"\033[91mDept {entry['old_dno']}\033[0m",
                    f"\033[92mDept {entry['new_dno']}\033[0m"
                ])
                
            print(tabulate(t_rows, headers=["#", "CHANGED AT", "FROM DEPT", "TO DEPT"], tablefmt="fancy_grid"))
        
#------------------------------------------TABLE AUDIT MENU---------------------------------#

def table_audit_menu():

    while True:
        # 1. Select the Table (Boxed View)
        print("\n" + tabulate([["\033[1;36mSECURITY AUDIT: TABLE SELECTION\033[0m"]], tablefmt="fancy_grid", stralign="center"))
        target_table = questionary.select(
            "SELECT DATASET TO ANALYZE:",
            choices=[
                "employee",
                "department",
                "project",
                "dept_locations",
                "works_on",
                "dependent",
                "Back to Audit Panel"
            ],
            style=custom_style,
            pointer=" ▶ "
        ).ask()

        if target_table is None: break

        if "Back to Audit Panel" in target_table:
            break

        # 2. Select Filter Type (Boxed View)
        # We strip the bars to keep the upper() function working correctly
        clean_table_name = target_table.replace("│", "").strip()
        
        print("\n" + tabulate([[f"\033[1;33mANALYSIS: {clean_table_name.upper()}\033[0m"]], tablefmt="fancy_grid", stralign="center"))
        
        choice = questionary.select(
            "CHOOSE FILTER CRITERIA:",
            choices=[
                "[A] Last 'N' Actions",
                "[B] Time-Window View",
                "[C] Filter by Operation",
                "Change Table / Back"
            ],
            style=custom_style,
            pointer=" ▶ "
        ).ask()

        if choice is None: continue

        if "Change Table / Back" in choice:
            continue

        # --- LOGIC HANDLING WITH 'IN' OPERATOR ---
        
        if "[A] Last 'N' Actions" in choice:
            try:
                n_input = questionary.text(f"How many actions for {clean_table_name}? (or 'back'):").ask()
                if n_input is None: continue
                if not n_input or n_input.lower() in ['back', 'b']: continue
                logs = get_table_specific_logs(table_name=clean_table_name, limit=int(n_input))
                display_audit_table(logs)
            except ValueError:
                print("Invalid input: please enter a number.")

        elif "[B] Time-Window View" in choice:
            interval = questionary.text(f"Enter time window for {clean_table_name} (or 'back'):").ask()
            if interval is None: continue
            if not interval or interval.lower() in ['back', 'b']: continue
            logs = get_table_specific_logs(table_name=clean_table_name, interval=interval)
            display_audit_table(logs)

        elif "[C] Filter by Operation" in choice:
            op_choice = questionary.select(
                "Select Operation Type:",
                choices=[
                    "INSERT",
                    "UPDATE",
                    "DELETE",
                    "Back"
                ],
                style=custom_style,
                pointer=" ▶ "
            ).ask()
 
            if op_choice is None: continue

            if "Back" in op_choice:
                continue
                
            op = op_choice.replace("│", "").strip()

            refine = questionary.select(
                f"Narrow down {op}s by:",
                choices=["Show All", "Last 'N' occurrences", "Specific Time Window"],
                style=custom_style
            ).ask()
 
            if refine is None: continue

            if refine == "Show All":
                logs = get_table_specific_logs(table_name=clean_table_name, operation=op)
            elif refine == "Last 'N' occurrences":
                n_input = questionary.text(f"Enter number of {op}s to show (or 'back'):").ask()
                if n_input is None: continue
                if not n_input or n_input.lower() in ['back', 'b']: continue
                logs = get_table_specific_logs(table_name=clean_table_name, operation=op, limit=int(n_input))
            elif refine == "Specific Time Window":
                interval = questionary.text(f"Enter window for {op}s (or 'back'):").ask()
                if interval is None: continue
                if not interval or interval.lower() in ['back', 'b']: continue
                logs = get_table_specific_logs(table_name=clean_table_name, operation=op, interval=interval)
            
            display_audit_table(logs)

        
#--------------------------------------OPERATION SUMMARY MENU-------------------------------#

def operation_summary_menu():
    while True:
        print("\n" + tabulate([["\033[1;36mOPERATION BREAKDOWN & METRICS\033[0m"]], tablefmt="fancy_grid", stralign="center"))
        
        choice = questionary.select(
            "SELECT TIME WINDOW:",
            choices=[
                "[A] All-Time Summary",
                "[B] Custom Time Interval",
                "Back to Audit Panel"
            ],
            style=custom_style,
            pointer=" ▶ "
        ).ask()

        if choice is None: break
        if "Back to Audit Panel" in choice: break

        interval = None
        if "[B] Custom Time Interval" in choice:
            print("\n\033[1;37mExamples: '1 hour', '1 day', '7 days', '1 month'\033[0m")
            interval = questionary.text("Enter time window (or 'back'):").ask()
            if interval is None: continue
            if not interval or interval.lower() in ['back', 'b']: continue
            print(f"\n\033[1;33m[SYSTEM]: Analyzing actions from the last {interval}...\033[0m")
        else:
            print(f"\n\033[1;33m[SYSTEM]: Analyzing all-time system actions...\033[0m")

        summary = get_operation_summary(interval=interval)
        
        if not summary:
            questionary.print(" No operational data found for this period.", style="#ff9d00")
            continue
            
        grid_data = []
        total_ops = 0
        
        for row in summary:
            table_name, op, count = row
            total_ops += count
            
            # Color coding
            t_col = f"\033[1m{table_name.upper()}\033[0m"
            if op == "INSERT":
                o_col = f"\033[92m{op}\033[0m"  # Green
            elif op == "DELETE":
                o_col = f"\033[91m{op}\033[0m"  # Red
            else:
                o_col = f"\033[93m{op}\033[0m"  # Yellow
                
            grid_data.append([t_col, o_col, f"\033[1;36m{count}\033[0m"])
            
        print(tabulate(grid_data, headers=["TABLE", "OPERATION", "COUNT"], tablefmt="fancy_grid"))
        print(f"  \033[1;33mTOTAL OPERATIONS MATCHED:\033[0m \033[1;36m{total_ops}\033[0m")

#------------------------------------------MAINTENANCE MENU---------------------------------#


# --- MULTITHREADING UTILITIES ---
# This list is our "Shared Bucket". 
# The background thread will put data in here, and the main menu will read from it.
audit_stats_bucket = []
def background_worker_stats():
    """
    A simple worker that runs independently.
    It calls your existing database function without blocking the UI.
    """
    global audit_stats_bucket
    
    time.sleep(3)
    # 1. We call your existing function from query_engine.py
    # No changes were made to your database code!
    results = get_audit_stats()
    
    # 2. We 'pour' the data into the bucket for the main thread to find
    audit_stats_bucket = results


def maintenance_menu():
    while True:
        # Maintenance header for broad POV
        print("\n" + tabulate([["\033[1;36mSYSTEM MAINTENANCE & DATABASE HEALTH\033[0m"]], tablefmt="fancy_grid", stralign="center"))

        choice = questionary.select(
            "SELECT UTILITY:",
            choices=[
                "[A] Data Retention (The Vacuum)",
                "[B] View Audit Statistics",
                "Back to Audit Panel"
            ],
            style=custom_style,
            pointer=" ▶ "
        ).ask()

        if choice is None: break

        if "Back to Audit Panel" in choice:
            break

        # --- OPTION A: THE VACUUM ---
        if "[A] Data Retention (The Vacuum)" in choice:
            days_input = questionary.text("Enter number of days to RETAIN (older logs will be deleted)\n(or type 'back'):").ask()
            if days_input is None: continue
            if not days_input or days_input.lower() in ['back', 'b']:
                continue
            try:
                count = clear_old_logs(int(days_input))
                questionary.print(f" Success: {count} old logs have been vacuumed from the system.", style="fg:#98c379")
            except ValueError:
                print("Please enter a valid number of days.")

        # --- OPTION B: STORAGE STATS (Professional Threaded Version) ---
        elif "[B] View Audit Statistics" in choice:
            global audit_stats_bucket
            audit_stats_bucket = []

            worker_thread = threading.Thread(target=background_worker_stats)
            worker_thread.start()

            # --- THE SPINNING WHEEL ---
            symbols = ["|", "/", "-", "\\"]
            i = 0
            print("\n\033[93m[SYSTEM]: ANALYZING STORAGE METRICS... \033[0m", end="", flush=True)
            
            while worker_thread.is_alive():
                print(f"\b{symbols[i]}", end="", flush=True)
                i = (i + 1) % len(symbols)
                time.sleep(0.1)
            
            print("\bDone!", flush=True)
            stats = audit_stats_bucket
            
            if stats:
                # 1. Prepare data for Tabulate
                # We add color codes to the numbers to make them pop
                formatted_stats = []
                for table, count, size in stats:
                    # Blue/Cyan for table names, Green for counts, Yellow for size
                    name = f"\033[1;36m{table.upper()}\033[0m"
                    logs = f"\033[92m{count}\033[0m"
                    kb = f"\033[93m{size} KB\033[0m"
                    formatted_stats.append([name, logs, kb])

                # 2. Use 'fancy_grid' for an even more formal look
                print("\n\033[1m DATABASE STORAGE HEALTH REPORT\033[0m")
                print(tabulate(formatted_stats, 
                               headers=["TABLE NAME", "TOTAL LOGS", "STORAGE SIZE"], 
                               tablefmt="fancy_grid"))
                
                # 3. Add a footer summary
                total_kb = sum(row[2] for row in stats)
            else:
                print("\nNo statistics available.")
        

if __name__ == "__main__":
    landing_page()