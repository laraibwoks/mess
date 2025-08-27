
# Mess Snacks Attendance — Mini App (Flask + SQLite)

## Quick Start
1. Install Python 3.10+ and pip.
2. In terminal:
```bash
cd mess_snacks_attendance
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env   # edit ADMIN_PASSWORD if you want
python app.py
```
3. Open: http://localhost:5000

## Workflow
- Public page (/) lets you mark today's snack by entering **Roll No** (or via QR link `/mark?roll=<ROLL>`).
- Admin pages (Dashboard, Students, Report) require login.
  - Default admin password: `mess123` (set in `.env`).
- Upload `students_sample.csv` (or your own CSV) to load students.

## CSV Format
`name,roll_no,hostel,batch` (headers must match)

## Generate QR per student
Create a QR pointing to: `http://<server>:5000/mark?roll=<ROLL_NO>`
Scanning it will mark attendance instantly (idempotent per day).

## Data
- SQLite file: `app.db` created on first run.
- Attendance is unique per (student, date).
