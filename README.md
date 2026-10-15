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
- GET /attendance (paginated, sorted, filtered, runs on an index)
- PATCH /attendance/{emp_code}/{date} (history entry, 409 on concurrent edit)
- GET /analytics/employees/{emp_code}/monthly
- GET /analytics/departments/summary
- GET /analytics/leaderboard/late
- GET /admin/explain/{endpoint} for attendance_list, employee_monthly, department_summary and late_leaderboard
- REVIEW.md (defects found in the starter code) and DECISIONS.md

## Not done yet
- GET /analytics/departments/{department}/trend
- /admin/explain/department_trend (returns 501 until the trend endpoint exists)