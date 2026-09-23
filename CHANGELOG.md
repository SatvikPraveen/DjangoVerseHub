# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.1.0] - 2026-09-23

The project previously existed as a generated scaffold that did not start
and whose test suite had 106 failures. This release makes it a working,
production-oriented application.

### Fixed
- Project boot with current django-allauth (missing AccountMiddleware).
- Template syntax across 15 templates (tags wrapped across lines by a
  formatter; duplicate nested `title` blocks in the base template).
- Web login never authenticated; API routes for users did not resolve.
- Comment emails crashed on every comment; notification signals referenced
  a nonexistent `Post` model.
- Drafts were readable by anyone; any authenticated user could edit or
  delete any other user via the API; private profile data leaked through
  serializers; open redirect on login.
- Generic `object_id` fields stored as text against UUID keys, which broke
  joins and counts.
- Content Security Policy blocked the CDN the templates actually use.
- JWT bearer tokens were rejected by resource viewsets.
- Management commands lived outside any installed app and were unreachable.
- Missing static assets referenced by templates (would break production
  `collectstatic`).

### Added
- `core` app: landing page, global search, informational and legal pages,
  contact and feedback forms, double opt-in newsletter, site settings,
  sitemap.xml, robots.txt, shared template tags, demo data generator.
- Users: follow system, leaderboard, activity feed, email verification,
  password reset, GDPR data export, account deletion/anonymisation.
- Articles: likes, bookmarks, revision history with restore, deduplicated
  view counting, related articles, RSS/Atom feeds, JSON-LD structured
  data, conditional GET with ETags.
- Comments: depth-limited threading, flag-based moderation threshold,
  atomic likes, edit window, `{% render_comments %}` tag, scoped throttle.
- Notifications: deduplicated fan-out with preferences, WebSocket consumer
  with acks and reconnecting client, daily/weekly digests, cleanup task.
- API: JWT (create/refresh/verify/blacklist), OpenAPI 3 via
  drf-spectacular with Swagger UI and ReDoc, uniform error envelope,
  rewritten search/stats/trending/dashboard endpoints.
- Sanitised Markdown rendering for articles and comments.
- Operations: liveness/readiness probes, request IDs in every response and
  log line, JSON logging in production, Prometheus `/metrics/`, working
  CSP and modern security headers, configurable rate limiting.
- Tooling: GitHub Actions CI (lint, Python 3.10-3.12, PostgreSQL job,
  Docker build), multi-stage Dockerfile with entrypoint, dev and prod
  compose stacks with nginx, Makefile, pre-commit, ruff, dependabot.
- Initial migrations for every app and a migration drift check.
- 680+ tests, passing on SQLite and PostgreSQL.

### Changed
- Settings consolidated into `base/dev/prod/test/ci`; unused duplicate
  settings modules removed. Local development runs without Redis.
- drf-yasg replaced by drf-spectacular.
- Requirements files corrected and pinned to Django 4.2.

## [1.0.0] - initial scaffold
