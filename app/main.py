"""
Employee Attendance & Analytics API - STARTER

Run:  uvicorn app.main:app --port 8000
Env:  MONGO_URI, MONGO_DB (a local .env is loaded for convenience)

This file was written quickly by a colleague who has left the company. The happy path
works, but nobody has reviewed it. Read PROBLEM_STATEMENT.docx for what is expected of you,
openapi.yaml for the contract and DATA_MODEL.md for what is stored in MongoDB.
"""
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

load_dotenv()

client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"), serverSelectionTimeoutMS=3000)
db = client[os.getenv("MONGO_DB", "attendance_db")]

IST = timezone(timedelta(hours=5, minutes=30))

@asynccontextmanager
async def lifespan(app):
    db.employees.create_index("emp_code", unique=True)
    db.attendance_logs.create_index([("emp_code", 1), ("date", 1)], unique=True)
    db.attendance_logs.create_index([("date", -1), ("emp_code", 1)])
    db.employees.create_index([("department", 1), ("emp_code", 1)])
    db.employees.create_index([("joined_on", 1), ("department", 1)])
    yield



app = FastAPI(title="Employee Attendance & Analytics API", version="2.0.0", lifespan=lifespan)
def to_millis(dt):
    dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def from_millis(ms: int) -> datetime:
    return datetime.fromtimestamp(ms // 1000, tz=timezone.utc)


def attendance_date(punch_in: datetime, shift_start: str, shift_end: str) -> str:
    ist_time = punch_in.astimezone(IST)
    day = ist_time.date()
    if shift_end <= shift_start and ist_time.strftime("%H:%M") < shift_end:
        day = day - timedelta(days=1)
    return day.isoformat()

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def ms_or_none(v):
    return to_millis(v) if isinstance(v, datetime) else v


def format_record(d: dict) -> dict:
    d.pop("_id", None)
    d["punch_in"] = ms_or_none(d.get("punch_in"))
    d["punch_out"] = ms_or_none(d.get("punch_out"))
    d.setdefault("half_day", False)
    d.setdefault("work_hours", None)
    d.setdefault("late_minutes", 0)
    d.setdefault("overtime_minutes", 0)
    history = d.get("history") or []
    for h in history:
        h["at"] = ms_or_none(h.get("at"))
        for ch in (h.get("changes") or {}).values():
            if isinstance(ch, dict):
                ch["from"] = ms_or_none(ch.get("from"))
                ch["to"] = ms_or_none(ch.get("to"))
    d["history"] = history
    return d

def compute_late_minutes(punch_in: datetime, shift_start: str, date_str: str) -> int:
    h, m = map(int, shift_start.split(":"))
    start = datetime.fromisoformat(date_str).replace(hour=h, minute=m, tzinfo=IST)
    seconds = int((punch_in - start).total_seconds())
    return seconds // 60 if seconds > 600 else 0

def as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

def compute_work_hours(punch_in: datetime, punch_out: datetime) -> float:
    seconds = int((as_utc(punch_out) - as_utc(punch_in)).total_seconds())
    hours = (Decimal(seconds) / Decimal(3600)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return float(hours)

def compute_overtime(punch_out: datetime, shift_start: str, shift_end: str, date_str: str) -> int:
    h, m = map(int, shift_end.split(":"))
    end = datetime.fromisoformat(date_str).replace(hour=h, minute=m, tzinfo=IST)
    if shift_end <= shift_start:
        end += timedelta(days=1)
    minutes = int((as_utc(punch_out) - end).total_seconds() // 60)
    return minutes if minutes >= 30 else 0


# --------------------------------------------------------------------------- #
# Models
# --------------------------------------------------------------------------- #
class EmployeeIn(BaseModel):
    emp_code: str = Field(pattern=r"^EMP\d{4,6}$")
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    department: str = Field(min_length=1, max_length=50)
    shift_start: str = Field(default="09:30", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    shift_end: str = Field(default="18:30", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    joined_on: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")

    @field_validator("joined_on")
    @classmethod
    def joined_on_must_be_real_date(cls, v):
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("joined_on must be a real date (YYYY-MM-DD)")
        return v

class PunchInIn(BaseModel):
    emp_code: str
    punched_at: Optional[StrictInt] = Field(default=None, ge=100000000000, le=4102444800000)
    status: Literal["PRESENT", "WFH", "ON_DUTY"] = "PRESENT"

class PunchOutIn(BaseModel):
    emp_code: str
    punched_at: Optional[StrictInt] = Field(default=None, ge=100000000000, le=4102444800000)

class RegularizeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Optional[Literal["PRESENT", "ABSENT", "LEAVE", "WFH", "ON_DUTY"]] = None
    punch_in: Optional[StrictInt] = Field(default=None, ge=100000000000, le=4102444800000)
    punch_out: Optional[StrictInt] = Field(default=None, ge=100000000000, le=4102444800000)
    reason: str = Field(min_length=5, max_length=200)
    regularized_by: str = Field(min_length=1, max_length=50)

# --------------------------------------------------------------------------- #
# Endpoints provided
# --------------------------------------------------------------------------- #

@app.get("/health")
def health():
    try:
        client.admin.command("ping")
    except Exception:
        raise HTTPException(503, "database unavailable")
    return {"status": "ok"}


@app.post("/employees", status_code=201)
def create_employee(body: EmployeeIn):
    doc = body.model_dump()
    doc["created_at"] = datetime.now(timezone.utc).replace(microsecond=0)
    try:
        db.employees.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "emp_code already exists")
    doc.pop("_id", None)
    doc["created_at"] = to_millis(doc["created_at"])
    return doc

@app.get("/employees")
def list_employees(
    department: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    q = {}
    if department:
        q["department"] = department

    skip = (page - 1) * page_size
    total = db.employees.count_documents(q)

    items = list(
        db.employees.find(q, {"_id": 0})
        .sort("emp_code", 1)
        .skip(skip)
        .limit(page_size)
    )

    for e in items:
        e["created_at"] = to_millis(e["created_at"])

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@app.post("/attendance/punch-in", status_code=201)
def punch_in(body: PunchInIn):
    emp = db.employees.find_one({"emp_code": body.emp_code})
    if not emp:
        raise HTTPException(404, "employee not found")
    if body.punched_at is not None:
        ts = from_millis(body.punched_at)
    else:
        ts = datetime.now(timezone.utc).replace(microsecond=0)
    d = attendance_date(ts, emp["shift_start"], emp["shift_end"])
    doc = {
        "emp_code": body.emp_code,
        "date": d,
        "status": body.status,
        "punch_in": ts,
        "punch_out": None,
        "work_hours": None,
        "late_minutes": compute_late_minutes(ts, emp["shift_start"], d),
        "overtime_minutes": 0,
        "half_day": False,
        "history": [],
    }
    try:
        db.attendance_logs.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(409, "already punched in for this date")
    doc.pop("_id", None)
    doc["punch_in"] = to_millis(doc["punch_in"])
    return doc


@app.post("/attendance/punch-out")
def punch_out(body: PunchOutIn):
    emp = db.employees.find_one({"emp_code": body.emp_code})
    if not emp:
        raise HTTPException(404, "employee not found")
    if body.punched_at is not None:
        ts = from_millis(body.punched_at)
    else:
        ts = datetime.now(timezone.utc).replace(microsecond=0)
    rec = db.attendance_logs.find_one(
        {"emp_code": body.emp_code, "punch_in": {"$lte": ts}},
        sort=[("punch_in", -1)],
    )
    if not rec:
        raise HTTPException(404, "no punch-in found")
    if rec.get("punch_out") is not None:
        raise HTTPException(409, "already punched out")
    pin = as_utc(rec["punch_in"])
    if ts <= pin or ts > pin + timedelta(hours=24):
        raise HTTPException(422, "punched_at must be after punch_in and within 24 hours")
    work_hours = compute_work_hours(pin, ts)
    overtime = compute_overtime(ts, emp["shift_start"], emp["shift_end"], rec["date"])
    updated = db.attendance_logs.find_one_and_update(
        {"_id": rec["_id"], "punch_out": None},
        {"$set": {
            "punch_out": ts,
            "work_hours": work_hours,
            "overtime_minutes": overtime,
            "half_day": work_hours < 4.5,
        }},
        return_document=True,
    )
    if updated is None:
        raise HTTPException(409, "already punched out")
    updated.pop("_id", None)
    updated["punch_in"] = to_millis(updated["punch_in"])
    updated["punch_out"] = to_millis(updated["punch_out"])
    return updated

ATTENDANCE_SORT = [("date", -1), ("emp_code", 1)]


def attendance_filter(emp_code, date_from, date_to, status) -> dict:
    q = {}
    if emp_code:
        q["emp_code"] = emp_code
    if date_from or date_to:
        q["date"] = {}
        if date_from:
            q["date"]["$gte"] = date_from
        if date_to:
            q["date"]["$lte"] = date_to
    if status:
        q["status"] = status
    return q


ATTENDANCE_SORT = [("date", -1), ("emp_code", 1)]


def attendance_filter(emp_code, date_from, date_to, status) -> dict:
    q = {}
    if emp_code:
        q["emp_code"] = emp_code
    if date_from or date_to:
        q["date"] = {}
        if date_from:
            q["date"]["$gte"] = date_from
        if date_to:
            q["date"]["$lte"] = date_to
    if status:
        q["status"] = status
    return q


@app.get("/attendance")
def list_attendance(
    emp_code: Optional[str] = None,
    date_from: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    date_to: Optional[str] = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    status: Optional[Literal["PRESENT", "ABSENT", "LEAVE", "WFH", "ON_DUTY"]] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "date_from must not be after date_to")
    q = attendance_filter(emp_code, date_from, date_to, status)
    total = db.attendance_logs.count_documents(q)
    cursor = (
        db.attendance_logs.find(q, {"_id": 0})
        .sort(ATTENDANCE_SORT)
        .skip((page - 1) * page_size)
        .limit(page_size)
    )
    items = [format_record(d) for d in cursor]
    return {"items": items, "total": total, "page": page, "page_size": page_size}

def same(a, b):
    if isinstance(a, datetime) and isinstance(b, datetime):
        return as_utc(a) == as_utc(b)
    return a == b


@app.patch("/attendance/{emp_code}/{date}")
def regularize(emp_code: str, date: str, body: RegularizeIn):
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(422, "date must be a real date (YYYY-MM-DD)")
    emp = db.employees.find_one({"emp_code": emp_code})
    if not emp:
        raise HTTPException(404, "employee not found")
    rec = db.attendance_logs.find_one({"emp_code": emp_code, "date": date})
    if not rec:
        raise HTTPException(404, "no record for this date")

    old = {
        "status": rec["status"],
        "punch_in": rec.get("punch_in"),
        "punch_out": rec.get("punch_out"),
        "work_hours": rec.get("work_hours"),
        "late_minutes": rec.get("late_minutes", 0),
        "overtime_minutes": rec.get("overtime_minutes", 0),
        "half_day": rec.get("half_day", False),
    }
    new = dict(old)
    if body.status is not None:
        new["status"] = body.status
    if body.punch_in is not None:
        new["punch_in"] = from_millis(body.punch_in)
    if body.punch_out is not None:
        new["punch_out"] = from_millis(body.punch_out)

    if new["status"] in ("ABSENT", "LEAVE"):
        if body.punch_in is not None or body.punch_out is not None:
            raise HTTPException(422, "ABSENT/LEAVE cannot have punch times")
        new.update(punch_in=None, punch_out=None, work_hours=None,
                   late_minutes=0, overtime_minutes=0, half_day=False)
    else:
        if new["punch_in"] is None:
            raise HTTPException(422, "a presence status needs a punch_in")
        pin = as_utc(new["punch_in"])
        if body.punch_in is not None and attendance_date(pin, emp["shift_start"], emp["shift_end"]) != date:
            raise HTTPException(422, "punch_in must stay on the record's attendance date")
        pout = new["punch_out"]
        if pout is not None and (body.punch_in is not None or body.punch_out is not None):
            pout = as_utc(pout)
            if pout <= pin or pout > pin + timedelta(hours=24):
                raise HTTPException(422, "punch_out must be after punch_in and within 24 hours")
        new["late_minutes"] = compute_late_minutes(pin, emp["shift_start"], date)
        if pout is not None:
            new["work_hours"] = compute_work_hours(pin, pout)
            new["overtime_minutes"] = compute_overtime(pout, emp["shift_start"], emp["shift_end"], date)
            new["half_day"] = new["work_hours"] < 4.5
        else:
            new["work_hours"] = None
            new["overtime_minutes"] = 0
            new["half_day"] = False

    changes = {k: {"from": old[k], "to": new[k]} for k in new if not same(old[k], new[k])}
    if not changes:
        raise HTTPException(422, "nothing to change")

    entry = {
        "at": datetime.now(timezone.utc).replace(microsecond=0),
        "by": body.regularized_by,
        "reason": body.reason,
        "changes": changes,
    }
    seen = len(rec.get("history") or [])
    updated = db.attendance_logs.find_one_and_update(
        {"_id": rec["_id"], "$expr": {"$eq": [{"$size": {"$ifNull": ["$history", []]}}, seen]}},
        {"$set": new, "$push": {"history": entry}},
        return_document=True,
    )
    if updated is None:
        raise HTTPException(409, "record was changed by someone else, retry")
    return format_record(updated)

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


def round_half_up(x, places=2) -> float:
    q = Decimal(1).scaleb(-places)
    return float(Decimal(str(x)).quantize(q, rounding=ROUND_HALF_UP))


def weekday_dates(month: str):
    y, m = map(int, month.split("-"))
    day = datetime(y, m, 1)
    out = []
    while day.month == m:
        if day.weekday() < 5:
            out.append(day.strftime("%Y-%m-%d"))
        day += timedelta(days=1)
    return out


def working_days_in_month(month: str, joined_on: str) -> int:
    return sum(1 for d in weekday_dates(month) if d >= joined_on)


def monthly_pipeline(emp_code: str, month: str):
    weekdays = weekday_dates(month)
    return [
        {"$match": {"emp_code": emp_code, "date": {"$gte": f"{month}-01", "$lte": f"{month}-31"}}},
        {"$group": {
            "_id": None,
            "present_days": {"$sum": {"$cond": [
                {"$and": [
                    {"$in": ["$status", ["PRESENT", "WFH", "ON_DUTY"]]},
                    {"$in": ["$date", weekdays]},
                ]},
                {"$cond": [{"$eq": [{"$ifNull": ["$half_day", False]}, True]}, 0.5, 1]},
                0,
            ]}},
            "leave_days": {"$sum": {"$cond": [{"$eq": ["$status", "LEAVE"]}, 1, 0]}},
            "late_count": {"$sum": {"$cond": [{"$gt": [{"$ifNull": ["$late_minutes", 0]}, 0]}, 1, 0]}},
            "total_late_minutes": {"$sum": {"$ifNull": ["$late_minutes", 0]}},
            "total_overtime_minutes": {"$sum": {"$ifNull": ["$overtime_minutes", 0]}},
        }},
    ]


@app.get("/analytics/employees/{emp_code}/monthly")
def employee_monthly(emp_code: str, month: str = Query(pattern=MONTH_PATTERN)):
    emp = db.employees.find_one({"emp_code": emp_code})
    if not emp:
        raise HTTPException(404, "employee not found")
    rows = list(db.attendance_logs.aggregate(monthly_pipeline(emp_code, month)))
    agg = rows[0] if rows else {}
    wd = working_days_in_month(month, emp["joined_on"])
    present = agg.get("present_days", 0)
    pct = None
    if wd > 0:
        pct = round_half_up(Decimal(str(present)) / Decimal(wd) * 100, 2)
    return {
        "emp_code": emp_code,
        "month": month,
        "working_days": wd,
        "present_days": present,
        "leave_days": agg.get("leave_days", 0),
        "late_count": agg.get("late_count", 0),
        "total_late_minutes": agg.get("total_late_minutes", 0),
        "total_overtime_minutes": agg.get("total_overtime_minutes", 0),
        "attendance_pct": pct,
    }

def department_summary_pipeline(month: str, department: Optional[str] = None):
    first, last = f"{month}-01", f"{month}-31"
    weekdays = weekday_dates(month)
    emp_match = {"joined_on": {"$lte": last}}
    if department:
        emp_match["department"] = department
    lookup = {"$lookup": {
        "from": "attendance_logs",
        "localField": "emp_code",
        "foreignField": "emp_code",
        "pipeline": [{"$match": {"date": {"$gte": first, "$lte": last}}}],
        "as": "logs",
    }}
    is_present = {"$in": ["$logs.status", ["PRESENT", "WFH", "ON_DUTY"]]}
    has_hours = {"$and": [is_present, {"$gt": ["$logs.work_hours", None]}]}
    late = {"$ifNull": ["$logs.late_minutes", 0]}
    return [
        {"$match": emp_match},
        lookup,
        {"$unwind": {"path": "$logs", "preserveNullAndEmptyArrays": True}},
        {"$group": {
            "_id": "$department",
            "emps": {"$addToSet": "$emp_code"},
            "present_days": {"$sum": {"$cond": [
                {"$and": [is_present, {"$in": ["$logs.date", weekdays]}]},
                {"$cond": [{"$eq": [{"$ifNull": ["$logs.half_day", False]}, True]}, 0.5, 1]},
                0,
            ]}},
            "hours_sum": {"$sum": {"$cond": [has_hours, "$logs.work_hours", 0]}},
            "hours_n": {"$sum": {"$cond": [has_hours, 1, 0]}},
            "late_count": {"$sum": {"$cond": [{"$gt": [late, 0]}, 1, 0]}},
            "total_late_minutes": {"$sum": late},
            "leave_count": {"$sum": {"$cond": [{"$eq": ["$logs.status", "LEAVE"]}, 1, 0]}},
            "on_duty_count": {"$sum": {"$cond": [{"$eq": ["$logs.status", "ON_DUTY"]}, 1, 0]}},
        }},
        {"$sort": {"_id": 1}},
    ]


@app.get("/analytics/departments/summary")
def department_summary(month: str = Query(pattern=MONTH_PATTERN), department: Optional[str] = None):
    items = []
    for row in db.employees.aggregate(department_summary_pipeline(month, department)):
        n = row["hours_n"]
        avg = None
        if n > 0:
            avg = round_half_up(Decimal(str(round(row["hours_sum"], 2))) / Decimal(n), 2)
        items.append({
            "department": row["_id"],
            "headcount": len(row["emps"]),
            "present_days": row["present_days"],
            "avg_work_hours": avg,
            "late_count": row["late_count"],
            "total_late_minutes": row["total_late_minutes"],
            "leave_count": row["leave_count"],
            "on_duty_count": row["on_duty_count"],
        })
    return {"month": month, "items": items}


def leaderboard_pipeline(month: str, limit: int, department: Optional[str] = None):
    first, last = f"{month}-01", f"{month}-31"
    late = {"$ifNull": ["$late_minutes", 0]}
    pipe = [
        {"$match": {"date": {"$gte": first, "$lte": last}}},
        {"$group": {
            "_id": "$emp_code",
            "total_late_minutes": {"$sum": late},
            "late_count": {"$sum": {"$cond": [{"$gt": [late, 0]}, 1, 0]}},
        }},
        {"$match": {"total_late_minutes": {"$gt": 0}}},
        {"$lookup": {"from": "employees", "localField": "_id", "foreignField": "emp_code", "as": "emp"}},
        {"$unwind": "$emp"},
    ]
    if department:
        pipe.append({"$match": {"emp.department": department}})
    pipe += [
        {"$setWindowFields": {"sortBy": {"total_late_minutes": -1}, "output": {"rank": {"$rank": {}}}}},
        {"$match": {"rank": {"$lte": limit}}},
        {"$sort": {"total_late_minutes": -1, "_id": 1}},
        {"$project": {
            "_id": 0,
            "rank": 1,
            "emp_code": "$_id",
            "name": "$emp.name",
            "department": "$emp.department",
            "total_late_minutes": 1,
            "late_count": 1,
        }},
    ]
    return pipe


@app.get("/analytics/leaderboard/late")
def late_leaderboard(
    month: str = Query(pattern=MONTH_PATTERN),
    limit: int = Query(default=10, ge=1, le=50),
    department: Optional[str] = None,
):
    items = list(db.attendance_logs.aggregate(leaderboard_pipeline(month, limit, department)))
    return {"month": month, "items": items}
# --------------------------------------------------------------------------- #
# TODO - the rest of the contract (see openapi.yaml):
#   POST  /attendance/punch-out
#   PATCH /attendance/{emp_code}/{date}
#   GET   /analytics/employees/{emp_code}/monthly
#   GET   /analytics/departments/summary
#   GET   /analytics/leaderboard/late
#   GET   /analytics/departments/{department}/trend
#   GET   /admin/explain/{endpoint}
# --------------------------------------------------------------------------- #
