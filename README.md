# Employee Management System (EMS)

**Full-stack multi-tenant workforce management platform.**  
FastAPI backend · HTML/JS frontend · Supabase PostgreSQL · Deployed on Render + Vercel

> Developer: Tanish Sanghavi · DAIICT Gandhinagar · Batch 2028  
> GitHub: [Tanish-30-08-2006/EMS](https://github.com/Tanish-30-08-2006/EMS)

---

## Table of Contents

1. [What is this Project?](#1-what-is-this-project)
2. [Folder Structure](#2-folder-structure)
3. [Database Design](#3-database-design)
4. [Backend Architecture](#4-backend-architecture)
5. [Complete API Reference](#5-complete-api-reference)
6. [Authentication Flows](#6-authentication-flows)
7. [Supabase Setup](#7-supabase-setup)
8. [Google Cloud Console Setup](#8-google-cloud-console-setup)
9. [Deployment — Render + Vercel](#9-deployment--render--vercel)
10. [Frontend Architecture](#10-frontend-architecture)
11. [Local Development Setup](#11-local-development-setup)
12. [Security Design](#12-security-design)
13. [Common Errors and Fixes](#13-common-errors-and-fixes)
14. [Quick Reference Cheatsheet](#14-quick-reference-cheatsheet)

---

## 1. What is this Project?

The Employee Management System (EMS) is a full-stack web application that lets a company manage its workforce from a browser. Any company can sign up, create a private workspace, and manage employees, departments, projects, work assignments, dependents, office locations, and an automatic audit trail — all in one place.

The system is built for multiple companies at the same time. Each company gets its own private space in the database. Company A cannot see Company B's data. This is called multi-tenancy.

### 1.1 The Two Interfaces

Both interfaces use the same database logic. Nothing is duplicated.

| Interface | How to start it | Who uses it |
|-----------|----------------|-------------|
| Web (Browser) | Deploy backend to Render, frontend to Vercel | End users, company admins |
| CLI (Terminal) | `python cli_main.py` from the backend folder | Developer / admin testing |

### 1.2 High-Level System Map

```
                        INTERNET
                           |
           +---------------+---------------+
           |                               |
    [Browser / User]              [Terminal / Developer]
     Vercel (HTML/JS)              cli_main.py (Python)
           |                               |
           | HTTP (JSON)                   | Direct Python call
           v                               v
    [FastAPI Server]  <----both---->  [query_engine.py]
     main.py on Render                (shared logic)
                          |
                          v
             [Supabase PostgreSQL]
          aws-1-ap-southeast-1.pooler.supabase.com
                          |
            +-------------+-------------+
            |             |             |
      [public schema]  [comp_abc]  [comp_xyz]
      tenants table    6 tables     6 tables
      (all companies)  (Company A)  (Company B)
```

> The key design principle: every company has its own PostgreSQL schema (like a private folder). When Company A logs in, the database only opens their folder. Company B's data is physically unreachable.

---

## 2. Folder Structure

```
Employee-Management-System/
├── backend/
│   ├── main.py                          FastAPI server. All HTTP routes.
│   ├── cli_main.py                      Terminal interface. No HTTP.
│   ├── render.yaml                      Render deployment config.
│   ├── requirements_web.txt             Python packages list.
│   ├── .env                             Secret credentials. Never commit to Git.
│   ├── services/
│   │   ├── query_engine.py              All SQL logic. Used by both main.py and cli_main.py.
│   │   └── data_porter.py               Exports company data to JSON or CSV.
│   └── app/
│       ├── core/
│       │   ├── connection_factory.py    Opens DB connections. Sets tenant search_path.
│       │   └── security.py              bcrypt password hashing and verification.
│       ├── system/
│       │   └── provisioning_service.py  Creates and deletes company workspaces.
│       ├── models/
│       │   ├── employee.py              Python dataclass blueprint for an employee.
│       │   ├── department.py
│       │   ├── project.py
│       │   ├── dependent.py
│       │   ├── works_on.py
│       │   ├── dept_locations.py
│       │   └── audit_log.py
│       └── database/
│           └── tenant_template.sql      SQL run when a new company signs up.
│
└── frontend/
    ├── config.js                        One line: window.API_BASE = '...'. Change on deploy.
    ├── ems-init.js                      Runs on every page. Restores accent colour.
    ├── index.html                       Public landing page.
    ├── login.html                       Three login methods: password, OTP, Google.
    ├── signup.html                      Creates a new workspace.
    ├── dashboard.html                   Summary stats and recent audit activity.
    ├── employees.html                   Full CRUD. Bulk import. Salary history.
    ├── departments.html                 Full CRUD. Payroll summary.
    ├── projects.html                    Full CRUD.
    ├── works-on.html                    Project assignments and hours.
    ├── dependents.html                  Employee family members.
    ├── dept-locations.html              Office locations per department.
    ├── audit.html                       Automatic audit trail viewer.
    ├── export.html                      JSON and CSV data export.
    ├── settings.html                    Password, email, appearance, danger zone.
    └── about.html                       Static info page.
```

---

## 3. Database Design

The database is hosted on Supabase, which is a managed PostgreSQL service. You do not run Postgres yourself — Supabase runs it in the cloud.

### 3.1 Multi-Tenancy: One Database, Many Companies

PostgreSQL has a feature called schemas. A schema is like a folder inside the database. Every company that signs up gets its own schema. The tables inside each schema are identical, but the data is completely separate.

```
  Supabase PostgreSQL Database
  |
  |-- public schema
  |     |-- tenants table  (master list of all registered companies)
  |
  |-- comp_tanish schema   (created when 'tanish' company signs up)
  |     |-- employee
  |     |-- department
  |     |-- project
  |     |-- works_on
  |     |-- dependent
  |     |-- dept_locations
  |     |-- audit_log
  |
  |-- comp_acme schema     (created when 'acme' company signs up)
        |-- employee       (completely separate data)
        |-- department
        | ... (same 6 tables, different data)
```

### 3.2 The public.tenants Table

This is the master registry. Every company in the system has one row here.

| Column | Type | Purpose |
|--------|------|---------|
| company_name | VARCHAR | The name the company registered with. Used at login. |
| tenant_id | VARCHAR | The schema name (e.g. `comp_tanish`). Derived from company_name. Stored in the JWT. |
| hashed_password | TEXT | bcrypt hash. The actual password is never stored. |
| email | VARCHAR | Optional. Used to link Google OAuth and Email OTP logins to the workspace. |
| created_at | TIMESTAMP | When the workspace was created. |

### 3.3 The 6 Tables Inside Every Company Schema

When a company signs up, the provisioning service runs a SQL template that creates these 6 tables automatically:

| Table | Primary Key | What it stores |
|-------|-------------|----------------|
| employee | eno (int) | Name, DOB, gender, salary, supervisor (self-ref), department number. |
| department | dno (int) | Department name, manager employee number, manager start date. |
| project | pno (int) | Project name, location, owning department number. |
| works_on | eno + pno | Links employees to projects. Stores hours worked. Composite key. |
| dependent | eno + name | Family members of an employee. Name, gender, DOB, relationship. |
| dept_locations | dno + location | A department can have multiple office locations. Composite key. |
| audit_log | log_id (serial) | Automatic record of every INSERT, UPDATE, DELETE. Stores old and new data as JSON. |

### 3.4 Entity Relationship Diagram

```
  [department] <---------- [employee] ----------> [department]
       |          (dno FK)      |       (dno FK)       |
       |                        |                       |
       v                        |                       v
  [dept_locations]              |                 [dependent]
  (dno FK, many locs            |                 (eno FK, family
   per department)              |                  members)
                                |
                                v
                          [works_on]
                        (eno FK, pno FK)
                                |
                                v
                           [project]
                         (pno, dno FK)

  employee.super_eno --> employee.eno  (self-referential: supervisor)
  All tables --> [audit_log]  (trigger writes changes automatically)
```

> The audit_log table is fed by PostgreSQL triggers. When any row in any of the 6 tables is changed, the trigger fires automatically and writes the old and new values to audit_log. The application does not write to audit_log manually.

### 3.5 Connection: Transaction Pooler

Render is a cloud server on IPv4. Supabase's direct connection is IPv6-only on the free plan. The Transaction Pooler bridges this gap and is IPv4 compatible.

| Variable | Value |
|----------|-------|
| DB_HOST | `aws-1-ap-southeast-1.pooler.supabase.com` |
| DB_PORT | `6543` — transaction pooler port, NOT 5432 |
| DB_NAME | `postgres` |
| DB_USER | `postgres.xvajtgcetorlzrnmklao` — includes project ref |
| DB_PASS | Your Supabase database password (set in Project Settings) |

---

## 4. Backend Architecture

### 4.1 How a Request Flows Through the Backend

**Login request (no auth required):**

```
  Browser sends:  POST /auth/login  {company_name, password}
                          |
                          v
  [FastAPI router in main.py]
    - CORS middleware checks origin
    - Route matched to login() function
                          |
                          v
  [login() function]
    - ConnectionFactory.get_admin_connection()
    - SELECT tenant_id, hashed_password FROM public.tenants
    - verify_password(plain, hashed)  [bcrypt check]
    - create_token(tenant_id, company_name)  [JWT minted]
                          |
                          v
  Response: { token, tenant_id, company_name, expires_in }
                          |
                          v
  Browser stores token in sessionStorage['ems_token']
```

**Every protected request (auth required):**

```
  Browser sends:  GET /employees
                  Header: Authorization: Bearer <token>
                          |
                          v
  [FastAPI dependency: get_current_tenant()]
    - Extracts Bearer token from header
    - decode_token() verifies signature + expiry
    - Extracts tenant_id from payload['sub']
    - Calls set_current_tenant(tenant_id)
                          |
                          v
  [Route handler: get_employees()]
    - Calls query_engine.get_all_employees()
                          |
                          v
  [query_engine.get_all_employees()]
    - ConnectionFactory.get_tenant_connection(CURRENT_TENANT_ID)
    - SET search_path TO comp_tanish, public
    - SELECT * FROM employee
                          |
                          v
  Response: [ {eno, ename, salary, ...}, ... ]
```

### 4.2 JWT Tokens Explained

A JWT (JSON Web Token) is how the server knows who is making a request without storing sessions. Think of it as a tamper-proof signed card.

| JWT Part | What it contains in EMS |
|----------|------------------------|
| Header | Algorithm: HS256. Token type: JWT. |
| Payload | `sub` = tenant_id, `company` = company name, `exp` = expiry (12 hours from login) |
| Signature | HMAC-SHA256 of header+payload using JWT_SECRET. Any tampering invalidates it. |

The `JWT_SECRET` environment variable is set on Render. It signs every token. If someone tries to forge a token, the signature check fails and they get a 401 error.

### 4.3 The query_engine.py File

This file is the central nervous system. It is the only file that runs SQL. Everything else calls its functions.

| Function | What it does |
|----------|-------------|
| `set_current_tenant(id)` | Sets a global variable. Every query after this uses that company's schema. |
| `get_all_employees()` | `SELECT * FROM employee`. Returns a list of Employee objects. |
| `add_new_employee(emp)` | `INSERT INTO employee`. Then commits the transaction. |
| `update_employee_salary(eno, salary)` | `UPDATE employee SET salary`. The audit trigger fires automatically. |
| `transfer_employee(eno, new_dno)` | `UPDATE employee SET dno`. Moves employee to another department. |
| `bulk_import_employees(list)` | Inserts multiple employees in one transaction. Rolls back all if any one fails. |
| `get_global_logs()` | `SELECT * FROM audit_log ORDER BY changed_at DESC`. |
| `get_salary_history(eno)` | Reads audit_log for UPDATE records on the employee table, filters by eno. |

### 4.4 ConnectionFactory: How Tenant Isolation Works

```
  Every API request:
                          |
                          v
  ConnectionFactory.get_tenant_connection('comp_tanish')
                          |
                          v
  psycopg2.connect(host, port, dbname, user, password)
                          |
                          v
  cursor.execute("SET search_path TO comp_tanish, public")
                          |
  From this point, all queries ONLY see the comp_tanish schema.
  Even if someone passes a different company's table name,
  PostgreSQL will not find it.
```

---

## 5. Complete API Reference

The base URL for all API calls is set in `config.js` as `window.API_BASE`.  
- Local: `http://localhost:8000`  
- Production: `https://ems-6syl.onrender.com`

Every protected endpoint requires this header:
```
Authorization: Bearer <token>
```

### 5.1 Authentication Endpoints

| Method | Endpoint | Auth | What it does |
|--------|----------|------|-------------|
| POST | `/auth/login` | No | Validates company_name + password. Returns JWT token. |
| POST | `/auth/signup` | No | Creates new workspace. Calls ProvisioningService. Returns JWT. |
| POST | `/auth/supabase-exchange` | No | Takes a Supabase access_token (from Google or OTP). Returns EMS JWT. |
| GET | `/auth/me` | Yes | Returns current company name, email, created_at. |
| POST | `/auth/change-password` | No* | Requires current password. Updates hashed_password. |
| POST | `/auth/update-email` | No* | Requires password verification. Updates email in tenants. |
| DELETE | `/auth/delete-workspace` | No* | Requires password. Drops schema and removes tenants row. |

*These endpoints verify the password inside the request body rather than via JWT.

### 5.2 Employee Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/employees` | Returns all employees for the company. |
| GET | `/employees/{eno}` | Returns one employee by their ID. |
| POST | `/employees` | Creates a new employee. Body: eno, ename, dob, gender, salary, dno. |
| DELETE | `/employees/{eno}` | Deletes an employee. Fails if they have linked records. |
| PATCH | `/employees/{eno}/salary` | Updates salary. Audit trigger records old and new values. |
| PATCH | `/employees/{eno}/transfer` | Changes employee department (dno). |
| POST | `/employees/bulk-import` | Inserts multiple employees in one transaction. |
| GET | `/employees/{eno}/salary-history` | Reads audit_log for past salary changes. |
| GET | `/employees/{eno}/transfer-history` | Reads audit_log for past department transfers. |

### 5.3 Other CRUD Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET/POST | `/departments` | List all departments or create a new one. |
| DELETE | `/departments/{dno}` | Deletes a department. |
| PATCH | `/departments/{dno}/manager` | Updates the manager of a department. |
| GET | `/departments-payroll-summary` | Aggregate salary totals grouped by department. |
| GET/POST | `/projects` | List all projects or create a new one. |
| DELETE | `/projects/{pno}` | Delete a project. |
| PATCH | `/projects/{pno}/location` | Update project location. |
| GET/POST | `/dependents` | List all dependents or add a new one. |
| DELETE | `/dependents/{eno}/{name}` | Remove a dependent. |
| GET/POST | `/works-on` | List all project assignments or add one. |
| DELETE | `/works-on/{eno}/{pno}` | Remove a project assignment. |
| GET/POST | `/dept-locations` | List all office locations or add one. |
| DELETE | `/dept-locations/{dno}/{location}` | Remove a location. |
| GET | `/dashboard/summary` | Employee count, department count, project count, recent audit activity. |
| GET | `/audit/global` | All audit log entries for the company. |
| GET | `/audit/employee/{eno}` | Audit entries for a specific employee. |
| GET | `/audit/table/{table_name}` | Audit entries filtered by table. |
| GET | `/audit/stats` | Count of log entries per table. |
| GET | `/audit/operation-summary` | Count of INSERT, UPDATE, DELETE operations. |
| DELETE | `/audit/clear` | Deletes log entries older than N days. |
| POST | `/export/json` | Exports all company data to a JSON file on the server. |
| POST | `/export/csv` | Exports all company data to CSV files. |
| GET | `/export/json/download` | Streams the JSON file to the browser as a download. |

---

## 6. Authentication Flows

EMS supports three ways to log in. All three end with the same result: an EMS JWT token stored in `sessionStorage`. The frontend code lives in `login.html`.

### 6.1 Method 1 — Password Login

```
  User types: company_name + password
                  |
                  v
  login.html  POST /auth/login  { company_name, password }
                  |
                  v
  main.py: SELECT tenant_id, hashed_password
           FROM public.tenants WHERE company_name = ?
                  |
                  v
  bcrypt.verify(password, hashed_password)
                  |
           Yes -> create_token(tenant_id, company_name)
           No  -> 401 Incorrect password
                  |
                  v
  login.html receives { token, tenant_id, company_name }
  sessionStorage['ems_token']     = token
  sessionStorage['ems_company']   = company_name
  sessionStorage['ems_tenant_id'] = tenant_id
                  |
                  v
  window.location.href = 'dashboard.html'
```

### 6.2 Method 2 — Email OTP Login

This uses Supabase Auth. Supabase sends a one-time passcode to the email address. The browser collects it, exchanges it with Supabase for a Supabase `access_token`, then sends that token to the EMS backend to get an EMS JWT.

```
  User types email address
                  |
                  v
  supabase.auth.signInWithOtp({ email })
  --> Supabase sends 8-digit OTP email to user
                  |
                  v
  User types the 8-digit code
                  |
                  v
  supabase.auth.verifyOtp({ email, token, type: 'email' })
  --> Supabase returns { session: { access_token } }
                  |
                  v
  login.html  POST /auth/supabase-exchange { access_token }
                  |
                  v
  main.py: GET https://supabase.co/auth/v1/user
           Header: Authorization: Bearer <access_token>
           --> gets user email from Supabase
                  |
                  v
  SELECT tenant_id, company_name FROM public.tenants WHERE email = ?
  Found     -> create_token(tenant_id, company_name) -> return EMS JWT
  Not found -> 404 'No EMS workspace registered with this email'
                  |
                  v
  Same sessionStorage storage + redirect as Method 1
```

### 6.3 Method 3 — Google Sign-In

This uses Supabase OAuth with Google as the provider. The page navigates away to Google, comes back with a token in the URL hash, then exchanges it for an EMS JWT.

```
  User clicks 'Continue with Google'
                  |
                  v
  supabase.auth.signInWithOAuth({
    provider: 'google',
    options: { redirectTo: window.location.origin + '/login.html' }
  })
  --> Browser navigates AWAY to Google login page
                  |
  User logs into Google
                  |
                  v
  Google redirects to: login.html#access_token=xxx&...
  (The token is in the URL hash, not visible as a query param)
                  |
                  v
  login.html page loads again
  IIFE detects '#access_token=' in window.location.hash
  Shows loading spinner
  supabase.auth.getSession() -- reads token from hash
                  |
                  v
  POST /auth/supabase-exchange { access_token }
  (Same exchange as OTP from here onwards)
                  |
                  v
  EMS JWT returned -> sessionStorage stored -> dashboard
```

> For Google Sign-In to work: (1) Add the Supabase callback URL to Google Cloud Console Authorised Redirect URIs. (2) Add your Vercel domain to Authorised JavaScript Origins. (3) Supabase must have the Google Client ID and Secret configured under Authentication > Providers.

---

## 7. Supabase Setup (Step by Step)

Supabase provides two things: the PostgreSQL database, and the Auth service (OTP and Google OAuth).

### 7.1 Create the Project

1. Go to [supabase.com](https://supabase.com) and sign in.
2. Click **New Project**. Choose a region (ap-southeast-1 for India).
3. Set a strong database password. Save it — you need it for the `.env` file.
4. Wait for the project to be ready (~2 minutes).

### 7.2 Run migration_v2.sql

This adds the email column to the tenants table. Without it, Google and OTP login cannot link to a workspace.

1. In Supabase: go to **SQL Editor**.
2. Paste and run:

```sql
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS email VARCHAR(255);
```

### 7.3 Configure Auth URLs

1. In Supabase: go to **Authentication > URL Configuration**.
2. Set the fields:

| Field | Value |
|-------|-------|
| Site URL | `https://ems-shade.vercel.app/login.html` |
| Redirect URL 1 | `https://ems-shade.vercel.app/login.html` |
| Redirect URL 2 | `https://ems-shade.vercel.app/*` |

### 7.4 Enable Google Provider

1. Go to **Authentication > Providers > Google**.
2. Toggle it on.
3. Paste the Google Client ID and Client Secret (from Chapter 8).
4. Save.

---

## 8. Google Cloud Console Setup

### 8.1 Create OAuth Credentials

1. Go to [console.cloud.google.com](https://console.cloud.google.com).
2. Go to **APIs and Services > Credentials**.
3. Click **Create Credentials > OAuth 2.0 Client ID**.
4. Application type: **Web application**.

### 8.2 Configure the Correct URLs

This is the most critical part. Google will reject any request from a domain not listed here.

| Field in Google Console | Value to add |
|------------------------|-------------|
| Authorised JavaScript Origins | `https://ems-shade.vercel.app` |
| Authorised JavaScript Origins (local) | `http://127.0.0.1:5500` |
| Authorised Redirect URIs | `https://xvajtgcetorlzrnmklao.supabase.co/auth/v1/callback` |
| Authorised Redirect URIs (also add) | `https://ems-shade.vercel.app/login.html` |

> The Supabase callback URL is the most important one. When Google finishes authentication, it sends the user back to Supabase first. Supabase then redirects to your Vercel site. If the Supabase URL is missing, you get `error 400: redirect_uri_mismatch`.

### 8.3 Copy Credentials to Supabase

1. Copy the **Client ID** and **Client Secret** from Google Console.
2. Paste both into Supabase > Authentication > Providers > Google.
3. Save. Allow 5 minutes for Google to propagate the changes.

---

## 9. Deployment — Render + Vercel

### 9.1 Why Two Platforms?

| | Vercel | Render |
|--|--------|--------|
| Good at | Serving static files (HTML, JS, CSS) globally fast | Running Python servers (FastAPI) persistently |
| Not good at | Running Python servers | Hosting static sites |
| Free tier | Unlimited static deploys | Web service sleeps after 15 min inactivity |

### 9.2 Deploying the Backend to Render

1. Go to [render.com](https://render.com) > **New > Web Service**.
2. Connect your GitHub repository.
3. Set **Root Directory** to `backend`.
4. **Build Command:** `pip install -r requirements_web.txt`
5. **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Add all environment variables:

| Variable | Value |
|----------|-------|
| DB_HOST | `aws-1-ap-southeast-1.pooler.supabase.com` |
| DB_PORT | `6543` |
| DB_NAME | `postgres` |
| DB_USER | `postgres.xvajtgcetorlzrnmklao` |
| DB_PASS | Your Supabase database password |
| JWT_SECRET | Any long random string. Keep it secret. |
| SUPABASE_ANON_KEY | Your Supabase project anon key |
| EMS_GMAIL_SENDER | Email address used for OTP emails |
| EMS_GMAIL_APP_PASSWORD | Gmail App Password (not your normal password) |

7. Click **Save, rebuild and deploy**.
8. Copy your URL: `https://ems-6syl.onrender.com`

### 9.3 Deploying the Frontend to Vercel

1. Open `frontend/config.js` and update:

```js
window.API_BASE = 'https://ems-6syl.onrender.com';
```

2. Push to GitHub:

```bash
git add frontend/
git commit -m "set render URL for production"
git push origin dev-branch
```

3. Go to [vercel.com](https://vercel.com) > **New Project** > Import GitHub repo.
4. Set **Root Directory** to `frontend`. Framework Preset: **Other**.
5. Click **Deploy**. Copy your Vercel URL.
6. Update Supabase Auth URLs with this Vercel URL (see Section 7.3).
7. Update Google Cloud Console Authorised Origins (see Section 8.2).

### 9.4 Full Deployment Flow

```
  Developer pushes code to GitHub
                  |
          +--------+--------+
          |                 |
      [Vercel]          [Render]
   detects frontend/    detects backend/
   folder changes       folder changes
          |                 |
   builds static        pip install
   HTML/JS files        requirements_web.txt
          |                 |
   serves at             starts uvicorn
   ems-shade.vercel.app  main:app --port $PORT
          |                 |
          |                 |
   User browser ------> HTTPS request to
   loads login.html     ems-6syl.onrender.com
                                |
                     JWT verified, tenant set
                                |
                    psycopg2 connects via pooler
                                |
                    [Supabase PostgreSQL]
                   comp_tanish schema tables
```

---

## 10. Frontend Architecture

The frontend is 14 plain HTML files. No JavaScript framework. Each page is self-contained with its own HTML, CSS, and JavaScript inside one file.

### 10.1 The 14 Pages

| Page | Purpose |
|------|---------|
| index.html | Public landing page. No auth guard. Links to login and signup. |
| login.html | Three login methods: password, OTP, Google. Stores JWT in sessionStorage. |
| signup.html | Creates a new workspace. Calls `/auth/signup`. |
| dashboard.html | Summary stats and recent activity. Calls `/dashboard/summary`. |
| employees.html | Full CRUD. Bulk CSV import. Salary history side panel. |
| departments.html | Full CRUD. Payroll summary table. |
| projects.html | Full CRUD for projects. |
| works-on.html | Manage which employees work on which projects and hours. |
| dependents.html | Manage family members linked to employees. |
| dept-locations.html | Manage office locations for each department. |
| audit.html | View the automatic audit trail. Filter by table, operation, or employee. |
| export.html | Export all company data as JSON or CSV download. |
| settings.html | Change password, email, accent colour. Delete workspace. |
| about.html | Static info page about the project. |

### 10.2 How Every Protected Page Works

Every page except index, login, and signup follows this exact pattern:

```
  1. config.js loads       -->  sets window.API_BASE
  2. ems-init.js loads     -->  restores accent colour from localStorage
  3. <script> block starts
     |
     |--> AUTH GUARD: if (!sessionStorage.getItem('ems_token'))
     |                   window.location.href = 'login.html'
     |                   (stops here if not logged in)
     |
     |--> apiCall() helper defined
     |    (adds Authorization: Bearer header to every request)
     |
     |--> loadPage() async function called
     |    (fetches data from API, renders into table or cards)
     |
     |--> Event listeners attached for buttons, modals, forms
     |
     |--> Logout modal HTML is placed BEFORE this script tag
          (so getElementById works immediately without waiting)
```

### 10.3 config.js and ems-init.js

| File | What it does |
|------|-------------|
| `config.js` | Sets `window.API_BASE`. Changing this one line switches the entire frontend between local dev and production. |
| `ems-init.js` | Reads `ems_accent` from localStorage and applies CSS variables immediately. This is why the accent colour carries across all pages without flashing. |

### 10.4 sessionStorage vs localStorage

| Key | Storage | Why this choice |
|-----|---------|----------------|
| ems_token | sessionStorage | JWT. Cleared when the browser tab closes. More secure. |
| ems_company | sessionStorage | Company name for display. Same session as token. |
| ems_tenant_id | sessionStorage | Used for workspace ID display in Settings. |
| ems_accent | localStorage | Accent colour preference. Persists across sessions and tabs. Not sensitive. |
| ems_compact | localStorage | Compact mode toggle. Persists across sessions. Not sensitive. |

---

## 11. Local Development Setup

### 11.1 Step-by-Step

**1. Clone the repository:**
```bash
git clone https://github.com/Tanish-30-08-2006/EMS.git
cd Employee-Management-System
```

**2. Create the `.env` file in the `backend/` folder:**
```dotenv
DB_HOST=aws-1-ap-southeast-1.pooler.supabase.com
DB_PORT=6543
DB_NAME=postgres
DB_USER=postgres.xvajtgcetorlzrnmklao
DB_PASS=<your supabase database password>
JWT_SECRET=<any long random string>
SUPABASE_ANON_KEY=<your supabase anon key>
EMS_GMAIL_SENDER=<your gmail address>
EMS_GMAIL_APP_PASSWORD=<gmail app password>
```

**3. Install Python dependencies:**
```bash
cd backend
pip install -r requirements_web.txt
```

**4. Start the backend server:**
```bash
uvicorn main:app --reload --port 8000
```

**5. In a second terminal, serve the frontend:**
```bash
cd frontend
python -m http.server 5500
```

**6. Open in browser:**
```
http://127.0.0.1:5500/index.html
```

> Make sure `config.js` has `window.API_BASE = 'http://localhost:8000'` for local development.

---

## 12. Security Design

### 12.1 Security Measures

| Area | How it is protected |
|------|-------------------|
| Passwords | Stored as bcrypt hashes. The plain text password is never saved anywhere. |
| Sessions | JWT tokens expire after 12 hours. Signing key is an environment variable, not in code. |
| Multi-tenancy | PostgreSQL `SET search_path` isolates each tenant. A token for Company A cannot access Company B. |
| SQL Injection | All queries use psycopg2 parameterised queries (`%s` placeholders). User input is never concatenated into SQL strings. |
| CORS | FastAPI CORS middleware. In production, restrict `allow_origins` to your Vercel domain. |
| Secrets | `.env` file is in `.gitignore`. Environment variables are set on Render directly, never committed to Git. |
| Auth bypass | Every protected HTML page has an auth guard at the top. No token = immediate redirect to login. |

### 12.2 The OTP Security Check

Email OTP login requires the email to be registered in the EMS workspace. Someone cannot log in with just any verified Supabase email.

```
  Attacker has verified email 'random@gmail.com' with Supabase OTP
                  |
                  v
  POST /auth/supabase-exchange { access_token }
                  |
                  v
  main.py gets email = 'random@gmail.com' from Supabase
                  |
                  v
  SELECT tenant_id FROM public.tenants WHERE email = 'random@gmail.com'
                  |
  No row found -> 404 'No EMS workspace registered with this email'
                  |
  Login BLOCKED. No token issued.
```

---

## 13. Common Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `password authentication failed for user postgres` | DB_PASS is wrong or DB_PORT is 5432 instead of 6543. | Reset password in Supabase Project Settings. Use port 6543. Check DB_NAME is literally `postgres` not the text `DB_NAME`. |
| `error 400: redirect_uri_mismatch` | Supabase callback URL is not in Google Authorised Redirect URIs. | Add `https://[ref].supabase.co/auth/v1/callback` to Google Redirect URIs. |
| `No EMS workspace registered with [email]` | Email not saved in Settings for this workspace. | Log in with password > Settings > Contact > save email > try OTP/Google again. |
| Sign Out button not clickable | Logout modal HTML was placed after the script that attaches its event listeners. | Modal HTML must come before the `<script>` tag that runs `getElementById` on it. |
| Accent colour not changing on other pages | Colour was saved to sessionStorage (tab-only) instead of localStorage. | Save to localStorage in settings.html. Read from localStorage in ems-init.js. |
| CORS error in browser console | config.js still points to localhost but you are on Vercel. | Update `window.API_BASE` in config.js to your Render URL. Push to GitHub. |
| First request is very slow | Render free plan spins down after 15 minutes of inactivity. | Normal behaviour. First request after inactivity takes 30–60 seconds to wake up. |

---

## 14. Quick Reference Cheatsheet

### Live URLs

| Service | URL |
|---------|-----|
| Frontend | https://ems-shade.vercel.app |
| Backend | https://ems-6syl.onrender.com |
| Backend Health Check | https://ems-6syl.onrender.com/health |
| GitHub Repository | https://github.com/Tanish-30-08-2006/EMS |
| Supabase Dashboard | https://supabase.com/dashboard/project/xvajtgcetorlzrnmklao |

### Local Development Commands

```bash
# Start backend
cd D:\DAIICT\Employee-Management-System\backend
uvicorn main:app --reload --port 8000

# Start frontend (separate terminal)
cd D:\DAIICT\Employee-Management-System\frontend
python -m http.server 5500

# Push changes to GitHub
git add frontend/ backend/
git commit -m "your message here"
git push origin dev-branch
```

### Environment Variables Checklist

```
DB_HOST       ✓  aws-1-ap-southeast-1.pooler.supabase.com
DB_PORT       ✓  6543  (not 5432)
DB_NAME       ✓  postgres
DB_USER       ✓  postgres.xvajtgcetorlzrnmklao
DB_PASS       ✓  your supabase database password
JWT_SECRET    ✓  any long random string
SUPABASE_ANON_KEY  ✓  from Supabase > Project Settings > API
EMS_GMAIL_SENDER   ✓  your gmail address
EMS_GMAIL_APP_PASSWORD  ✓  gmail app password
```

### Tech Stack Summary

| Layer | Technology | Hosted on |
|-------|-----------|-----------|
| Frontend | HTML, CSS, Vanilla JavaScript | Vercel |
| Backend API | Python, FastAPI, Uvicorn | Render |
| Database | PostgreSQL (Supabase managed) | Supabase (AWS ap-southeast-1) |
| Auth (OTP + Google) | Supabase Auth | Supabase |
| Password hashing | bcrypt | Backend |
| Session tokens | JWT (HS256, 12h expiry) | Backend |
| DB driver | psycopg2-binary | Backend |

---

*Built by Tanish Sanghavi — DAIICT Gandhinagar, Batch 2028*