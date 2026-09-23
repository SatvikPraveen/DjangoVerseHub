# File: DjangoVerseHub/apps/core/signals.py
"""Domain-event hooks that feed the Prometheus counters in django_verse_hub.metrics."""

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from apps.articles.models import Article
from apps.comments.models import Comment
from apps.notifications.models import Notification
from django_verse_hub import metrics

User = get_user_model()


@receiver(post_save, sender=User, dispatch_uid="core.metrics.user_registered")
def count_user_registered(sender, instance, created, **kwargs):
    if created:
        metrics.users_registered_total.inc()


@receiver(pre_save, sender=Article, dispatch_uid="core.metrics.article_previous_status")
def remember_article_status(sender, instance, **kwargs):
    if instance.pk:
        instance._metrics_previous_status = (
            Article.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
        )
    else:
        instance._metrics_previous_status = None


@receiver(post_save, sender=Article, dispatch_uid="core.metrics.article_published")
def count_article_published(sender, instance, **kwargs):
    previous = getattr(instance, "_metrics_previous_status", None)
    if instance.status == "published" and previous != "published":
        metrics.articles_published_total.inc()


@receiver(post_save, sender=Comment, dispatch_uid="core.metrics.comment_created")
def count_comment_created(sender, instance, created, **kwargs):
    if created:
        metrics.comments_created_total.inc()


@receiver(post_save, sender=Notification, dispatch_uid="core.metrics.notification_created")
def count_notification_created(sender, instance, created, **kwargs):
    if created:
        metrics.notifications_created_total.labels(notification_type=instance.notification_type).inc()
