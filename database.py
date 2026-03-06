"""
setup_db.py
-----------
Run this ONCE before starting the app for the first time.
Creates database.db with all tables and a seeded admin account.

Usage:
    python setup_db.py
Then:
    python app.py
    Open http://127.0.0.1:5000
"""

import sqlite3
import hashlib

DATABASE = "database.db"

# Simple function to hash passwords using SHA-256 for secure storage in the database.
def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()

# The setup function initializes the SQLite database, creates the necessary tables for users,
# students, companies, drives, and applications, and seeds an admin account if it doesn't already exist.
# It also enables foreign key constraints to maintain data integrity across related tables.
def setup():
    conn = sqlite3.connect(DATABASE)
    conn.execute("PRAGMA foreign_keys = ON")
    
    # The users table stores all user accounts, including students,
    # companies, and admins, with fields for username, password, role, and active status.
    # ── users ────────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT UNIQUE NOT NULL,
            password    TEXT NOT NULL,
            role        TEXT NOT NULL,
            is_active   INTEGER DEFAULT 1
        )
    """)

    # The students table stores detailed information about student users, including their full name,
    # email, phone number, branch of study, CGPA, skills, and a URL to their resume. It has a foreign key
    # relationship with the users table to link each student to their corresponding user account.
    # ── students ─────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER UNIQUE NOT NULL,
            full_name   TEXT NOT NULL,
            email       TEXT NOT NULL,
            phone       TEXT,
            branch      TEXT NOT NULL,
            cgpa        REAL NOT NULL,
            skills      TEXT,
            resume_url  TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # The companies table stores information about company users, including the company name, HR contact,
    # email, website, industry, description, and approval status.
    # It also has a foreign key relationship with the users table to link each company 
    # to their corresponding user account. The approval_status field is used by admins 
    # to approve or reject company registrations.
    # ── companies ────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER UNIQUE NOT NULL,
            company_name    TEXT NOT NULL,
            hr_contact      TEXT,
            email           TEXT NOT NULL,
            website         TEXT,
            industry        TEXT,
            description     TEXT,
            approval_status TEXT DEFAULT 'pending',
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # The drives table stores information about placement drives created by companies, including the job title,
    # job description, eligibility criteria, package offered, application deadline,
    # and current status of the drive.
    # It has a foreign key relationship with the companies table to link each drive 
    # to the company that created it. 
    # The status field is used to track whether a drive is pending, active, or closed.
    # ── drives ───────────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS drives (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id      INTEGER NOT NULL,
            job_title       TEXT NOT NULL,
            job_description TEXT,
            eligibility     TEXT,
            package         TEXT,
            deadline        TEXT,
            status          TEXT DEFAULT 'pending',
            created_on      TEXT DEFAULT (DATE('now')),
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)

    # The applications table stores information about student applications to placement drives, 
    # including the drive ID,student ID, application status, and the date of application. 
    # It has foreign key relationships with both the drives and students tables to link each application
    # to the corresponding drive and student.
    # ── applications ─────────────────────────────────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            drive_id    INTEGER NOT NULL,
            student_id  INTEGER NOT NULL,
            status      TEXT DEFAULT 'Applied',
            applied_on  TEXT DEFAULT (DATE('now')),
            UNIQUE (drive_id, student_id),
            FOREIGN KEY (drive_id)   REFERENCES drives(id),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """)

    # After creating the tables, we check if an admin account already exists.
    # If not, we insert a default admin user with the username "admin" and password "admin123". 
    # The password is hashed using the hash_pw function before being stored in the database for security reasons. This seeded admin account allows you to log in to the admin dashboard and manage the application right away.
    # ── seed admin ───────────────────────────────────────────
    if not conn.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
        conn.execute(
            "INSERT INTO users (username, password, role) VALUES (?,?,?)",
            ("admin", hash_pw("admin123"), "admin")
        )
        print("✅ Admin account seeded")
        print("   Username : admin")
        print("   Password : admin123")
    else:
        print("ℹ️  Admin already exists, skipping.")

    conn.commit()
    conn.close()
    print("✅ database.db is ready!")
    print("\nNow run:  python app.py")
    print("Visit:    http://127.0.0.1:5000")


# When this script is run directly,
# it calls the setup function to initialize the database and create the necessary tables and admin account.
if __name__ == "__main__":
    setup()