# REVIEW.md

Defects found in the starter `app/main.py`, and how each one was fixed.

| # | Where (function / line) | What is wrong | How you'd notice it | How I fixed it |
|---|---|---|---|---|
| 1 | `list_employees`, `skip` | `skip = page * page_size` skips the first page of results. | `?page=1` returns an empty `items` list while `total` is 6. | `skip = (page - 1) * page_size`. |
| 2 | `list_employees`, `total` | `count_documents({})` ignores the department filter. | `?department=Sales` returns `total: 6` instead of 2. | `count_documents(q)`. |
| 3 | `list_employees`, `created_at` | Returned as an ISO string; the contract requires epoch milliseconds (integer). | Response shows `"2026-02-01T04:30:00"`. | Added `to_millis()` and applied it to every item. |
| 4 | `create_employee`, `created_at` | `datetime.now()` is naive local time, and the response returns it as text. | `created_at` is a string and the stored time is off by the server's UTC offset. | `datetime.now(timezone.utc)` and `to_millis()` in the response. |
| 5 | `EmployeeIn` | No validation at all: `"string"` is accepted as `emp_code`, email, date. | `emp_code: "string"` returns 201. | Pydantic `Field(pattern=...)` with the contract's rules. |
| 6 | `compute_late_minutes` | Not converted to IST; `> 10` on integer minutes misses 09:40:01; overnight shifts use the wrong day. | 09:40:01 gives `late_minutes: 0`; the contract expects 10. | Convert to IST, count in seconds (`> 600`), floor to minutes, start from the attendance date. |
| 7 | `punch_in`, time conversion | `datetime.fromtimestamp(ms / 1000)` uses the server's local time zone and keeps fractions of a second. | Same request gives a different time on a server in another time zone. | `from_millis()`: UTC, whole seconds only (R1). |
| 8 | `punch_in`, `date` | `ts.date()` is not the IST day; wrong for overnight shifts. | A 01:30 IST punch-in gets the wrong date. | `attendance_date()` helper (R1). |
| 9 | `punch_in`, unknown employee | `find_one` returns `None`, then `emp["shift_start"]` crashes. | `emp_code: "EMP9999"` returns 500. | Return 404. |
| 10 | `PunchInIn.status` | Any string accepted, including `ABSENT`. | `status: "ABSENT"` returns 201. | `Literal["PRESENT", "WFH", "ON_DUTY"]`. |
| 11 | `PunchInIn.punched_at` | Seconds-looking values, floats and strings accepted. | `punched_at: 12345` returns 201. | `StrictInt` with `ge` / `le` limits. |
| 12 | `punch_in`, duplicate check | Check-then-insert is a race, and there is no unique index. | Two simultaneous punch-ins both return 201. | Unique index on `(emp_code, date)` created at startup; `DuplicateKeyError` returns 409. |
| 13 | `punch_in`, response | Extra `id` field; `punch_in` returned as a raw datetime. | Response contains `"id"` and a datetime string. | Removed `_id`; `punch_in` converted with `to_millis()`. |
| 14 | `create_employee`, duplicate check | Check-then-insert is a race; no unique index on `emp_code`. | Two simultaneous requests both return 201. | Unique index on `emp_code`; `DuplicateKeyError` returns 409. |
| 15 | `EmployeeIn.joined_on` | Only checks the shape `dddd-dd-dd`, so impossible dates pass. | `joined_on: "1752-89-20"` returns 201. | `field_validator` using `datetime.strptime` to require a real date. |
| 16 | `compute_work_hours` | Python's `round()` is not half-up, but R4 requires half-up. | 4050 seconds (1.125 h) gives `1.12`, expected `1.13`. | `Decimal` with `ROUND_HALF_UP`, computed from whole seconds. |
| 17 | `compute_overtime` | No 30-minute minimum; wrong shift end for overnight shifts. | Leaving 5 minutes after shift end gives `5`, expected `0`. | Added the 30-minute threshold; for overnight shifts the end is on the next day. |
| 18 | `list_attendance`, sorting and paging | Loads the whole collection into memory and sorts in Python; no `emp_code` tie-break. | Slow on ~100,000 records; order of same-date records is undefined. | Sort in MongoDB by `date` desc, `emp_code` asc, with `skip` / `limit` and a `(date, emp_code)` index. |
| 19 | `list_attendance`, validation | `page=0`, huge `page_size`, bad `status`, bad dates and `date_from > date_to` are accepted. | `?status=XYZ` returns 200; `?page=0` gives a negative skip. | `Query(ge=..., le=...)`, `Literal` status, date pattern, 422 when `date_from > date_to`. |
| 20 | `list_attendance`, response shape | Extra `id`, raw datetimes, and legacy records miss `history`, `half_day`, `late_minutes`. | Response has `"id"` and datetime strings; older records lack fields. | `format_record()` removes `_id`, converts times to milliseconds and fills defaults. |

## Not a defect

- `GET /` and `/favicon.ico` return 404: the contract does not define these routes, so 404 is correct.
- `load_dotenv()` does not override real environment variables by default, so `MONGO_URI` / `MONGO_DB` from the environment still take priority over a local `.env`.