# Infinity Designer Boutique – Management System

**Phase 0: Identity, Access & Staff Management**

A production-ready boutique management system built with Python (Flask) backend,
modern HTML/CSS/JS frontend (Tailwind CSS), and Google Firebase/Firestore as the database.

---

## Architecture Overview

```
infinitydesignerboutique-mgmt/
├── app.py                        # Flask application factory & entry point
├── config.py                     # Centralised configuration (env-driven)
├── requirements.txt              # Python dependencies
├── setup_root_admin.py           # One-time root admin seeding script
├── firestore.rules               # Firestore security rules
├── .env.example                  # Environment variable template
├── modules/                      # Flask Blueprints (route handlers)
│   ├── auth/routes.py            # Login, logout, PIN change
│   ├── users/routes.py           # Admin & Staff CRUD, gallery, logs
│   └── attendance/routes.py     # Punch in/out, history, analytics
├── services/                     # Business logic layer
│   ├── auth_service.py           # PIN hashing/verification, authentication
│   ├── user_service.py           # User management, gallery, perf logs
│   └── attendance_service.py    # Attendance tracking & analytics
├── utils/                        # Shared utilities
│   ├── firebase_client.py        # Firebase Admin SDK initialisation
│   ├── logger.py                 # IST-stamped rotating file logger + audit log
│   ├── timezone_utils.py         # Asia/Kolkata helpers, period calculations
│   └── validators.py             # Input validation
├── middleware/
│   └── auth_middleware.py        # RBAC decorators (admin_required, staff_required)
└── templates/
    ├── index.html                # Login page
    ├── change_pin.html           # First-login / voluntary PIN change
    ├── admin/
    │   ├── base.html             # Side-navigation layout
    │   ├── dashboard.html        # Attendance overview + analytics
    │   ├── staff_directory.html  # Staff list, search, status/PIN actions
    │   ├── staff_create.html     # Onboard staff or admin
    │   ├── staff_edit.html       # Edit staff profile
    │   └── staff_profile.html    # Full profile, gallery, notes, attendance
    └── staff/
        └── duty_station.html     # Visual punch-in/out station (simple UI)
```

---

## Firestore Database Structure

```
/admins/{user_id}
    user_id, full_name, phone_number, pin_hash (bcrypt),
    role: "admin", is_root, is_first_login, created_at, updated_at, created_by

/staff/{user_id}
    user_id, full_name, phone_number (immutable), designation,
    joining_date (IST), standard_login_time, standard_logout_time,
    emergency_contact, weekly_salary, skills: [str], status, pin_hash (bcrypt),
    role: "staff", is_first_login, created_at, updated_at, created_by

/staff/{user_id}/work_gallery/{image_id}
    image_id, image_url (Firebase Storage), storage_path, caption, uploaded_at, uploaded_by

/staff/{user_id}/performance_logs/{log_id}
    log_id, note, created_at, created_by

/attendance/{user_id}/records/{YYYYMMDD}
    user_id, date, punch_in, punch_out, status ("in"|"out"),
    duration_minutes, created_at, updated_at
```

---

## Quick Start

### 1. Install
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Firebase credentials
```

### 2. Seed Root Admin
```bash
python setup_root_admin.py
```

### 3. Run
```bash
python app.py
# OR production:
gunicorn -w 4 -b 0.0.0.0:8000 "app:create_app()"
```

---

## Features (Phase 0)

- Phone-based login + 4-digit bcrypt PIN authentication
- First-login PIN enforcement (staff must set private PIN)
- Admin PIN reset flow (temp PIN → forced change)
- Root Admin hidden from all lists, cannot be modified
- Staff directory: 3 designations, 3 statuses (Active/Inactive/Deactivated)
- Immutable phone numbers (audit trail integrity)
- Skill tags, work gallery (Firebase Storage), performance notes
- State-aware punch in/out, one record per day, double-click guard
- Analytics: Daily/Weekly/Monthly/Quarterly/Yearly
- IST timezone locked throughout
- Rotating log files with IST timestamps + audit log
- Modern Tailwind CSS UI (no Bootstrap), visual staff duty station

## Security

- All PINs bcrypt-hashed (12 rounds), never logged
- Server-side sessions (HttpOnly cookies)
- RBAC enforced server-side
- Firestore rules deny all direct client access
