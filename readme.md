# LTTS Solution Maturity Self-Assessment

A rule-based web application that classifies a software solution as **PoC**, **MVP**, or **Enterprise-Grade** based on a structured, evidence-driven questionnaire. Assessments are stored centrally in PostgreSQL and managed through a project portfolio view.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Frontend** | Single-page HTML + vanilla JavaScript + CSS (no framework, no build step) |
| **Backend** | Python 3.8+, Flask |
| **Database** | PostgreSQL (JSONB for answer storage) |
| **DB Driver** | psycopg2 |
| **WSGI Server** | Gunicorn (production) |
| **Hosting** | Render (Web Service + Managed PostgreSQL) |

---

## Architecture

```
  Browser (index.html)          Flask (server.py)            PostgreSQL
 ┌──────────────────┐         ┌───────────────────┐        ┌──────────────┐
 │ Projects tab     │  HTTP   │ /            (UI)  │  SQL   │ assessments  │
 │ Assessment tab   │ ──────► │ /save  /list       │ ─────► │  id          │
 │ Result tab       │  JSON   │ /get   /result     │        │  name/owner  │
 │ scoring engine   │ ◄────── │ /delete            │ ◄───── │  scope       │
 │ (client-side)    │         │  init_db()         │        │  answers JSONB│
 └──────────────────┘         └───────────────────┘        │  result      │
                                                            └──────────────┘
```

- **Single web service** serves both the static UI and the JSON API (same origin → no CORS).
- **Classification logic runs client-side**; the server only persists records and the computed result.
- **Answers stored as JSONB**, enabling flexible schema-free storage of all questionnaire responses.

---

## API Endpoints

| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/` | Serve the application UI |
| GET | `/list` | List all saved assessments |
| GET | `/get/<id>` | Fetch a single assessment |
| POST | `/save` | Insert new, or update when `id` supplied |
| POST | `/result/<id>` | Persist computed classification |
| POST | `/delete/<id>` | Delete a record |

---

## Data Model

```sql
CREATE TABLE assessments (
    id       SERIAL PRIMARY KEY,
    name     TEXT,          -- solution name
    owner    TEXT,          -- assessor / team
    scope    TEXT,          -- assessment scope
    answers  JSONB,         -- {questionId: Yes|Partly|No}
    result   TEXT,          -- PoC | MVP | Enterprise-Grade (empty until run)
    created  TIMESTAMP DEFAULT NOW(),
    updated  TIMESTAMP DEFAULT NOW()
);
```

---

## Classification Rules

| Class | Rule |
|-------|------|
| **PoC** | Feasibility evidence exists; one or more MVP gates unmet |
| **MVP** | All MVP gates pass (bounded workflow, real users, real data, measured value, controlled ops) |
| **Enterprise-Grade** | All MVP gates + all critical enterprise controls = Yes + every enterprise control ≥ Partly + enterprise readiness ≥ 85% |

Mandatory gates override average scores.

---

## Application Flow

1. **Projects** – lists all saved solutions; **+ Add New Solution** opens a blank form.
2. **Assessment** – all fields + every Yes/Partly/No are mandatory; nothing is saved unless complete.
3. A saved project with an **empty result** can be **Edited** or **Run**.
4. **Run assessment** computes the class, shows it in **Result**, and locks Edit/Run for that row.

---

## Local Setup (pgAdmin)

```bash
# 1. Install dependencies (one-time)
pip install -r requirements.txt

# 2. Create a database named "maturity" in pgAdmin

# 3. Configure connection (local Postgres has SSL off)
export DATABASE_URL="postgresql://postgres:PASSWORD@localhost:5432/maturity"
export PGSSLMODE="disable"        # Windows: $env:PGSSLMODE="disable"

# 4. Run
python server.py
```

Open **http://localhost:5000** — the `assessments` table auto-creates on first launch.

---

## Deployment (Render)

1. Push repo to GitHub.
2. Render → **New → Blueprint** → select repo → **Apply**.
3. `render.yaml` provisions the Web Service + free PostgreSQL and auto-injects `DATABASE_URL`.

> Do **not** set `PGSSLMODE=disable` on Render — cloud Postgres requires SSL (code defaults to `require`).

---

## Project Structure

```
solQualificationFwk/
├── server.py            # Flask backend + API
├── requirements.txt     # flask, gunicorn, psycopg2-binary
├── render.yaml          # Render blueprint (web + Postgres)
├── .env.example         # local env template
└── static/
    └── index.html       # full SPA (UI + scoring engine)
```

---

## Notes

- **Free Render Postgres expires (~30 days)** — schedule regular `pg_dump` backups.
- **Free web service cold-starts** (~30–50s) after idle.
- Keep to **a single instance** for consistent writes.
