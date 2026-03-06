"""
Placement Portal – app.py
==========================
Backend for a campus placement management system.
Roles: Admin (pre-seeded), Company, Student.

Key rules from the project spec:
  • Companies can only log in after Admin approves their registration.
  • Companies can only create drives after Admin approval of the company.
  • Drives start as 'Pending' and must be approved by Admin before students see them.
  • Application statuses: Applied → Shortlisted → Selected / Rejected.
  • Admin can blacklist/deactivate students and companies.
  • Admin can search students and companies.
  • JS is NOT used for any core feature (Bootstrap modals use data-bs-* attributes, no custom JS logic).
"""

from flask import (
    Flask, render_template, request,
    redirect, url_for, session, flash
)
import sqlite3
import hashlib

app = Flask(__name__)
app.secret_key = "placement_portal_2024_secret"

DATABASE = "database.db"


# ──────────────────────────────────────────────────────────────
#  DB HELPERS
# ──────────────────────────────────────────────────────────────

# Note: In a production app, use connection pooling and proper error handling.
def get_db():
    """Return a Row-factory-enabled SQLite connection."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

# Note: In a real app, use a stronger hashing algorithm like bcrypt with salt.
def hash_pw(password):
    """SHA-256 hash a password string."""
    return hashlib.sha256(password.encode()).hexdigest()

# Note: Call this once at startup to create tables and seed admin.
def init_db():
    """
    Create all tables programmatically and seed the admin account.
    Called once when app.py starts.
    """
    conn = get_db()

    # ── users: login credentials for every role ─────────────
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT UNIQUE NOT NULL,
            password    TEXT NOT NULL,
            role        TEXT NOT NULL,          -- 'admin' | 'student' | 'company'
            is_active   INTEGER DEFAULT 1       -- 0 = blacklisted / deactivated
        )
    """)

    # ── students: profile data ───────────────────────────────
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

    # ── companies: profile + approval status ────────────────
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
            approval_status TEXT DEFAULT 'pending',  -- 'pending' | 'approved' | 'rejected'
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    # ── drives: placement drives created by companies ────────
    # Status lifecycle: pending (waiting admin) → approved → closed
    conn.execute("""
        CREATE TABLE IF NOT EXISTS drives (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id      INTEGER NOT NULL,
            job_title       TEXT NOT NULL,
            job_description TEXT,
            eligibility     TEXT,               -- e.g. "Min CGPA 7.0, CS/IT only"
            package         TEXT,
            deadline        TEXT,
            status          TEXT DEFAULT 'pending',  -- 'pending' | 'approved' | 'closed'
            created_on      TEXT DEFAULT (DATE('now')),
            FOREIGN KEY (company_id) REFERENCES companies(id)
        )
    """)

    # ── applications: student → drive ───────────────────────
    # Status lifecycle: Applied → Shortlisted → Selected / Rejected
    conn.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            drive_id    INTEGER NOT NULL,
            student_id  INTEGER NOT NULL,
            status      TEXT DEFAULT 'Applied',   -- 'Applied'|'Shortlisted'|'Selected'|'Rejected'
            applied_on  TEXT DEFAULT (DATE('now')),
            UNIQUE (drive_id, student_id),         -- prevents duplicate applications
            FOREIGN KEY (drive_id)   REFERENCES drives(id),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """)

    # ── Seed admin ───────────────────────────────────────────
    if not conn.execute("SELECT 1 FROM users WHERE role='admin'").fetchone():
        conn.execute(
            "INSERT INTO users (username, password, role) VALUES (?,?,?)",
            ("admin", hash_pw("admin123"), "admin")
        )
        print("✅ Admin seeded  →  username: admin | password: admin123")

    conn.commit()
    conn.close()


# ──────────────────────────────────────────────────────────────
#  AUTH
# ──────────────────────────────────────────────────────────────

# Note: In a real app, use Flask-Login or similar for session management and access control.
# For simplicity, we store user_id, username, and role in the session after login.
@app.route("/")

# Redirect to login page
# In a real app, you might want to redirect to different dashboards based on session or show a landing page.
def index():
    return redirect(url_for("login"))

# Note: In a real app, implement proper error handling and rate limiting for login attempts.
# Also, consider using Flask-WTF for form handling and CSRF protection.
# This route handles both login and registration form submissions from the same page.
@app.route("/login", methods=["GET", "POST"])

# For GET requests, it simply renders the login.html template.
# For POST requests, it checks if the form submission is for login or registration
# based on the presence of the "role" field (which is only in the registration form).
# Then it processes the login or registration accordingly, with appropriate flash messages for feedback.
# After successful login, it redirects users to their respective dashboards based on their role.
# The registration process includes checks for unique usernames 
# and handles the creation of user records in the database,
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, hash_pw(password))
        ).fetchone()
        conn.close()

        if not user:
            flash("Incorrect username or password.", "danger")
            return render_template("login.html")

        # Blacklisted users cannot log in
        if not user["is_active"]:
            flash("Your account has been deactivated. Contact the placement cell.", "danger")
            return render_template("login.html")

        # Companies must be approved before they can log in
        if user["role"] == "company":
            conn = get_db()
            co = conn.execute(
                "SELECT approval_status FROM companies WHERE user_id=?", (user["id"],)
            ).fetchone()
            conn.close()
            if co and co["approval_status"] != "approved":
                flash("Your company registration is awaiting admin approval.", "warning")
                return render_template("login.html")

        # Store session
        session["user_id"]  = user["id"]
        session["username"] = user["username"]
        session["role"]     = user["role"]

        if user["role"] == "admin":
            return redirect(url_for("admin_dashboard"))
        elif user["role"] == "student":
            return redirect(url_for("student_dashboard"))
        else:
            return redirect(url_for("company_dashboard"))

    return render_template("login.html")

# Note: In a real app, implement proper error handling and rate limiting for registration.
# Also, consider using Flask-WTF for form handling and CSRF protection.
# This route processes the registration form submission. It checks the role (student or company),
# validates the uniqueness of the username, and then creates the user record in the database.
@app.route("/register", methods=["POST"])

# For student registration, it also creates a corresponding record in the students table 
# with the provided profile information.
# For company registration, it creates a record in the companies table 
# with the provided profile information and sets the approval_status to 'pending' by default. 
# After successful registration, it flashes a message and redirects to the login page.
# Note that companies cannot log in until an admin approves their registration,
def register():
    role     = request.form.get("role", "")
    username = request.form["username"].strip()
    password = request.form["password"]

    if role not in ("student", "company"):
        flash("Invalid role.", "danger")
        return render_template("login.html")

    conn = get_db()
    if conn.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
        flash("Username already taken. Choose another.", "danger")
        conn.close()
        return render_template("login.html")

    # Insert user
    conn.execute(
        "INSERT INTO users (username, password, role) VALUES (?,?,?)",
        (username, hash_pw(password), role)
    )
    conn.commit()
    uid = conn.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()["id"]

    if role == "student":
        conn.execute(
            """INSERT INTO students (user_id, full_name, email, phone, branch, cgpa, skills)
               VALUES (?,?,?,?,?,?,?)""",
            (uid,
             request.form.get("full_name", "").strip(),
             request.form.get("email", "").strip(),
             request.form.get("phone", "").strip(),
             request.form.get("branch", "").strip(),
             float(request.form.get("cgpa") or 0),
             request.form.get("skills", "").strip())
        )
        conn.commit()
        conn.close()
        flash("Registration successful! You can now log in.", "success")

    elif role == "company":
        conn.execute(
            """INSERT INTO companies
               (user_id, company_name, hr_contact, email, website, industry, description)
               VALUES (?,?,?,?,?,?,?)""",
            (uid,
             request.form.get("company_name", "").strip(),
             request.form.get("hr_contact", "").strip(),
             request.form.get("email", "").strip(),
             request.form.get("website", "").strip(),
             request.form.get("industry", "").strip(),
             request.form.get("description", "").strip())
        )
        conn.commit()
        conn.close()
        flash("Company registered! Please wait for admin approval before logging in.", "info")

    return redirect(url_for("login"))

# Note: In a real app, ensure that logout properly clears the session and 
# consider using Flask-Login's logout_user() for better session management.
# This route simply clears the session and redirects to the login page with a flash message.
@app.route("/logout")

# Logs out the user by clearing the session and redirects to the login page.
# In a real application, you might want to perform additional cleanup or logging on logout.
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))


# ──────────────────────────────────────────────────────────────
#  ADMIN
# ──────────────────────────────────────────────────────────────

# Note: In a real app, implement proper access control and error handling for admin routes.
# This function checks if the current session belongs to an admin user.
def admin_required():
    return session.get("role") == "admin"

# The admin dashboard route displays all students, companies, drives, and applications.
# It also supports optional search queries for students and companies.
@app.route("/admin/dashboard")

# This route renders the admin dashboard, showing lists of students, companies, drives, and applications.
# It also calculates some statistics like total counts for each entity.
def admin_dashboard():
    if not admin_required():
        return redirect(url_for("login"))

    # Optional search query
    q_student = request.args.get("q_student", "").strip()
    q_company = request.args.get("q_company", "").strip()

    conn = get_db()

    # Search students by name, ID, or email (phone used as contact)
    if q_student:
        students = conn.execute("""
            SELECT students.*, users.username, users.is_active
            FROM students JOIN users ON students.user_id = users.id
            WHERE students.full_name LIKE ?
               OR CAST(students.id AS TEXT) LIKE ?
               OR students.email LIKE ?
               OR students.phone LIKE ?
            ORDER BY students.id DESC
        """, (f"%{q_student}%", f"%{q_student}%", f"%{q_student}%", f"%{q_student}%")).fetchall()
    else:
        students = conn.execute("""
            SELECT students.*, users.username, users.is_active
            FROM students JOIN users ON students.user_id = users.id
            ORDER BY students.id DESC
        """).fetchall()

    # Search companies by name
    if q_company:
        companies = conn.execute("""
            SELECT companies.*, users.username, users.is_active
            FROM companies JOIN users ON companies.user_id = users.id
            WHERE companies.company_name LIKE ?
            ORDER BY companies.id DESC
        """, (f"%{q_company}%",)).fetchall()
    else:
        companies = conn.execute("""
            SELECT companies.*, users.username, users.is_active
            FROM companies JOIN users ON companies.user_id = users.id
            ORDER BY companies.id DESC
        """).fetchall()

    drives = conn.execute("""
        SELECT drives.*, companies.company_name
        FROM drives JOIN companies ON drives.company_id = companies.id
        ORDER BY drives.id DESC
    """).fetchall()

    applications = conn.execute("""
        SELECT applications.*,
               students.full_name AS student_name,
               drives.job_title,
               companies.company_name
        FROM applications
        JOIN students  ON applications.student_id = students.id
        JOIN drives    ON applications.drive_id   = drives.id
        JOIN companies ON drives.company_id       = companies.id
        ORDER BY applications.id DESC
    """).fetchall()

    stats = {
        "total_students"  : conn.execute("SELECT COUNT(*) FROM students").fetchone()[0],
        "total_companies" : conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0],
        "total_drives"    : conn.execute("SELECT COUNT(*) FROM drives").fetchone()[0],
        "total_apps"      : conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0],
    }

    conn.close()
    return render_template("admin_dashboard.html",
        students=students, companies=companies, drives=drives,
        applications=applications, stats=stats,
        q_student=q_student, q_company=q_company)


# ── Approve / Reject company registration ──────────────────

# This route allows the admin to approve or reject a company's registration.
# It updates the approval_status field in the companies table based on the action taken by the admin.
@app.route("/admin/company/<int:co_id>/approve", methods=["POST"])

# The admin can set the company's approval_status to 'approved' or 'rejected' based on the form submission.
def admin_approve_company(co_id):
    if not admin_required(): return redirect(url_for("login"))
    action = request.form.get("action")   # 'approved' or 'rejected'
    conn = get_db()
    conn.execute("UPDATE companies SET approval_status=? WHERE id=?", (action, co_id))
    conn.commit()
    conn.close()
    flash(f"Company {'approved' if action=='approved' else 'rejected'}.", "success")
    return redirect(url_for("admin_dashboard"))


# ── Approve / Reject / Close a placement drive ─────────────

# This route allows the admin to update the status of a placement drive to 'approved', 'closed', or 'pending'.
@app.route("/admin/drive/<int:drive_id>/status", methods=["POST"])

# The admin can set the drive's status based on the form submission,
# which determines whether the drive is visible to students and whether it is active for applications.
def admin_drive_status(drive_id):
    if not admin_required(): return redirect(url_for("login"))
    new_status = request.form.get("status")   # 'approved' | 'closed' | 'pending'
    conn = get_db()
    conn.execute("UPDATE drives SET status=? WHERE id=?", (new_status, drive_id))
    conn.commit()
    conn.close()
    flash(f"Drive status set to '{new_status}'.", "success")
    return redirect(url_for("admin_dashboard"))


# ── Blacklist / Activate student ───────────────────────────

# This route allows the admin to toggle a student's active status, 
# effectively blacklisting or activating the student.
@app.route("/admin/student/<int:student_id>/toggle", methods=["POST"])

# The admin can toggle the student's is_active status in the users table,
# which determines whether the student can log in and apply for drives.
def admin_toggle_student(student_id):
    if not admin_required(): return redirect(url_for("login"))
    conn = get_db()
    s = conn.execute(
        "SELECT users.id, users.is_active FROM students JOIN users ON students.user_id=users.id WHERE students.id=?",
        (student_id,)
    ).fetchone()
    if s:
        new_val = 0 if s["is_active"] else 1
        conn.execute("UPDATE users SET is_active=? WHERE id=?", (new_val, s["id"]))
        conn.commit()
        flash("Student " + ("activated." if new_val else "blacklisted."), "success")
    conn.close()
    return redirect(url_for("admin_dashboard"))


# ── Blacklist / Activate company ───────────────────────────

# This route allows the admin to toggle a company's active status,
# effectively blacklisting or activating the company.
@app.route("/admin/company/<int:co_id>/toggle", methods=["POST"])

# The admin can toggle the company's is_active status in the users table,
# which determines whether the company can log in and create drives.
def admin_toggle_company(co_id):
    if not admin_required(): return redirect(url_for("login"))
    conn = get_db()
    c = conn.execute(
        "SELECT users.id, users.is_active FROM companies JOIN users ON companies.user_id=users.id WHERE companies.id=?",
        (co_id,)
    ).fetchone()
    if c:
        new_val = 0 if c["is_active"] else 1
        conn.execute("UPDATE users SET is_active=? WHERE id=?", (new_val, c["id"]))
        conn.commit()
        flash("Company " + ("activated." if new_val else "blacklisted."), "success")
    conn.close()
    return redirect(url_for("admin_dashboard"))


# ── Delete student ─────────────────────────────────────────

# This route allows the admin to delete a student from the system,
# including their user record and any applications they have made.
@app.route("/admin/student/<int:student_id>/delete", methods=["POST"])

# The admin can delete the student by removing their record from the students table,
# their user record from the users table, and any related applications from the applications table.
def admin_delete_student(student_id):
    if not admin_required(): return redirect(url_for("login"))
    conn = get_db()
    s = conn.execute("SELECT user_id FROM students WHERE id=?", (student_id,)).fetchone()
    if s:
        conn.execute("DELETE FROM applications WHERE student_id=?", (student_id,))
        conn.execute("DELETE FROM students WHERE id=?", (student_id,))
        conn.execute("DELETE FROM users WHERE id=?", (s["user_id"],))
        conn.commit()
        flash("Student deleted.", "success")
    conn.close()
    return redirect(url_for("admin_dashboard"))


# ── Delete company ─────────────────────────────────────────

# This route allows the admin to delete a company from the system,
# including their user record, any drives they have created, and any applications to those drives.
@app.route("/admin/company/<int:co_id>/delete", methods=["POST"])

# The admin can delete the company by removing their record from the companies table,
# their user record from the users table, any drives they have created from the drives table,
# and any applications to those drives from the applications table.
def admin_delete_company(co_id):
    if not admin_required(): return redirect(url_for("login"))
    conn = get_db()
    c = conn.execute("SELECT user_id FROM companies WHERE id=?", (co_id,)).fetchone()
    if c:
        # Remove applications for drives belonging to this company first
        conn.execute("""
            DELETE FROM applications WHERE drive_id IN
            (SELECT id FROM drives WHERE company_id=?)
        """, (co_id,))
        conn.execute("DELETE FROM drives WHERE company_id=?", (co_id,))
        conn.execute("DELETE FROM companies WHERE id=?", (co_id,))
        conn.execute("DELETE FROM users WHERE id=?", (c["user_id"],))
        conn.commit()
        flash("Company deleted.", "success")
    conn.close()
    return redirect(url_for("admin_dashboard"))


# ──────────────────────────────────────────────────────────────
#  STUDENT
# ──────────────────────────────────────────────────────────────

# This function checks if the current session belongs to a student user.
def student_required():
    return session.get("role") == "student"

# The student dashboard route displays the student's profile, available drives, and their application history.
@app.route("/student/dashboard")

# This route renders the student dashboard, showing the student's profile information,
def student_dashboard():
    if not student_required(): return redirect(url_for("login"))

    conn = get_db()
    student = conn.execute(
        "SELECT * FROM students WHERE user_id=?", (session["user_id"],)
    ).fetchone()

    # Only show APPROVED drives
    drives = conn.execute("""
        SELECT drives.*, companies.company_name
        FROM drives JOIN companies ON drives.company_id = companies.id
        WHERE drives.status = 'approved'
        ORDER BY drives.id DESC
    """).fetchall()

    # This student's applications (all statuses = history)
    applications = []
    if student:
        applications = conn.execute("""
            SELECT applications.*, drives.job_title, drives.package,
                   companies.company_name
            FROM applications
            JOIN drives    ON applications.drive_id   = drives.id
            JOIN companies ON drives.company_id       = companies.id
            WHERE applications.student_id = ?
            ORDER BY applications.id DESC
        """, (student["id"],)).fetchall()

    conn.close()
    return render_template("student_dashboard.html",
        student=student, drives=drives, applications=applications)

# This route allows a student to apply for a placement drive.
# It checks if the student has already applied to the drive and prevents duplicate applications.
@app.route("/student/apply/<int:drive_id>", methods=["POST"])

# The student can apply to a drive by creating a new record in the applications table
# with the status set to 'Applied'.
def student_apply(drive_id):
    if not student_required(): return redirect(url_for("login"))
    conn = get_db()
    student = conn.execute(
        "SELECT id FROM students WHERE user_id=?", (session["user_id"],)
    ).fetchone()
    if student:
        exists = conn.execute(
            "SELECT 1 FROM applications WHERE drive_id=? AND student_id=?",
            (drive_id, student["id"])
        ).fetchone()
        if exists:
            flash("You have already applied to this drive.", "warning")
        else:
            try:
                conn.execute(
                    "INSERT INTO applications (drive_id, student_id) VALUES (?,?)",
                    (drive_id, student["id"])
                )
                conn.commit()
                flash("Application submitted successfully!", "success")
            except Exception:
                flash("Could not apply. Please try again.", "danger")
    conn.close()
    return redirect(url_for("student_dashboard"))

# This route allows a student to update their profile information.
@app.route("/student/profile/update", methods=["POST"])

# The student can update their profile by modifying their record in the students table 
# with the new information provided in the form.
def student_profile_update():
    if not student_required(): return redirect(url_for("login"))
    conn = get_db()
    conn.execute("""
        UPDATE students
        SET full_name=?, email=?, phone=?, branch=?, cgpa=?, skills=?, resume_url=?
        WHERE user_id=?
    """, (
        request.form.get("full_name","").strip(),
        request.form.get("email","").strip(),
        request.form.get("phone","").strip(),
        request.form.get("branch","").strip(),
        float(request.form.get("cgpa") or 0),
        request.form.get("skills","").strip(),
        request.form.get("resume_url","").strip(),
        session["user_id"]
    ))
    conn.commit()
    conn.close()
    flash("Profile updated!", "success")
    return redirect(url_for("student_dashboard"))


# ──────────────────────────────────────────────────────────────
#  COMPANY
# ──────────────────────────────────────────────────────────────

# This function checks if the current session belongs to a company user.
def company_required():
    return session.get("role") == "company"

# The company dashboard route displays the company's profile, their created drives, 
# and applications to those drives.
@app.route("/company/dashboard")

# This route renders the company dashboard, showing the company's profile information,
# the drives they have created, and the applications to those drives along with applicant details.
def company_dashboard():
    if not company_required(): return redirect(url_for("login"))

    conn = get_db()
    company = conn.execute(
        "SELECT * FROM companies WHERE user_id=?", (session["user_id"],)
    ).fetchone()

    drives = []
    applications = []

    if company:
        drives = conn.execute(
            "SELECT * FROM drives WHERE company_id=? ORDER BY id DESC",
            (company["id"],)
        ).fetchall()

        applications = conn.execute("""
            SELECT applications.*,
                   students.full_name, students.email, students.phone,
                   students.branch, students.cgpa, students.skills, students.resume_url,
                   drives.job_title
            FROM applications
            JOIN students ON applications.student_id = students.id
            JOIN drives   ON applications.drive_id   = drives.id
            WHERE drives.company_id = ?
            ORDER BY applications.id DESC
        """, (company["id"],)).fetchall()

    conn.close()
    return render_template("company_dashboard.html",
        company=company, drives=drives, applications=applications)


# This route allows a company to create a new placement drive.
@app.route("/company/drive/create", methods=["POST"])

# The company can create a drive by inserting a new record into the drives table with the provided information.
def company_create_drive():
    if not company_required(): return redirect(url_for("login"))
    conn = get_db()
    company = conn.execute(
        "SELECT id, approval_status FROM companies WHERE user_id=?",
        (session["user_id"],)
    ).fetchone()

    if not company or company["approval_status"] != "approved":
        flash("Only approved companies can create placement drives.", "danger")
        conn.close()
        return redirect(url_for("company_dashboard"))

    conn.execute("""
        INSERT INTO drives (company_id, job_title, job_description, eligibility, package, deadline)
        VALUES (?,?,?,?,?,?)
    """, (
        company["id"],
        request.form["job_title"].strip(),
        request.form.get("job_description","").strip(),
        request.form.get("eligibility","").strip(),
        request.form.get("package","").strip(),
        request.form.get("deadline","").strip()
    ))
    conn.commit()
    conn.close()
    flash("Drive submitted for admin approval.", "info")
    return redirect(url_for("company_dashboard"))


# This route allows a company to edit an existing placement drive.
@app.route("/company/drive/<int:drive_id>/edit", methods=["POST"])

# The company can edit a drive by updating the corresponding record 
# in the drives table with the new information provided in the form.
def company_edit_drive(drive_id):
    if not company_required(): return redirect(url_for("login"))
    conn = get_db()
    # Verify this drive belongs to this company
    company = conn.execute(
        "SELECT id FROM companies WHERE user_id=?", (session["user_id"],)
    ).fetchone()
    drive = conn.execute(
        "SELECT id FROM drives WHERE id=? AND company_id=?",
        (drive_id, company["id"] if company else -1)
    ).fetchone()
    if drive:
        conn.execute("""
            UPDATE drives
            SET job_title=?, job_description=?, eligibility=?, package=?, deadline=?
            WHERE id=?
        """, (
            request.form["job_title"].strip(),
            request.form.get("job_description","").strip(),
            request.form.get("eligibility","").strip(),
            request.form.get("package","").strip(),
            request.form.get("deadline","").strip(),
            drive_id
        ))
        conn.commit()
        flash("Drive updated successfully.", "success")
    conn.close()
    return redirect(url_for("company_dashboard"))

# This route allows a company to close an active placement drive, changing its status to 'closed'.
@app.route("/company/drive/<int:drive_id>/close", methods=["POST"])

# The company can close a drive by updating the status field of the corresponding record in the
# drives table to 'closed'.
def company_close_drive(drive_id):
    if not company_required(): return redirect(url_for("login"))
    conn = get_db()
    company = conn.execute(
        "SELECT id FROM companies WHERE user_id=?", (session["user_id"],)
    ).fetchone()
    if company:
        conn.execute(
            "UPDATE drives SET status='closed' WHERE id=? AND company_id=?",
            (drive_id, company["id"])
        )
        conn.commit()
        flash("Drive closed.", "success")
    conn.close()
    return redirect(url_for("company_dashboard"))

# This route allows a company to delete a placement drive, 
# removing it from the system along with any applications to that drive.
@app.route("/company/drive/<int:drive_id>/delete", methods=["POST"])

# The company can delete a drive by removing the corresponding record from the drives table,
# and also deleting any related applications from the applications table to maintain data integrity.
def company_delete_drive(drive_id):
    if not company_required(): return redirect(url_for("login"))
    conn = get_db()
    company = conn.execute(
        "SELECT id FROM companies WHERE user_id=?", (session["user_id"],)
    ).fetchone()
    if company:
        conn.execute("DELETE FROM applications WHERE drive_id=?", (drive_id,))
        conn.execute(
            "DELETE FROM drives WHERE id=? AND company_id=?",
            (drive_id, company["id"])
        )
        conn.commit()
        flash("Drive deleted.", "success")
    conn.close()
    return redirect(url_for("company_dashboard"))

# This route allows a company to shortlist, select, or reject an applicant for a placement drive.
@app.route("/company/application/<int:app_id>/status", methods=["POST"])

# The company can update an application's status by modifying the status field of the corresponding record
# in the applications table to 'Shortlisted', 'Selected', or 'Rejected' based on the form submission.
def company_update_application(app_id):
    """Company shortlists / selects / rejects an applicant."""
    if not company_required(): return redirect(url_for("login"))
    new_status = request.form.get("status")
    allowed = ("Shortlisted", "Selected", "Rejected")
    if new_status not in allowed:
        flash("Invalid status.", "danger")
        return redirect(url_for("company_dashboard"))
    conn = get_db()
    conn.execute("UPDATE applications SET status=? WHERE id=?", (new_status, app_id))
    conn.commit()
    conn.close()
    flash(f"Applicant marked as '{new_status}'.", "success")
    return redirect(url_for("company_dashboard"))

# This route allows a company to update their profile information.
@app.route("/company/profile/update", methods=["POST"])


# The company can update their profile by modifying their record in the companies table
# with the new information provided in the form. Note that the approval_status is not changed here,
# so any updates to the profile do not require re-approval by the admin.
def company_profile_update():
    if not company_required(): return redirect(url_for("login"))
    conn = get_db()
    conn.execute("""
        UPDATE companies
        SET company_name=?, hr_contact=?, email=?, website=?, industry=?, description=?
        WHERE user_id=?
    """, (
        request.form.get("company_name","").strip(),
        request.form.get("hr_contact","").strip(),
        request.form.get("email","").strip(),
        request.form.get("website","").strip(),
        request.form.get("industry","").strip(),
        request.form.get("description","").strip(),
        session["user_id"]
    ))
    conn.commit()
    conn.close()
    flash("Profile updated!", "success")
    return redirect(url_for("company_dashboard"))


# ──────────────────────────────────────────────────────────────
#  ENTRY POINT
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    app.run(debug=True)