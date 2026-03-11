# Employee Management System (EMS)

A full-stack, multi-tenant Employee Management System built with a **FastAPI** backend and a **vanilla HTML/CSS/JS** frontend. Designed for small-to-medium organisations to manage employees, departments, projects, assignments, dependents, and department locations — all in one place, with a full audit trail on every action.

**Live Demo:** [ems-shade.vercel.app](https://ems-shade.vercel.app)  
**Backend API:** [ems-6syl.onrender.com](https://ems-6syl.onrender.com)

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Database Schema](#database-schema)
- [API Reference](#api-reference)
- [Authentication](#authentication)
- [Getting Started — Local Development](#getting-started--local-development)
- [Deployment](#deployment)
- [Environment Variables](#environment-variables)
- [Screenshots](#screenshots)
- [Developer](#developer)

---

## Features

### Core Modules
| Module | Capabilities |
|--------|-------------|
| **Employees** | Add, view, delete, bulk CSV import, salary update, department transfer, salary history |
| **Departments** | Create, view, delete, manager assignment, payroll summary |
| **Projects** | Create, view, delete, location update |
| **Works On** | Assign employees to projects, view by employee or project, remove assignments |
| **Dependents** | Add/remove employee dependents, filter by employee |
| **Dept. Locations** | Manage multiple locations per department |

### System Features
- **Multi-Tenant Architecture** — every company gets a fully isolated PostgreSQL schema; Company A can never see Company B's data
- **Automatic Audit Trail** — every INSERT, UPDATE, and DELETE is logged with a timestamp, the operation type, and changed values
- **Three Authentication Methods** — password login, email OTP (via Supabase), and Google Sign-In (OAuth 2.0)
- **Data Export** — export your entire workspace as JSON or CSV, streamed directly to the browser
- **JWT Sessions** — stateless 12-hour tokens; no server-side session storage needed
- **Appearance Customisation** — 6 accent colour presets, persisted across all pages via localStorage
- **Responsive Design** — mobile sidebar, hamburger menu, works on all screen sizes

---

## Tech Stack

### Backend
- **Python 3.11+**
- **FastAPI** — REST API framework
- **psycopg2** — PostgreSQL driver
- **python-jose** — JWT creation and verification
- **bcrypt** — password hashing
- **httpx** — async HTTP for Supabase token exchange
- **openpyxl** — Excel export support
- **Uvicorn** — ASGI server

### Frontend
- **Vanilla HTML5 / CSS3 / JavaScript** — no framework, no build step
- **Supabase JS SDK** — for OTP and Google OAuth flows
- Hosted on **Vercel**

### Database & Auth
- **Supabase** (PostgreSQL) — database + OTP email + Google OAuth provider
- **Render** — backend hosting

---

## Architecture

```
┌─────────────────────┐        ┌──────────────────────────────┐
│   Frontend (Vercel) │        │     Backend (Render)         │
│                     │        │                              │
│  14 HTML pages      │──────▶ │  main.py  (FastAPI)          │
│  config.js          │  HTTP  │     │                        │
│  ems-init.js        │        │     ├── query_engine.py      │
│                     │        │     ├── connection_factory.py│
└─────────────────────┘        │     ├── provisioning_service │
                                │     └── security.py         │
                                │           │                  │
                                │           ▼                  │
                                │   Supabase PostgreSQL        │
                                │   (per-tenant schemas)       │
                                └──────────────────────────────┘
```

### Tenancy Model — "Shared Database, Isolated Schemas"

When a company signs up, a dedicated PostgreSQL schema is created automatically:

```
public.tenants          ← master company registry
comp_acme/              ← Acme Corp's private schema
  ├── employee
  ├── department
  ├── project
  ├── works_on
  ├── dependent
  ├── dept_locations
  └── audit_log
comp_globex/            ← Globex Corp's private schema (completely separate)
  └── ...
```

Every API request decodes the JWT to extract `tenant_id`, then sets `search_path` to that company's schema before executing any query. Cross-tenant access is structurally impossible.

### Dual Entry Points

```
cli_main.py   (Terminal CLI)  ──┐
                                 ├── services/query_engine.py ── Supabase PostgreSQL
main.py       (FastAPI / Web)  ──┘
```

Both the CLI and the web server share the exact same `query_engine.py`. No business logic is duplicated.

---

## Project Structure

```
Employee-Management-System/
├── backend/
│   ├── main.py                        # FastAPI app — all HTTP endpoints
│   ├── cli_main.py                    # Terminal interface
│   ├── requirements_web.txt           # Python dependencies
│   ├── render.yaml                    # Render deployment config
│   ├── services/
│   │   ├── query_engine.py            # All SQL logic (the core engine)
│   │   └── data_porter.py             # JSON/CSV export logic
│   └── app/
│       ├── core/
│       │   ├── connection_factory.py  # DB connection + tenant isolation
│       │   └── security.py            # bcrypt hashing helpers
│       ├── models/                    # Pydantic-compatible data models
│       │   ├── employee.py
│       │   ├── department.py
│       │   ├── project.py
│       │   ├── dependent.py
│       │   ├── works_on.py
│       │   └── dept_locations.py
│       └── system/
│           └── provisioning_service.py  # Schema creation on signup
└── frontend/
    ├── config.js          # Single source of truth for API_BASE URL
    ├── ems-init.js        # Runs on every page: restores accent colour + compact mode
    ├── index.html         # Landing page
    ├── login.html         # Password + OTP + Google Sign-In
    ├── signup.html        # New workspace registration
    ├── dashboard.html     # Stats overview
    ├── employees.html
    ├── departments.html
    ├── projects.html
    ├── works-on.html
    ├── dependents.html
    ├── dept-locations.html
    ├── audit.html         # Audit trail viewer
    ├── export.html        # Data export (JSON / CSV)
    ├── settings.html      # Profile, appearance, workspace management
    ├── about.html
    └── developer.html
```

---

## Database Schema

Each tenant schema contains these 6 tables plus an audit log:

```sql
employee (eno PK, ename, bdate, address, gender, salary, dno FK)
department (dno PK, dname, mgr_eno FK, mgr_start_date)
project (pno PK, pname, plocation, dno FK)
works_on (eno FK, pno FK, hours — composite PK)
dependent (eno FK, dependent_name, gender, bdate, relationship — composite PK)
dept_locations (dno FK, location — composite PK)
audit_log (id, table_name, operation, record_id, old_values, new_values, changed_at)
```

The `audit_log` table is populated automatically by PostgreSQL triggers on every table — no application-level logging code required.

---

## API Reference

All protected endpoints require `Authorization: Bearer <token>` in the request header.

### Auth
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/login` | None | Password login → returns JWT |
| POST | `/auth/signup` | None | Create workspace → returns JWT |
| POST | `/auth/supabase-exchange` | None | Exchange Supabase OAuth token for EMS JWT |
| POST | `/auth/change-password` | JWT | Update password |
| POST | `/auth/update-email` | JWT | Update email |
| DELETE | `/auth/delete-workspace` | None | Permanently delete company + schema |
| GET | `/auth/me` | JWT | Returns current session info |

### Employees
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/employees` | List all employees |
| POST | `/employees` | Add employee |
| GET | `/employees/{eno}` | Get single employee |
| DELETE | `/employees/{eno}` | Delete employee |
| PATCH | `/employees/{eno}/salary` | Update salary |
| PATCH | `/employees/{eno}/transfer` | Transfer to department |
| POST | `/employees/bulk-import` | Bulk import from CSV data |
| GET | `/employees/{eno}/salary-history` | Salary change audit log |
| GET | `/employees/{eno}/transfer-history` | Department transfer log |

### Departments
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/departments` | List all departments |
| POST | `/departments` | Create department |
| GET | `/departments/{dno}` | Get single department |
| DELETE | `/departments/{dno}` | Delete department |
| PATCH | `/departments/{dno}/manager` | Assign manager |
| GET | `/departments-payroll-summary` | Payroll stats per department |

### Projects
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/projects` | List all projects |
| POST | `/projects` | Create project |
| GET | `/projects/{pno}` | Get single project |
| DELETE | `/projects/{pno}` | Delete project |
| PATCH | `/projects/{pno}/location` | Update location |

### Works On, Dependents, Dept. Locations
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET/POST | `/works-on` | List all / create assignment |
| DELETE | `/works-on/{eno}/{pno}` | Remove assignment |
| GET/POST | `/dependents` | List all / add dependent |
| DELETE | `/dependents/{eno}/{name}` | Remove dependent |
| GET/POST | `/dept-locations` | List all / add location |
| PATCH/DELETE | `/dept-locations/{dno}/{loc}` | Update / remove location |

### Audit & Export
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/audit/global` | Company-wide activity feed |
| GET | `/audit/stats` | Log counts by table |
| GET | `/audit/operation-summary` | INSERT/UPDATE/DELETE totals |
| DELETE | `/audit/clear` | Remove logs older than N days |
| GET | `/dashboard/summary` | All dashboard stats in one call |
| POST | `/export/json` | Trigger JSON export |
| POST | `/export/csv` | Trigger CSV export |
| GET | `/export/json/download` | Stream JSON file to browser |

---

## Authentication

### Flow 1 — Password Login
1. POST `/auth/login` with `{ company_name, password }`
2. Backend verifies bcrypt hash → returns 12-hour JWT
3. JWT stored in `sessionStorage` as `ems_token`

### Flow 2 — Email OTP
1. Supabase sends an 8-digit OTP to the user's email
2. User enters OTP → Supabase verifies → returns `access_token`
3. Frontend POSTs token to `/auth/supabase-exchange`
4. Backend looks up the verified email in `public.tenants` → returns EMS JWT

### Flow 3 — Google Sign-In
1. Full-page redirect to Google via Supabase OAuth
2. Google redirects back to `login.html#access_token=...`
3. Page detects hash → calls `supabase.auth.getSession()` → exchanges token at `/auth/supabase-exchange`
4. Backend verifies email exists in workspace → returns EMS JWT

---

## Getting Started — Local Development

### Prerequisites
- Python 3.11+
- A Supabase project (free tier is fine)
- Node.js (only needed if you want a local HTTP server — optional)

### 1. Clone the repo

```bash
git clone https://github.com/Tanish-30-08-2006/EMS.git
cd Employee-Management-System
```

### 2. Set up the backend

```bash
cd backend
pip install -r requirements_web.txt
```

Create a `.env` file in the `backend/` directory:

```dotenv
DB_HOST=aws-1-ap-southeast-1.pooler.supabase.com
DB_PORT=6543
DB_NAME=postgres
DB_USER=postgres.<your-project-ref>
DB_PASS=<your-supabase-password>
JWT_SECRET=<any-long-random-string>
SUPABASE_ANON_KEY=<your-supabase-anon-key>
EMS_GMAIL_SENDER=<your-gmail>
EMS_GMAIL_APP_PASSWORD=<your-gmail-app-password>
```

Run the migration in Supabase SQL Editor:
```sql
ALTER TABLE public.tenants ADD COLUMN IF NOT EXISTS email VARCHAR(255);
```

Start the backend:
```bash
uvicorn main:app --reload --port 8000
```

### 3. Set up the frontend

```bash
cd frontend
```

Make sure `config.js` points to your local backend:
```js
window.API_BASE = 'http://localhost:8000';
```

Serve the frontend (Python's built-in server works fine):
```bash
python -m http.server 5500
```

Open [http://127.0.0.1:5500/login.html](http://127.0.0.1:5500/login.html)

---

## Deployment

### Backend — Render

1. Push to GitHub
2. Render → New Web Service → connect repo
3. Root Directory: `backend`
4. Build command: `pip install -r requirements_web.txt`
5. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
6. Add all environment variables from the table below
7. Deploy → copy the service URL (e.g. `https://ems-xyz.onrender.com`)

### Frontend — Vercel

1. Update `frontend/config.js` with your Render URL:
   ```js
   window.API_BASE = 'https://ems-xyz.onrender.com';
   ```
2. Push to GitHub
3. Vercel → New Project → import repo → Root Directory: `frontend`
4. Deploy → copy the Vercel URL (e.g. `https://ems-shade.vercel.app`)

### Post-Deployment — Supabase

In Supabase → Authentication → URL Configuration:
- **Site URL:** `https://ems-shade.vercel.app/login.html`
- **Redirect URLs:** `https://ems-shade.vercel.app/login.html` and `https://ems-shade.vercel.app/*`

### Post-Deployment — Google Cloud Console

In your OAuth 2.0 Client:
- **Authorised JavaScript Origins:** `https://ems-shade.vercel.app`
- **Authorised Redirect URIs:**
  - `https://ems-shade.vercel.app/login.html`
  - `https://<your-project-ref>.supabase.co/auth/v1/callback`

---

## Environment Variables

| Variable | Where set | Description |
|----------|-----------|-------------|
| `DB_HOST` | Render + `.env` | Supabase pooler host |
| `DB_PORT` | Render + `.env` | `6543` for transaction pooler |
| `DB_NAME` | Render + `.env` | `postgres` |
| `DB_USER` | Render + `.env` | `postgres.<project-ref>` |
| `DB_PASS` | Render + `.env` | Supabase database password |
| `JWT_SECRET` | Render + `.env` | Secret key for signing JWTs |
| `SUPABASE_ANON_KEY` | Render + `.env` | From Supabase → API settings |
| `EMS_GMAIL_SENDER` | Render + `.env` | Gmail address for OTP emails |
| `EMS_GMAIL_APP_PASSWORD` | Render + `.env` | Gmail app password (not account password) |

---

## Developer

**Tanish Sanghavi**  
B.Tech, DAIICT Gandhinagar — Batch 2028  
[github.com/Tanish-30-08-2006](https://github.com/Tanish-30-08-2006)  
tanishsanghavi2@gmail.com

---

*Built as a full-stack academic project demonstrating multi-tenant SaaS architecture, REST API design, and modern frontend patterns — without any frontend framework.*