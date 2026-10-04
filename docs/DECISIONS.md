# Design Decisions — Part 1

Each entry records what was decided, what else was considered, and the cost
accepted. Entries marked **Known gap** are limitations noticed and deliberately
left in place.

---

## 1. Layering

### 1.1 The service commits, not the session dependency

**Decision.** `get_session` opens a session per request, rolls back if the
request raised, and always closes. It never commits. Each service function
that writes ends with an explicit `await session.commit()`.

**Alternative.** Have the dependency commit automatically when the request
finishes. Less code, and impossible to forget.

**Why.** With automatic commit, the commit happens after the service and the
router have both returned. There is no line in application code where the
transaction is known to be durable. Any side effect that must happen only
after a successful commit — sending a notification, starting a background
job — would have nowhere to go. Making the commit explicit puts that point in
the service, where it can be seen.

**Cost.** A write service that forgets to commit returns success while its
change is rolled back. This fails loudly the first time the endpoint is
exercised, so it is caught early; mis-ordered side effects would fail rarely
and only in production.

### 1.2 Schema ↔ Model conversion happens in the service

**Decision.** The service builds models from request schemas and builds
response schemas from models.

**Alternatives.** In the router — rejected, it would put storage classes in
the HTTP layer. A separate mapper module per entity — rejected as more files
than the conversion warrants; most conversions are a single
`model_validate` or a dictionary spread.

**Why.** The repository takes plain arguments and never sees Pydantic; the
router never sees models. The service is the only layer that legitimately
holds both, and choosing what crosses the boundary is a business decision —
the public event type exposes five of twelve columns on purpose.

### 1.3 Repositories are functions that take the session as an argument

**Decision.** `find_by_email(session, email)`, not
`UserRepository(session).find_by_email(email)`.

**Alternative.** A repository class holding the session — the familiar Spring
arrangement.

**Why.** A single `AsyncSession` runs one query at a time. Code that needs
several independent queries to run concurrently must give each its own
session. Passing the session per call lets the caller decide; storing it on an
object fixes the choice at construction. It is also simpler: no classes, no
construction, no wiring. The session factory is exposed at module level in
`app/database.py` for the same reason.

### 1.4 Dependency injection stops at the router

FastAPI's `Depends()` supplies what a route handler needs — the session and
the host id. Below the router, everything is passed as ordinary arguments.
There is no container and no global object graph.

---

## 2. HTTP contract

### 2.1 One error hierarchy, mapped in one place

Services raise `NotFoundError`, `ConflictError` or `BadRequestError`. Each
carries its own `status_code`, so a single handler covers all three. Services
never mention HTTP; the mapping lives only in `app/main.py`.

Five handlers are registered:

| Handler | Produces |
|---|---|
| `ApiError` | The subclass's status and message |
| `RequestValidationError` | 400 (FastAPI's default is 422) |
| `StarletteHTTPException` | Envelope for unmatched routes and similar |
| `IntegrityError` | 409 for a unique-constraint violation (see 3.2) |
| `Exception` | 500; traceback logged, and shown only in development |

The `StarletteHTTPException` handler is easy to miss. An unmatched path is
rejected by the router before any application code runs, so without it
`{"detail": "Not Found"}` escapes.

Validation error details are reduced to `{field, message}` pairs. Pydantic's
raw list can contain Python exception objects, which cannot be serialised to
JSON and would turn a 400 into a 500.

### 2.2 404, not 403, for another host's rows

Host scoping is applied in the query itself (`WHERE hostId = :host_id`), so a
row owned by someone else is never loaded and is reported exactly like a row
that does not exist. A 403 would confirm the row exists and let anyone
enumerate other hosts' data.

The public endpoint applies the same idea: missing event type, inactive event
type and missing host all return the same 404 with the same message. The
inactive check is part of the query, so there is no branch that could reveal
the difference.

### 2.3 Header-less 400 message

`x-user-id` is optional at the FastAPI level and checked by our own
dependency, so missing, non-numeric and non-positive values all produce one
message: *Missing or invalid x-user-id header*.

---

## 3. Users

### 3.1 Slug collisions

- **Derived** from the name and taken → append `-2`, `-3`, … until free, as the
  spec requires. Registration should not fail because two people share a name.
- **Supplied explicitly** and taken → **409**. The caller asked for that exact
  slug; quietly substituting another would be surprising.

### 3.2 The check-then-insert race — Known gap, with a safety net

Uniqueness of email and slug is checked before inserting, which gives clear
messages. Two simultaneous requests can both pass the check; the database's
unique constraint then rejects the second.

**Decision.** Keep the readable check, and catch the constraint violation
(`IntegrityError` with SQLSTATE `23505`) in one handler that returns
**409 "Conflicts with existing data"** instead of a 500. The database
guarantees correctness; the handler guarantees an honest status code. The
handler also covers event-type slugs and any future unique column.

**Alternatives.** A table lock — serialises every registration to protect a
rare case. A row lock — impossible, because the row does not exist yet.

**Cost.** The loser of a race gets a generic 409 rather than being transparently
given `jane-doe-2`. Production improvement: attempt the insert and retry with
the next number on violation.

### 3.3 User slugs follow the URL-safe pattern

The spec states 1–100 characters for user slugs. They are additionally held to
`^[a-z0-9-]+$`, the pattern the spec gives for event-type slugs, because a slug
with spaces or capitals defeats its purpose. Slugs are not updatable through
PATCH, matching the spec's field list.

### 3.4 Timezones are checked against the exact list of names

The validator checks the value against `zoneinfo.available_timezones()` rather
than attempting `ZoneInfo(value)`. On a case-insensitive filesystem (macOS),
`ZoneInfo("asia/kolkata")` succeeds and would store a name that fails on Linux.
The list check behaves the same everywhere. The same reusable type
(`TimezoneStr`) is used by users, rules and exceptions.

### 3.5 PATCH null handling

An empty PATCH body is rejected (spec). Setting a non-nullable column to
`null` is also rejected, with the field named.

---

## 4. Event types

### 4.1 Slug collisions are always 409

Unlike users, a clash on `(hostId, slug)` is reported even when the slug was
derived from the title. The host is naming their own products and should be
told.

### 4.2 Unknown host on create

`x-user-id` is only an assertion. Creating an event type for a host id that
does not exist would otherwise reach the foreign key and fail as a database
error. The service checks first and returns **404 "User not found"**. The same
check applies to creating rules and exceptions. Reads for an unknown host need
no check — they simply find nothing.

### 4.3 Empty PATCH is accepted

The spec requires a non-empty body only for users. For event types, rules and
exceptions an empty body is accepted, changes nothing, and does not commit.
`description` and `locationValue` may be set to `null` to clear them; every
other field rejects `null`.

### 4.4 Hard delete — Known gap

Deleting an event type, or a user, removes the row and cascades to its
children. In Part 1 the cascade only reaches availability configuration. Once
bookings reference event types, the same delete would remove real meetings
with no record. Soft delete via the existing `isActive` flag is the right
answer at that point.

### 4.5 One query for the public view

The public endpoint loads the event type and its host in a single joined
query. The relationship is declared with `lazy="raise"`, so accessing it
without loading it first fails immediately instead of quietly issuing an
extra query per row.

---

## 5. Availability

### 5.1 PATCH validates the combined row

**Problem.** A stored rule is 09:00–17:00. `PATCH {"endTime": "08:00"}` is a
valid time on its own, but produces 09:00–08:00 — a rule that can never yield
availability. The invariant can only be checked against the merged state, which
the schema layer cannot see.

**Decision.** The service loads the stored row, overlays the fields that were
sent, and validates the result with the **same** schema the POST endpoint
uses. The rule stays declared once, in the schema layer; the service supplies
the data. The row is not modified until the check passes, so a failed PATCH
changes nothing.

**Alternatives.** An `if` in the service — moves a declared rule into
imperative code. Requiring both times whenever either is sent — breaks partial
update, which the spec wants.

### 5.2 Exceptions are three shapes chosen by `type`

| Type | Times |
|---|---|
| `BLOCK_FULL_DAY` | Not allowed — sending them is a 400 |
| `BLOCK_PARTIAL` | Required, end after start |
| `ADD_AVAILABLE_WINDOW` | Required, end after start |

Modelled as three Pydantic classes and a discriminated union on `type`, so
`/docs` shows three separate request shapes rather than one with optional
times. This is what the spec means by the constraint being visible in the
generated schema.

### 5.3 Changing an exception's type

Switching a `BLOCK_PARTIAL` to `BLOCK_FULL_DAY` while times are stored is
**rejected**. The client must send `startTime: null` and `endTime: null`
explicitly. Nothing changes that the client did not ask to change. After a
successful check every column is written from the validated result, so the
stored row always matches exactly one valid shape.

### 5.4 Times are fixed-width text

`startTime`/`endTime` are `HH:mm` text, validated by
`^([01]\d|2[0-3]):[0-5]\d$`. Because the format is fixed-width, two values
compare correctly as strings, and no time-of-day type is needed. They are
stored as text with an IANA zone, not as `TIME` or UTC, because the same local
time is a different instant on either side of a daylight-saving change.

**Known gap.** The pattern does not admit `24:00`, so a window running to
midnight must end at `23:59`.

### 5.5 Weekday encoding

The schema uses `0 = Sunday … 6 = Saturday`, which matches neither Python's
`date.weekday()` (0 = Monday) nor ISO (1 = Monday … 7 = Sunday). The conversion
lives in one pure helper, `app/utils/weekday.py`. Part 1 only stores and
validates the integer; the helper exists so later code that resolves dates
against rules does not re-derive it.

### 5.6 Overlapping rules are allowed

The spec puts no uniqueness rule on availability rules. Two overlapping
Monday rules are stored as given; merging them into one window belongs to the
code that resolves availability into times.

### 5.7 Ordering

| Endpoint | Order |
|---|---|
| Event types | `createdAt DESC`, then `id DESC` |
| Rules | `weekday`, `startTime`, then `id` |
| Exceptions | `date`, `startTime NULLS FIRST`, then `id` |
| Users | `id` (not specified; chosen for stable output) |

The trailing `id` breaks ties so output never depends on physical row order.

---

## 6. Storage conventions

### 6.1 Naive UTC timestamps

`createdAt`/`updatedAt` are `TIMESTAMP(3) WITHOUT TIME ZONE`. UTC is a
convention the application enforces, not something the column records.
`createdAt` is filled by the database; `updatedAt` by SQLAlchemy's `onupdate`.
Responses render them as `2026-10-04T11:53:43.151Z`.

### 6.2 Enumerated values are TEXT

`type` and `locationType` are TEXT columns with allowed values enforced by
Python `StrEnum`/`Literal` at the Pydantic boundary, so they appear in
`/docs`. Adding a value to a PostgreSQL enum needs a migration and takes a
lock.

**Known gap.** A write that bypasses the application can store an unknown
value. A `CHECK` constraint would close this without the locking problem; it is
not specified and has not been added.

### 6.3 `expire_on_commit=False`

By default SQLAlchemy marks loaded objects stale after commit, so reading an
attribute afterwards triggers a refresh — which in async code fails. Services
commit and then build the response from the model, so expiry is disabled.
Repositories `refresh` after each flush to load database-filled columns
(`id`, timestamps).

### 6.4 Ids may have gaps

A PostgreSQL sequence is never rolled back. Failed or rolled-back inserts
consume ids. Nothing in the code assumes ids are continuous.

---

## 7. Configuration and runtime

- One `Settings` class, constructed once at import. `DATABASE_URL` has no
  default, so a missing value stops the process at startup.
- `ENVIRONMENT` is restricted to `development` or `production`; a typo fails
  at startup instead of silently disabling tracebacks.
- PostgreSQL 16 runs in Docker on host port **5433**, because 5432 was
  occupied on the development machine. The README gives the exact command.

---

## 8. Known gaps — summary

| Gap | Note |
|---|---|
| No authentication | `x-user-id` identifies, it does not prove |
| Check-then-insert race on unique fields | Loser gets 409, not an automatic retry |
| Hard delete cascades | Dangerous once bookings exist; soft delete is the fix |
| Enum values not enforced in the database | A `CHECK` constraint would close it |
| No `24:00` end time | Spec regex; use `23:59` |
| No pagination | Lists are unbounded |
| Out of scope by the spec | CORS, rate limiting, request logging, versioning, containerisation of the app, automated tests |