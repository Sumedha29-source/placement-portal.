# placement-portal.
web portal where everything is managed in one place.

# 🎓 PlacementHub — Campus Placement Portal

A full-stack web application built with **Flask** that manages campus recruitment activities between Students, Companies, and the Institute's Placement Cell (Admin).

---

## 📁 Project Structure

```
placement-portal/
│
├── app.py                        ← All Flask routes and backend logic
├── database.py                   ← Run once to create database.db
├── database.db                   ← SQLite database (auto-created by setup_db.py)
│
├── templates/
│   ├── login.html                ← Login + Register page (all roles)
│   ├── student_dashboard.html    ← Student portal
│   ├── admin_dashboard.html      ← Admin portal
│   └── company_dashboard.html    ← Company portal
│
└── static/
        └── style.css             ← Custom styles (built on top of Bootstrap 5)
```

---

## ⚙️ Tech Stack

| Layer       | Technology                        |
|-------------|-----------------------------------|
| Backend     | Python 3, Flask                   |
| Frontend    | Jinja2, HTML5, Bootstrap 5, CSS3  |
| Database    | SQLite (via Python's `sqlite3`)   |
| Auth        | Flask sessions + SHA-256 hashing  |

---

## 🚀 How to Run Locally

### 1. Install dependencies

```bash
pip install flask
```

### 2. Set up the database

> ⚠️ Do this **once** before running the app for the first time.
> If you already have an old `database.db`, delete it first.

```bash
python setup_db.py
```

This creates `database.db` with all tables and seeds a default admin account:

| Field    | Value      |
|----------|------------|
| Username | `admin`    |
| Password | `admin123` |

### 3. Start the app

```bash
python app.py
```

### 4. Open in browser

```
http://127.0.0.1:5000
```

---

## 👥 Roles & Features

### 🛡️ Admin
- Pre-seeded in the database (no registration needed)
- View dashboard stats: total students, companies, drives, applications
- **Approve or reject** company registrations
- **Approve, reject, or close** placement drives
- View all students, companies, drives, and applications
- **Search** students by name, ID, email, or phone
- **Search** companies by name
- **Blacklist or activate** student and company accounts
- **Delete** student or company accounts

### 🏢 Company
- Register and create a company profile (HR contact, website, industry)
- Login **only after admin approval**
- **Create placement drives** (only if approved) — drives start as `Pending`
- Edit, close, or delete their own drives
- View all student applicants for their drives
- **Shortlist, select, or reject** applicants

### 🎓 Student
- Self-register and log in immediately
- View all **approved** placement drives with eligibility criteria
- **Apply** to drives (one application per drive enforced)
- Track **application status** (Applied → Shortlisted → Selected / Rejected)
- View **placement history**
- Edit profile: branch, CGPA, skills, phone, resume link

---

## 🗄️ Database Schema

### `users`
| Column      | Type    | Description                          |
|-------------|---------|--------------------------------------|
| id          | INTEGER | Primary key                          |
| username    | TEXT    | Unique login username                |
| password    | TEXT    | SHA-256 hashed password              |
| role        | TEXT    | `admin` / `student` / `company`      |
| is_active   | INTEGER | `1` = active, `0` = blacklisted      |

### `students`
| Column     | Type    | Description                  |
|------------|---------|------------------------------|
| id         | INTEGER | Primary key                  |
| user_id    | INTEGER | FK → users.id                |
| full_name  | TEXT    |                              |
| email      | TEXT    |                              |
| phone      | TEXT    |                              |
| branch     | TEXT    |                              |
| cgpa       | REAL    |                              |
| skills     | TEXT    | Comma-separated              |
| resume_url | TEXT    | Google Drive or URL link     |

### `companies`
| Column          | Type | Description                                   |
|-----------------|------|-----------------------------------------------|
| id              | INTEGER | Primary key                              |
| user_id         | INTEGER | FK → users.id                            |
| company_name    | TEXT |                                               |
| hr_contact      | TEXT | HR name / phone                               |
| email           | TEXT |                                               |
| website         | TEXT |                                               |
| industry        | TEXT |                                               |
| description     | TEXT |                                               |
| approval_status | TEXT | `pending` / `approved` / `rejected`           |

### `drives` (Placement Drives)
| Column          | Type    | Description                          |
|-----------------|---------|--------------------------------------|
| id              | INTEGER | Primary key                          |
| company_id      | INTEGER | FK → companies.id                    |
| job_title       | TEXT    |                                      |
| job_description | TEXT    |                                      |
| eligibility     | TEXT    | e.g. "Min CGPA 7.0, CSE/IT only"    |
| package         | TEXT    | e.g. "12 LPA"                        |
| deadline        | TEXT    | Application deadline date            |
| status          | TEXT    | `pending` / `approved` / `closed`    |
| created_on      | TEXT    | Auto-set to current date             |

### `applications`
| Column     | Type    | Description                                         |
|------------|---------|-----------------------------------------------------|
| id         | INTEGER | Primary key                                         |
| drive_id   | INTEGER | FK → drives.id                                      |
| student_id | INTEGER | FK → students.id                                    |
| status     | TEXT    | `Applied` / `Shortlisted` / `Selected` / `Rejected` |
| applied_on | TEXT    | Auto-set to current date                            |

> **Unique constraint** on `(drive_id, student_id)` prevents duplicate applications at the database level.

---

## 🔄 Key Workflows

```
Company registers → Admin approves company → Company creates drive
→ Admin approves drive → Students see & apply → Company shortlists/selects
```

```
Student registers → Logs in → Browses approved drives → Applies
→ Checks status (Applied → Shortlisted → Selected/Rejected)
```

---

## 🔐 Security Notes

- Passwords are stored as **SHA-256 hashes**, never plain text
- Role-based access: every route checks `session["role"]` before serving
- Blacklisted users are blocked at login
- Unapproved companies are blocked at login
- SQL queries use **parameterised statements** (`?` placeholders) to prevent SQL injection

---

## ❗ Common Issue

**`IndexError: No item with that key`** on login?

Your `database.db` was created by an older version of the code.
Fix it by deleting the old database and running setup again:

```bash
# Windows
del database.db
python setup_db.py

# Mac / Linux
rm database.db
python setup_db.py
```

---

## 📝 Default Login

| Role    | Username | Password   |
|---------|----------|------------|
| Admin   | `admin`  | `admin123` |
| Student | *(register on the login page)* | |
| Company | *(register, then wait for admin approval)* | |
