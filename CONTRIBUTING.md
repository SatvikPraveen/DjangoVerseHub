# Contributing to DjangoVerseHub

Thanks for taking the time to contribute. This document explains how the
project is organised and what a good change looks like.

## Getting set up

```bash
git clone https://github.com/SatvikPraveen/DjangoVerseHub.git
cd DjangoVerseHub
make venv            # creates .venv and installs requirements/dev.txt
cp .env.example .env # then edit DB_* for your PostgreSQL
make migrate
make demo            # optional: realistic demo content
make run
```

Redis is optional locally: leave `REDIS_URL` empty and the cache, channel
layer and Celery fall back to in-process implementations.

Install the pre-commit hooks once so lint, formatting and migration checks
run before every commit:

```bash
.venv/bin/pre-commit install
```

## Project layout

| Path | Purpose |
| --- | --- |
| `apps/core` | Landing page, search, informational pages, newsletter, site settings, shared template tags, management commands |
| `apps/users` | Custom user model, profiles, follows, auth flows, account export/deletion |
| `apps/articles` | Articles, categories, tags, likes, bookmarks, revisions, feeds |
| `apps/comments` | Generic threaded comments with moderation |
| `apps/notifications` | In-app notifications, WebSocket consumer, preferences, digests |
| `apps/api` | Cross-cutting API endpoints, routers, JWT, OpenAPI |
| `django_verse_hub` | Settings, ASGI/WSGI, Celery app, middleware, health and metrics |

Each app owns its models, views, serializers, templates and tests. Cross-app
behaviour goes through signals (see `apps/notifications/signals.py`) or
explicit helper functions, never by reaching into another app's views.

## Making changes

1. Branch from `main`.
2. Write or update tests next to the code (`apps/<app>/tests/`). The suite
   runs on SQLite in memory by default; set `KEEP_MIGRATIONS=1` to run the
   real migration graph, and use `django_verse_hub.settings.ci` to run
   against PostgreSQL.
3. Run `make ci` before pushing. CI runs the same steps on Python 3.10-3.12
   plus a PostgreSQL job and a Docker build.
4. If you change a model, commit the migration (`make makemigrations`).
5. Keep commits focused and write messages that explain *why*.

## Style

- `ruff` handles formatting and linting (`make format`, `make lint`).
- Prefer querysets with `select_related`/`prefetch_related` in list views;
  tests may assert query counts with `assertNumQueries`.
- Never render user content with `|safe`; use the `markdown` filter, which
  sanitises output.
- New settings must be read through `decouple.config` with a default and
  documented in `.env.example`.

## Reporting security issues

See [SECURITY.md](SECURITY.md).
