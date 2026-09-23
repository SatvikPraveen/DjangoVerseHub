# File: DjangoVerseHub/apps/core/management/commands/generate_demo_data.py
"""
Populate a development database with realistic, interlinked demo content.

    python manage.py generate_demo_data                 # defaults
    python manage.py generate_demo_data --users 30 --articles 120 --seed 42
    python manage.py generate_demo_data --clear         # remove previous demo data first

Everything created here is tagged with the DEMO_EMAIL_DOMAIN so --clear can
remove it without touching real accounts. Notifications are produced by the
regular signal handlers (comments, likes, follows, publishing), so the demo
exercises the same code paths as production.
"""

import random
from datetime import timedelta

from faker import Faker

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.articles.models import Article, ArticleLike, Bookmark, Category, Tag
from apps.comments.models import Comment
from apps.core.models import SiteSetting
from apps.notifications.models import Notification
from apps.users.models import Follow

User = get_user_model()

DEMO_EMAIL_DOMAIN = "demo.djangoversehub.local"
DEMO_PASSWORD = "demo-password-123"

CATEGORIES = [
    ("Django", "Framework internals, ORM, views, forms and everything in between."),
    ("Python", "Language features, tooling and idioms."),
    ("REST APIs", "Designing and building APIs with Django REST Framework."),
    ("Async & Real-time", "Channels, WebSockets, ASGI and background work with Celery."),
    ("Testing", "pytest, factories, fixtures and CI."),
    ("Deployment", "Docker, gunicorn, nginx, observability and operations."),
    ("Databases", "PostgreSQL, indexes, migrations and query performance."),
    ("Frontend", "Templates, HTMX, Bootstrap and progressive enhancement."),
]

TAGS = [
    "orm",
    "querysets",
    "migrations",
    "drf",
    "serializers",
    "permissions",
    "channels",
    "websockets",
    "celery",
    "redis",
    "postgresql",
    "caching",
    "docker",
    "pytest",
    "security",
    "performance",
    "templates",
    "forms",
    "signals",
    "middleware",
    "asgi",
    "type-hints",
    "logging",
    "ci",
]

TITLE_PATTERNS = [
    "Understanding {topic} in Django",
    "{topic}: a practical guide",
    "How we cut {metric} by {pct}% with {topic}",
    "{n} things I wish I knew about {topic}",
    "Stop doing this with {topic}",
    "From zero to production with {topic}",
    "A deep dive into {topic}",
    "{topic} patterns for large Django projects",
]

TOPICS = [
    "select_related",
    "prefetch_related",
    "database indexes",
    "Celery beat",
    "Channels consumers",
    "DRF viewsets",
    "JWT authentication",
    "signals",
    "custom user models",
    "generic relations",
    "full-text search",
    "caching strategies",
    "middleware",
    "class-based views",
    "Docker Compose",
    "structured logging",
    "rate limiting",
    "migrations",
    "transactions",
    "F expressions",
]


class Command(BaseCommand):
    help = "Generate interlinked demo users, articles, comments, likes, bookmarks and follows."

    def add_arguments(self, parser):
        parser.add_argument("--users", type=int, default=25, help="Number of demo users (default: 25)")
        parser.add_argument("--articles", type=int, default=80, help="Number of articles (default: 80)")
        parser.add_argument("--comments", type=int, default=300, help="Number of comments (default: 300)")
        parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducible output")
        parser.add_argument("--clear", action="store_true", help="Delete previously generated demo data first")
        parser.add_argument(
            "--admin", action="store_true", help=f"Also create admin@{DEMO_EMAIL_DOMAIN} / {DEMO_PASSWORD}"
        )

    # ------------------------------------------------------------------ main
    def handle(self, *args, **options):
        if options["seed"] is not None:
            random.seed(options["seed"])
            Faker.seed(options["seed"])
        self.fake = Faker()

        if options["clear"]:
            self.clear_demo_data()

        with transaction.atomic():
            users = self.create_users(options["users"], options["admin"])
            categories = self.create_categories()
            tags = self.create_tags()
            articles = self.create_articles(options["articles"], users, categories, tags)
            self.create_follows(users)
            self.create_engagement(users, articles)
            self.create_comments(options["comments"], users, articles)
            self.create_site_settings()

        self.print_summary()

    # ------------------------------------------------------------------ steps
    def clear_demo_data(self):
        demo_users = User.objects.filter(email__endswith="@" + DEMO_EMAIL_DOMAIN)
        count = demo_users.count()
        # Cascades remove profiles, articles, comments, likes, bookmarks, follows and notifications.
        demo_users.delete()
        Category.objects.filter(name__in=[name for name, _ in CATEGORIES], articles__isnull=True).delete()
        Tag.objects.filter(name__in=TAGS, articles__isnull=True).delete()
        self.stdout.write(self.style.WARNING(f"Removed {count} demo users and their content"))

    def create_users(self, count, with_admin):
        users = []
        if with_admin and not User.objects.filter(email=f"admin@{DEMO_EMAIL_DOMAIN}").exists():
            admin = User.objects.create_superuser(
                email=f"admin@{DEMO_EMAIL_DOMAIN}",
                username="admin",
                password=DEMO_PASSWORD,
                first_name="Demo",
                last_name="Admin",
                email_verified=True,
            )
            users.append(admin)

        existing = set(User.objects.values_list("username", flat=True))
        for _ in range(count):
            first, last = self.fake.first_name(), self.fake.last_name()
            base = slugify(f"{first}{last}")[:20] or "user"
            username = base
            while username in existing:
                username = f"{base}{random.randint(1, 9999)}"
            existing.add(username)
            user = User.objects.create_user(
                email=f"{username}@{DEMO_EMAIL_DOMAIN}",
                username=username,
                password=DEMO_PASSWORD,
                first_name=first,
                last_name=last,
                email_verified=random.random() < 0.8,
            )
            user.date_joined = timezone.now() - timedelta(days=random.randint(1, 400))
            user.last_login = user.date_joined + timedelta(days=random.randint(0, 30))
            user.save(update_fields=["date_joined", "last_login"])

            profile = user.profile
            profile.bio = self.fake.sentence(nb_words=random.randint(8, 20))
            profile.location = self.fake.city()
            profile.website = self.fake.url() if random.random() < 0.4 else ""
            profile.github = f"https://github.com/{username}" if random.random() < 0.6 else ""
            profile.is_public = random.random() < 0.9
            profile.theme = random.choice(["light", "dark"])
            profile.save()
            users.append(user)
        self.stdout.write(f"Users: {len(users)}")
        return users

    def create_categories(self):
        categories = []
        for name, description in CATEGORIES:
            category, _ = Category.objects.get_or_create(name=name, defaults={"description": description})
            categories.append(category)
        self.stdout.write(f"Categories: {len(categories)}")
        return categories

    def create_tags(self):
        tags = [Tag.objects.get_or_create(name=name)[0] for name in TAGS]
        self.stdout.write(f"Tags: {len(tags)}")
        return tags

    def _title(self):
        return random.choice(TITLE_PATTERNS).format(
            topic=random.choice(TOPICS),
            metric=random.choice(["query time", "p95 latency", "memory"]),
            pct=random.choice([30, 42, 60, 75]),
            n=random.choice([5, 7, 10]),
        )

    def _content(self):
        paragraphs = [self.fake.paragraph(nb_sentences=random.randint(4, 9)) for _ in range(random.randint(5, 12))]
        code = (
            "\n\n```python\nfrom django.db.models import Count\n\n"
            "qs = Article.objects.annotate(n=Count('comments')).order_by('-n')\n```\n\n"
        )
        insert_at = random.randint(1, len(paragraphs) - 1)
        return "\n\n".join(paragraphs[:insert_at]) + code + "\n\n".join(paragraphs[insert_at:])

    def create_articles(self, count, users, categories, tags):
        authors = [u for u in users if not u.is_superuser] or users
        articles = []
        for _ in range(count):
            author = random.choice(authors)
            status = random.choices(["published", "draft", "archived"], weights=[80, 15, 5])[0]
            created = timezone.now() - timedelta(days=random.randint(0, 365), hours=random.randint(0, 23))
            article = Article(
                title=self._title(),
                author=author,
                category=random.choice(categories),
                summary=self.fake.sentence(nb_words=random.randint(12, 25)),
                content=self._content(),
                status=status,
                is_featured=random.random() < 0.08,
                allow_comments=random.random() < 0.95,
            )
            article.save()
            # Backdate after save so the slug/publish logic runs first.
            Article.objects.filter(pk=article.pk).update(
                created_at=created,
                updated_at=created,
                published_at=created if status == "published" else None,
                views_count=random.randint(0, 2500) if status == "published" else 0,
            )
            article.tags.set(random.sample(tags, k=random.randint(1, 4)))
            articles.append(article)
        self.stdout.write(f"Articles: {len(articles)}")
        return articles

    def create_follows(self, users):
        created = 0
        for user in users:
            for target in random.sample(users, k=min(len(users) - 1, random.randint(0, 6))):
                if target != user:
                    _, was_created = Follow.objects.get_or_create(follower=user, following=target)
                    created += was_created
        self.stdout.write(f"Follows: {created}")

    def create_engagement(self, users, articles):
        published = [a for a in articles if a.status == "published"]
        likes = bookmarks = 0
        for article in published:
            for user in random.sample(users, k=min(len(users), random.randint(0, 12))):
                if user != article.author and not ArticleLike.objects.filter(user=user, article=article).exists():
                    ArticleLike.toggle(user, article)
                    likes += 1
                if random.random() < 0.25 and not Bookmark.objects.filter(user=user, article=article).exists():
                    Bookmark.toggle(user, article)
                    bookmarks += 1
        self.stdout.write(f"Likes: {likes}, Bookmarks: {bookmarks}")

    def create_comments(self, count, users, articles):
        published = [a for a in articles if a.status == "published" and a.allow_comments]
        if not published:
            return
        comments = []
        for _ in range(count):
            article = random.choice(published)
            parent = None
            if comments and random.random() < 0.35:
                candidate = random.choice(comments)
                if candidate.content_object == article and candidate.can_reply:
                    parent = candidate
                else:
                    article = candidate.content_object
                    parent = candidate if candidate.can_reply else None
            comment = Comment.objects.create(
                content_object=article,
                author=random.choice(users),
                parent=parent,
                content=self.fake.paragraph(nb_sentences=random.randint(1, 4)),
            )
            comments.append(comment)
        # Some comment likes
        liked = 0
        for comment in random.sample(comments, k=min(len(comments), count // 3)):
            liker = random.choice(users)
            if liker != comment.author:
                comment.toggle_like(liker)
                liked += 1
        self.stdout.write(f"Comments: {len(comments)}, Comment likes: {liked}")

    def create_site_settings(self):
        SiteSetting.objects.get_or_create(
            key="announcement",
            defaults={"value": "Welcome to the DjangoVerseHub demo. Log in with any demo user.", "is_public": True},
        )

    def print_summary(self):
        self.stdout.write(self.style.SUCCESS("\nDemo data ready"))
        self.stdout.write(f"  users:         {User.objects.count()}")
        self.stdout.write(f"  articles:      {Article.objects.count()} ({Article.published.count()} published)")
        self.stdout.write(f"  comments:      {Comment.objects.count()}")
        self.stdout.write(f"  follows:       {Follow.objects.count()}")
        self.stdout.write(f"  notifications: {Notification.objects.count()}")
        self.stdout.write(f"\nLog in with any *@{DEMO_EMAIL_DOMAIN} address and password '{DEMO_PASSWORD}'.")
