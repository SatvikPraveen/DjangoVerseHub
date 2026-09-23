# Concept Index

DjangoVerseHub is a learning codebase. This index maps Django, Django REST Framework, Channels, Celery and operations concepts to the place in the repository where each one is used, so you can read a real implementation instead of a toy example. Paths are relative to the repository root.

## Project layout and settings

| Concept | Where |
| --- | --- |
| Split settings modules that build on a shared base | `django_verse_hub/settings/base.py`, `dev.py`, `prod.py`, `test.py`, `ci.py` |
| Environment-driven configuration with python-decouple (`config()`, `Csv()`) | `django_verse_hub/settings/base.py`, `.env.example` |
| Optional infrastructure chosen at settings time: Redis vs in-memory channel layer and cache, eager Celery without a broker | `django_verse_hub/settings/base.py` (`REDIS_URL`, `CHANNEL_LAYERS`), `dev.py` (`CACHES`, `CELERY_TASK_ALWAYS_EAGER`), `ci.py` |
| Prometheus metrics: django-prometheus middleware, custom `Counter`/`Gauge`, a token- or staff-protected exposition view | `django_verse_hub/metrics.py`, `django_verse_hub/urls.py` (`metrics/`), `apps/core/signals.py` |
| Content-Security-Policy and other security headers assembled from settings (report-only mode, extra sources) | `django_verse_hub/middleware.py` (`SecurityHeadersMiddleware.build_csp`), `django_verse_hub/settings/base.py` (`CSP_*`) |
| Custom middleware with `MiddlewareMixin` (`process_request` / `process_response`) | `django_verse_hub/middleware.py` |
| Request ids via `contextvars` and a `logging.Filter` that stamps every record | `django_verse_hub/middleware.py` (`request_id_var`, `RequestIDFilter`, `RequestIDMiddleware`) |
| `LOGGING` dict config with a JSON formatter for production | `django_verse_hub/settings/base.py`, `prod.py` |
| Liveness and readiness probes | `django_verse_hub/health.py`, wired in `django_verse_hub/urls.py` |
| Custom error handlers and error templates | `django_verse_hub/urls.py` (`handler400`…`handler500`), `templates/errors/` |
| Silencing specific system checks | `django_verse_hub/settings/base.py` (`SILENCED_SYSTEM_CHECKS`) |
| `STORAGES` with WhiteNoise manifest static files | `django_verse_hub/settings/prod.py` |
| Sessions stored in the cache backend | `django_verse_hub/settings/prod.py` (`SESSION_ENGINE`) |
| Sentry SDK with Django, Celery and Redis integrations | `django_verse_hub/settings/prod.py` |
| django-allauth: email login, mandatory verification, social providers, `AccountMiddleware` | `django_verse_hub/settings/base.py`, `django_verse_hub/urls.py` (`accounts/`) |
| Sites framework, sitemaps and robots.txt | `apps/core/sitemaps.py`, `apps/core/urls.py`, `apps/core/views.py` (`robots_txt`) |

## Models and the ORM

| Concept | Where |
| --- | --- |
| Custom user model (`AbstractUser`, `USERNAME_FIELD = "email"`, UUID primary key) and manager | `apps/users/models.py` (`CustomUser`), `apps/users/managers.py` (`CustomUserManager`) |
| One-to-one profile created by a `post_save` signal | `apps/users/models.py` (`Profile`), `apps/users/signals.py` (`create_user_profile`) |
| Self-referential many-to-many through an explicit model with `UniqueConstraint` and `CheckConstraint` | `apps/users/models.py` (`Follow`, `CustomUser.follow/unfollow/followers/following`) |
| Custom `QuerySet` + `Manager.from_queryset` with chainable filters | `apps/articles/managers.py`, `apps/users/managers.py`, `apps/comments/models.py`, `apps/notifications/models.py` |
| Multiple managers on one model (`objects` vs `published`) | `apps/articles/models.py` (`Article.objects`, `Article.published`) |
| Generic relations: `GenericForeignKey`, `GenericRelation`, `ContentType` | `apps/comments/models.py` (`Comment.content_object`), `apps/articles/models.py` (`Article.comments`), `apps/notifications/models.py` (`Notification.content_object`) |
| Atomic counters with `F()` expressions and `Greatest` | `apps/articles/models.py` (`ArticleLike.toggle`, `Article.increment_views`), `apps/comments/signals.py` |
| `transaction.atomic()` and `transaction.on_commit()` | `apps/articles/models.py` (`Article.save`), `apps/comments/signals.py`, `apps/articles/signals.py` |
| `Exists`/`OuterRef` annotations for per-user flags in one query | `apps/articles/managers.py` (`with_user_flags`) |
| Conditional aggregation `Count(..., filter=Q(...))`, `Coalesce`, `Sum` | `apps/articles/managers.py` (`with_article_count`), `apps/users/views.py` (`LeaderboardView`), `apps/core/views.py` (`_home_context`) |
| `select_related` / `prefetch_related` with `Prefetch` objects | `apps/articles/managers.py` (`with_related`), `apps/notifications/models.py` (`with_related`) |
| Properties that read an annotation when present and fall back to a query | `apps/articles/models.py` (`AnnotatedArticleCountMixin`, `Article.comment_count`) |
| Overriding `save()`: slugs, publish timestamps, derived fields, revision snapshots | `apps/articles/models.py` (`Article.save`, `_unique_slug`, `ArticleRevision`) |
| Restoring an earlier version of a record | `apps/articles/models.py` (`ArticleRevision.restore`), `apps/articles/views.py` (`article_revision_restore_view`) |
| Adjacency-list tree (parent FK) built in Python from one query, with depth limit | `apps/comments/models.py` (`build_comment_tree`, `Comment.depth`, `MAX_THREAD_DEPTH`) |
| Soft delete with placeholders for removed nodes | `apps/comments/models.py` (`Comment.soft_delete`, `REMOVED_PLACEHOLDER`) |
| Threshold-based moderation with a per-user unique flag | `apps/comments/models.py` (`Comment.add_flag`, `CommentFlag`) |
| `bulk_create` with pre-filtering (dedupe, preferences) | `apps/notifications/models.py` (`NotificationManager.notify`) |
| Abstract base model, `TextChoices`, `db_table`, `Meta.indexes` and `constraints` | `apps/core/models.py` (`TimeStampedModel`, `ContactMessage`), `apps/comments/models.py` (`CommentFlag.Reason`), model `Meta` classes throughout |
| PostgreSQL full-text search (`SearchVector`, `SearchQuery`, `SearchRank`, `SearchHeadline`) with a vendor check and `icontains` fallback | `apps/articles/search.py` (`search_all`, `ArticleSearchManager`) |
| Migrations for every app plus a drift check | `apps/*/migrations/0001_initial.py`, `Makefile` (`check`), `.github/workflows/ci.yml`, `django_verse_hub/settings/test.py` (`KEEP_MIGRATIONS`) |

## Views, forms and templates

| Concept | Where |
| --- | --- |
| Class-based generic views (`ListView`, `DetailView`, `CreateView`, `UpdateView`, `DeleteView`) and function-based views side by side | `apps/articles/views.py`, `apps/users/views.py`, `apps/comments/views.py` |
| Mixins for shared context and access control | `apps/articles/views.py` (`ArticleSidebarMixin`, `ArticleAuthorRequiredMixin`), `django_verse_hub/permissions.py` (`IsOwnerMixin`, `IsStaffMixin`) |
| Draft visibility rules enforced in the queryset | `apps/articles/managers.py` (`visible_to`), `apps/articles/models.py` (`can_be_viewed_by`, `can_be_edited_by`) |
| Safe redirects with `url_has_allowed_host_and_scheme` | `apps/users/views.py` (`_safe_redirect_target`) |
| One view answering both HTML and JSON (XHR detection) | `apps/users/views.py` (`_wants_json`, `_follow_toggle`), `apps/articles/views.py` (`_is_ajax`, `_toggle_response`) |
| `ModelForm` with `clean_<field>()`, injected user and file validation | `apps/articles/forms.py` (`ArticleForm`), `apps/users/forms.py` (`ProfileForm`), `apps/comments/forms.py` |
| Custom `AuthenticationForm` accepting email or username | `apps/users/forms.py` (`CustomLoginForm`), `apps/users/utils.py` (`authenticate_by_identifier`) |
| Honeypot anti-spam field as a form mixin | `apps/core/forms.py` (`HoneypotMixin`) |
| Double opt-in flow with unguessable tokens | `apps/core/models.py` (`NewsletterSubscriber`), `apps/core/views.py` (`newsletter_*`), `apps/core/tasks.py` |
| Context processors with `SimpleLazyObject` so unused values cost no queries | `apps/core/context_processors.py` |
| Custom template tags and filters: `simple_tag`, `filter`, `inclusion_tag` | `apps/core/templatetags/core_tags.py`, `apps/comments/templatetags/comment_tags.py` (`render_comments`) |
| Template fragment caching with `{% cache %}` | `templates/includes/cache/user_sidebar.html`, `templates/includes/cache/popular_articles.html` |
| Per-view caching with `cache_page` | `apps/articles/views.py` (`trending_articles_view`), `apps/core/views.py` (`robots_txt`) |
| Manual `Paginator` use and `ListView.paginate_by` | `apps/core/views.py` (`search_view`), `apps/articles/views.py` (`CategoryDetailView`) |
| Syndication framework: RSS 2.0 and Atom feeds (`Feed`, `Atom1Feed`) with per-object feeds | `apps/articles/feeds.py`, `apps/articles/urls.py`, `templates/base.html` (`rel="alternate"`) |
| Conditional GET: weak `ETag` from content timestamps, `If-None-Match` → 304 | `apps/articles/views.py` (`ArticleDetailView.get`, `compute_etag`) |
| Markdown rendering with an HTML sanitiser (nh3 allow-lists per profile) and content-hash caching | `apps/core/markdown.py`, `apps/core/templatetags/core_tags.py` (`markdown`, `markdown_text` filters) |
| JSON-LD structured data (schema.org `BlogPosting`) from a template tag | `apps/articles/templatetags/article_tags.py` (`article_json_ld`) |
| Signed, expiring tokens with `django.core.signing` (salts, `max_age`, invalidation by password fingerprint) | `apps/users/utils.py` (`make_email_verification_token`, `load_password_reset_token`) |
| Account lifecycle: email verification, password reset with `SetPasswordForm`, GDPR export, delete-or-anonymise | `apps/users/views.py` (`verify_email_view`, `password_reset_confirm_view`, `export_data_view`, `delete_account_view`), `apps/users/utils.py` (`build_user_export`, `anonymise_user`) |
| `cache.add` as an atomic cooldown / "seen once" guard | `apps/users/views.py` (`resend_verification_view`), `apps/articles/models.py` (`increment_views`) |
| Image validation and resizing with Pillow at save time | `apps/users/models.py` (`Profile.save`, `_resize_image`), `apps/articles/tasks.py` (`process_article_images`) |
| Admin customisation: actions, list filters, inlines | `apps/articles/admin.py`, `apps/comments/admin.py`, `apps/core/admin.py`, `apps/notifications/admin.py`, `apps/users/admin.py` |
| Management commands with arguments, `transaction.atomic` and styled output | `apps/core/management/commands/generate_demo_data.py`, `cleanup_unused_media.py` |
| Editable key/value site settings with cache invalidation on save | `apps/core/models.py` (`SiteSetting.public_settings`) |

## Django REST Framework

| Concept | Where |
| --- | --- |
| `ModelViewSet` / `GenericViewSet` with mixins, registered on a `DefaultRouter`; a custom router with optional trailing slash | `apps/api/routers.py`, `apps/users/views.py` (`UserViewSet`), `apps/articles/views.py` |
| Extra routes with `@action(detail=True/False)` and per-action permissions | `apps/users/views.py` (`follow`, `followers`), `apps/articles/views.py` (`like`, `bookmark`, `revisions`), `apps/comments/views.py` (`tree`, `flag`) |
| Choosing the serializer per action (`get_serializer_class`) and per-action permissions (`get_permissions`) | `apps/articles/views.py` (`ArticleViewSet`), `apps/users/views.py`, `apps/comments/views.py` |
| Serializer techniques: `SerializerMethodField`, `source=`, nested read-only serializers, write-only fields, `read_only_fields` | `apps/articles/serializers.py`, `apps/users/serializers.py`, `apps/notifications/serializers.py` |
| Privacy filtering in `to_representation` | `apps/users/serializers.py` (`UserSerializer`, `ProfileSerializer`, `PublicProfileSerializer`) |
| Custom `ListSerializer` that primes data for a whole page in one query | `apps/articles/serializers.py` (`ArticleListSerializerMany`), `apps/articles/models.py` (`attach_comment_counts`) |
| Passing batch data through `serializer.context` to avoid N+1 queries | `apps/comments/views.py` (`_prime_batch`, `get_serializer_context`), `apps/comments/serializers.py` (`_ViewerFieldsMixin`) |
| Object-level permissions (`has_object_permission`) | `apps/api/permissions.py`, `apps/comments/permissions.py` (`IsCommentAuthorOrStaff`), `apps/users/views.py` (`IsSelfOrReadOnly`), `django_verse_hub/permissions.py` |
| Token, session and JWT authentication (simplejwt with rotation and blacklist) | `django_verse_hub/settings/base.py` (`REST_FRAMEWORK`, `SIMPLE_JWT`), `apps/api/urls.py`, `apps/api/views.py` (`LoginAPIView`, `LogoutAPIView`) |
| Throttle scopes and custom throttle classes (including reading the rate at request time) | `django_verse_hub/settings/base.py` (`DEFAULT_THROTTLE_RATES`), `apps/api/throttling.py`, `apps/comments/throttling.py` (`CommentCreateThrottle`) |
| Filtering, search and ordering backends (`django-filter`, `SearchFilter`, `OrderingFilter`) | `apps/articles/views.py` (`ArticleViewSet`), `apps/comments/views.py` (`CommentViewSet`) |
| Custom pagination classes and extra keys in the paginated response | `apps/notifications/views.py` (`NotificationPagination`), `apps/comments/views.py` (`CommentPagination`), `apps/api/pagination.py` |
| Custom exception handler producing a uniform error envelope | `apps/api/exceptions.py` (`api_exception_handler`) |
| OpenAPI 3 schema with drf-spectacular (`extend_schema`, `OpenApiParameter`, tags, Swagger/ReDoc views) | `apps/api/views.py`, `apps/api/urls.py`, `django_verse_hub/settings/base.py` (`SPECTACULAR_SETTINGS`) |
| Plain `APIView` / `@api_view` endpoints with caching | `apps/api/views.py` (`SearchAPIView`, `TrendingContentAPIView`, `api_stats`, `user_dashboard`) |
| Function-based DRF views (`generics.ListAPIView`, `RetrieveUpdateAPIView`, `@api_view`) | `apps/notifications/views.py` |

## Channels and WebSockets

| Concept | Where |
| --- | --- |
| ASGI entry point: `ProtocolTypeRouter`, `URLRouter`, `AuthMiddlewareStack`, `AllowedHostsOriginValidator` | `django_verse_hub/asgi.py` |
| WebSocket URL routing | `apps/notifications/routing.py` |
| `AsyncWebsocketConsumer` with per-user groups, JSON protocol and `database_sync_to_async` | `apps/notifications/consumers.py` (`NotificationConsumer`) |
| Sending to a group from synchronous code with `async_to_sync(channel_layer.group_send)` | `apps/notifications/signals.py` (`send_notification_to_user`) |
| Redis channel layer in dev/prod, in-memory layer in tests | `django_verse_hub/settings/base.py` (`CHANNEL_LAYERS`), `django_verse_hub/settings/test.py` |
| Browser client: reconnect with exponential backoff, HTTP fallback | `static/js/notifications.js`, `apps/notifications/templates/notifications/notifications_ws.html` |
| Testing consumers with `WebsocketCommunicator` on a `TransactionTestCase` | `apps/notifications/tests/test_consumers.py` |

## Celery and background work

| Concept | Where |
| --- | --- |
| Celery application, `config_from_object` with the `CELERY_` namespace, `autodiscover_tasks` | `django_verse_hub/celery.py`, `django_verse_hub/__init__.py` |
| `@shared_task` with `bind=True`, `max_retries` and `self.retry` on transport errors only | `apps/comments/tasks.py` (`_deliver`), `apps/users/tasks.py`, `apps/notifications/tasks.py` |
| Beat schedule and django-celery-beat's `DatabaseScheduler` | `django_verse_hub/celery.py` (`beat_schedule`), `django_verse_hub/settings/base.py` (`CELERY_BEAT_SCHEDULER`) |
| Routing tasks to named queues | `django_verse_hub/settings/base.py` (`CELERY_TASK_ROUTES`), `scripts/docker-entrypoint.sh` (`-Q`) |
| Eager execution for tests and local development | `django_verse_hub/settings/test.py`, `django_verse_hub/settings/dev.py` (`CELERY_TASK_ALWAYS_EAGER`) |
| Enqueueing only after the transaction commits | `apps/comments/signals.py` (`transaction.on_commit(dispatch)`), `apps/articles/signals.py` |
| Never letting a broker outage break a request | `apps/users/signals.py` (`create_user_profile`), `apps/notifications/signals.py` (`queue_notification_email`) |
| Digest emails with `EmailMultiAlternatives` and text + HTML templates | `apps/notifications/tasks.py` (`_send_digest`), `apps/notifications/templates/notifications/emails/` |
| Periodic housekeeping tasks | `apps/notifications/tasks.py` (`cleanup_old_notifications`), `apps/users/tasks.py` (`cleanup_unverified_users`), `apps/comments/tasks.py` (`cleanup_old_flagged_comments`) |

## Signals and event flow

| Concept | Where |
| --- | --- |
| `post_save`, `post_delete`, `pre_save`, `m2m_changed` receivers with `dispatch_uid` | `apps/articles/signals.py`, `apps/notifications/signals.py`, `apps/comments/signals.py`, `apps/users/signals.py` |
| Registering receivers in `AppConfig.ready()` and wiring optional models lazily with `apps.get_model` | `apps/notifications/apps.py`, `apps/notifications/signals.py` (`connect_optional_like_signals`) |
| Detecting a state transition (draft → published) with `pre_save` + `post_save` | `apps/notifications/signals.py` (`remember_previous_status`, `create_article_published_notification`) |
| One `notify()` helper that creates, de-duplicates, respects preferences and delivers | `apps/notifications/signals.py` (`notify`, `dispatch_notifications`), `apps/notifications/models.py` (`NotificationManager.notify`) |
| Cache invalidation from signals | `apps/articles/signals.py`, `apps/users/signals.py` |

## Caching

| Concept | Where |
| --- | --- |
| Low-level cache API: `get`/`set`/`delete_many` for computed views and rendered Markdown | `apps/api/views.py` (`api_stats`, `TrendingContentAPIView`), `apps/core/views.py` (`_home_context`), `apps/core/markdown.py` (`render_markdown`) |
| Cache-aside helpers and key builders | `apps/articles/cache.py` (`ArticleCacheManager`), `apps/users/cache.py`, `django_verse_hub/utils.py` (`get_or_create_cache`) |
| Cache backends per environment: Redis (when `REDIS_URL` is set) with key prefixes, local memory otherwise | `django_verse_hub/settings/dev.py`, `prod.py`, `ci.py`, `test.py` |

## Security

| Concept | Where |
| --- | --- |
| Response security headers (`X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`) set with `setdefault` so views can override | `django_verse_hub/middleware.py` (`SecurityHeadersMiddleware.process_response`) |
| Domain-event metrics from signal receivers (state-transition detection for "published") | `apps/core/signals.py`, `apps/core/apps.py` (`ready`) |
| Per-IP rate limiting backed by the cache | `django_verse_hub/middleware.py` (`RateLimitMiddleware`) |
| Production hardening (`SECURE_*`, secure cookies, `SECURE_PROXY_SSL_HEADER`, `sslmode=require`) | `django_verse_hub/settings/prod.py` |
| Privacy-aware public profiles and search results | `apps/users/serializers.py`, `apps/users/views.py` (`UserViewSet.get_queryset`), `apps/api/views.py` (`SearchAPIView`) |
| Password validators, prohibited usernames and `validate_password` in serializers | `django_verse_hub/settings/base.py`, `apps/users/serializers.py` (`UserRegistrationSerializer`) |

## Testing and quality

| Concept | Where |
| --- | --- |
| pytest-django configuration and shared fixtures | `pyproject.toml` (`[tool.pytest.ini_options]`), `tests/conftest.py` |
| Fast test settings: SQLite in-memory, disabled migrations, MD5 hasher, locmem cache, eager Celery | `django_verse_hub/settings/test.py` |
| Testing against PostgreSQL and Redis in CI with real migrations | `django_verse_hub/settings/ci.py`, `.github/workflows/ci.yml` (`postgres` job) |
| Query-count and N+1 tests | `tests/test_performance.py` |
| Cross-app integration tests, URL resolution tests | `tests/test_integration.py`, `tests/test_urls.py` |
| Infrastructure tests: probes, request ids, error envelope, docs endpoints | `tests/test_infrastructure.py` |
| Hardening tests: security headers, metrics endpoint, conditional GET | `tests/test_hardening.py` |
| Feature tests for feeds, Markdown sanitising, management commands and account flows | `apps/articles/tests/test_feeds.py`, `apps/core/tests/test_markdown.py`, `apps/core/tests/test_management.py`, `apps/users/tests/test_account.py` |
| `override_settings` and `unittest.mock` in tests | `tests/test_infrastructure.py`, `apps/notifications/tests/` |
| Coverage configuration with `fail_under` | `pyproject.toml` (`[tool.coverage.*]`) |
| Linting and formatting with ruff, pre-commit hooks, mypy with django-stubs | `pyproject.toml` (`[tool.ruff]`, `[tool.mypy]`), `.pre-commit-config.yaml`, `Makefile` |

## Operations

| Concept | Where |
| --- | --- |
| Multi-stage Dockerfile: wheel builder, non-root user, build-time `collectstatic`, `HEALTHCHECK` | `Dockerfile` |
| Entrypoint script that waits for the database and dispatches `web`/`asgi`/`worker`/`beat`/`migrate` | `scripts/docker-entrypoint.sh` |
| Compose with YAML anchors, health-checked dependencies and an optional `proxy` profile | `docker-compose.yml`, `docker-compose.prod.yml` |
| nginx as reverse proxy: static/media, WebSocket upgrade for `/ws/`, request-id propagation | `nginx/nginx.conf` |
| gunicorn (WSGI) and daphne (ASGI) side by side | `django_verse_hub/wsgi.py`, `django_verse_hub/asgi.py`, `scripts/docker-entrypoint.sh` |
| CI matrix across Python versions with pip caching and Docker build validation | `.github/workflows/ci.yml` |
| Makefile as the task runner | `Makefile` |
