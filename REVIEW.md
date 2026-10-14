# REVIEW.md

| # | Where (function / line) | What is wrong | How you'd notice it | How you fixed it |
|---|---|---|---|---|
| 1 | `list_employees`, `skip` | `page * page_size` galat tha, page 1 par pehle 20 employees chhod deta tha | `?page=1` par `items` khaali aata tha jabki `total: 6` | `(page - 1) * page_size` kiya |
| 2 | `list_employees`, `total` | `count_documents({})` filter ke bina gin raha tha | `?department=Sales` par `total: 6` aata tha | `count_documents(q)` kiya |
| 3 | `list_employees`, `created_at` | Time text mein ja raha tha, contract epoch milliseconds (integer) maangta hai | Response mein `"2026-02-01T04:30:00"` dikha | `to_millis()` helper banaya aur har item par lagaya |
| 4 | `create_employee`, `created_at` | `datetime.now()` local time deta hai (naive), aur response mein time text ban ke jaata tha | Response mein `created_at` string tha | `datetime.now(timezone.utc)` kiya aur response mein `to_millis()` lagaya |
| 5 | `EmployeeIn` model | Koi validation nahi tha, `"string"` jaisi values bhi accept hoti thi | `emp_code: "string"` par bhi `201` mila | Pydantic `Field(pattern=...)` se contract ke rules lagaye |

## Not a defect
- `GET /` aur `/favicon.ico` par 404: in routes ki zaroorat hi nahi hai, isliye ye sahi hai.