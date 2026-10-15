## 1. Indexes

I use a unique `emp_code` index to prevent duplicate employees, a unique `(emp_code, date)` index to prevent duplicate daily attendance, `(date DESC, emp_code ASC)` for attendance sorting, and `(department, emp_code)` for department filtering. I rejected a `status` index because it has only 5 values, so it offers little benefit and adds write cost.I also use (joined_on, department) to support the month-end headcount filter.

## 2. Race Condition

A `find_one` check before insert is not safe, because both requests can pass it. The unique `(emp_code, date)` index allows only one insert. The other raises `DuplicateKeyError`, which the API handles with `409 Conflict`.

## 3. Ranking Ties

Ranking is calculated before filtering with `rank <= limit`. Employees with equal values receive the same rank, so the response may contain more rows than the requested limit. Example: ranks 1, 2, 2, 4 with `limit=2` returns 3 rows.

## 4. Headcount

The pipeline starts from `employees` and uses `$lookup` to join attendance records. `$unwind` with `preserveNullAndEmptyArrays: true` retains employees without logs. `$addToSet` collects unique employee codes. Only employees with `joined_on` on or before month end are counted.

## 5. Scaling

For 100x more data, I would maintain monthly summaries in a separate collection. This reduces repeated aggregation over large attendance datasets. Every punch-in, punch-out and correction would also have to update the summary.