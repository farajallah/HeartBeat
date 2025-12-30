### Project Name

**Lightweight Time Attendance & Balance Tracker**

---

## Goal

Generate a **complete, runnable, lightweight full-stack application** with:

1. A **local heartbeat agent** that logs work time every minute
2. A **FastAPI web server** that:

   * Stores raw heartbeats
   * Calculates worked time, expected time, and balance
   * Provides a small web UI for dashboard, settings, and corrections

The system must be **simple, deterministic, and easy to maintain**.

---

## Mandatory Stack

### Backend

* Python **3.11+**
* FastAPI
* Uvicorn
* SQLite (single DB file)
* SQLAlchemy or SQLModel
* Jinja2 templates

### Frontend

* Server-rendered HTML
* **HTMX** for interactivity
* **Chart.js** for graphs
* Minimal CSS (no heavy framework)

### Local Agent

* Python script
* Uses `requests`
* Triggered every minute (OS scheduler, not daemon logic)

---

## Core Design Rules (STRICT)

1. **All recorded minutes are valid**

   * No working-hour windows
   * Weekends and holidays are allowed work time

2. **Raw heartbeats are immutable**

   * Never modified or deleted

3. **Corrections override derived values**

   * Corrections do not alter raw data

4. **Expected minutes are policy-based only**

   * Used only to calculate balance
   * Never restrict logging

---

## Database Schema (CREATE EXACTLY)

### `heartbeat`

```sql
id INTEGER PRIMARY KEY AUTOINCREMENT
device_id TEXT NOT NULL
ts DATETIME DEFAULT CURRENT_TIMESTAMP
```

---

### `daily_attendance` (derived / cached)

```sql
date DATE PRIMARY KEY
recorded_minutes INTEGER NOT NULL
```

---

### `correction`

```sql
date DATE PRIMARY KEY
corrected_minutes INTEGER NOT NULL
reason TEXT
```

---

### `settings` (single row only)

```sql
id INTEGER PRIMARY KEY CHECK (id = 1)
start_date DATE
end_date DATE
working_days TEXT
daily_required_minutes INTEGER
```

---

### `holiday`

```sql
date DATE PRIMARY KEY
description TEXT
```

---

## Attendance Calculation Logic (MUST IMPLEMENT)

### Recorded Minutes

* Each heartbeat = **1 minute**
* All heartbeats count
* Heartbeats ≤ 2 minutes apart are continuous
* Aggregate per **calendar date**

---

### Effective Worked Minutes (per date)

```
effective_minutes =
    correction.corrected_minutes
    OR daily_attendance.recorded_minutes
```

---

### Required Minutes (per date)

| Condition                | Required               |
| ------------------------ | ---------------------- |
| Outside reporting period | 0                      |
| Holiday                  | 0                      |
| Non-working day          | 0                      |
| Working day              | daily_required_minutes |

---

### Daily Balance

```
daily_balance = effective_minutes - required_minutes
```

---

## Web Pages (MUST IMPLEMENT)

### 0️⃣ Dashboard (`/dashboard`)

* Large centered **TOTAL BALANCE**
* Monthly table:

  * Month
  * Worked hours
  * Required hours
  * Balance
* Monthly bar chart (worked vs required)

---

### 1️⃣ Settings (`/settings`)

Form fields:

* Start date
* End date
* Working days (checkboxes)
* Daily required hours
* Holidays list (add/remove)

Changing settings must **recalculate derived attendance**.

---

### 2️⃣ Corrections (`/corrections`)

* Table or calendar view
* One row per date:

  * Recorded minutes
  * Required minutes
  * Editable corrected minutes
* HTMX-based updates

---

## API Endpoints (REQUIRED)

### Heartbeat

```
POST /api/heartbeat
```

Payload:

```json
{ "device_id": "laptop-01" }
```

---

### Settings

```
GET /settings
POST /settings
```

---

### Holidays

```
GET /holidays
POST /holidays
DELETE /holidays/{date}
```

---

### Corrections

```
GET /corrections
POST /corrections
```

---

## Security (MINIMAL)

* Static Bearer token
* Header:

```
Authorization: Bearer <TOKEN>
```

---

## Local Agent (MUST INCLUDE)

Create a Python script:

* Sends POST request to `/api/heartbeat`
* Runs every 60 seconds
* Includes device_id and token
* Silent failure if offline

---

## Required Project Structure

Generate the full project with this layout:

```
app/
 ├── main.py
 ├── database.py
 ├── models.py
 ├── services/
 │    ├── attendance.py
 │    ├── statistics.py
 ├── templates/
 │    ├── dashboard.html
 │    ├── settings.html
 │    ├── corrections.html
 ├── static/
 │    └── charts.js
 └── agent/
      └── heartbeat.py
```

---

## Windsurf-Specific Instructions

* Generate **all files**
* Include database initialization
* Include sample `.env` values
* Code must run with:

```bash
uvicorn app.main:app --reload
```

* Avoid unnecessary abstractions
* Prefer explicit logic over cleverness
* Comment important logic clearly

---

## Final Instruction

> Generate a **fully working application** that strictly follows this specification.
> Do not ask clarification questions.
> Prioritize correctness, simplicity, and readability.
