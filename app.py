
import os
import sqlite3
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, session, jsonify
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import io
import csv

load_dotenv()

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(APP_ROOT, "app.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        roll_no TEXT NOT NULL UNIQUE,
        hostel TEXT,
        batch TEXT
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        snacks_taken INTEGER NOT NULL DEFAULT 1,
        ts TEXT NOT NULL,
        UNIQUE(student_id, date),
        FOREIGN KEY(student_id) REFERENCES students(id)
    )""")
    conn.commit()
    conn.close()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "mess123")

init_db()

def today_str():
    return date.today().isoformat()

def require_admin():
    if not session.get("is_admin"):
        flash("Please login as admin.", "warning")
        return False
    return True

@app.route("/", methods=["GET", "POST"])
def index():
    conn = get_db()
    cur = conn.cursor()
    message = None
    status = "info"
    roll_q = request.args.get("roll", "").strip()
    if roll_q:
        request.form = request.form.copy()
        try:
            request.form = request.form.to_dict(flat=True)
        except Exception:
            pass
        request.form = {"roll_no": roll_q}

    if request.method == "POST" or roll_q:
        roll_no = (request.form.get("roll_no") or "").strip()
        if roll_no:
            cur.execute("SELECT * FROM students WHERE roll_no = ?", (roll_no,))
            stu = cur.fetchone()
            if stu:
                try:
                    cur.execute(
                        "INSERT INTO attendance (student_id, date, snacks_taken, ts) VALUES (?, ?, 1, ?)",
                        (stu["id"], today_str(), datetime.now().isoformat(timespec="seconds"))
                    )
                    conn.commit()
                    message = f"Marked: {stu['name']} ({stu['roll_no']})"
                    status = "success"
                except sqlite3.IntegrityError:
                    message = f"Already marked today for {stu['name']} ({stu['roll_no']})."
                    status = "warning"
            else:
                message = f"No student found with Roll No {roll_no}."
                status = "danger"
        else:
            message = "Please enter a Roll No."
            status = "danger"

    cur.execute("SELECT COUNT(*) AS total FROM students")
    total = (cur.fetchone()["total"] or 0)
    cur.execute("SELECT COUNT(*) AS taken FROM attendance WHERE date = ?", (today_str(),))
    taken = (cur.fetchone()["taken"] or 0)
    conn.close()

    return render_template("index.html", total=total, taken=taken, message=message, status=status, today=today_str())

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pwd = request.form.get("password", "")
        if pwd == ADMIN_PASSWORD:
            session["is_admin"] = True
            flash("Logged in as admin.", "success")
            return redirect(url_for("dashboard"))
        flash("Wrong password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("index"))

@app.route("/dashboard")
def dashboard():
    if not require_admin():
        return redirect(url_for("login"))
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS total FROM students")
    total = cur.fetchone()["total"] or 0
    cur.execute("SELECT COUNT(*) AS taken FROM attendance WHERE date = ?", (today_str(),))
    taken = cur.fetchone()["taken"] or 0
    cur.execute("""
        SELECT date, COUNT(*) AS count
        FROM attendance
        GROUP BY date ORDER BY date DESC LIMIT 14
    """)
    recent = cur.fetchall()
    conn.close()
    return render_template("dashboard.html", total=total, taken=taken, recent=recent, today=today_str())

@app.route("/students", methods=["GET", "POST"])
def students():
    if not require_admin():
        return redirect(url_for("login"))
    conn = get_db()
    cur = conn.cursor()
    if request.method == "POST":
        name = request.form.get("name","").strip()
        roll = request.form.get("roll_no","").strip()
        hostel = request.form.get("hostel","").strip()
        batch = request.form.get("batch","").strip()
        if name and roll:
            try:
                cur.execute(
                    "INSERT INTO students(name, roll_no, hostel, batch) VALUES (?, ?, ?, ?)",
                    (name, roll, hostel, batch)
                )
                conn.commit()
                flash("Student added.", "success")
            except sqlite3.IntegrityError:
                flash("Roll No already exists.", "danger")
        else:
            flash("Name and Roll No are required.", "danger")

    cur.execute("SELECT * FROM students ORDER BY CAST(roll_no AS INTEGER) ASC")
    rows = cur.fetchall()
    conn.close()
    return render_template("students.html", rows=rows)

@app.route("/students/upload", methods=["POST"])
def upload_students():
    if not require_admin():
        return redirect(url_for("login"))
    file = request.files.get("file")
    if not file:
        flash("No file selected.", "danger")
        return redirect(url_for("students"))
    filename = secure_filename(file.filename)
    if not filename.lower().endswith(".csv"):
        flash("Please upload a CSV file.", "danger")
        return redirect(url_for("students"))
    content = file.stream.read().decode("utf-8").splitlines()
    reader = csv.DictReader(content)
    expected = {"name","roll_no","hostel","batch"}
    if not expected.issubset({(c or '').strip().lower() for c in (reader.fieldnames or [])}):
        flash("CSV must have headers: name, roll_no, hostel, batch", "danger")
        return redirect(url_for("students"))
    conn = get_db()
    cur = conn.cursor()
    added = 0
    skipped = 0
    for row in reader:
        name = (row.get("name","") or "").strip()
        roll = (row.get("roll_no","") or "").strip()
        hostel = (row.get("hostel","") or "").strip()
        batch = (row.get("batch","") or "").strip()
        if not name or not roll:
            skipped += 1
            continue
        try:
            cur.execute(
                "INSERT INTO students(name, roll_no, hostel, batch) VALUES (?, ?, ?, ?)",
                (name, roll, hostel, batch)
            )
            added += 1
        except sqlite3.IntegrityError:
            skipped += 1
    conn.commit()
    conn.close()
    flash(f"Upload complete. Added {added}, skipped {skipped}.", "info")
    return redirect(url_for("students"))

@app.route("/mark")
def mark_via_get():
    roll = (request.args.get("roll") or "").strip()
    if not roll:
        flash("Missing roll parameter.", "danger")
        return redirect(url_for("index"))
    return redirect(url_for("index", roll=roll))

@app.route("/report", methods=["GET", "POST"])
def report():
    if not require_admin():
        return redirect(url_for("login"))
    conn = get_db()
    cur = conn.cursor()
    selected_date = request.values.get("date", today_str())
    cur.execute("""
        SELECT s.roll_no, s.name, s.hostel, s.batch,
               CASE WHEN a.id IS NULL THEN 0 ELSE 1 END AS taken
        FROM students s
        LEFT JOIN attendance a
          ON a.student_id = s.id AND a.date = ?
        ORDER BY CAST(s.roll_no AS INTEGER) ASC
    """, (selected_date,))
    rows = cur.fetchall()
    taken = sum(1 for r in rows if r["taken"] == 1)
    total = len(rows)
    conn.close()
    return render_template("report.html", rows=rows, selected_date=selected_date, total=total, taken=taken)

@app.route("/export.csv")
def export_csv():
    if not require_admin():
        return redirect(url_for("login"))
    selected_date = request.args.get("date", today_str())
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT s.roll_no, s.name, s.hostel, s.batch,
               CASE WHEN a.id IS NULL THEN 0 ELSE 1 END AS snacks_taken
        FROM students s
        LEFT JOIN attendance a
          ON a.student_id = s.id AND a.date = ?
        ORDER BY CAST(s.roll_no AS INTEGER) ASC
    """, (selected_date,))
    rows = cur.fetchall()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["roll_no","name","hostel","batch","snacks_taken","date"])
    for r in rows:
        writer.writerow([r["roll_no"], r["name"], r["hostel"], r["batch"], r["snacks_taken"], selected_date])
    mem = io.BytesIO()
    mem.write(output.getvalue().encode("utf-8"))
    mem.seek(0)
    filename = f"attendance_{selected_date}.csv"
    return send_file(mem, as_attachment=True, download_name=filename, mimetype="text/csv")

@app.route("/scan")
def scan():
    return render_template("scan.html")


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)


