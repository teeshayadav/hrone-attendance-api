# Employee Attendance & Analytics API

FastAPI + MongoDB. All code is in `app/main.py`.

## Run
    pip install -r requirements.txt
    uvicorn app.main:app --port 8000

Set `MONGO_URI` and `MONGO_DB` as environment variables (defaults: `mongodb://localhost:27017`, `attendance_db`).
Indexes are created at startup.

## Done
- GET /health, POST /employees, GET /employees
- POST /attendance/punch-in, POST /attendance/punch-out
- GET /attendance, PATCH /attendance/{emp_code}/{date}
- GET /analytics/employees/{emp_code}/monthly
- GET /analytics/departments/summary
- GET /analytics/leaderboard/late
- Part A review: see REVIEW.md

## Not done yet
- GET /analytics/departments/{department}/trend
- GET /admin/explain/{endpoint}
- DECISIONS.md is incomplete