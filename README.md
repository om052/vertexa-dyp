# CodeQuest AI

CodeQuest AI is being developed as a coding-learning platform with an
image-based Buddy mentor. This repository contains the Flask and SQLite foundations, starter curriculum,
and a responsive curriculum-browsing website. It is not the finished platform.

## Requirements

- Python 3.10 or newer
- pip

Python packages are listed in `requirements.txt`:

- Flask: web application and CLI.
- python-dotenv: loads local `.env` settings for Flask commands.
- Flask-SQLAlchemy and SQLAlchemy: database models, queries, and request-scoped
  sessions.
- Flask-Migrate and Alembic: versioned, reviewable database schema migrations.
- Flask-WTF: global CSRF protection for state-changing forms.

## Set up locally

In PowerShell, from the project directory:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

The `.venv` environment is already present in this workspace. For a fresh
checkout only, create it first with `py -3.12 -m venv .venv`. Copy
`.env.example` to `.env` if you need local environment settings:

```powershell
Copy-Item .env.example .env
```

The checked-in migrations already describe the initial schema. Apply them to
create the local database:

```powershell
python -m flask --app app:create_app db upgrade
```

The default development database is `instance/codequest.sqlite3`. You can
change its location with `CODEQUEST_DATABASE_PATH` in `.env`. Relative paths
are resolved from the project directory; absolute paths are also accepted.
Application startup prepares the parent directory but does not create tables
or run migrations. The database file is created when a migration is applied.

For production configuration, set `CODEQUEST_ENV=production`, provide a
`CODEQUEST_SECRET_KEY`, and set `CODEQUEST_DATABASE_PATH` to an explicit
absolute path. Production startup fails rather than silently choosing a
database path. Never commit a real `.env` file or secret.

## Run

```powershell
python -m flask --app app:create_app run --debug
```

Open <http://127.0.0.1:5000/> for the learning dashboard,
<http://127.0.0.1:5000/health> for the lightweight JSON liveness check. The
health endpoint does not query the database.

## Curriculum website

The current website includes a dashboard (`/`), a learning-path directory
(`/learn`), language roadmaps (`/learn/<language>`), topic pages, lesson pages,
registration (`/auth/register`), login (`/auth/login`), a private learner
profile (`/account/profile`), profile settings (`/account/settings`), and a
POST-only logout (`/auth/logout`). Public curriculum remains available without
an account. If the database has no seeded catalog, learning pages show an
empty state; browsing never seeds or changes curriculum data. Buddy is shown
only as a clearly marked future feature. Saved lesson progress, interactive
coding, AI assistance, games, and XP are not implemented.

The interface uses server-rendered Flask templates with plain HTML, CSS, and
JavaScript. API-provided lesson text and code examples are inserted as text,
not interpreted as HTML. The frontend has loading, empty, and request-error
states and adapts to narrow screens. Account pages use the same responsive
layouts, including an accessible expandable mobile navigation menu. Form
submission and validation run on Flask, so registration and account editing do
not depend on JavaScript.

The responsive layouts were checked in browser emulation at 320, 375, 390, 430,
768, 1024, 1366, and 1920 CSS pixels. These checks are not physical-device
tests.

## Schema changes

After changing a model, create and review a migration:

```powershell
python -m flask --app app:create_app db migrate -m "describe the schema change"
```

If Alembic reports that there are no changes, no migration file is needed.
Review generated files in `migrations/versions/`, then apply the migration:

```powershell
python -m flask --app app:create_app db upgrade
```

Commit reviewed migration files with their model changes. Do not use
`db.create_all()` or manually rebuild a database instead of migrations.
Migrations do not seed learner or course records. Back up important data before
applying schema changes; avoid downgrading a database without first considering
whether the migration removes data. The SQLite migration environment temporarily
disables foreign-key enforcement during Alembic operations that rebuild tables,
then runs `PRAGMA foreign_key_check` before re-enabling it. Normal application
connections always enable foreign keys.

## Test

```powershell
python -m unittest discover -s tests -v
```

Tests create temporary SQLite files, apply the same migrations as the
application, and remove the files afterward. They do not use the development
database.

## Database design

Flask-SQLAlchemy manages a single SQLAlchemy engine and application-context
scoped sessions. The models provide:
Flask-WTF protects state-changing forms from cross-site request forgery (CSRF);
templates include tokens and the server rejects missing or invalid tokens. The models provide:

- `User`: generated UUID identifier and UTC creation/update timestamps; no
  plaintext credentials; normalized, unique username and email fields plus a
  Werkzeug password hash. Credential columns remain nullable solely to
  preserve legacy user rows that predate registration.
- `LearnerProfile`: optional display name, short bio, and preferred language,
  separate from the stable user identity. Registration creates the user and
  profile atomically; users without profiles can still view their account and
  have one recreated on their next valid settings update.
- `Language`, `Topic`, and `Lesson`: normalized learning content with stable
  language codes, per-parent unique slugs, ordered lessons, and content stored
  independently of frontend presentation.
- `LearningProgress`: per-user, per-lesson status only. New records begin as
  `not_started`; there are no XP points, scores, or invented completion data.

Foreign keys are enabled on every SQLite connection. User-owned profile and
progress records are removed with their user; referenced learning content
cannot be deleted while topics, lessons, or progress depend on it. A removed
preferred language is cleared from profiles. Migration
`a81f2d7c9b44` adds account fields as nullable columns, preserving existing
users and profiles while enforcing uniqueness for new non-null usernames and
emails.

## Accounts and security

Registration accepts a username (3–30 letters, digits, or underscores), email,
and matching password fields. Usernames are lowercased and emails are
case-folded before storage, and both have database uniqueness constraints.
Passwords must be 12–128 characters and are stored as Werkzeug password
hashes; plaintext passwords are never stored. Registration creates the user
and learner profile in one database transaction and deliberately does not log
the new user in.

Login accepts username or email and returns the same error for an unknown
account and an incorrect password. Successful login clears previous session
contents before saving only the user ID and a permanence flag. Flask's default
signed-cookie session is retained: its contents are integrity-protected, not
encrypted, so the app stores no passwords, email, or profile data in the
session. Cookies are `HttpOnly` and `SameSite=Lax`; `Secure` is enabled in
production. Sessions expire after 12 hours. In development, if no secret is
configured, a random process-local signing key is generated; this makes
sessions invalid after restart. Set `CODEQUEST_SECRET_KEY` in `.env` to a
private random value for stable local sessions. Production requires an
explicit `CODEQUEST_SECRET_KEY` and never generates a fallback.

CSRF tokens are required on registration, login, profile updates, and logout.
Logout is POST-only. Login's optional `next` destination is restricted to safe
local paths; external, protocol-relative, control-character, and encoded
backslash destinations are rejected. Account and profile routes are private;
profile updates operate on the authenticated account rather than accepting a
user ID from the browser.

No brute-force protection or rate limiting is implemented. Before public
deployment, add and test rate limiting, enforce HTTPS end-to-end, keep the
production key private, and review proxy/cookie configuration. Email
verification, password reset, two-factor authentication, social login, and
account deletion are deferred; no email or verification badge is fabricated.

## Starter curriculum

The initial catalog provides beginner-oriented, original starter material for
Python, JavaScript, C, and C++. Each language has ten ordered topics and one
lesson in each topic (40 lessons total). It covers getting started, first
output, variables and types, input/output, operators, conditionals, loops,
functions, language-specific collections and strings, and debugging.

Seed the catalog after applying migrations:

```powershell
python -m flask --app app:create_app seed-curriculum
```

The command creates missing records in a transaction. It uses language codes
and parent-scoped topic/lesson slugs as stable keys. Repeating the command does
not add duplicates. If an existing record with a catalog key has different
seeded content, the command fails and rolls back instead of silently
overwriting it. Edit the catalog in `app/curriculum_data.py`; review and test
those edits before seeding. This initial seed policy intentionally does not
provide automatic content updates or deletion.

Lessons can reference an earlier lesson as a prerequisite. The seed validator
checks that every prerequisite exists, appears earlier in its language's
sequence, and forms no cycles. The database stores these references in the
`lesson_prerequisites` association table. There is not yet a learner-unlocking
engine.

## Read-only curriculum API

The JSON endpoints read persisted catalog records and do not expose user
profiles or progress:

- `GET /api/languages` — languages in configured order.
- `GET /api/languages/python` — one language and its ordered topics.
- `GET /api/languages/python/topics/variables-and-types` — a topic and its
  ordered lessons, including prerequisite slugs.
- `GET /api/languages/python/topics/variables-and-types/lessons/variables-and-types`
  — a single lesson.

Example:

```powershell
curl.exe http://127.0.0.1:5000/api/languages
```

Example response:

```json
{
  "languages": [
    {
      "slug": "python",
      "name": "Python",
      "description": "A gentle path from your first Python program to functions, collections, and debugging.",
      "topic_count": 10,
      "lesson_count": 10
    },
    {
      "slug": "javascript",
      "name": "JavaScript",
      "description": "A beginner path through JavaScript values, browser output, control flow, functions, arrays, and debugging.",
      "topic_count": 10,
      "lesson_count": 10
    },
    {
      "slug": "c",
      "name": "C",
      "description": "A beginner path through compiling C programs, typed values, input, control flow, functions, arrays, and debugging.",
      "topic_count": 10,
      "lesson_count": 10
    },
    {
      "slug": "cpp",
      "name": "C++",
      "description": "A beginner path through compiling C++, typed values, console input, control flow, functions, vectors, and debugging.",
      "topic_count": 10,
      "lesson_count": 10
    }
  ]
}
```

Unknown or malformed language, topic, and lesson slugs return HTTP 404 with a
consistent JSON error. Ordering uses explicit positions and stable IDs/slugs
for ties.

To add a language, topic, or lesson, add a validated entry to
`app/curriculum_data.py`, include any prerequisites using `(topic_slug,
lesson_slug)` pairs, run the tests, apply any model migration if the schema
changes, then run `seed-curriculum`. Never edit the database by deleting and
recreating it as a way to refresh catalog data. Existing content conflicts are
reported; they are not overwritten by the seed command.

## Backups and SQLite limitations

No automated backup or restore facility is implemented or verified. For a
small local project, stop the application before copying the database file and
store the copy somewhere private and separate from this workspace. Test a
restore procedure before relying on a backup.

SQLite is a good fit for local development and an initial single-instance
deployment, but it permits only one writer at a time and can encounter lock
contention under concurrent writes. It is not configured here for a
multi-instance deployment; reassess the database before scaling concurrent
writers. This foundation is not a production-readiness claim.

## Project structure

- `app/`: factory, configuration, extensions, models, auth/account and catalog
  routes, services, templates, and static frontend assets.
- `migrations/`: Alembic environment and versioned schema migrations.
- `tests/`: application, database, curriculum, and auth tests using isolated
  temporary databases.

Learner-unlocking workflows, saved lesson progress, code execution, Buddy
interactions, AI, and games/progression are not implemented yet. Add their
modules when those features are developed.
#   v e r t e x a - d y p  
 