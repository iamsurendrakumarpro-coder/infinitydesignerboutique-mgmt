# Infinity Designer Boutique – Management System

Enterprise-grade boutique management system featuring a **React.js PWA** frontend and **Python Flask REST API** backend, powered by **Firebase Firestore**. Handles staff lifecycle, attendance, finances, overtime, weekly settlements, and real-time dashboards — all under a single, role-based platform.

---

## Architecture

| Layer | Technology |
|-------|------------|
| **Frontend** | React 19 PWA · Tailwind CSS v4 · Vite 7 · Recharts · Axios |
| **Backend** | Python Flask 3.1 REST API · Service-Oriented Architecture |
| **Database** | Firebase Firestore (NoSQL, real-time) · Firebase Storage |
| **Auth** | Session-based · Bcrypt PIN hashing (12 rounds) · RBAC |
| **Timezone** | All timestamps locked to **IST (Asia/Kolkata)** |

---

## Project Structure

```
infinitydesignerboutique-mgmt/
├── app.py                          # Flask application factory & entry point
├── config.py                       # Centralised configuration (env-driven)
├── requirements.txt                # Python dependencies
├── setup_root_admin.py             # One-time root admin seeding script
├── firebase.json                   # Firebase project configuration
├── firestore.indexes.json          # Firestore composite indexes
├── firestore.rules                 # Firestore security rules
│
├── modules/                        # Flask Blueprints (route handlers)
│   ├── auth/routes.py              # Authentication endpoints
│   ├── users/routes.py             # User management endpoints
│   ├── attendance/routes.py        # Attendance tracking endpoints
│   ├── financial/routes.py         # Financial request endpoints
│   ├── overtime/routes.py          # Overtime management endpoints
│   ├── settlements/routes.py       # Settlement generation endpoints
│   └── dashboard/routes.py         # Dashboard analytics endpoints
│
├── services/                       # Business logic layer
│   ├── auth_service.py             # PIN hashing/verification, session management
│   ├── user_service.py             # User CRUD, gallery, performance logs
│   ├── attendance_service.py       # Punch in/out, attendance analytics
│   ├── financial_service.py        # Financial request lifecycle
│   ├── overtime_service.py         # Overtime record management
│   ├── settlement_service.py       # Weekly settlement generation
│   └── dashboard_service.py        # Dashboard metrics & aggregations
│
├── middleware/
│   └── auth_middleware.py          # RBAC decorators (@login_required, @admin_required, @staff_required)
│
├── utils/
│   ├── firebase_client.py          # Firebase Admin SDK initialisation (singleton)
│   ├── logger.py                   # IST-stamped rotating file logger + audit log
│   ├── timezone_utils.py           # UTC↔IST conversion, period range calculations
│   └── validators.py               # Input validation (phone, PIN, amounts)
│
└── frontend/                       # React.js PWA
    ├── package.json
    ├── vite.config.js
    ├── index.html
    ├── public/sw.js                # Service worker
    └── src/
        ├── App.jsx                 # Root component & routing
        ├── main.jsx                # Entry point
        ├── context/
        │   └── AuthContext.jsx     # Global auth state provider
        ├── pages/
        │   ├── auth/               # LoginPage, ChangePinPage
        │   ├── admin/              # Dashboard, StaffDirectory, StaffCreate,
        │   │                       # StaffEdit, StaffProfileView, Approvals,
        │   │                       # Settlements, Reports
        │   └── staff/              # DutyStation, MyMoney, StaffProfile
        ├── components/
        │   ├── layout/             # AdminLayout, StaffLayout
        │   └── common/             # ProtectedRoute, LoadingSpinner,
        │                           # SkeletonLoader, NumberPad, StatusBadge
        └── services/               # Axios HTTP client wrappers
            ├── api.js              # Base Axios configuration
            ├── auth.js             # Auth API calls
            ├── users.js            # User API calls
            ├── attendance.js       # Attendance API calls
            ├── financial.js        # Financial API calls
            ├── overtime.js         # Overtime API calls
            ├── settlements.js      # Settlement API calls
            └── dashboard.js        # Dashboard API calls
```

---

## Modules

### Module 1 – Authentication & Security

- Phone number + 4-digit PIN login (bcrypt-hashed, 12 rounds)
- First-login PIN enforcement — staff must set a private PIN before accessing features
- Admin-initiated PIN reset (temporary PIN → forced change on next login)
- Role-Based Access Control: `admin`, `staff`, `root_admin`
- Root Admin is hidden from all listings and cannot be modified

### Module 2 – User Lifecycle Management

- Dynamic staff creation forms with designation-based fields
- Three designations: `cutting_master`, `handwork_expert`, `tailor`
- Auto-calculated daily salary derived from weekly salary
- Skill tags, work gallery (Firebase Storage), and performance notes
- Soft deletion via status transitions: `active` → `inactive` → `deactivated`
- Immutable phone numbers to preserve audit trail integrity

### Module 3 – Attendance (Duty Station)

- Visual punch in/out station with real-time status display
- One attendance record per staff member per day
- Double-click guard prevents duplicate punches
- Automatic duration calculation on punch-out
- Analytics: daily, weekly, monthly, quarterly, and yearly breakdowns

### Module 4 – Financial Requests

- Two request types: **shop expenses** and **personal advances**
- Staff submit requests with amount and reason; admins review
- Status lifecycle: `pending` → `approved` / `rejected`
- Color-coded status tracking across all views
- Full audit trail with timestamps and reviewer identity

### Module 5 – Admin Approvals & Overtime Engine

- Centralized approval queue for financial requests and overtime records
- Overtime auto-generated from attendance when shift exceeds standard hours
- **60-minute grace rule**: overtime only counts after the first 60 minutes past standard logout
- Admin approve/reject workflow with notes

### Module 6 – Weekly Settlement Engine

- Automated settlement generation for a configurable week period
- Formula: **Base Salary + Overtime Pay + Approved Expenses − Advances = Net Payable**
- Itemized breakdown per staff member
- Historical settlement records for audit and reporting

### Module 7 – Enterprise Dashboards

- Real-time admin dashboard with daily summary cards
- Charts powered by Recharts (attendance trends, financial breakdowns)
- Multi-period roll-ups: daily, weekly, monthly, quarterly, yearly
- Staff-facing views: personal attendance history, financial balance

---

## API Reference

### Authentication

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/auth/login` | — | Phone + PIN login |
| `POST` | `/api/auth/logout` | `login_required` | Clear session |
| `POST` | `/api/auth/change-pin` | `login_required` | Change current user's PIN |
| `GET` | `/api/auth/me` | `login_required` | Get current session info |

### Users – Staff

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/users/staff` | `admin_required` | List all staff (filterable by status) |
| `POST` | `/api/users/staff` | `admin_required` | Create new staff member |
| `GET` | `/api/users/staff/<uid>` | `admin_required` | Get staff profile |
| `PUT` | `/api/users/staff/<uid>` | `admin_required` | Update staff details |
| `PATCH` | `/api/users/staff/<uid>/status` | `admin_required` | Change staff status |
| `POST` | `/api/users/staff/<uid>/reset-pin` | `admin_required` | Reset staff PIN |
| `POST` | `/api/users/staff/<uid>/skills` | `admin_required` | Add skill tag |
| `DELETE` | `/api/users/staff/<uid>/skills` | `admin_required` | Remove skill tag |
| `GET` | `/api/users/staff/<uid>/gallery` | `admin_required` | List work gallery |
| `POST` | `/api/users/staff/<uid>/gallery` | `admin_required` | Upload gallery image |
| `DELETE` | `/api/users/staff/<uid>/gallery/<gid>` | `admin_required` | Delete gallery image |
| `GET` | `/api/users/staff/<uid>/performance` | `admin_required` | List performance logs |
| `POST` | `/api/users/staff/<uid>/performance` | `admin_required` | Add performance log |
| `DELETE` | `/api/users/staff/<uid>/performance/<lid>` | `admin_required` | Delete performance log |

### Users – Admin

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/users/admins` | `admin_required` | List all admins (excludes root) |
| `POST` | `/api/users/admins` | `admin_required` | Create new admin |

### Attendance

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/attendance/status` | `login_required` | Today's punch status |
| `POST` | `/api/attendance/punch` | `login_required` | Toggle punch in/out |
| `GET` | `/api/attendance/history` | `login_required` | Attendance history (date range / period) |
| `GET` | `/api/attendance/analytics` | `login_required` | Attendance analytics |

### Financial Requests

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/financial/requests` | `login_required` | Create financial request |
| `GET` | `/api/financial/requests` | `login_required` | List requests (filterable) |
| `GET` | `/api/financial/requests/<id>` | `login_required` | Get request detail |
| `PATCH` | `/api/financial/requests/<id>` | `admin_required` | Approve or reject request |

### Overtime

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/overtime/pending` | `admin_required` | List pending overtime records |
| `GET` | `/api/overtime/user/<user_id>` | `login_required` | Get overtime for a user |
| `PATCH` | `/api/overtime/<id>/approve` | `admin_required` | Approve overtime |
| `PATCH` | `/api/overtime/<id>/reject` | `admin_required` | Reject overtime |

### Settlements

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/api/settlements/generate` | `admin_required` | Generate weekly settlements |
| `GET` | `/api/settlements` | `admin_required` | List settlements (filterable) |
| `GET` | `/api/settlements/<id>` | `login_required` | Get settlement detail |
| `GET` | `/api/settlements/user/<user_id>` | `login_required` | Get user's settlement history |

### Dashboard

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/dashboard/summary` | `admin_required` | Daily summary (or specific date) |
| `GET` | `/api/dashboard/financial-summary` | `admin_required` | Financial breakdown by period |
| `GET` | `/api/dashboard/attendance-summary` | `admin_required` | Attendance analytics by period |

### Health

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `GET` | `/api/health` | — | Health check |

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- Firebase project with Firestore and Storage enabled

### Backend Setup

```bash
# Create virtual environment
python -m venv venv && source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Firebase credentials and secrets

# Seed the root admin account
python setup_root_admin.py

# Start the development server
python app.py
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start the development server
npm run dev
```

### Production Deployment

```bash
# Backend — Gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 "app:create_app()"

# Frontend — Static build
cd frontend && npm run build
# Serve the dist/ directory with any static file server
```

---

## Database Schema

### Firestore Collections

```
admins/{user_id}
  ├── user_id          (string)    Auto-generated UUID
  ├── full_name        (string)
  ├── phone_number     (string)    Unique, immutable
  ├── pin_hash         (string)    Bcrypt hash
  ├── role             (string)    "admin"
  ├── is_root          (boolean)
  ├── is_first_login   (boolean)
  ├── created_at       (timestamp) IST
  ├── updated_at       (timestamp) IST
  └── created_by       (string)

staff/{user_id}
  ├── user_id          (string)    Auto-generated UUID
  ├── full_name        (string)
  ├── phone_number     (string)    Unique, immutable
  ├── designation      (string)    cutting_master | handwork_expert | tailor
  ├── joining_date     (string)    IST date
  ├── weekly_salary    (number)
  ├── standard_login_time   (string)
  ├── standard_logout_time  (string)
  ├── emergency_contact     (string)
  ├── skills           (array)
  ├── status           (string)    active | inactive | deactivated
  ├── pin_hash         (string)    Bcrypt hash
  ├── role             (string)    "staff"
  ├── is_first_login   (boolean)
  ├── created_at       (timestamp) IST
  └── updated_at       (timestamp) IST

staff/{user_id}/work_gallery/{image_id}
  ├── image_url        (string)    Firebase Storage URL
  ├── storage_path     (string)
  ├── caption          (string)
  ├── uploaded_at      (timestamp) IST
  └── uploaded_by      (string)

staff/{user_id}/performance_logs/{log_id}
  ├── note             (string)
  ├── created_at       (timestamp) IST
  └── created_by       (string)

attendance/{user_id}/records/{YYYYMMDD}
  ├── user_id          (string)
  ├── date             (string)
  ├── punch_in         (timestamp) IST
  ├── punch_out        (timestamp) IST
  ├── status           (string)    "in" | "out"
  ├── duration_minutes (number)
  ├── created_at       (timestamp) IST
  └── updated_at       (timestamp) IST

financial_requests/{request_id}
  ├── user_id          (string)
  ├── type             (string)    shop_expense | personal_advance
  ├── amount           (number)
  ├── reason           (string)
  ├── status           (string)    pending | approved | rejected
  ├── reviewed_by      (string)
  ├── reviewed_at      (timestamp) IST
  └── created_at       (timestamp) IST

overtime_records/{record_id}
  ├── user_id          (string)
  ├── date             (string)
  ├── overtime_minutes (number)
  ├── status           (string)    pending | approved | rejected
  ├── approved_by      (string)
  ├── approved_at      (timestamp) IST
  └── created_at       (timestamp) IST

settlements/{settlement_id}
  ├── user_id          (string)
  ├── week_start       (string)
  ├── week_end         (string)
  ├── base_salary      (number)
  ├── overtime_pay     (number)
  ├── expenses         (number)
  ├── advances         (number)
  ├── net_payable      (number)
  ├── generated_by     (string)
  └── created_at       (timestamp) IST

phone_index/{phone_number}
  └── user_id          (string)    Internal uniqueness lookup
```

---

## Security Features

- **Bcrypt PIN Hashing** — All PINs hashed with 12 rounds; plaintext PINs never stored or logged
- **Session-Based Authentication** — Secure HttpOnly server-side sessions
- **Role-Based Access Control** — `@admin_required`, `@staff_required`, `@login_required` decorators enforced server-side
- **Immutable Phone Numbers** — Cannot be changed after creation to preserve audit trail
- **Root Admin Protection** — Hidden from all listings, cannot be modified or deleted
- **Firestore Rules** — Deny all direct client access; all operations flow through the API
- **Audit Logging** — All sensitive operations (login, PIN change, approvals) logged with user context
- **First-Login Enforcement** — New and PIN-reset users must change their PIN before accessing features
- **CORS Configuration** — Origin whitelist configurable per environment

---

## Logging

All logs are written to the `logs/` directory with **IST timestamps** and automatic rotation.

| Log File | Contents |
|----------|----------|
| `app.log` | Application events, errors, request logs |
| `audit.log` | Security-sensitive actions (login, PIN changes, approvals) |

- **Format**: `[YYYY-MM-DD HH:MM:SS IST] LEVEL — module — message`
- **Rotation**: Size-based with configurable max bytes and backup count
- PINs and sensitive credentials are **never** written to logs
