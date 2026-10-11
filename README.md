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

## Buddy Gemini setup

The app defaults to `BUDDY_PROVIDER=mock`; this deterministic mode is offline
and sends no learner messages to an AI service. To select Gemini, install the
declared dependency and edit the ignored `.env` file (never `.env.example`):

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
notepad .env
```

In `.env`, set `BUDDY_PROVIDER=gemini`, `GEMINI_API_KEY` to the key from Google
AI Studio, and `BUDDY_GEMINI_ADULTS_ONLY=true` only if the service is genuinely
restricted to adults. Set `BUDDY_GEMINI_FREE_TIER_CONFIRMED=true` only after
checking that the model is available in the project's free tier and that
billing is not enabled. Keep the key in this ignored file; never put it in
tracked files, templates, JavaScript, logs, or commands.

The adapter uses the official `google-genai` SDK and is fixed to
`gemini-2.5-flash`, listed in Google's current model catalog. Google's pricing
documentation describes free access as limited to certain models, and quotas
are project-specific and may change. The app cannot inspect AI Studio billing
or guarantee a project's free-tier status. The two `BUDDY_GEMINI_*` flags are
operator attestations, not a technical billing lock. Check AI Studio before
enabling Gemini; no alternate model or provider is selected automatically.

Google's current Gemini API terms require API clients to be restricted to
adults 18 or older. Do not enable this integration for a service intended for,
or likely to be accessed by, minors. Each learner must separately confirm
they are 18+ and consent before their first Gemini request in a signed-in
session. Google's terms say unpaid Gemini prompts and responses may be used to
improve services and may be processed by human reviewers. Do not submit
personal, sensitive, confidential, or secret information. Only the current
message and selected language are sent; saved conversation history and Buddy
memory are deliberately excluded. Local saving remains controlled by its
separate existing consent.

Gemini requests make one SDK attempt, use a 15-second SDK request timeout, cap
generation at 192 tokens and responses at 1,000 characters, and add stricter
process-local per-user/global request limits to the existing Buddy limiter.
The global limiter is not shared across multiple workers and these safeguards
do not replace Google account quotas. Quota exhaustion, bad credentials,
timeouts, and outages fail visibly; Gemini mode never falls back to the mock.

### Start, switch, and restart in Windows PowerShell

With the values stored in `.env`, start Gemini mode from the project folder:

```powershell
$env:BUDDY_PROVIDER = "gemini"
$env:BUDDY_GEMINI_ADULTS_ONLY = "true"
$env:BUDDY_GEMINI_FREE_TIER_CONFIRMED = "true"
python -m flask --app app:create_app run --debug
```

The API key is read by Flask from `GEMINI_API_KEY` in `.env`; it is not printed
by these commands or sent to the browser. To switch back to the offline mock,
stop Flask with `Ctrl+C`, then run:

```powershell
$env:BUDDY_PROVIDER = "mock"
python -m flask --app app:create_app run --debug
```

After changing `.env` or provider settings, stop Flask with `Ctrl+C` and start
it again with the selected command. The debug reloader reloads source code;
environment configuration is read when the server process starts. To remove a
PowerShell override and let `.env` control that setting, run
`Remove-Item Env:BUDDY_PROVIDER` (and similarly remove the `BUDDY_GEMINI_*`
overrides).

Troubleshooting: verify missing keys in `.env` and restart; verify credentials
and model access in Google AI Studio for authentication errors; wait and check
the project's quota page for quota errors; retry manually after timeouts or
outages. Responses do not include provider details or credentials, and errors
never trigger a mock fallback.

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
empty state; browsing never seeds or changes curriculum data. Signed-in users
can access Buddy's authenticated chat, which currently uses a clearly labeled
deterministic local mock by default. An operator may explicitly select the
consent-gated Gemini integration described above; it is unavailable until its
server-side configuration is valid. Saved lesson progress, interactive coding,
games, and XP are not implemented.

The interface uses server-rendered Flask templates with plain HTML, CSS, and
JavaScript. API-provided lesson text and code examples are inserted as text,
not interpreted as HTML. The frontend has loading, empty, and request-error
states and adapts to narrow screens. Account pages use the same responsive
layouts, including an accessible expandable mobile navigation menu. Form
submission and validation run on Flask, so registration and account editing do
not depend on JavaScript.

The authenticated Buddy page progressively enhances its SVG fallback with
Google's pinned `model-viewer` 4.1.0 browser component. It loads only
`app/static/models/buddy/greetings.glb`; the provided GLBs were byte-identical
in this workspace and each is about 59 MB. Idle, greeting, confused, yes, and
two-hand cheering clips were confirmed in the browser. The renderer script
comes from Google's CDN, so 3D requires an internet connection; if rendering
or the asset fails, the existing SVG remains visible. Reduced-motion settings
pause animation. Buddy's shared policy now requests gentle bug-focused humor,
calmer help when frustration is expressed, and technical accuracy. The
separately supplied Buddy Master Script was not present in the workspace, so
its full behavior is not claimed as implemented.

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

Learner-unlocking workflows, saved lesson progress, code execution, external AI
integration beyond the optional Gemini adapter, and games/progression are not
implemented yet. Buddy's authenticated chat supports the deterministic local
mock and explicitly configured Gemini mode.

## Buddy storage services

The Buddy database foundation includes explicit-consent saved conversations,
ordered messages, learner-approved memory items, and per-user privacy settings.
Service functions enforce ownership, reject expired conversations for reads,
and treat missing privacy settings as memory disabled. The default provider is
the deterministic local mock; Gemini is opt-in, consent-gated, and disabled
unless its server configuration is complete.

The mock is for tests and development only. Its output is explicitly marked
`MOCK ONLY`; it does not analyze or execute submitted code. The calling
service must pass conversation context explicitly and may pass approved
memories only after the privacy service confirms opt-in.

To remove conversations whose 90-day expiry has elapsed, run:

```powershell
python -m flask --app app:create_app purge-buddy-conversations
```

The command is safe to repeat. It removes expired conversations and their
messages from the configured database. Deployment scheduling is an operator
responsibility; no scheduler or worker is included. This command does not
change backup retention: older backups may still contain deleted conversation
data, and their retention and expiry cleanup must be managed separately.

## Buddy interface (mock only)

Signed-in pages show a small animated Buddy launcher with a brief greeting and
quick links for hints, explanations, and debugging. Those links open the
existing authenticated Buddy chat and submit a fixed starter request through
its existing API flow. The Buddy page also has the same quick actions beside
its composer. Expressions reflect local UI states such as waiting for a mock
reply or receiving one; they do not indicate code execution or infer learner
emotion. The launcher and animations respect keyboard focus and reduced-motion
settings. Replies remain deterministic local mock output; no external AI
provider is connected.

## Buddy protected API

All routes below are authenticated, return JSON, and set `Cache-Control:
no-store`. Unauthenticated requests receive HTTP 401; private resources owned
by another learner and expired conversations both receive the same generic
404. State-changing requests use Flask-WTF CSRF protection and must send the
token rendered in the current session using the `X-CSRFToken` header. JSON
requests are limited to 64 KiB. Request errors use the shape
`{"error":{"code":"...","message":"..."}}`.

History consent is an explicit, revocable choice held in the authenticated
Flask session. It is not a durable account preference: each saved conversation
still records its own consent timestamp and policy version. Without session
consent, a Buddy response uses only the current message and is not saved.

| Method and route | Request JSON | Response JSON |
| --- | --- | --- |
| `GET /api/buddy/status` | — | `available`, `provider` (`name`, `is_mock`, `mode`, safe `message`), `external_consent`, `history`, and `memory` |
| `POST /api/buddy/external-consent` | `{"consent":true,"adult_confirmed":true}` or `{"consent":false}` | Session-scoped Google Gemini disclosure consent |
| `POST /api/buddy/history-consent` | `{"consent": true}` or `{"consent": false}` | `history` (`consent`, `consent_scope`, `policy_version`) |
| `POST /api/buddy/respond` | `{"message":"...", "conversation_id":"optional UUID", "language":"python"}`; `language` may be `javascript`, `c`, or `cpp` | `response` (`content`, `provider`, `is_mock`, `intent`, `teaching_approach`), `conversation` (metadata or `null`), and `saved` |
| `GET /api/buddy/conversations` | — | `conversations`: the current learner's unexpired conversation metadata |
| `GET /api/buddy/conversations/<id>` | — | `conversation` metadata and ordered `messages` |
| `DELETE /api/buddy/conversations/<id>` | — | `{"deleted":true}` |
| `GET /api/buddy/privacy` | — | `privacy` (`memory_enabled`, `memory_consent_at`, `memory_policy_version`) |
| `PATCH /api/buddy/privacy` | `{"memory_enabled":true}` or `{"memory_enabled":false,"confirm_delete_existing":true}` | Updated `privacy` fields |
| `GET /api/buddy/memory` | — | `memory_enabled` and approved `items` |
| `POST /api/buddy/memory` | `{"category":"learning_goal","content":"...","learner_approved":true}` | Created `item` (HTTP 201) |
| `PATCH /api/buddy/memory/<id>` | `{"category":"learning_focus","content":"...","learner_approved":true}` | Updated `item` |
| `DELETE /api/buddy/memory/<id>` | — | `{"deleted":true}` |

Only the deterministic local mock is configured; responses are marked
`MOCK ONLY` and `is_mock: true`. No route executes submitted code or connects
to an external AI service. Buddy endpoints are limited to 30 requests per
authenticated user per 60-second sliding window in each application process.
This in-process limiter is not shared across multiple workers or machines and
is not a substitute for a distributed production rate limiter.

## Buddy chat page (mock only)

The authenticated page is available at `GET /buddy`. It calls the documented
`/api/buddy/...` routes from the browser and receives the CSRF token in a page
meta element for state-changing requests. Sign-in is required; the API remains
responsible for authentication, ownership checks, validation, CSRF protection,
and rate limiting.

Saved conversation history is off until the learner explicitly opts in.
Without consent, exchanges are sent to the mock for the current response only
and stay in tab memory; they are not written to browser or server storage.
Turning off consent clears the unsaved page transcript but does not delete
previously saved conversations. Saved conversations can be selected or
deleted from the page. Memory is a separate opt-in; creating or editing a
memory requires learner approval, and disabling memory may require confirmation
to delete stored items.

All Buddy responses are visibly labelled as simulated mock output. The page
does not execute learner code or connect to an external provider. The
per-process API request limiter does not coordinate across workers, and this
development mock interface is not a production AI launch.

## Buddy pre-provider safeguards

The current request limits are 64 KiB per JSON request, 12,000 characters per
learner message, 20 context messages / 24,000 context characters, 20 approved
memory items / 5,000 memory characters, and at most 4,000 output characters.
The API currently requests at most 1,000 output characters. The deterministic
mock itself also truncates output to the request limit. The synchronous
provider adapter recognizes a raised `TimeoutError` but does not enforce a
wall-clock timeout or retry policy.

Before enabling any real provider, require enforced connect/read/overall
timeouts, bounded retries with backoff and duplicate-safe semantics, explicit
token and output caps, per-user and global usage/cost budgets, quota-exhaustion
and missing-credential fail-closed behavior, and verified provider retention,
training, and data-processing terms. Disclose third-party transmission before
consent, minimize the context sent, and define provider-side deletion and
retention behavior. None of these provider terms or safeguards is verified or
implemented by this local-mock phase.

Saved responses are committed atomically with their user/assistant messages,
but `/api/buddy/respond` has no durable idempotency key. A client retry after
an ambiguous failure can therefore create a duplicate exchange; the current
browser retry is manual and warns that it may duplicate. Robust deduplication
across concurrent requests and application workers needs a durable unique
request key scoped to the user, a request fingerprint, and a stored processing
result linked transactionally to the conversation exchange. This requires a
schema migration and is not implemented pending approval.
#   v e r t e x a - d y p  
 