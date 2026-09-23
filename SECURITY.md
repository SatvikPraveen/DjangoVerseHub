# Security Policy

## Reporting a vulnerability

Please do not open a public issue for security problems. Email
satvikpraveen707@gmail.com with a description, reproduction steps and the
affected version or commit. You will get an acknowledgement within a few
days and a fix or mitigation plan once the report is confirmed.

## What is in place

- Email and password login with Django's validators, signed and expiring
  email-verification and password-reset tokens, and allauth rate limits on
  failed logins.
- API authentication via JWT (rotating refresh tokens with blacklisting),
  DRF tokens or sessions; per-scope throttling; a uniform error envelope
  that never leaks stack traces.
- Object-level permissions on users, profiles, articles, comments and
  notifications, with tests asserting that private profiles, drafts and
  other users' notifications are not readable.
- User-supplied Markdown is sanitised with an allow-list (`apps/core/markdown.py`)
  before rendering.
- Content Security Policy, `frame-ancestors 'none'`, `Permissions-Policy`,
  HSTS and secure cookies in production settings; per-IP rate limiting
  middleware; request IDs on every response for incident tracing.
- Accounts can export their data and delete or anonymise themselves.

## Supported versions

Only the `main` branch receives fixes.
