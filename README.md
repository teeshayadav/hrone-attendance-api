# Employee Attendance & Analytics API

FastAPI + MongoDB. All code is in `app/main.py`.

## Run
    pip install -r requirements.txt
    uvicorn app.main:app --port 8000

Set `MONGO_URI` and `MONGO_DB` as environment variables (defaults: `mongodb://localhost:27017`, `attendance_db`).
Indexes are created at startup.

## Done
- POST /employees, GET /employees
- POST /attendance/punch-in
- POST /attendance/punch-out
- GET /attendance
- Part A review: see REVIEW.md

## Not done yet
- PATCH /attendance/{emp_code}/{date}
- Analytics endpoints (monthly, department summary, late leaderboard, trend)
- /admin/explain
- Small gaps: /health does not return 503 when MongoDB is down; GET /employees is not sorted by emp_code and has no page_size limit