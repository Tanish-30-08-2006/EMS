# ==============================================================================
# backend/grand_stability_test.py
# ==============================================================================
# GRAND STABILITY TEST — Tests every feature of the EMS system end-to-end.
# Run this file directly: python grand_stability_test.py
# It will create a test company, run all operations, check results, then clean up.
# ==============================================================================

import sys
import os
import csv
import time
from datetime import date

# ── Path setup so imports work when run from /backend ──────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.query_engine import (
    set_current_tenant,
    # Employee
    get_all_employees, get_employee_by_id, add_new_employee,
    update_employee_salary, delete_employee,
    search_employees_by_name, bulk_import_employees,
    # Department
    get_all_departments, get_department_by_id, add_new_department,
    update_department_manager, delete_department, get_payroll_summary,
    # Project
    get_all_projects, get_project_by_id, add_new_project,
    update_project_location, delete_project,
    # Dependent
    get_all_dependents, get_dependents_by_eno, add_new_dependent, delete_dependent,
    # Dept Locations
    get_all_dept_locations, get_locations_by_dno, add_dept_location,
    update_dept_location, delete_dept_location,
    # Works On
    get_all_work_records, get_work_by_eno, add_work_record, delete_work_record,
    # Audit
    get_global_logs, get_employee_specific_logs,
    get_table_specific_logs, clear_old_logs, get_audit_stats,
)
from app.models.employee import Employee
from app.models.department import Department
from app.models.project import Project
from app.models.dependent import Dependent
from app.models.dept_locations import DeptLocation
from app.models.works_on import WorksOn
from app.system.provisioning_service import ProvisioningService
from services.data_porter import export_company_data_json, export_company_data_csv

# ── Test counters ───────────────────────────────────────────────────────────
passed = 0
failed = 0
TEST_COMPANY = "TEST_GrandStability_EMS"
TEST_PASSWORD = "TestPass@9999"

def ok(msg):
    global passed
    passed += 1
    print(f"  \033[92m[PASS]\033[0m {msg}")

def fail(msg):
    global failed
    failed += 1
    print(f"  \033[91m[FAIL]\033[0m {msg}")

def section(title):
    print(f"\n\033[1;36m{'='*60}\033[0m")
    print(f"\033[1;33m  {title}\033[0m")
    print(f"\033[1;36m{'='*60}\033[0m")

# ==============================================================================
# SETUP: Create test company
# ==============================================================================
section("SETUP — Provisioning Test Company")

# Clean up any previous failed run
try:
    ProvisioningService.force_delete_test_company(TEST_COMPANY)
    print("  [INFO] Cleaned up leftover test company from previous run.")
except:
    pass

success, result = ProvisioningService.provision_new_company(TEST_COMPANY, TEST_PASSWORD)
if success:
    ok(f"Company provisioned. Tenant ID: {result}")
    set_current_tenant(result)
else:
    fail(f"Provisioning failed: {result}")
    sys.exit(1)

time.sleep(0.5)

# ==============================================================================
# SECTION 1: DEPARTMENTS
# ==============================================================================
section("SECTION 1 — Department CRUD")

d1 = Department(1, "Engineering", None, None)
d2 = Department(2, "Human Resources", None, None)
d3 = Department(3, "Marketing", None, None)

ok("Adding Department 1 (Engineering)") if add_new_department(d1) else fail("Add Dept 1")
ok("Adding Department 2 (HR)") if add_new_department(d2) else fail("Add Dept 2")
ok("Adding Department 3 (Marketing)") if add_new_department(d3) else fail("Add Dept 3")

depts = get_all_departments()
ok(f"get_all_departments returned {len(depts)} departments") if len(depts) == 3 else fail(f"Expected 3 depts, got {len(depts)}")

found = get_department_by_id(2)
ok("get_department_by_id(2) = HR") if found and found.dname == "Human Resources" else fail("get_department_by_id failed")

ok("Delete Department 3") if delete_department(3) else fail("Delete Dept 3 failed")
depts_after = get_all_departments()
ok("Department 3 deleted, 2 remain") if len(depts_after) == 2 else fail(f"Expected 2 depts after delete, got {len(depts_after)}")

# ==============================================================================
# SECTION 2: EMPLOYEES
# ==============================================================================
section("SECTION 2 — Employee CRUD")

e1 = Employee(101, "Alice Johnson", "1985-06-15", "F", 75000, None, 1)
e2 = Employee(102, "Bob Martinez", "1990-11-22", "M", 55000, 101, 1)
e3 = Employee(103, "Carol Singh", "1992-03-08", "F", 62000, 101, 2)
e4 = Employee(104, "David Lee", "1988-09-30", "M", 48000, 103, 2)
e5 = Employee(105, "Eva Patel", "1995-01-17", "F", 51000, 101, 1)

ok("Add Employee 101") if add_new_employee(e1) else fail("Add Employee 101")
ok("Add Employee 102") if add_new_employee(e2) else fail("Add Employee 102")
ok("Add Employee 103") if add_new_employee(e3) else fail("Add Employee 103")
ok("Add Employee 104") if add_new_employee(e4) else fail("Add Employee 104")
ok("Add Employee 105") if add_new_employee(e5) else fail("Add Employee 105")

# Now set managers for departments
ok("Set Dept 1 manager to E101") if update_department_manager(1, 101) else fail("Update Dept 1 manager")
ok("Set Dept 2 manager to E103") if update_department_manager(2, 103) else fail("Update Dept 2 manager")

all_emps = get_all_employees()
ok(f"get_all_employees returned {len(all_emps)} employees") if len(all_emps) == 5 else fail(f"Expected 5, got {len(all_emps)}")

found_emp = get_employee_by_id(103)
ok("get_employee_by_id(103) = Carol Singh") if found_emp and found_emp.ename == "Carol Singh" else fail("get_employee_by_id failed")

ok("Update salary for E102 to 60000") if update_employee_salary(102, 60000) else fail("Salary update failed")
updated = get_employee_by_id(102)
ok("Salary update confirmed") if updated and float(updated.salary) == 60000.0 else fail(f"Salary not updated, got {updated.salary if updated else 'None'}")

ok("Delete Employee 105") if delete_employee(105) else fail("Delete E105")
after_del = get_all_employees()
ok("4 employees remain after delete") if len(after_del) == 4 else fail(f"Expected 4, got {len(after_del)}")

# ==============================================================================
# SECTION 3: SEARCH BY NAME (NEW FEATURE)
# ==============================================================================
section("SECTION 3 — Search Employees by Name (NEW)")

results_ali = search_employees_by_name("ali")
ok(f"search 'ali' found {len(results_ali)} result(s) — Alice") if len(results_ali) >= 1 else fail(f"'ali' search returned {len(results_ali)}")

results_son = search_employees_by_name("son")
ok(f"search 'son' found Alice Johnson") if any(e.ename == "Alice Johnson" for e in results_son) else fail("'son' search missed Alice Johnson")

results_none = search_employees_by_name("XXXXXXXX")
ok("search 'XXXXXXXX' returns empty list") if results_none == [] else fail("Expected empty list for gibberish search")

results_partial = search_employees_by_name("ar")
ok(f"search 'ar' (partial) found {len(results_partial)} — Carol, Martinez") if len(results_partial) >= 1 else fail("Partial name search failed")

# ==============================================================================
# SECTION 4: BULK IMPORT (NEW FEATURE)
# ==============================================================================
section("SECTION 4 — Bulk Import from CSV (NEW)")

# Write a temp CSV
csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_bulk_import.csv")
with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(["eno", "ename", "dob", "gender", "salary", "super_eno", "dno"])
    writer.writerow([201, "Frank Okafor",   "1991-07-12", "M", 53000, 101, 1])
    writer.writerow([202, "Grace Tanaka",   "1993-02-28", "F", 58000, 101, 1])
    writer.writerow([203, "Henry Vasquez",  "1987-11-05", "M", 67000, 103, 2])

success_count, errors = bulk_import_employees([
    Employee(201, "Frank Okafor",  "1991-07-12", "M", 53000, 101, 1),
    Employee(202, "Grace Tanaka",  "1993-02-28", "F", 58000, 101, 1),
    Employee(203, "Henry Vasquez", "1987-11-05", "M", 67000, 103, 2),
])
ok(f"Bulk import: {success_count} employees inserted, 0 errors") if success_count == 3 and not errors else fail(f"Bulk import failed: {errors}")

all_after_bulk = get_all_employees()
ok(f"Total employees now {len(all_after_bulk)} (4 original + 3 bulk)") if len(all_after_bulk) == 7 else fail(f"Expected 7, got {len(all_after_bulk)}")

# Test duplicate rejection
dup_count, dup_errors = bulk_import_employees([
    Employee(201, "Duplicate Frank", "1991-07-12", "M", 53000, 101, 1)
])
ok("Duplicate bulk import correctly rejected") if dup_errors else fail("Duplicate was not rejected")

# Clean up CSV
os.remove(csv_path)

# ==============================================================================
# SECTION 5: PAYROLL SUMMARY (NEW FEATURE)
# ==============================================================================
section("SECTION 5 — Payroll Summary by Department (NEW)")

payroll = get_payroll_summary()
ok(f"get_payroll_summary returned {len(payroll)} rows") if len(payroll) >= 2 else fail(f"Expected >= 2 dept rows, got {len(payroll)}")

eng_row = next((r for r in payroll if r[1] == "Engineering"), None)
ok("Engineering dept found in payroll") if eng_row else fail("Engineering not in payroll")

if eng_row:
    dno, dname, headcount, total_sal, avg_sal, max_sal, min_sal = eng_row
    ok(f"Engineering headcount = {headcount}") if headcount >= 4 else fail(f"Expected >= 4 in Engineering, got {headcount}")
    ok("Total salary > 0") if total_sal and float(total_sal) > 0 else fail("Total salary is 0 or None")
    ok("Max salary >= Min salary") if max_sal and min_sal and float(max_sal) >= float(min_sal) else fail("Max < Min salary — impossible")

# ==============================================================================
# SECTION 6: PROJECTS
# ==============================================================================
section("SECTION 6 — Project CRUD")

p1 = Project(1, "Phoenix Platform", "Ahmedabad", 1)
p2 = Project(2, "DataBridge API",   "Mumbai",    1)
p3 = Project(3, "HR Automation",    "Bangalore", 2)

ok("Add Project 1") if add_new_project(p1) else fail("Add Project 1")
ok("Add Project 2") if add_new_project(p2) else fail("Add Project 2")
ok("Add Project 3") if add_new_project(p3) else fail("Add Project 3")

all_proj = get_all_projects()
ok(f"get_all_projects: {len(all_proj)} projects") if len(all_proj) == 3 else fail(f"Expected 3, got {len(all_proj)}")

proj = get_project_by_id(2)
ok("get_project_by_id(2) = DataBridge API") if proj and proj.pname == "DataBridge API" else fail("get_project_by_id failed")

ok("Update Project 1 location to 'Surat'") if update_project_location(1, "Surat") else fail("update_project_location failed")
updated_p = get_project_by_id(1)
ok("Location update confirmed") if updated_p and updated_p.plocation == "Surat" else fail("Location not updated")

ok("Delete Project 3") if delete_project(3) else fail("Delete Project 3")
ok("2 projects remain") if len(get_all_projects()) == 2 else fail("Expected 2 projects after delete")

# ==============================================================================
# SECTION 7: WORKS ON (Project Assignments)
# ==============================================================================
section("SECTION 7 — Works On CRUD")

w1 = WorksOn(101, 1, 20.0)
w2 = WorksOn(102, 1, 30.0)
w3 = WorksOn(101, 2, 15.5)
w4 = WorksOn(203, 2, 40.0)

ok("Assign E101 to P1") if add_work_record(w1) else fail("Add work W1")
ok("Assign E102 to P1") if add_work_record(w2) else fail("Add work W2")
ok("Assign E101 to P2") if add_work_record(w3) else fail("Add work W3")
ok("Assign E203 to P2") if add_work_record(w4) else fail("Add work W4")

all_work = get_all_work_records()
ok(f"get_all_work_records: {len(all_work)} records") if len(all_work) == 4 else fail(f"Expected 4, got {len(all_work)}")

e101_work = get_work_by_eno(101)
ok("E101 has 2 project assignments") if len(e101_work) == 2 else fail(f"Expected 2 for E101, got {len(e101_work)}")

ok("Delete E102 from P1") if delete_work_record(102, 1) else fail("Delete work record")
ok("3 work records remain") if len(get_all_work_records()) == 3 else fail("Expected 3 after delete")

# ==============================================================================
# SECTION 8: DEPENDENTS
# ==============================================================================
section("SECTION 8 — Dependent CRUD")

dep1 = Dependent(101, "Tommy Johnson",  "M", "2015-04-10", "Son")
dep2 = Dependent(101, "Sara Johnson",   "F", "2018-09-22", "Daughter")
dep3 = Dependent(103, "Raj Singh",      "M", "1960-01-30", "Father")
dep4 = Dependent(102, "Maria Martinez", "F", "1988-07-14", "Spouse")

ok("Add dependent 1 (Tommy)") if add_new_dependent(dep1) else fail("Add dep1")
ok("Add dependent 2 (Sara)") if add_new_dependent(dep2) else fail("Add dep2")
ok("Add dependent 3 (Raj)") if add_new_dependent(dep3) else fail("Add dep3")
ok("Add dependent 4 (Maria)") if add_new_dependent(dep4) else fail("Add dep4")

all_deps = get_all_dependents()
ok(f"get_all_dependents: {len(all_deps)} records") if len(all_deps) == 4 else fail(f"Expected 4, got {len(all_deps)}")

e101_deps = get_dependents_by_eno(101)
ok("E101 has 2 dependents") if len(e101_deps) == 2 else fail(f"Expected 2 for E101, got {len(e101_deps)}")

ok("Delete dependent Sara Johnson") if delete_dependent(101, "Sara Johnson") else fail("Delete dependent")
ok("E101 now has 1 dependent") if len(get_dependents_by_eno(101)) == 1 else fail("Expected 1 after delete")

# ==============================================================================
# SECTION 9: DEPARTMENT LOCATIONS
# ==============================================================================
section("SECTION 9 — Department Locations CRUD")

loc1 = DeptLocation(1, "Ahmedabad HQ")
loc2 = DeptLocation(1, "Mumbai Office")
loc3 = DeptLocation(2, "Bangalore Campus")

ok("Add location 1") if add_dept_location(loc1) else fail("Add loc1")
ok("Add location 2") if add_dept_location(loc2) else fail("Add loc2")
ok("Add location 3") if add_dept_location(loc3) else fail("Add loc3")

all_locs = get_all_dept_locations()
ok(f"get_all_dept_locations: {len(all_locs)} records") if len(all_locs) == 3 else fail(f"Expected 3, got {len(all_locs)}")

dept1_locs = get_locations_by_dno(1)
ok("Dept 1 has 2 locations") if len(dept1_locs) == 2 else fail(f"Expected 2 for Dept 1, got {len(dept1_locs)}")

ok("Update location: Mumbai Office → Mumbai Branch") if update_dept_location(1, "Mumbai Office", "Mumbai Branch") else fail("update_dept_location failed")
updated_locs = get_locations_by_dno(1)
ok("Location rename confirmed") if any(l.dlocation == "Mumbai Branch" for l in updated_locs) else fail("Rename not confirmed")

ok("Delete Bangalore Campus") if delete_dept_location(2, "Bangalore Campus") else fail("delete_dept_location failed")
ok("2 locations remain") if len(get_all_dept_locations()) == 2 else fail("Expected 2 after delete")

# ==============================================================================
# SECTION 10: AUDIT TRAIL
# ==============================================================================
section("SECTION 10 — Audit Trail")

time.sleep(1)  # Small pause to ensure logs have been written

global_logs = get_global_logs(limit=100)
ok(f"get_global_logs returned {len(global_logs)} entries") if len(global_logs) > 0 else fail("No global logs found — audit trigger may not be working")

e101_logs = get_employee_specific_logs(target_eno=101, limit=50)
ok(f"Employee-specific logs for E101: {len(e101_logs)} entries") if len(e101_logs) > 0 else fail("No logs found for E101")

emp_table_logs = get_table_specific_logs(table_name="employee", limit=50)
ok(f"Table-specific logs for 'employee': {len(emp_table_logs)} entries") if len(emp_table_logs) > 0 else fail("No table logs for employee")

insert_logs = get_table_specific_logs(table_name="employee", operation="INSERT", limit=50)
ok(f"INSERT-filtered logs for employee: {len(insert_logs)}") if len(insert_logs) > 0 else fail("No INSERT logs for employee")

update_logs = get_table_specific_logs(table_name="employee", operation="UPDATE", limit=50)
ok(f"UPDATE-filtered logs for employee: {len(update_logs)}") if len(update_logs) > 0 else fail("No UPDATE logs — salary update should have created one")

delete_logs = get_table_specific_logs(table_name="employee", operation="DELETE", limit=50)
ok(f"DELETE-filtered logs for employee: {len(delete_logs)}") if len(delete_logs) > 0 else fail("No DELETE logs — we deleted employees in test")

interval_logs = get_global_logs(limit=50, interval="1 hour")
ok(f"Time-filtered logs (last 1 hour): {len(interval_logs)} entries") if len(interval_logs) > 0 else fail("Time-filtered logs empty — all test actions should be in last 1 hour")

dept_logs = get_table_specific_logs(table_name="department", limit=20)
ok(f"Department audit logs: {len(dept_logs)} entries") if len(dept_logs) > 0 else fail("No department audit logs")

proj_logs = get_table_specific_logs(table_name="project", limit=20)
ok(f"Project audit logs: {len(proj_logs)} entries") if len(proj_logs) > 0 else fail("No project audit logs")

dep_logs = get_table_specific_logs(table_name="dependent", limit=20)
ok(f"Dependent audit logs: {len(dep_logs)} entries") if len(dep_logs) > 0 else fail("No dependent audit logs")

loc_logs = get_table_specific_logs(table_name="dept_locations", limit=20)
ok(f"Dept locations audit logs: {len(loc_logs)} entries") if len(loc_logs) > 0 else fail("No dept_locations audit logs")

works_logs = get_table_specific_logs(table_name="works_on", limit=20)
ok(f"Works_on audit logs: {len(works_logs)} entries") if len(works_logs) > 0 else fail("No works_on audit logs")

stats = get_audit_stats()
ok(f"get_audit_stats returned {len(stats)} table entries") if len(stats) > 0 else fail("Audit stats empty")
if stats:
    print("  [INFO] Audit stats breakdown:")
    for count_tuple in stats:
        table_name, count = count_tuple[0], count_tuple[1]
        print(f"         {table_name}: {count} log entries")

ok("clear_old_logs(365) ran without error") if clear_old_logs(365) else fail("clear_old_logs failed")

# ==============================================================================
# SECTION 11: DATA EXPORT
# ==============================================================================
section("SECTION 11 — Data Export (CSV + JSON)")

csv_success, csv_result = export_company_data_csv()
ok(f"CSV export succeeded: {csv_result}") if csv_success else fail(f"CSV export failed: {csv_result}")

json_success, json_result = export_company_data_json()
ok(f"JSON export succeeded: {json_result}") if json_success else fail(f"JSON export failed: {json_result}")

# ==============================================================================
# TEARDOWN: Delete the test company
# ==============================================================================
section("TEARDOWN — Removing Test Company")

success, msg = ProvisioningService.force_delete_test_company(TEST_COMPANY)
ok(f"Test company deleted: {msg}") if success else fail(f"Cleanup failed: {msg}")

# ==============================================================================
# FINAL REPORT
# ==============================================================================
total = passed + failed
print(f"\n\033[1;36m{'='*60}\033[0m")
print(f"\033[1;33m  GRAND STABILITY TEST — FINAL REPORT\033[0m")
print(f"\033[1;36m{'='*60}\033[0m")
print(f"  Total Tests : {total}")
print(f"  \033[92mPassed      : {passed}\033[0m")
print(f"  \033[91mFailed      : {failed}\033[0m")
print(f"\033[1;36m{'='*60}\033[0m")

if failed == 0:
    print(f"\n  \033[1;92m ALL {passed} TESTS PASSED. SYSTEM IS STABLE.\033[0m\n")
else:
    print(f"\n  \033[1;91m {failed} TEST(S) FAILED. REVIEW ABOVE OUTPUT.\033[0m\n")
    sys.exit(1)
