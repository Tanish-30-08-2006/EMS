# =============================================================================
# backend/grand_stability_test_v2.py
# =============================================================================
# GRAND STABILITY TEST v2
# Covers: all 6 tables + 4 new features + full audit trail with edge cases.
# Creates a real isolated test company, runs every scenario, then cleans up.
# Run from /backend:  python grand_stability_test_v2.py
# =============================================================================

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.query_engine import (
    set_current_tenant,
    get_all_employees, get_employee_by_id, add_new_employee,
    update_employee_salary, delete_employee,
    transfer_employee, get_salary_history, get_transfer_history,
    get_all_departments, get_department_by_id, add_new_department,
    update_department_manager, delete_department, get_payroll_summary,
    get_all_projects, get_project_by_id, add_new_project,
    update_project_location, delete_project,
    get_all_dependents, get_dependents_by_eno, add_new_dependent, delete_dependent,
    get_all_dept_locations, get_locations_by_dno, add_dept_location,
    update_dept_location, delete_dept_location,
    get_all_work_records, get_work_by_eno, add_work_record, delete_work_record,
    get_global_logs, get_employee_specific_logs, get_table_specific_logs,
    get_operation_summary, clear_old_logs, get_audit_stats,
)
from app.models.employee       import Employee
from app.models.department     import Department
from app.models.project        import Project
from app.models.dependent      import Dependent
from app.models.dept_locations import DeptLocation
from app.models.works_on       import WorksOn
from app.system.provisioning_service import ProvisioningService
from services.data_porter import export_company_data_json, export_company_data_csv

# ── Counters ─────────────────────────────────────────────────────────────────
passed = 0
failed = 0
TEST_COMPANY  = "TEST_GrandStabilityV2_EMS"
ORIGINAL_PASS = "OriginalPass@1111"
CHANGED_PASS  = "ChangedPass@2222"

def ok(msg):
    global passed; passed += 1
    print(f"  \033[92m[PASS]\033[0m {msg}")

def fail(msg):
    global failed; failed += 1
    print(f"  \033[91m[FAIL]\033[0m {msg}")

def info(msg):
    print(f"  \033[90m[INFO]\033[0m {msg}")

def section(title):
    print(f"\n\033[1;36m{'═'*68}\033[0m")
    print(f"\033[1;33m  {title}\033[0m")
    print(f"\033[1;36m{'═'*68}\033[0m")

# =============================================================================
# SETUP
# =============================================================================
section("SETUP — Provision Isolated Test Company")

try:
    ProvisioningService.force_delete_test_company(TEST_COMPANY)
    info("Cleaned up leftover test company from a previous run.")
except Exception:
    pass

ok_prov, prov_result = ProvisioningService.provision_new_company(
    TEST_COMPANY, ORIGINAL_PASS)
if ok_prov:
    ok(f"Company provisioned. Tenant ID: {prov_result}")
    set_current_tenant(prov_result)
else:
    fail(f"Provisioning failed: {prov_result}")
    sys.exit(1)

time.sleep(0.3)

# =============================================================================
# SECTION 1 — PASSWORD CHANGE (all edge cases)
# =============================================================================
section("SECTION 1 — Password Change")

# 1-a: Wrong current password must fail
s, m = ProvisioningService.change_company_password(
    TEST_COMPANY, "WRONG_PASSWORD", CHANGED_PASS, CHANGED_PASS)
ok("Wrong current password correctly rejected") if not s else fail(
    f"Should reject wrong password; got: {m}")

# 1-b: Mismatched new passwords must fail
s, m = ProvisioningService.change_company_password(
    TEST_COMPANY, ORIGINAL_PASS, "AAA@111", "BBB@222")
ok("Mismatched new passwords correctly rejected") if not s else fail(
    f"Should reject mismatch; got: {m}")

# 1-c: Blank/whitespace-only new password must fail
s, m = ProvisioningService.change_company_password(
    TEST_COMPANY, ORIGINAL_PASS, "   ", "   ")
ok("Blank new password correctly rejected") if not s else fail(
    f"Should reject blank; got: {m}")

# 1-d: Non-existent company must fail
s, m = ProvisioningService.change_company_password(
    "NO_SUCH_COMPANY_XYZ", ORIGINAL_PASS, CHANGED_PASS, CHANGED_PASS)
ok("Non-existent company correctly rejected") if not s else fail(
    f"Should reject unknown company; got: {m}")

# 1-e: All-correct change must succeed
s, m = ProvisioningService.change_company_password(
    TEST_COMPANY, ORIGINAL_PASS, CHANGED_PASS, CHANGED_PASS)
ok(f"Valid password change succeeded") if s else fail(
    f"Valid change failed: {m}")

# 1-f: Old password must now be rejected
s, m = ProvisioningService.change_company_password(
    TEST_COMPANY, ORIGINAL_PASS, "any@New1", "any@New1")
ok("Old password correctly invalidated after change") if not s else fail(
    "Old password still works — SECURITY BREACH")

# 1-g: Cannot change password to the same password
s, m = ProvisioningService.change_company_password(
    TEST_COMPANY, CHANGED_PASS, CHANGED_PASS, CHANGED_PASS)
ok("Same new password correctly rejected") if not s else fail(
    f"Should reject same password; got: {m}")

# 1-h: New password works — change back so remaining tests run normally
s, m = ProvisioningService.change_company_password(
    TEST_COMPANY, CHANGED_PASS, ORIGINAL_PASS, ORIGINAL_PASS)
ok("Reverted to original password successfully") if s else fail(
    f"Could not revert: {m}")

# =============================================================================
# SECTION 2 — DEPARTMENTS
# =============================================================================
section("SECTION 2 — Department CRUD")

d1 = Department(1, "Engineering",     None, None)
d2 = Department(2, "Human Resources", None, None)
d3 = Department(3, "Marketing",       None, None)
d4 = Department(4, "Finance",         None, None)

for dept, lbl in [(d1,"D1"),(d2,"D2"),(d3,"D3"),(d4,"D4")]:
    ok(f"Add {lbl} {dept.dname}") if add_new_department(dept) else fail(f"Add {lbl}")

ok("get_all_departments = 4") if len(get_all_departments()) == 4 else fail(
    f"Expected 4, got {len(get_all_departments())}")

fd = get_department_by_id(2)
ok("get_department_by_id(2) = Human Resources") if (
    fd and fd.dname == "Human Resources") else fail("get_department_by_id(2) failed")

# Duplicate dno must fail
ok("Duplicate dept ID rejected") if not add_new_department(
    Department(1, "Duplicate", None, None)) else fail("Duplicate dept accepted")

ok("Delete D4 Finance") if delete_department(4) else fail("Delete D4")
ok("3 depts remain after delete") if len(get_all_departments()) == 3 else fail(
    f"Expected 3, got {len(get_all_departments())}")

# =============================================================================
# SECTION 3 — EMPLOYEES
# =============================================================================
section("SECTION 3 — Employee CRUD")

employees = [
    (Employee(101, "Alice Johnson", "1985-06-15", "F", 70000, None, 1), "E101"),
    (Employee(102, "Bob Martinez",  "1990-11-22", "M", 55000, 101,  1), "E102"),
    (Employee(103, "Carol Singh",   "1992-03-08", "F", 62000, 101,  2), "E103"),
    (Employee(104, "David Lee",     "1988-09-30", "M", 48000, 103,  2), "E104"),
    (Employee(105, "Eva Patel",     "1995-01-17", "F", 51000, 101,  1), "E105"),
    (Employee(106, "Frank Okafor",  "1991-07-12", "M", 53000, 101,  1), "E106"),
]
for emp, lbl in employees:
    ok(f"Add {lbl} {emp.ename}") if add_new_employee(emp) else fail(f"Add {lbl}")

ok("Set D1 manager → E101") if update_department_manager(1, 101) else fail("D1 mgr")
ok("Set D2 manager → E103") if update_department_manager(2, 103) else fail("D2 mgr")

ok("get_all_employees = 6") if len(get_all_employees()) == 6 else fail(
    f"Expected 6, got {len(get_all_employees())}")

e103 = get_employee_by_id(103)
ok("get_employee_by_id(103) = Carol Singh") if (
    e103 and e103.ename == "Carol Singh") else fail("get_employee_by_id(103) failed")

# Duplicate eno must fail
ok("Duplicate eno rejected") if not add_new_employee(
    Employee(101, "Dup", "1985-06-15", "F", 9999, None, 1)) else fail(
    "Duplicate eno accepted")

ok("Delete E106") if delete_employee(106) else fail("Delete E106")
ok("5 employees remain") if len(get_all_employees()) == 5 else fail(
    f"Expected 5, got {len(get_all_employees())}")

ok("Delete non-existent E999 does not crash") if (
    delete_employee(999) is not None) else fail("delete_employee returned None")

# =============================================================================
# SECTION 4 — SALARY HISTORY
# =============================================================================
section("SECTION 4 — Salary History (new feature)")

# 4-a: No history before any updates
ok("E101 salary history empty before updates") if get_salary_history(101) == [] else fail(
    f"Expected [], got {len(get_salary_history(101))} entries")

# 4-b: Three salary updates with distinct values
ok("Raise E101 70000→80000") if update_employee_salary(101, 80000) else fail("Update 1")
time.sleep(0.15)
ok("Raise E101 80000→95000") if update_employee_salary(101, 95000) else fail("Update 2")
time.sleep(0.15)
ok("Cut  E101 95000→72000")  if update_employee_salary(101, 72000) else fail("Update 3")
time.sleep(0.25)

hist = get_salary_history(101)
ok(f"Salary history has 3 entries (got {len(hist)})") if len(hist) == 3 else fail(
    f"Expected 3, got {len(hist)}")

if len(hist) == 3:
    ok("Entry 1 = RAISE (70000→80000)") if hist[0]['direction'] == "RAISE" else fail(
        f"Expected RAISE, got {hist[0]['direction']}")
    ok("Entry 2 = RAISE (80000→95000)") if hist[1]['direction'] == "RAISE" else fail(
        f"Expected RAISE, got {hist[1]['direction']}")
    ok("Entry 3 = CUT  (95000→72000)") if hist[2]['direction'] == "CUT" else fail(
        f"Expected CUT, got {hist[2]['direction']}")
    ok("Entry 1 old_salary = 70000") if abs(hist[0]['old_salary'] - 70000) < 0.01 else fail(
        f"Expected 70000, got {hist[0]['old_salary']}")
    ok("Entry 3 new_salary = 72000") if abs(hist[2]['new_salary'] - 72000) < 0.01 else fail(
        f"Expected 72000, got {hist[2]['new_salary']}")
    ok("Entry 3 diff is negative (CUT)") if (
        hist[2]['new_salary'] - hist[2]['old_salary'] < 0) else fail("CUT diff not negative")

# 4-c: Same-value update → SAME direction
ok("Same-value update E102 55000→55000") if update_employee_salary(102, 55000) else fail(
    "Same-value update failed")
time.sleep(0.1)
h102 = get_salary_history(102)
ok(f"E102 history has 1 entry (got {len(h102)})") if len(h102) == 1 else fail(
    f"Expected 1, got {len(h102)}")
if len(h102) == 1:
    ok("E102 direction = SAME") if h102[0]['direction'] == "SAME" else fail(
        f"Expected SAME, got {h102[0]['direction']}")

# 4-d: Employee never updated → empty
ok("E103 salary history = [] (never updated)") if get_salary_history(103) == [] else fail(
    f"Expected [], got {len(get_salary_history(103))}")

# 4-e: Non-existent employee → empty
ok("Salary history for non-existent E9999 = []") if get_salary_history(9999) == [] else fail(
    f"Expected [], got {len(get_salary_history(9999))}")

# =============================================================================
# SECTION 5 — EMPLOYEE TRANSFER
# =============================================================================
section("SECTION 5 — Employee Transfer (new feature)")

# 5-a: Baseline
e102_pre = get_employee_by_id(102)
ok(f"E102 is in Dept 1 before transfer") if (
    e102_pre and e102_pre.dno == 1) else fail(
    f"E102 not in Dept 1, in {e102_pre.dno if e102_pre else None}")

# 5-b: Valid transfer 1→2
s, result = transfer_employee(102, 2)
ok(f"Transfer E102 Dept 1→2, old_dno returned = {result}") if (
    s and result == 1) else fail(f"Transfer failed: {result}")
e102_post = get_employee_by_id(102)
ok("E102 confirmed in Dept 2 after transfer") if (
    e102_post and e102_post.dno == 2) else fail(
    f"E102 not updated, got {e102_post.dno if e102_post else None}")

# 5-c: Same-dept no-op must fail
s, msg = transfer_employee(102, 2)
ok("Same-dept transfer rejected") if not s else fail(
    f"No-op should fail; got: {msg}")

# 5-d: Non-existent dept must fail
s, msg = transfer_employee(102, 9999)
ok("Transfer to non-existent dept rejected") if not s else fail(
    f"Should reject dept 9999; got: {msg}")

# 5-e: Non-existent employee must fail
s, msg = transfer_employee(9999, 1)
ok("Transfer of non-existent employee rejected") if not s else fail(
    f"Should reject eno 9999; got: {msg}")

# 5-f: Transfer back 2→1 and verify history = 2 entries
time.sleep(0.15)
s, result = transfer_employee(102, 1)
ok("Transfer E102 back Dept 2→1") if s else fail(f"Transfer back failed: {result}")
time.sleep(0.25)

transfers = get_transfer_history(102)
ok(f"Transfer history for E102 = 2 entries (got {len(transfers)})") if (
    len(transfers) == 2) else fail(f"Expected 2, got {len(transfers)}")
if len(transfers) == 2:
    ok("Transfer 1: 1→2") if (
        transfers[0]['old_dno'] == 1 and transfers[0]['new_dno'] == 2) else fail(
        f"Expected 1→2, got {transfers[0]['old_dno']}→{transfers[0]['new_dno']}")
    ok("Transfer 2: 2→1") if (
        transfers[1]['old_dno'] == 2 and transfers[1]['new_dno'] == 1) else fail(
        f"Expected 2→1, got {transfers[1]['old_dno']}→{transfers[1]['new_dno']}")

# 5-g: E101 had salary changes but no transfers → empty transfer history
ok("E101 transfer history = [] (never transferred)") if (
    get_transfer_history(101) == []) else fail(
    f"Expected [], got {len(get_transfer_history(101))}")

# 5-h: Non-existent employee → empty
ok("Transfer history for non-existent E9999 = []") if (
    get_transfer_history(9999) == []) else fail(
    f"Expected [], got {len(get_transfer_history(9999))}")

# 5-i: Multiple transfers build up correctly — do a third transfer for E102
time.sleep(0.15)
s, _ = transfer_employee(102, 3)  # 1→3 (Marketing)
ok("Third transfer E102 Dept 1→3") if s else fail("Third transfer failed")
time.sleep(0.15)
transfers_3 = get_transfer_history(102)
ok(f"Transfer history now has 3 entries (got {len(transfers_3)})") if (
    len(transfers_3) == 3) else fail(f"Expected 3, got {len(transfers_3)}")

# Transfer back to dept 1 for payroll calc consistency
transfer_employee(102, 1)
time.sleep(0.15)

# =============================================================================
# SECTION 6 — PAYROLL SUMMARY
# =============================================================================
section("SECTION 6 — Payroll Summary (new feature)")

payroll = get_payroll_summary()
ok(f"get_payroll_summary returned {len(payroll)} rows") if len(payroll) >= 2 else fail(
    f"Expected >= 2 rows, got {len(payroll)}")

# Engineering: E101 (72000), E102 (55000), E105 (51000) = 3 employees
eng_row = next((r for r in payroll if r[1] == "Engineering"), None)
ok("Engineering in payroll") if eng_row else fail("Engineering missing from payroll")

if eng_row:
    dno, dname, hc, tot, avg, mx, mn = eng_row
    ok(f"Engineering headcount >= 3 (got {hc})") if hc >= 3 else fail(
        f"Expected >= 3, got {hc}")
    ok("Engineering total salary > 0") if tot and float(tot) > 0 else fail(
        "Total is 0 or None")
    ok("max >= avg >= min (ordering valid)") if (mx and mn and avg and
        float(mx) >= float(avg) >= float(mn)) else fail("Salary ordering violated")
    ok("avg is between min and max (math valid)") if (mn and mx and avg and
        float(mn) <= float(avg) <= float(mx)) else fail("avg outside [min, max]")

# Marketing has no employees → LEFT JOIN must still show it with headcount=0
mkt_row = next((r for r in payroll if r[1] == "Marketing"), None)
ok("Marketing in payroll (LEFT JOIN working)") if mkt_row else fail(
    "Marketing missing — LEFT JOIN not working")
if mkt_row:
    ok(f"Marketing headcount = 0") if mkt_row[2] == 0 else fail(
        f"Expected 0, got {mkt_row[2]}")
    ok("Marketing total_salary is NULL (no employees)") if (
        mkt_row[3] is None) else fail(f"Expected NULL, got {mkt_row[3]}")

# Grand total must equal sum of all employee current salaries
all_emp_now = get_all_employees()
expected_total = sum(float(e.salary) for e in all_emp_now)
actual_total   = sum(float(r[3]) for r in payroll if r[3] is not None)
ok(f"Grand payroll total = {actual_total:,.2f} (matches sum of salaries)") if (
    abs(actual_total - expected_total) < 0.01) else fail(
    f"Mismatch: expected {expected_total:,.2f}, got {actual_total:,.2f}")

# =============================================================================
# SECTION 7 — PROJECTS
# =============================================================================
section("SECTION 7 — Project CRUD")

for proj, lbl in [
    (Project(1, "Phoenix Platform", "Ahmedabad", 1), "P1"),
    (Project(2, "DataBridge API",   "Mumbai",    1), "P2"),
    (Project(3, "HR Automation",    "Bangalore", 2), "P3"),
    (Project(4, "Market Surge",     "Delhi",     3), "P4"),
]:
    ok(f"Add {lbl} {proj.pname}") if add_new_project(proj) else fail(f"Add {lbl}")

ok("get_all_projects = 4") if len(get_all_projects()) == 4 else fail(
    f"Expected 4, got {len(get_all_projects())}")
p2 = get_project_by_id(2)
ok("get_project_by_id(2) = DataBridge API") if (
    p2 and p2.pname == "DataBridge API") else fail("get_project_by_id(2) failed")
ok("Update P1 location to Surat") if update_project_location(1, "Surat") else fail(
    "update_project_location")
ok("P1 location = Surat") if (
    get_project_by_id(1) and get_project_by_id(1).plocation == "Surat") else fail(
    "Location not updated")
ok("Delete P4") if delete_project(4) else fail("Delete P4")
ok("3 projects remain") if len(get_all_projects()) == 3 else fail(
    f"Expected 3, got {len(get_all_projects())}")

# =============================================================================
# SECTION 8 — WORKS ON
# =============================================================================
section("SECTION 8 — Works On CRUD")

for w, lbl in [
    (WorksOn(101, 1, 20.0), "E101→P1"),
    (WorksOn(102, 1, 30.0), "E102→P1"),
    (WorksOn(101, 2, 15.5), "E101→P2"),
    (WorksOn(103, 3, 40.0), "E103→P3"),
    (WorksOn(104, 3, 35.0), "E104→P3"),
]:
    ok(f"Add work {lbl}") if add_work_record(w) else fail(f"Add {lbl}")

ok("get_all_work_records = 5") if len(get_all_work_records()) == 5 else fail(
    f"Expected 5, got {len(get_all_work_records())}")
ok("E101 has 2 assignments") if len(get_work_by_eno(101)) == 2 else fail(
    f"Expected 2, got {len(get_work_by_eno(101))}")
ok("Delete E102 from P1") if delete_work_record(102, 1) else fail("Delete work")
ok("4 records remain") if len(get_all_work_records()) == 4 else fail(
    f"Expected 4, got {len(get_all_work_records())}")
ok("Delete non-existent work record does not crash") if (
    delete_work_record(999, 999) is not None) else fail("delete_work_record returned None")

# =============================================================================
# SECTION 9 — DEPENDENTS
# =============================================================================
section("SECTION 9 — Dependent CRUD")

for d, lbl in [
    (Dependent(101, "Tommy Johnson",  "M", "2015-04-10", "Son"),      "Tommy"),
    (Dependent(101, "Sara Johnson",   "F", "2018-09-22", "Daughter"), "Sara"),
    (Dependent(103, "Raj Singh",      "M", "1960-01-30", "Father"),   "Raj"),
    (Dependent(102, "Maria Martinez", "F", "1988-07-14", "Spouse"),   "Maria"),
]:
    ok(f"Add dependent {lbl}") if add_new_dependent(d) else fail(f"Add {lbl}")

ok("get_all_dependents = 4") if len(get_all_dependents()) == 4 else fail(
    f"Expected 4, got {len(get_all_dependents())}")
ok("E101 has 2 dependents") if len(get_dependents_by_eno(101)) == 2 else fail(
    f"Expected 2, got {len(get_dependents_by_eno(101))}")
ok("Delete Sara Johnson") if delete_dependent(101, "Sara Johnson") else fail("Delete Sara")
ok("E101 now has 1 dependent") if len(get_dependents_by_eno(101)) == 1 else fail(
    "Expected 1 after delete")
ok("Duplicate dependent rejected") if not add_new_dependent(
    Dependent(101, "Tommy Johnson", "M", "2015-04-10", "Son")) else fail(
    "Duplicate dependent accepted")

# =============================================================================
# SECTION 10 — DEPARTMENT LOCATIONS
# =============================================================================
section("SECTION 10 — Department Locations CRUD")

for l, lbl in [
    (DeptLocation(1, "Ahmedabad HQ"),     "L1"),
    (DeptLocation(1, "Mumbai Office"),    "L2"),
    (DeptLocation(2, "Bangalore Campus"), "L3"),
    (DeptLocation(3, "Delhi Branch"),     "L4"),
]:
    ok(f"Add {lbl} {l.dlocation}") if add_dept_location(l) else fail(f"Add {lbl}")

ok("get_all_dept_locations = 4") if len(get_all_dept_locations()) == 4 else fail(
    f"Expected 4, got {len(get_all_dept_locations())}")
ok("Dept 1 has 2 locations") if len(get_locations_by_dno(1)) == 2 else fail(
    f"Expected 2, got {len(get_locations_by_dno(1))}")
ok("Rename Mumbai Office → Mumbai Branch") if update_dept_location(
    1, "Mumbai Office", "Mumbai Branch") else fail("update_dept_location")
ok("Rename confirmed") if any(
    l.dlocation == "Mumbai Branch" for l in get_locations_by_dno(1)) else fail(
    "Rename not confirmed")
ok("Delete Delhi Branch") if delete_dept_location(3, "Delhi Branch") else fail(
    "delete_dept_location")
ok("3 locations remain") if len(get_all_dept_locations()) == 3 else fail(
    f"Expected 3, got {len(get_all_dept_locations())}")
ok("Duplicate location rejected") if not add_dept_location(
    DeptLocation(1, "Ahmedabad HQ")) else fail("Duplicate location accepted")

# =============================================================================
# SECTION 11 — FULL AUDIT TRAIL
# =============================================================================
section("SECTION 11 — Full Audit Trail")

time.sleep(0.5)

# 11-a: Global logs
g_logs = get_global_logs(limit=500)
ok(f"get_global_logs returned {len(g_logs)} entries") if len(g_logs) > 0 else fail(
    "No global audit logs found")

# 11-b: Time-filtered global logs
i_logs = get_global_logs(limit=500, interval="1 hour")
ok(f"Time-filtered logs (1 hour): {len(i_logs)}") if len(i_logs) > 0 else fail(
    "Time-filtered logs empty")
ok("interval count <= total count") if len(i_logs) <= len(g_logs) else fail(
    "Interval returned MORE than all-time")

# 11-c: Employee-specific logs
e101_logs = get_employee_specific_logs(target_eno=101, limit=200)
ok(f"Employee logs for E101: {len(e101_logs)}") if len(e101_logs) > 0 else fail(
    "No logs for E101")
e101_i_logs = get_employee_specific_logs(target_eno=101, limit=200, interval="1 hour")
ok(f"E101 time-filtered logs: {len(e101_i_logs)}") if len(e101_i_logs) > 0 else fail(
    "E101 interval logs empty")

# 11-d: Table-specific logs — every table
for tname in ["employee", "department", "project",
              "works_on", "dependent", "dept_locations"]:
    tbl = get_table_specific_logs(table_name=tname, limit=200)
    ok(f"Table logs '{tname}': {len(tbl)}") if len(tbl) > 0 else fail(
        f"No audit logs for {tname}")

# 11-e: Operation filters for employee table
for op in ["INSERT", "UPDATE", "DELETE"]:
    op_l = get_table_specific_logs(table_name="employee", operation=op, limit=200)
    ok(f"employee {op} logs: {len(op_l)}") if len(op_l) > 0 else fail(
        f"No employee {op} logs")

# 11-f: Combined table + operation + interval
emp_upd = get_table_specific_logs(
    table_name="employee", operation="UPDATE", limit=200, interval="1 hour")
ok(f"employee UPDATE logs in last 1 hour: {len(emp_upd)}") if len(
    emp_upd) > 0 else fail("No recent employee UPDATE logs")

# 11-g: Operation summary all-time
op_sum = get_operation_summary()
ok(f"get_operation_summary all-time: {len(op_sum)} rows") if len(
    op_sum) > 0 else fail("Operation summary is empty")

tables_seen = {r[0] for r in op_sum}
for exp_tbl in ["employee", "department", "project",
                "works_on", "dependent", "dept_locations"]:
    ok(f"'{exp_tbl}' in operation summary") if exp_tbl in tables_seen else fail(
        f"'{exp_tbl}' missing from operation summary")

ops_seen = {r[1] for r in op_sum}
for exp_op in ["INSERT", "UPDATE", "DELETE"]:
    ok(f"'{exp_op}' operation type in summary") if exp_op in ops_seen else fail(
        f"'{exp_op}' missing from operation summary")

# 11-h: Operation summary with interval
op_sum_i = get_operation_summary(interval="1 hour")
ok(f"Time-filtered operation summary: {len(op_sum_i)} rows") if len(
    op_sum_i) > 0 else fail("Time-filtered operation summary empty")

# 11-i: INSERT counts must be logical
emp_inserts = next(
    (r[2] for r in op_sum if r[0] == "employee" and r[1] == "INSERT"), 0)
ok(f"Employee INSERT count = {emp_inserts} (expected 6)") if (
    emp_inserts >= 6) else fail(f"Expected >= 6 inserts, got {emp_inserts}")

# 11-j: Salary history cross-check
sal_xcheck = get_salary_history(101)
ok(f"Salary history cross-check: E101 = {len(sal_xcheck)} entries (expected 3)") if (
    len(sal_xcheck) == 3) else fail(f"Expected 3, got {len(sal_xcheck)}")

# 11-k: Transfer history cross-check (E102 had 3 transfers + 1 return = 4 total now)
tr_xcheck = get_transfer_history(102)
ok(f"Transfer history cross-check: E102 = {len(tr_xcheck)} entries") if (
    len(tr_xcheck) >= 2) else fail(f"Expected >= 2, got {len(tr_xcheck)}")

# 11-l: get_audit_stats — existing 3-tuple format must not be broken
stats = get_audit_stats()
ok(f"get_audit_stats returned {len(stats)} rows") if len(stats) > 0 else fail(
    "Audit stats empty")
info("Audit stats breakdown:")
for row in stats:
    table_name, count, _ = row   # third element is the hardcoded 0 placeholder
    info(f"  {table_name}: {count} log entries")

# 11-m: clear_old_logs(365) deletes nothing recent and does not crash
ok("clear_old_logs(365) runs without error") if clear_old_logs(365) else fail(
    "clear_old_logs crashed")
ok("Logs still exist after 365-day clear") if len(
    get_global_logs(limit=10)) > 0 else fail("All logs wiped — threshold too small")

# =============================================================================
# SECTION 12 — DATA EXPORT
# =============================================================================
section("SECTION 12 — Data Export")

csv_ok, csv_res = export_company_data_csv()
ok(f"CSV export succeeded: {csv_res}") if csv_ok else fail(
    f"CSV export failed: {csv_res}")

json_ok, json_res = export_company_data_json()
ok(f"JSON export succeeded: {json_res}") if json_ok else fail(
    f"JSON export failed: {json_res}")

# =============================================================================
# TEARDOWN
# =============================================================================
section("TEARDOWN — Removing Test Company")

s, m = ProvisioningService.force_delete_test_company(TEST_COMPANY)
ok(f"Test company deleted: {m}") if s else fail(f"Cleanup failed: {m}")

# =============================================================================
# FINAL REPORT
# =============================================================================
total = passed + failed
print(f"\n\033[1;36m{'═'*68}\033[0m")
print(f"\033[1;33m  GRAND STABILITY TEST v2 — FINAL REPORT\033[0m")
print(f"\033[1;36m{'═'*68}\033[0m")
print(f"  Total Tests  : {total}")
print(f"  \033[92mPassed       : {passed}\033[0m")
print(f"  \033[91mFailed       : {failed}\033[0m")
print(f"\033[1;36m{'═'*68}\033[0m")

if failed == 0:
    print(f"\n  \033[1;92m ALL {passed} TESTS PASSED. SYSTEM IS FULLY STABLE.\033[0m\n")
else:
    print(f"\n  \033[1;91m {failed} TEST(S) FAILED. SEE OUTPUT ABOVE.\033[0m\n")
    sys.exit(1)
