# Setup Guide

This guide gets DjangoVerseHub running on a workstation, either directly in a virtualenv or with Docker Compose, and explains the moving parts you need for the full feature set (WebSockets, background jobs, demo data).

## Contents

- [Prerequisites](#prerequisites)
- [Local setup with the Makefile](#local-setup-with-the-makefile)
- [Running with or without Redis](#running-with-or-without-redis)
- [Docker Compose setup](#docker-compose-setup)
- [Environment variables](#environment-variables)
- [Settings modules](#settings-modules)
- [Running Celery and Channels](#running-celery-and-channels)
- [Demo data](#demo-data)
- [Account flows to try](#account-flows-to-try)
- [Everyday commands](#everyday-commands)
- [Troubleshooting](#troubleshooting)

## Prerequisites

| Requirement | Why |
| --- | --- |
| Python 3.10, 3.11 or 3.12 | `requires-python = ">=3.10"`; CI tests all three |
| PostgreSQL 13+ (15 in Docker) | the `dev`, `prod` and `ci` settings use `django.db.backends.postgresql`; only the `test` settings use SQLite |
| Redis 6+ (7 in Docker), optional locally | cache, Channels layer, Celery broker and result backend; the dev settings fall back to in-process alternatives when `REDIS_URL` is empty |
| `libpq` headers if `psycopg2-binary` has no wheel for your platform | the Docker image installs `libpq-dev` |
| Docker + Compose v2 (optional) | container route |

There is no Node.js toolchain: static assets under `static/` are plain CSS and JavaScript served by Django/WhiteNoise.

## Local setup with the Makefile

```bash
git clone https://github.com/SatvikPraveen/DjangoVerseHub.git
cd DjangoVerseHub

make venv                 # python3 -m venv .venv && pip install -r requirements/dev.txt
cp .env.example .env
```

Edit `.env`:

- `SECRET_KEY`: any long random string (`python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"`).
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`: your PostgreSQL. Create the database if needed: `createdb djangoversehub` (and a role matching `DB_USER`).
- `REDIS_URL`: leave at `redis://localhost:6379/0` if Redis runs locally, or set it to empty to run without Redis (next section).

Then:

```bash
make migrate              # apply migrations (dev settings)
make superuser            # create an admin account (email + username + password)
make demo                 # optional, see "Demo data"
make run                  # ASGI runserver (HTTP + WebSockets) on http://0.0.0.0:8000
```

Every Makefile target sets `DJANGO_SETTINGS_MODULE=django_verse_hub.settings.dev` for you and uses `.venv/bin/python`. If you prefer to call `manage.py` directly, activate the venv (`source .venv/bin/activate`); `manage.py` defaults to the dev settings as well.

Useful URLs after `make run`:

- http://localhost:8000/ home
- http://localhost:8000/admin/ admin
- http://localhost:8000/api/v1/ API root, http://localhost:8000/api/v1/docs/ Swagger UI
- http://localhost:8000/articles/feed/ RSS, http://localhost:8000/articles/feed/atom/ Atom
- http://localhost:8000/health/ready/ readiness probe, http://localhost:8000/metrics/ Prometheus (staff session or `METRICS_TOKEN`)
- http://localhost:8000/__debug__/ django-debug-toolbar assets (toolbar shows on pages when `DEBUG=True`)

## Running with or without Redis

`django_verse_hub/settings/base.py` reads `REDIS_URL` (default empty) and `dev.py` adapts to it:

| `REDIS_URL` | Cache | Channel layer | Celery |
| --- | --- | --- | --- |
| set (e.g. `redis://localhost:6379/0`) | Django's Redis cache backend, key prefix `djangoversehub_dev` | `channels_redis` (works across processes) | broker/result backend from `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND`; run `make worker` and `make beat` |
| empty | `LocMemCache` | Channels `InMemoryChannelLayer` (single process only) | `CELERY_TASK_ALWAYS_EAGER=True`: tasks run inline in the request, no worker needed |

You can override the Celery choice explicitly with `CELERY_TASK_ALWAYS_EAGER=True|False`. Production (`prod.py`) always requires `REDIS_URL`, `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND`.

## Docker Compose setup

```bash
cp .env.example .env      # the compose files read it; DB_HOST/REDIS_URL are overridden to the service names
make docker-up            # docker compose up --build
```

`docker-compose.yml` builds the `development` image target, mounts the source into the containers and starts:

| Service | Command | Port |
| --- | --- | --- |
| `db` | postgres:15-alpine, credentials from `DB_NAME`/`DB_USER`/`DB_PASSWORD` (defaults `djangoversehub`/`django_user`/`django_password`) | 5432 |
| `redis` | redis:7-alpine with persistence | 6379 |
| `web` | `python manage.py migrate --noinput && python manage.py runserver 0.0.0.0:8000` | 8000 |
| `asgi` | `daphne -b 0.0.0.0 -p 8001 django_verse_hub.asgi:application` | 8001 |
| `worker` | `celery -A django_verse_hub worker -l info -Q celery,notifications,articles,users` | – |
| `beat` | `celery -A django_verse_hub beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler` | – |
| `nginx` | profile `proxy` only: serves `./staticfiles` and media, proxies `/ws/` to `asgi:8001` and everything else to `web:8000` | 80 |

Migrations run automatically when `web` starts. Create an admin and demo content:

```bash
docker compose exec web python manage.py createsuperuser
docker compose exec web python manage.py generate_demo_data --admin
```

For WebSockets through one origin start the proxy profile and use port 80:

```bash
docker compose --profile proxy up --build
# http://localhost/  (HTTP -> web, /ws/ -> asgi)
```

When you open http://localhost:8000 directly, the notification client connects to `ws://localhost:8000/ws/notifications/`; `runserver` serves it because Daphne is installed as the development server. If the socket is unavailable the client falls back to the HTTP endpoints when you act on notifications.

The production-style stack is described in the README (`docker compose -f docker-compose.prod.yml up -d --build`).

## Environment variables

`.env.example` lists the common variables; the README's configuration table has the complete set with defaults. Grouped by purpose:

**Django**: `DJANGO_SETTINGS_MODULE`, `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS` (comma separated), `CSRF_TRUSTED_ORIGINS`, `SITE_NAME`, `SITE_TAGLINE`, `SITE_URL` (used to build absolute links in emails and feeds), `APP_VERSION`.

**Database**: `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`. There is no `DATABASE_URL` support.

**Redis and Celery**: `REDIS_URL` (see the table above), `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` (defaults in dev, required in prod), `CELERY_TASK_ALWAYS_EAGER` (dev only).

**Email**: `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`. The dev settings use the console email backend regardless, the test settings use the in-memory backend. `ACCOUNT_EMAIL_VERIFICATION` (`mandatory` | `optional` | `none`) controls allauth's own flow; the project's `/users/signup/` sends its own verification link.

**Auth tokens**: `JWT_ACCESS_MINUTES` (30), `JWT_REFRESH_DAYS` (14).

**Request handling, security headers and logging**: `RATE_LIMIT_ENABLED`, `RATE_LIMIT_REQUESTS_PER_MINUTE` (per client IP, skipped when `DEBUG` or on `/admin/`, `/static/`, `/media/`, `/health/`, `/metrics/`), `SLOW_REQUEST_THRESHOLD_MS`, `CSP_ENABLED`, `CSP_REPORT_ONLY`, `CSP_REPORT_URI`, `METRICS_TOKEN`, `LOG_LEVEL`, `LOG_FORMAT` (`verbose` | `json`), `LOG_DIR` (prod file handler), `SQL_LOG_LEVEL` (dev; `DEBUG` prints SQL).

**Production security**: `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `CORS_ALLOWED_ORIGINS`, `ADMIN_URL` (read by `prod.py` but the URLconf currently hardcodes `admin/`).

**Media on S3 (prod, optional)**: `USE_S3`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`.

**Social login**: `GOOGLE_OAUTH2_KEY`, `GOOGLE_OAUTH2_SECRET`, `GITHUB_KEY`, `GITHUB_SECRET` are listed in `.env.example` for convenience but are not read by the settings. allauth looks up credentials in `SocialApp` rows: Admin > Social applications > add an app for the `google` or `github` provider and attach it to the site with `SITE_ID = 1`.

**Monitoring (prod, optional)**: `SENTRY_DSN`, `SENTRY_ENVIRONMENT`, `SENTRY_TRACES_SAMPLE_RATE`, `SENTRY_PROFILES_SAMPLE_RATE`.

**Tests**: `KEEP_MIGRATIONS=1` makes the test settings use the real migration graph (used by `make check`, the pre-commit hook and CI's drift check).

## Settings modules

| Module | Purpose | Notable behaviour |
| --- | --- | --- |
| `django_verse_hub.settings.base` | everything shared | PostgreSQL, channel layer (Redis or in-memory), DRF/JWT/spectacular config, CSP and metrics settings, Celery routing, logging with request ids |
| `.dev` | local development (default for `manage.py`, Makefile, `celery.py`, `asgi.py`) | `DEBUG=True`, debug toolbar, django-extensions, Redis or local-memory cache, eager Celery without Redis, console email, CORS open, rotating log file under `logs/` |
| `.prod` | production (default for `wsgi.py`, Docker `production` target) | requires `ALLOWED_HOSTS`, `REDIS_URL`, broker URLs; SSL/HSTS/secure cookies; sessions in cache; WhiteNoise manifest storage; JSON logs; Sentry/S3 optional |
| `.test` | pytest (`pyproject.toml`) | SQLite in-memory, migrations disabled unless `KEEP_MIGRATIONS=1`, locmem cache, in-memory channel layer, eager Celery, MD5 hasher, throttles off, rate limit off |
| `.ci` | CI PostgreSQL job | `.test` plus PostgreSQL, real migrations, and the Redis cache when CI provides `REDIS_URL` |

## Running Celery and Channels

**Celery** (needs Redis and the database):

```bash
make worker     # celery -A django_verse_hub worker -l info
make beat       # celery -A django_verse_hub beat -l info  (DatabaseScheduler from settings)
```

Tasks are routed by module (`CELERY_TASK_ROUTES`): `apps.notifications.tasks.*` to `notifications`, `apps.articles.tasks.*` to `articles`, `apps.users.tasks.*` to `users`; everything else goes to `celery`. `make worker` consumes the default queue only; to process all of them locally run `celery -A django_verse_hub worker -l info -Q celery,notifications,articles,users` (this is what the Docker entrypoint and compose file do). Beat's schedule (`django_verse_hub/celery.py`) is written to the `django_celery_beat` tables on first start and is editable in the admin.

Without Redis (`REDIS_URL` empty) tasks run inline; the code that enqueues transactional email also catches broker errors, so a missing broker never breaks sign-up or commenting.

**Channels / WebSockets**: the ASGI application is `django_verse_hub.asgi:application`. In development `runserver` already serves it through Daphne (`daphne` is first in `INSTALLED_APPS`); running daphne directly is equivalent:

```bash
DJANGO_SETTINGS_MODULE=django_verse_hub.settings.dev \
  .venv/bin/daphne -b 0.0.0.0 -p 8000 django_verse_hub.asgi:application
```

Then log in, open http://localhost:8000/notifications/websocket/ in one tab and trigger an event from another account (like an article, follow the user, comment on their article): the toast and badge update without a reload. With `REDIS_URL` set the channel layer is `channels_redis`; without it the in-memory layer works as long as everything runs inside that one daphne process. The `AllowedHostsOriginValidator` rejects sockets whose `Origin` host is not in `ALLOWED_HOSTS`.

## Demo data

```bash
make demo
# or
python manage.py generate_demo_data --users 30 --articles 120 --comments 400 --seed 42 --admin
```

- Creates users `<name>@demo.djangoversehub.local` with password `demo-password-123`; `--admin` adds `admin@demo.djangoversehub.local` as a superuser with the same password.
- Creates 8 categories, 24 tags, articles in mixed statuses with backdated timestamps and view counts, follows, likes, bookmarks, threaded comments and comment likes. Notifications are produced by the regular signal handlers.
- `--seed N` makes the output reproducible; `--clear` deletes everything previously generated (by email domain) before generating again.

## Account flows to try

With the dev settings all email is printed to the console running the server (or the worker when Redis is used), so links are easy to copy.

- **Sign-up and verification**: `/users/signup/` creates the account, logs you in and sends a verification link to `/users/verify-email/<token>/` (valid for 3 days). A banner on the profile/settings pages offers **Resend**, limited to once per 10 minutes.
- **Password reset**: `/users/password-reset/` sends a link to `/users/password-reset/confirm/<token>/`; the token is invalid once the password changes.
- **Export**: on the settings page, "Download my data" posts to `/users/export/` and returns a JSON attachment (also `GET /api/v1/users/me/export/`).
- **Delete account**: `/users/delete/` asks for the current password. Accounts with published articles are anonymised (username/email replaced, profile cleared, sessions and tokens revoked, drafts/likes/bookmarks/follows/notifications removed) so their articles remain; other accounts are deleted outright. The API equivalent is `DELETE /api/v1/users/me/` with `{"password": "..."}`.

## Everyday commands

```bash
make help            # list targets
make shell           # shell_plus with models pre-imported and SQL echo
make makemigrations  # after model changes
make check           # django check + migration drift check (KEEP_MIGRATIONS=1 under test settings)
make test            # pytest
make test-fast       # pytest -n auto
make coverage        # coverage report, htmlcov/index.html
make lint / make format
make typecheck       # mypy (currently reports errors)
make clean           # remove caches, coverage and htmlcov
```

`pre-commit install` enables the hooks from `.pre-commit-config.yaml`: whitespace/YAML/TOML/JSON checks, ruff lint + format, `manage.py check` and the migration drift check.

## Troubleshooting

**`allauth.account.middleware.AccountMiddleware must be added to settings.MIDDLEWARE`** or **`ImproperlyConfigured` mentioning `ACCOUNT_LOGIN_METHODS`**
The project targets django-allauth 0.61+ (`ACCOUNT_LOGIN_METHODS`, `ACCOUNT_SIGNUP_FIELDS`, `allauth.account.middleware.AccountMiddleware`). Reinstall dependencies with `make install` if an older allauth is on the path. The middleware is already listed in `base.py`; keep it after `AuthenticationMiddleware`.

**Cannot log in via `/accounts/login/`, "Verify your email address"**
`ACCOUNT_EMAIL_VERIFICATION=mandatory` is the default for allauth's own pages. In development set it to `optional` in `.env`, or use the project's login page at `/users/login/` (email or username + password), which does not block unverified accounts. With the dev settings emails are printed to the console, so the verification link is visible there.

**`redis.exceptions.ConnectionError: Error 61 connecting to localhost:6379` / readiness returns 503**
`REDIS_URL` (or the Celery URLs) point at a Redis that is not running. Start it (`redis-server`, `brew services start redis`, or the compose `redis` service) or set `REDIS_URL=` to use the in-process fallbacks. `/health/ready/` reports which dependency failed under `checks`; the Celery check is skipped when tasks run eagerly.

**`django.db.utils.OperationalError: connection refused` / `password authentication failed`**
PostgreSQL is not running or the `DB_*` values in `.env` do not match. In Docker the entrypoint retries the database for 60 seconds before giving up.

**WebSocket keeps reconnecting, badge never updates**
The page origin is not in `ALLOWED_HOSTS`, or you are running several processes with the in-memory channel layer. Set `REDIS_URL` for multi-process setups or use the compose `proxy` profile. Anonymous users are disconnected on purpose.

**`/metrics/` returns 403**
Send `Authorization: Bearer <METRICS_TOKEN>`; when `METRICS_TOKEN` is empty you must be logged in as staff in the browser.

**Migrations**
- `make check` fails with "Your models have changes that are not yet reflected in a migration": run `make makemigrations` and commit the result. Each app has a single `0001_initial.py`.
- Tests fail with `no such table` after adding a model: the test settings synchronise models directly (migrations disabled), so this usually means the app is missing from `INSTALLED_APPS`.
- To run tests against the real migration graph: `KEEP_MIGRATIONS=1 python -m pytest`.
- Fresh database in Docker: `docker compose down -v` removes the `postgres_data` volume.

**Celery tasks never run**
No worker is consuming the queue the task was routed to. Start a worker with `-Q celery,notifications,articles,users`, or set `CELERY_TASK_ALWAYS_EAGER=True` for inline execution.

**`make typecheck` reports hundreds of errors**
Known; mypy with django-stubs is configured but the codebase is not yet clean. It is not part of `make ci` or the CI workflow.

**Static files missing in the production image**
`collectstatic` runs at build time with throwaway settings and WhiteNoise serves `staticfiles/`. If you add new static files, rebuild the image. nginx also mounts the `static_volume` populated by the `web` container.
