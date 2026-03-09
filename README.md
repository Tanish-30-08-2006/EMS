# Aegis — Employee Management System

A high-performance, multi-tenant Employee Management System (EMS) built with a modern FastAPI backend and a premium Vanilla JS frontend.

## 🚀 Features

- **Multi-Tenancy**: Isolated database schemas for every company.
- **Audit Logging**: Comprehensive tracking of every row change (Insert/Update/Delete).
- **Interactive Dashboard**: Real-time stats and data visualization.
- **CSV Bulk Import**: Fast employee onboarding via structured data.
- **Google OAuth**: Secure sign-in with Google and Supabase integration.
- **Premium UI**: Sleek, glassmorphic design with dark mode and smooth animations.

## 🛠 Tech Stack

- **Frontend**: HTML5, Vanilla CSS3, JavaScript (ES6+).
- **Backend**: Python, FastAPI, Psycopg2.
- **Database**: PostgreSQL (Supabase) with triggered audit trails.
- **Auth**: JWT (JSON Web Tokens) & Supabase Auth.

## 📦 Fast Setup

### 1. Backend

```bash
cd backend
pip install -r requirements_web.txt
uvicorn main:app --reload
```

### 2. Frontend

Open `frontend/index.html` in your browser (Live Server recommended).

---

_Note: This is a temporary README for development._
