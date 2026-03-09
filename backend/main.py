# ==================================================================================================
# main.py  —  EMS FastAPI Server
# ==================================================================================================
# THE BRIDGE: This file is the web-facing entry point for the Employee Management System.
#
# ARCHITECTURE PRINCIPLE:
#   - cli_main.py   → Terminal users  → imports query_engine directly
#   - main.py       → Browser users   → HTTP API → imports same query_engine
#   Both share the same database logic. Neither knows the other exists.
#
# HOW TENANCY WORKS IN THE WEB CONTEXT:
#   The CLI uses a global CURRENT_TENANT_ID (fine for single-user terminal).
#   The web API is stateless: every request carries a JWT token that contains the
#   tenant_id. We call set_current_tenant() at the start of each request, and the
#   global is safe because each HTTP request is handled sequentially in this setup.
#   For production multi-user scaling, upgrade to per-request context vars.
#
# TO RUN (from the backend/ directory):
#   cd Employee-Management-System/backend
#   pip install -r requirements_web.txt
#   uvicorn main:app --reload --port 8000
#
# CORS is configured to allow your frontend (any origin in dev, lock down in prod).
# ==================================================================================================

import os
import json
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, List
import csv
import io

from fastapi import FastAPI, HTTPException, Depends, status, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from jose import JWTError, jwt
import httpx

# --------------------------------------------------------------------------------------------------
# IMPORT YOUR EXISTING BACKEND — ZERO CHANGES TO THESE FILES
# --------------------------------------------------------------------------------------------------
from app.core.connection_factory import ConnectionFactory
from app.core.security import verify_password, hash_password
from app.system.provisioning_service import ProvisioningService

import services.query_engine as qe
from services.query_engine import (
    set_current_tenant,
    get_all_employees, get_employee_by_id, add_new_employee,
    delete_employee, update_employee_salary, search_employees_by_name,
    bulk_import_employees, transfer_employee,
    get_all_departments, get_department_by_id, add_new_department,
    delete_department, update_department_manager, get_payroll_summary,
    get_all_projects, get_project_by_id, add_new_project,
    delete_project, update_project_location,
    get_all_dependents, get_dependents_by_eno, add_new_dependent, delete_dependent,
    get_all_dept_locations, get_locations_by_dno, add_dept_location,
    update_dept_location, delete_dept_location,
    get_all_work_records, get_work_by_eno, add_work_record, delete_work_record,
    get_global_logs, get_employee_specific_logs, get_table_specific_logs,
    get_salary_history, get_transfer_history, get_operation_summary,
    clear_old_logs, get_audit_stats,
)

from app.models.employee import Employee
from app.models.department import Department
from app.models.project import Project
from app.models.dependent import Dependent
from app.models.works_on import WorksOn
from app.models.dept_locations import DeptLocation

from services.data_porter import export_company_data_json, export_company_data_csv

# --------------------------------------------------------------------------------------------------
# JWT CONFIG  —  Change SECRET_KEY to a long random string before deploying
# --------------------------------------------------------------------------------------------------
SECRET_KEY = os.getenv("JWT_SECRET", "ems-super-secret-dev-key-change-in-production")
SUPABASE_ANON_KEY = os.getenv(
    "SUPABASE_ANON_KEY",
    # Fallback: the public anon key for this Supabase project (safe to hardcode — it's public)
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inh2YWp0Z2NldG9ybHpybm1rbGFvIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzIxODI3MjYsImV4cCI6MjA4Nzc1ODcyNn0.Tf31vlooUkG-K42C3WYhSctANQJyk9u-syDqn9dH70g"
)
ALGORITHM  = "HS256"
TOKEN_EXPIRE_HOURS = 12

security = HTTPBearer()


# ==================================================================================================
# APP SETUP
# ==================================================================================================

app = FastAPI(
    title="EMS API",
    description="Employee Management System — REST API for the web frontend",
    version="1.0.0"
)

# Allow the HTML files to call this API (open in dev; restrict to your domain in prod)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================================================================================================
# SERIALISATION HELPERS
# --------------------------------------------------------------------------------------------------
# Python objects from query_engine (Employee, Department etc.) are not directly JSON-serialisable.
# These helpers convert them to plain dicts that FastAPI can return as JSON.
# ==================================================================================================

def serial(obj):
    """Recursively convert any unserialisable Python type to a JSON-safe value."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, dict):
        return {k: serial(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [serial(i) for i in obj]
    return obj


def emp_to_dict(e) -> dict:
    return serial({
        "eno": e.eno, "ename": e.ename, "dob": e.dob,
        "gender": e.gender, "salary": e.salary,
        "super_eno": e.super_eno, "dno": e.dno
    })


def dept_to_dict(d) -> dict:
    return serial({
        "dno": d.dno, "dname": d.dname,
        "mgr_eno": d.mgr_eno, "mgrstartdate": d.mgrstartdate
    })


def proj_to_dict(p) -> dict:
    return serial({
        "pno": p.pno, "pname": p.pname,
        "plocation": p.plocation, "dno": p.dno
    })


def dep_to_dict(d) -> dict:
    return serial({
        "eno": d.eno, "dependent_name": d.dependent_name,
        "gender": d.gender, "dob": d.dob, "relationship": d.relationship
    })


def loc_to_dict(l) -> dict:
    return serial({"dno": l.dno, "dlocation": l.dlocation})


def work_to_dict(w) -> dict:
    return serial({"eno": w.eno, "pno": w.pno, "hours": w.hours})


def log_to_dict(log) -> dict:
    """Convert a psycopg2 DictRow audit log to a plain JSON-safe dict."""
    return serial({
        "log_id":     log["log_id"],
        "table_name": log["table_name"],
        "operation":  log["operation"],
        "old_data":   log["old_data"],
        "new_data":   log["new_data"],
        "changed_at": log["changed_at"],
    })


# ==================================================================================================
# JWT UTILITIES
# ==================================================================================================

def create_token(tenant_id: str, company_name: str) -> str:
    """Mint a JWT that encodes who is logged in."""
    expire = datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": tenant_id,
        "company": company_name,
        "exp": expire
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises HTTPException on failure."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session. Please log in again."
        )


def get_current_tenant(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    FastAPI dependency: extracts tenant_id from the Bearer token,
    then calls set_current_tenant() so query_engine works correctly.
    Inject this into any protected route with: tenant=Depends(get_current_tenant)
    """
    payload    = decode_token(credentials.credentials)
    tenant_id  = payload.get("sub")
    if not tenant_id:
        raise HTTPException(status_code=401, detail="Token missing tenant context.")
    set_current_tenant(tenant_id)
    return tenant_id


# ==================================================================================================
# PYDANTIC REQUEST MODELS
# --------------------------------------------------------------------------------------------------
# These define the shape of JSON bodies the frontend sends to POST/PUT endpoints.
# ==================================================================================================

class LoginRequest(BaseModel):
    company_name: str
    password: str

class SignupRequest(BaseModel):
    company_name: str
    password: str
    email: Optional[str] = None

class ChangePasswordRequest(BaseModel):
    company_name: str
    current_password: str
    new_password: str

class UpdateEmailRequest(BaseModel):
    company_name: str
    password: str
    new_email: str

class EmployeeCreate(BaseModel):
    eno: int
    ename: str
    dob: str            # "YYYY-MM-DD"
    gender: str         # "M" or "F"
    salary: float
    super_eno: Optional[int] = None
    dno: int

class EmployeeUpdate(BaseModel):
    new_salary: Optional[float] = None
    new_dno: Optional[int]      = None  # for transfer

class BulkEmployee(BaseModel):
    employees: List[EmployeeCreate]

class DepartmentCreate(BaseModel):
    dno: int
    dname: str
    mgr_eno: int
    mgrstartdate: str   # "YYYY-MM-DD"

class DepartmentManagerUpdate(BaseModel):
    mgr_eno: int

class ProjectCreate(BaseModel):
    pno: int
    pname: str
    plocation: str
    dno: int

class ProjectLocationUpdate(BaseModel):
    new_location: str

class DependentCreate(BaseModel):
    eno: int
    dependent_name: str
    gender: str
    dob: str
    relationship: str

class LocationCreate(BaseModel):
    dno: int
    dlocation: str

class LocationUpdate(BaseModel):
    old_location: str
    new_location: str

class WorkCreate(BaseModel):
    eno: int
    pno: int
    hours: float

class ClearLogsRequest(BaseModel):
    days: int = 30


# ==================================================================================================
# SECTION 0: HEALTH CHECK
# ==================================================================================================

@app.get("/")
def root():
    return {"status": "EMS API is running", "version": "1.0.0"}

@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ==================================================================================================
# SECTION 1: AUTHENTICATION
# ==================================================================================================

@app.post("/auth/login")
def login(body: LoginRequest):
    """
    Validates company credentials against public.tenants.
    Returns a JWT token on success — the frontend stores this and sends it on every request.
    """
    try:
        with ConnectionFactory.get_admin_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT tenant_id, hashed_password FROM public.tenants WHERE company_name = %s",
                    (body.company_name,)
                )
                row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=401, detail="Company not found.")

        tenant_id, hashed_pwd = row
        if not verify_password(body.password, hashed_pwd):
            raise HTTPException(status_code=401, detail="Incorrect password.")

        token = create_token(tenant_id, body.company_name)
        return {
            "token":        token,
            "tenant_id":    tenant_id,
            "company_name": body.company_name,
            "expires_in":   TOKEN_EXPIRE_HOURS * 3600
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login error: {str(e)}")


@app.post("/auth/signup")
def signup(body: SignupRequest):
    """
    Creates a new company workspace.
    Calls the same ProvisioningService the CLI uses — nothing duplicated.
    """
    if not body.company_name.strip() or not body.password.strip():
        raise HTTPException(status_code=400, detail="Company name and password are required.")

    success, result = ProvisioningService.provision_new_company(
        body.company_name.strip(),
        body.password,
        body.email
    )

    if not success:
        raise HTTPException(status_code=400, detail=result)

    # Auto-login: mint a token immediately after signup
    token = create_token(result, body.company_name.strip())
    return {
        "token":        token,
        "tenant_id":    result,
        "company_name": body.company_name.strip(),
        "message":      "Workspace created successfully."
    }


@app.post("/auth/change-password")
def change_password(body: ChangePasswordRequest):
    """Changes the company password. Requires current password for verification."""
    success, msg = ProvisioningService.change_company_password(
        body.company_name, body.current_password,
        body.new_password, body.new_password  # confirm = new (frontend already validated)
    )
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg}


@app.post("/auth/update-email")
def update_email(body: UpdateEmailRequest):
    """Updates the company's registered email address."""
    success, msg = ProvisioningService.update_company_email(
        body.company_name, body.password, body.new_email
    )
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg}


class DeleteWorkspaceRequest(BaseModel):
    company_name: str
    password: str

@app.delete("/auth/delete-workspace")
def delete_workspace(body: DeleteWorkspaceRequest):
    """Permanently deletes a company workspace. Called from the Settings danger zone."""
    success, msg = ProvisioningService.delete_company_space(body.company_name, body.password)
    if not success:
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg}



class SupabaseExchangeRequest(BaseModel):
    access_token: str

@app.post("/auth/supabase-exchange")
async def supabase_exchange(body: SupabaseExchangeRequest):
    """
    Receives a Supabase access_token (from Google OAuth or Email OTP),
    looks up which EMS workspace is registered with that email,
    and returns an EMS JWT — same shape as /auth/login.
    """
    # 1. Ask Supabase who this token belongs to
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://xvajtgcetorlzrnmklao.supabase.co/auth/v1/user",
                headers={
                    "Authorization": f"Bearer {body.access_token}",
                    "apikey": SUPABASE_ANON_KEY,
                },
                timeout=10,
            )
        if resp.status_code != 200:
            raise HTTPException(
                status_code=401,
                detail=f"Supabase token rejected (status {resp.status_code}). "
                       f"Response: {resp.text[:200]}"
            )
        user_email = resp.json().get("email")
        if not user_email:
            raise HTTPException(status_code=401, detail="No email found in Supabase token.")
    except HTTPException:
        raise
    except httpx.RequestError as e:
        raise HTTPException(status_code=503, detail=f"Could not reach Supabase: {str(e)}")

    # 2. Look up the EMS workspace by email
    try:
        with ConnectionFactory.get_admin_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT tenant_id, company_name FROM public.tenants WHERE email = %s",
                    (user_email,)
                )
                row = cur.fetchone()
        if not row:
            raise HTTPException(
                status_code=404,
                detail=f"No EMS workspace is registered with {user_email}. "
                       "Log in with your company name and password, go to Settings → Contact, "
                       "save this email address, then try again."
            )
        tenant_id, company_name = row
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 3. Mint and return an EMS JWT — identical shape to /auth/login
    token = create_token(tenant_id, company_name)
    return {
        "token":        token,
        "company_name": company_name,
        "tenant_id":    tenant_id,
    }


@app.get("/auth/me")
def get_me(tenant: str = Depends(get_current_tenant)):
    """
    Returns current session info. The frontend calls this on page load
    to verify the token is still valid and get the company name.
    """
    try:
        with ConnectionFactory.get_admin_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT company_name, email, created_at FROM public.tenants WHERE tenant_id = %s",
                    (tenant,)
                )
                row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Tenant not found.")
        company_name, email, created_at = row
        return {
            "tenant_id":    tenant,
            "company_name": company_name,
            "email":        email,
            "created_at":   serial(created_at),
        }
    except HTTPException:
        raise
    except Exception as e:
        # email column might not exist yet — return without it
        return {"tenant_id": tenant, "company_name": tenant, "email": None}


# ==================================================================================================
# SECTION 2: EMPLOYEES
# ==================================================================================================

@app.get("/employees")
def list_employees(tenant: str = Depends(get_current_tenant)):
    employees = get_all_employees()
    return [emp_to_dict(e) for e in employees]


@app.get("/employees/search")
def search_employees(q: str, tenant: str = Depends(get_current_tenant)):
    results = search_employees_by_name(q)
    return [emp_to_dict(e) for e in results]


@app.get("/employees/{eno}")
def get_employee(eno: int, tenant: str = Depends(get_current_tenant)):
    emp = get_employee_by_id(eno)
    if not emp:
        raise HTTPException(status_code=404, detail=f"Employee {eno} not found.")
    return emp_to_dict(emp)


@app.post("/employees", status_code=201)
def create_employee(body: EmployeeCreate, tenant: str = Depends(get_current_tenant)):
    emp = Employee(
        body.eno, body.ename, body.dob, body.gender,
        body.salary, body.super_eno, body.dno
    )
    success = add_new_employee(emp)
    if not success:
        raise HTTPException(status_code=400, detail="Could not add employee. Check for duplicate ID or invalid department.")
    return emp_to_dict(emp)


@app.delete("/employees/{eno}")
def remove_employee(eno: int, tenant: str = Depends(get_current_tenant)):
    success = delete_employee(eno)
    if not success:
        raise HTTPException(status_code=400, detail=f"Could not delete employee {eno}.")
    return {"message": f"Employee {eno} deleted."}


@app.patch("/employees/{eno}/salary")
def update_salary(eno: int, body: EmployeeUpdate, tenant: str = Depends(get_current_tenant)):
    if body.new_salary is None:
        raise HTTPException(status_code=400, detail="new_salary is required.")
    success = update_employee_salary(eno, body.new_salary)
    if not success:
        raise HTTPException(status_code=400, detail=f"Could not update salary for employee {eno}.")
    return {"message": f"Salary updated for employee {eno}.", "new_salary": body.new_salary}


@app.patch("/employees/{eno}/transfer")
def transfer_emp(eno: int, body: EmployeeUpdate, tenant: str = Depends(get_current_tenant)):
    if body.new_dno is None:
        raise HTTPException(status_code=400, detail="new_dno is required.")
    success, result = transfer_employee(eno, body.new_dno)
    if not success:
        raise HTTPException(status_code=400, detail=f"Transfer failed: {result}")
    return {"message": f"Employee {eno} transferred.", "old_dno": result, "new_dno": body.new_dno}


@app.post("/employees/bulk-import", status_code=201)
def bulk_import(body: BulkEmployee, tenant: str = Depends(get_current_tenant)):
    emp_objects = [
        Employee(e.eno, e.ename, e.dob, e.gender, e.salary, e.super_eno, e.dno)
        for e in body.employees
    ]
    count, errors = bulk_import_employees(emp_objects)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})
    return {"message": f"{count} employees imported successfully.", "count": count}


@app.get("/employees/{eno}/salary-history")
def salary_history(eno: int, tenant: str = Depends(get_current_tenant)):
    history = get_salary_history(eno)
    return [serial(dict(h)) for h in history]


@app.get("/employees/{eno}/transfer-history")
def transfer_history(eno: int, tenant: str = Depends(get_current_tenant)):
    history = get_transfer_history(eno)
    return [serial(dict(h)) for h in history]


# ==================================================================================================
# SECTION 3: DEPARTMENTS
# ==================================================================================================

@app.get("/departments")
def list_departments(tenant: str = Depends(get_current_tenant)):
    return [dept_to_dict(d) for d in get_all_departments()]


@app.get("/departments/{dno}")
def get_department(dno: int, tenant: str = Depends(get_current_tenant)):
    dept = get_department_by_id(dno)
    if not dept:
        raise HTTPException(status_code=404, detail=f"Department {dno} not found.")
    return dept_to_dict(dept)


@app.post("/departments", status_code=201)
def create_department(body: DepartmentCreate, tenant: str = Depends(get_current_tenant)):
    dept = Department(body.dno, body.dname, body.mgr_eno, body.mgrstartdate)
    success = add_new_department(dept)
    if not success:
        raise HTTPException(status_code=400, detail="Could not add department. Check for duplicate ID.")
    return dept_to_dict(dept)


@app.delete("/departments/{dno}")
def remove_department(dno: int, tenant: str = Depends(get_current_tenant)):
    success = delete_department(dno)
    if not success:
        raise HTTPException(status_code=400, detail=f"Could not delete department {dno}. It may have active employees.")
    return {"message": f"Department {dno} deleted."}


@app.patch("/departments/{dno}/manager")
def update_manager(dno: int, body: DepartmentManagerUpdate, tenant: str = Depends(get_current_tenant)):
    success = update_department_manager(dno, body.mgr_eno)
    if not success:
        raise HTTPException(status_code=400, detail="Could not update manager.")
    return {"message": f"Manager updated for department {dno}."}


@app.get("/departments-payroll-summary")
def payroll_summary(tenant: str = Depends(get_current_tenant)):
    """Returns per-department headcount + salary stats for the dashboard."""
    rows = get_payroll_summary()
    result = []
    for row in rows:
        dno, dname, headcount, total_sal, avg_sal, max_sal, min_sal = row
        result.append({
            "dno":       dno,
            "dname":     dname,
            "headcount": headcount or 0,
            "total_sal": float(total_sal) if total_sal else 0.0,
            "avg_sal":   float(avg_sal)   if avg_sal   else 0.0,
            "max_sal":   float(max_sal)   if max_sal   else 0.0,
            "min_sal":   float(min_sal)   if min_sal   else 0.0,
        })
    return result


# ==================================================================================================
# SECTION 4: PROJECTS
# ==================================================================================================

@app.get("/projects")
def list_projects(tenant: str = Depends(get_current_tenant)):
    return [proj_to_dict(p) for p in get_all_projects()]


@app.get("/projects/{pno}")
def get_project(pno: int, tenant: str = Depends(get_current_tenant)):
    proj = get_project_by_id(pno)
    if not proj:
        raise HTTPException(status_code=404, detail=f"Project {pno} not found.")
    return proj_to_dict(proj)


@app.post("/projects", status_code=201)
def create_project(body: ProjectCreate, tenant: str = Depends(get_current_tenant)):
    proj = Project(body.pno, body.pname, body.plocation, body.dno)
    success = add_new_project(proj)
    if not success:
        raise HTTPException(status_code=400, detail="Could not add project.")
    return proj_to_dict(proj)


@app.delete("/projects/{pno}")
def remove_project(pno: int, tenant: str = Depends(get_current_tenant)):
    success = delete_project(pno)
    if not success:
        raise HTTPException(status_code=400, detail=f"Could not delete project {pno}.")
    return {"message": f"Project {pno} deleted."}


@app.patch("/projects/{pno}/location")
def update_proj_location(pno: int, body: ProjectLocationUpdate, tenant: str = Depends(get_current_tenant)):
    success = update_project_location(pno, body.new_location)
    if not success:
        raise HTTPException(status_code=400, detail="Could not update project location.")
    return {"message": f"Project {pno} location updated."}


# ==================================================================================================
# SECTION 5: DEPENDENTS
# ==================================================================================================

@app.get("/dependents")
def list_dependents(tenant: str = Depends(get_current_tenant)):
    return [dep_to_dict(d) for d in get_all_dependents()]


@app.get("/dependents/by-employee/{eno}")
def get_employee_dependents(eno: int, tenant: str = Depends(get_current_tenant)):
    return [dep_to_dict(d) for d in get_dependents_by_eno(eno)]


@app.post("/dependents", status_code=201)
def create_dependent(body: DependentCreate, tenant: str = Depends(get_current_tenant)):
    dep = Dependent(body.eno, body.dependent_name, body.gender, body.dob, body.relationship)
    success = add_new_dependent(dep)
    if not success:
        raise HTTPException(status_code=400, detail="Could not add dependent. Check employee ID exists.")
    return dep_to_dict(dep)


@app.delete("/dependents/{eno}/{dependent_name}")
def remove_dependent(eno: int, dependent_name: str, tenant: str = Depends(get_current_tenant)):
    success = delete_dependent(eno, dependent_name)
    if not success:
        raise HTTPException(status_code=400, detail="Could not delete dependent.")
    return {"message": f"Dependent '{dependent_name}' removed from employee {eno}."}


# ==================================================================================================
# SECTION 6: DEPARTMENT LOCATIONS
# ==================================================================================================

@app.get("/dept-locations")
def list_locations(tenant: str = Depends(get_current_tenant)):
    return [loc_to_dict(l) for l in get_all_dept_locations()]


@app.get("/dept-locations/{dno}")
def get_dept_locations(dno: int, tenant: str = Depends(get_current_tenant)):
    return [loc_to_dict(l) for l in get_locations_by_dno(dno)]


@app.post("/dept-locations", status_code=201)
def create_location(body: LocationCreate, tenant: str = Depends(get_current_tenant)):
    loc = DeptLocation(body.dno, body.dlocation)
    success = add_dept_location(loc)
    if not success:
        raise HTTPException(status_code=400, detail="Could not add location. Check department ID exists.")
    return loc_to_dict(loc)


@app.patch("/dept-locations/{dno}")
def update_location(dno: int, body: LocationUpdate, tenant: str = Depends(get_current_tenant)):
    success = update_dept_location(dno, body.old_location, body.new_location)
    if not success:
        raise HTTPException(status_code=400, detail="Could not update location.")
    return {"message": "Location updated."}


@app.delete("/dept-locations/{dno}/{dlocation}")
def remove_location(dno: int, dlocation: str, tenant: str = Depends(get_current_tenant)):
    success = delete_dept_location(dno, dlocation)
    if not success:
        raise HTTPException(status_code=400, detail="Could not delete location.")
    return {"message": f"Location '{dlocation}' removed from department {dno}."}


# ==================================================================================================
# SECTION 7: WORKS ON (Project Assignments)
# ==================================================================================================

@app.get("/works-on")
def list_work_records(tenant: str = Depends(get_current_tenant)):
    return [work_to_dict(w) for w in get_all_work_records()]


@app.get("/works-on/by-employee/{eno}")
def get_work_by_employee(eno: int, tenant: str = Depends(get_current_tenant)):
    return [work_to_dict(w) for w in get_work_by_eno(eno)]


@app.post("/works-on", status_code=201)
def create_work_record(body: WorkCreate, tenant: str = Depends(get_current_tenant)):
    work = WorksOn(body.eno, body.pno, body.hours)
    success = add_work_record(work)
    if not success:
        raise HTTPException(status_code=400, detail="Could not add work record. Check employee and project IDs.")
    return work_to_dict(work)


@app.delete("/works-on/{eno}/{pno}")
def remove_work_record(eno: int, pno: int, tenant: str = Depends(get_current_tenant)):
    success = delete_work_record(eno, pno)
    if not success:
        raise HTTPException(status_code=400, detail="Could not delete work record.")
    return {"message": f"Work record for employee {eno} on project {pno} removed."}


# ==================================================================================================
# SECTION 8: AUDIT LOGS
# ==================================================================================================

@app.get("/audit/global")
def audit_global(
    limit: int = 50,
    interval: Optional[str] = None,
    tenant: str = Depends(get_current_tenant)
):
    """
    Returns the company-wide activity feed.
    Query params: ?limit=50  and/or  ?interval=1%20hour
    """
    logs = get_global_logs(limit=limit, interval=interval)
    return [log_to_dict(l) for l in logs]


@app.get("/audit/employee/{eno}")
def audit_employee(
    eno: int,
    limit: int = 50,
    interval: Optional[str] = None,
    tenant: str = Depends(get_current_tenant)
):
    logs = get_employee_specific_logs(target_eno=eno, limit=limit, interval=interval)
    return [log_to_dict(l) for l in logs]


@app.get("/audit/table/{table_name}")
def audit_table(
    table_name: str,
    operation: Optional[str] = None,
    limit: int = 50,
    interval: Optional[str] = None,
    tenant: str = Depends(get_current_tenant)
):
    logs = get_table_specific_logs(
        table_name=table_name, operation=operation,
        limit=limit, interval=interval
    )
    return [log_to_dict(l) for l in logs]


@app.get("/audit/stats")
def audit_stats(tenant: str = Depends(get_current_tenant)):
    stats = get_audit_stats()
    return [{"table_name": row[0], "count": row[1]} for row in stats]


@app.get("/audit/operation-summary")
def operation_summary(
    interval: Optional[str] = None,
    tenant: str = Depends(get_current_tenant)
):
    rows = get_operation_summary(interval=interval)
    return [{"table_name": r[0], "operation": r[1], "count": r[2]} for r in rows]


@app.delete("/audit/clear")
def clear_logs(body: ClearLogsRequest, tenant: str = Depends(get_current_tenant)):
    success = clear_old_logs(days=body.days)
    if not success:
        raise HTTPException(status_code=500, detail="Could not clear logs.")
    return {"message": f"Logs older than {body.days} days have been removed."}


# ==================================================================================================
# SECTION 9: DASHBOARD SUMMARY
# ==================================================================================================

@app.get("/dashboard/summary")
def dashboard_summary(tenant: str = Depends(get_current_tenant)):
    """
    Single endpoint that returns all the numbers the dashboard page needs.
    One call, one round-trip — avoids 6 separate fetches on page load.
    """
    try:
        employees    = get_all_employees()
        departments  = get_all_departments()
        projects     = get_all_projects()
        work_records = get_all_work_records()
        recent_logs  = get_global_logs(limit=10)

        # Department headcount map
        dept_counts = {}
        for e in employees:
            dept_counts[e.dno] = dept_counts.get(e.dno, 0) + 1

        dept_summary = []
        for d in departments:
            dept_summary.append({
                "dno":       d.dno,
                "dname":     d.dname,
                "headcount": dept_counts.get(d.dno, 0),
            })

        # Recent activity (last 10 logs)
        activity = [log_to_dict(l) for l in recent_logs]

        return {
            "total_employees":   len(employees),
            "total_departments": len(departments),
            "total_projects":    len(projects),
            "total_assignments": len(work_records),
            "dept_breakdown":    dept_summary,
            "recent_activity":   activity,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard error: {str(e)}")


# ==================================================================================================
# SECTION 10: DATA EXPORT
# ==================================================================================================

@app.post("/export/json")
def export_json(tenant: str = Depends(get_current_tenant)):
    """
    Triggers JSON snapshot export.
    Returns the file path (the server saves it; the client sees confirmation).
    For a browser download, this could be adapted to return StreamingResponse.
    """
    success, result = export_company_data_json()
    if not success:
        raise HTTPException(status_code=500, detail=result)
    return {"message": "JSON export complete.", "path": result}


@app.post("/export/csv")
def export_csv(tenant: str = Depends(get_current_tenant)):
    """Triggers CSV bundle export."""
    success, result = export_company_data_csv()
    if not success:
        raise HTTPException(status_code=500, detail=result)
    return {"message": "CSV export complete.", "path": result}


@app.get("/export/json/download")
def download_json(tenant: str = Depends(get_current_tenant)):
    """
    Streams a JSON export directly to the browser as a file download.
    The frontend can trigger this via window.location or an <a> tag with the token.
    """
    try:
        set_current_tenant(tenant)
        import psycopg2.extras
        from decimal import Decimal

        def clean(obj):
            if isinstance(obj, (datetime, date)): return obj.isoformat()
            if isinstance(obj, Decimal):          return float(obj)
            if isinstance(obj, dict):             return {k: clean(v) for k, v in obj.items()}
            if isinstance(obj, list):             return [clean(i) for i in obj]
            return obj

        tables = ["employee", "department", "project", "works_on",
                  "dependent", "dept_locations", "audit_log"]
        data   = {"tenant_id": tenant, "exported_at": datetime.now().isoformat(), "records": {}}

        with ConnectionFactory.get_tenant_connection(tenant) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                for table in tables:
                    cur.execute(f"SELECT * FROM {table};")
                    data["records"][table] = [clean(dict(r)) for r in cur.fetchall()]

        output   = json.dumps(data, indent=2)
        filename = f"ems_export_{date.today()}.json"
        return StreamingResponse(
            io.StringIO(output),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==================================================================================================
# END OF main.py
# ==================================================================================================