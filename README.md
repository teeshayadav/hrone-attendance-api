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
- Part A review: see REVIEW.md

## Not done yet
- POST /attendance/punch-out
- PATCH /attendance/{emp_code}/{date}
- GET /attendance (starter version still has known issues)
- Analytics endpoints and /admin/explain