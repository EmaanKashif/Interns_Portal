# Intern Management Portal — Phase 1 (Sample MVP)

Django + PostgreSQL. This is a **sample starter project** built from your
spec, since no existing codebase was available to extend. It implements
Phase 1 only: authentication, roles, intern onboarding, the department →
week → topic → task hierarchy, and basic intern/supervisor dashboards.
Phases 2 (attendance, submissions, feedback, evaluations, daily log) and
3 (analytics, reports, PDF export) are not built yet — see "Roadmap" below
for how they plug into this structure.

## Project layout

```
intern_portal/
    intern_portal/       # project settings, root urls
    accounts/             # User, SupervisorProfile, InternProfile, activation, login
    academics/            # Department, InternshipWeek, Topic, DailyTask
    dashboard/            # intern_dashboard, supervisor_dashboard, role router
    templates/
        accounts/          # login.html, activate.html
        dashboard/          # intern_dashboard.html, supervisor_dashboard.html
        base.html
    requirements.txt
```

## Why this structure

- **`accounts`** owns *who* someone is (User with a `role`, plus the
  Intern/Supervisor profile tables and the activation flow). Keeping
  auth/roles in one app makes it the single place permission logic lives.
- **`academics`** owns *what an intern is learning* — the
  Department → Week → Topic → DailyTask chain from your spec. It's separate
  from `accounts` so new departments/weeks/tasks can be added without
  touching auth code at all.
- **`dashboard`** only *reads* data from the other two apps and renders it.
  It has no models of its own — this keeps it easy to extend in Phase 2/3
  without dashboard logic leaking into the data-owning apps.

## Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Database

Runs on **SQLite by default** — zero setup, good for development:

```bash
python manage.py migrate
```

To use **PostgreSQL** (matches your production target), create a database
and set these environment variables before running `migrate`:

```bash
export DB_ENGINE=postgres
export DB_NAME=intern_portal
export DB_USER=postgres
export DB_PASSWORD=yourpassword
export DB_HOST=localhost
export DB_PORT=5432

python manage.py migrate
```

(On Windows, use `set VAR=value` instead of `export`.)

### Create an admin account

```bash
python manage.py createsuperuser
```
When prompted for role-related fields, log into `/admin/` afterward and set
`role = admin` on that user (the createsuperuser prompt doesn't ask for it).

### Run the server

```bash
python manage.py runserver
```

## How to test each feature

**1. Admin/Supervisor creates an intern record**
Go to `http://127.0.0.1:8000/admin/`, log in as your superuser.
- Under **Users**, add a new user with `role = supervisor`, then under
  **Supervisor profiles**, create a profile linked to that user.
- Under **Intern profiles**, click "Add", fill in name/university/degree/
  dates/supervisor, and save. Django auto-generates the **Intern ID**
  (e.g. `INT-2026-0001`) — it appears once you save.

**2. Intern activates their account**
Visit `http://127.0.0.1:8000/accounts/activate/`, enter that Intern ID,
a real email, and a password. On success you're logged straight into the
intern dashboard. Try an already-used or fake Intern ID — it's rejected.

**3. Build a schedule for that intern**
In `/admin/`, add a **Department** (e.g. "ERP"), then an **Internship
week** (pick the intern, department, week number 1, dates). Inside that
week's edit page you can add **Topics** inline, and inside a topic's own
edit page you can add **Daily tasks** inline (mark one `completed` to see
progress change).

**4. Intern dashboard**
Log in as the intern (`/accounts/login/`) — you'll see their current week,
that week's tasks, and a completed/total progress bar.

**5. Supervisor dashboard**
Log in as the supervisor — you'll see only the interns assigned to them,
with a progress column for each.

**6. Permission checks**
Try visiting `/supervisor/` while logged in as an intern (or vice versa) —
you should get a `403 Forbidden`. This is enforced in the view itself
(`accounts/decorators.py`), not just hidden in the template.

## Roadmap — how Phase 2/3 attach to this

- **Attendance / Leave** → new `attendance` app, `Attendance` model FK'd to
  `InternProfile` with a `unique_together = ('intern', 'date')` constraint
  to block duplicates.
- **Submission Vault** → new `submissions` app, `Submission` model FK'd to
  `DailyTask` + `InternProfile`, with a `status` field
  (Pending/Submitted/Reviewed/Revision Required) and a `FileField` with
  extension/size validation.
- **Feedback / Evaluations** → new `evaluations` app, `Evaluation` model
  FK'd to `InternProfile` + the `SupervisorProfile` who wrote it, read-only
  to interns (no update view exposed to the `intern` role).
- **Daily Learning Log** → small model FK'd to `InternProfile` + date;
  feeds directly into Phase 3 reports.
- **Progress Dashboard / Reports** → aggregation queries over the models
  above (mostly `Count`/`Avg` annotations), rendered as charts, then
  exported via `weasyprint` or `reportlab` for PDF.
- **Calendar** → a view that merges `InternshipWeek` dates, `DailyTask`
  due dates, and (once built) evaluation/submission deadlines into one
  feed — no new "calendar" model needed, it's a read-only aggregation.

Each of these follows the same pattern already in place: a model FK'd to
`InternProfile` and/or `SupervisorProfile`, a role-checked view using
`@role_required(...)`, and a template extending `base.html`.
