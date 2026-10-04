# Scheduling Platform — Backend (Part 1)

The backend of a Calendly-style scheduling service. A host registers, publishes
bookable **event types** ("30 Minute Intro Call"), and declares when they are
available — **weekly rules** plus **per-date exceptions**. An unauthenticated
public endpoint exposes one event type so an invitee-facing page can render it.

Part 1 stores availability as a *description*. Turning it into concrete
bookable time slots is out of scope here.

---

## Architecture

### Layers

```
Client ──JSON──▶ Router ──Schema──▶ Service ──Model──▶ Repository ──SQL──▶ PostgreSQL
```

| Layer | Folder | Responsibility | Never contains |
|---|---|---|---|
| Router | `app/api/routers/` | HTTP: read input, call one service function, wrap the result | Queries, business rules |
| Schema | `app/schemas/` | Pydantic request/response shapes **and every validation rule** | Database access |
| Service | `app/services/` | Business rules, Schema↔Model conversion, **commits the transaction** | SQL, HTTP concepts (`Request`, status codes) |
| Repository | `app/repositories/` | The only place queries are built; returns models or `None` | Decisions, commits, raised errors |
| Model | `app/models/` | SQLAlchemy table definitions | Behaviour |

Dependencies point one way only: router → service → repository → database.

### How a request flows

1. FastAPI matches the route; unmatched paths return a 404 in the standard envelope.
2. Dependencies run: a database session is opened; for host-scoped routes the
   `x-user-id` header is parsed (missing or non-numeric → 400).
3. Pydantic validates the body. Invalid input → 400 before any application code runs.
4. The router calls one service function.
5. The service applies the rules, calls the repository, and **commits**.
6. The service converts the model into a response schema; the router wraps it
   in the envelope.
7. The session is closed — rolled back first if anything raised.

### Response contract

Success:

```json
{ "success": true, "data": { }, "message": "User created successfully" }
```

Failure:

```json
{ "success": false, "message": "Validation failed", "details": [ { "field": "timezone", "message": "..." } ] }
```

| Code | Meaning |
|---|---|
| 200 | Successful GET, PATCH, DELETE |
| 201 | Successful POST |
| 400 | Validation failure; missing or invalid `x-user-id` |
| 404 | Not found, belongs to another host, or unmatched route |
| 409 | Duplicate email; slug already taken |
| 500 | Unexpected error |

Services raise domain errors (`NotFoundError`, `ConflictError`,
`BadRequestError` in `app/errors.py`); handlers registered in `app/main.py`
turn them into the envelope and status code. FastAPI's default
`{"detail": ...}` shape never appears. Tracebacks appear in `details` only when
`ENVIRONMENT=development`.

### Identifying the host

There is no authentication. Endpoints under `/api/event-types` and
`/api/availability` read the host's integer id from the `x-user-id` header.
A row owned by another host returns 404, exactly as if it did not exist.
`/api/users`, `/api/public/*` and `/health` need no header.

### Data model

```
users
 ├── event_types              (hostId → users.id, ON DELETE CASCADE)
 ├── availability_rules       (userId → users.id, ON DELETE CASCADE)
 └── availability_exceptions  (userId → users.id, ON DELETE CASCADE)
```

Tables are snake_case; columns are camelCase; Python attributes are snake_case.
Timestamps are `TIMESTAMP(3)` in UTC. Availability times are stored as `HH:mm`
text with an IANA timezone name. Weekday `0` is Sunday.

Schema changes are versioned with Alembic in `alembic/versions/`.

---

## Running locally

### Prerequisites

- Python 3.12+ (developed on 3.13)
- [uv](https://docs.astral.sh/uv/)
- Docker

### 1. Start PostgreSQL 16

PostgreSQL runs in Docker. The container's port 5432 is published on host
port **5433**, because 5432 was already taken on the development machine.

```bash
docker run --name scheduling-db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=scheduling \
  -p 5433:5432 \
  -d postgres:16
```

If port 5432 is free on your machine you can use `-p 5432:5432` instead —
change the port in `.env` to match.

### 2. Configure

```bash
cp .env.example .env
```

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | *required* | `postgresql+asyncpg://user:password@host:port/db` |
| `ENVIRONMENT` | `development` | `development` or `production`; controls traceback exposure |
| `PORT` | `8000` | Port for the API |

The application refuses to start if `DATABASE_URL` is missing.

### 3. Install dependencies

```bash
uv sync
```

Installs the exact versions pinned in `uv.lock`.

### 4. Build the schema

```bash
uv run alembic upgrade head
```

Applies every migration in order, from an empty database.

### 5. Run the API

```bash
uv run uvicorn app.main:app --reload --port 8000
```

- API: <http://localhost:8000>
- Interactive docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>

### Quick check

```bash
curl -s localhost:8000/health

curl -s -X POST localhost:8000/api/users \
  -H 'content-type: application/json' \
  -d '{"email":"jane@example.com","name":"Jane Doe","timezone":"Asia/Kolkata"}'
```

---

## Endpoints

| Method | Path | Header |
|---|---|---|
| GET | `/health` | — |
| GET | `/api/users` | — |
| GET | `/api/users/{user_id}` | — |
| POST | `/api/users` | — |
| PATCH | `/api/users/{user_id}` | — |
| DELETE | `/api/users/{user_id}` | — |
| GET | `/api/event-types` | `x-user-id` |
| GET | `/api/event-types/{event_type_id}` | `x-user-id` |
| POST | `/api/event-types` | `x-user-id` |
| PATCH | `/api/event-types/{event_type_id}` | `x-user-id` |
| DELETE | `/api/event-types/{event_type_id}` | `x-user-id` |
| GET | `/api/availability/rules` | `x-user-id` |
| POST | `/api/availability/rules` | `x-user-id` |
| PATCH | `/api/availability/rules/{rule_id}` | `x-user-id` |
| DELETE | `/api/availability/rules/{rule_id}` | `x-user-id` |
| GET | `/api/availability/exceptions` | `x-user-id` |
| POST | `/api/availability/exceptions` | `x-user-id` |
| PATCH | `/api/availability/exceptions/{exception_id}` | `x-user-id` |
| DELETE | `/api/availability/exceptions/{exception_id}` | `x-user-id` |
| GET | `/api/public/users/{user_id}/event-types/{slug}` | — |

Full request and response shapes are in `/docs`.

---

## Project structure

```
app/
  main.py                  app factory, exception handlers, router mounting
  config/settings.py       typed configuration from the environment
  database.py              async engine, session factory, get_session
  errors.py                domain error hierarchy
  api/
    deps.py                x-user-id and session dependencies
    routers/               health, users, event_types, availability, public_events
  schemas/                 common, user, event_type, availability
  models/                  base, user, event_type, availability_rule, availability_exception
  repositories/            one module per table
  services/                user, event_type, availability_rule, availability_exception
  utils/                   slug, weekday
alembic/                   migration environment and versions
docs/DECISIONS.md          design decisions, trade-offs and known gaps
```