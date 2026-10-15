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
- GET /analytics/departments/{department}/trend
- GET /admin/explain/{endpoint} for all five endpoints
- REVIEW.md (defects found in the starter code) and DECISIONS.md

## Not done / limits
- All endpoints were tested by hand in Swagger with the sample seed data.
- The IXSCAN check on /admin/explain was done on that small data, not on a 100k-record dataset.
- No automated tests are included.