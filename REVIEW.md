# REVIEW.md

| # | Where (function / line) | What is wrong | How you'd notice it | How you fixed it |
|---|---|---|---|---|
| 1 | `list_employees`, `skip` | `page * page_size` galat tha, page 1 par pehle 20 employees chhod deta tha | `?page=1` par `items` khaali aata tha jabki `total: 6` | `(page - 1) * page_size` kiya |
| 2 | `list_employees`, `total` | `count_documents({})` filter ke bina gin raha tha | `?department=Sales` par `total: 6` aata tha | `count_documents(q)` kiya |
| 3 | `list_employees`, `created_at` | Time text mein ja raha tha, contract epoch milliseconds (integer) maangta hai | Response mein `"2026-02-01T04:30:00"` dikha | `to_millis()` helper banaya aur har item par lagaya |
| 4 | `create_employee`, `created_at` | `datetime.now()` local time deta hai (naive), aur response mein time text ban ke jaata tha | Response mein `created_at` string tha | `datetime.now(timezone.utc)` kiya aur response mein `to_millis()` lagaya |
| 5 | `EmployeeIn` model | Koi validation nahi tha, `"string"` jaisi values bhi accept hoti thi | `emp_code: "string"` par bhi `201` mila | Pydantic `Field(pattern=...)` se contract ke rules lagaye |
| 6 | `compute_late_minutes` | Time ko IST mein nahi badalta; 09:40:01 par 10 minute aate hain par `> 10` check isse late nahi maanta; raat ki shift ka din bhi galat | 09:40:01 par `late_minutes` 0 aata, contract kehta hai 10 | IST mein badla, seconds mein gina (`> 600`), minutes floor kiye, shift ki date se start nikala |
| 7 | `punch_in`, time conversion | `datetime.fromtimestamp(ms / 1000)` laptop ke local timezone mein badalta hai aur milliseconds nahi hatata | Alag timezone wale server par same request alag time deti | `from_millis()` se UTC mein, poore seconds tak |
| 8 | `punch_in`, `date` | `ts.date()` IST ka din nahi deta; raat ki shift (22:00-06:00) ka din bhi galat | Raat 01:30 IST ke punch-in ka din galat aata | `attendance_date()` helper (R1) |
| 9 | `punch_in`, unknown employee | `find_one` ka `None` seedha `emp["shift_start"]` par use hota hai | `emp_code: "EMP9999"` par 500 crash | `404` raise kiya |
| 10 | `PunchInIn.status` | Koi bhi string accept hoti thi (`ABSENT` bhi) | `status: "ABSENT"` par `201` mila | `Literal["PRESENT", "WFH", "ON_DUTY"]` |
| 11 | `PunchInIn.punched_at` | Seconds, float jaisi koi bhi value accept hoti thi | `punched_at: 12345` par `201` mila | `StrictInt` aur `ge`/`le` limits |
| 12 | `punch_in`, duplicate check | `find_one` phir `insert_one` (check-then-insert) race hai, aur koi unique index nahi | Do saath requests dono `201` paati | Unique index `(emp_code, date)` startup par, `DuplicateKeyError` par `409` |
| 13 | `punch_in`, response | Response mein extra `id`, aur `punch_in` raw datetime tha | Response mein `"id"` aur datetime text | `_id` hataya, `punch_in` ko `to_millis()` se number kiya |
| 14 | `create_employee`, duplicate check | `find_one` phir `insert_one` race hai, aur `emp_code` par unique index nahi | Do saath requests dono `201` paati | Unique index `emp_code` par, `DuplicateKeyError` par `409` |
| 15 | `EmployeeIn.joined_on` | Sirf `dddd-dd-dd` pattern dekhta tha, impossible date bhi chalti thi | `joined_on: "1752-89-20"` par `201` mila | `field_validator` jo `strptime` se asli date check karta hai |

## Not a defect
- `GET /` aur `/favicon.ico` par 404: in routes ki zaroorat hi nahi hai, isliye ye sahi hai.