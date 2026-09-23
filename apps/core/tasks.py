# File: DjangoVerseHub/apps/core/tasks.py

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

from .models import NewsletterSubscriber

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_newsletter_confirmation(self, subscriber_id):
    """Send the double opt-in confirmation email."""
    try:
        subscriber = NewsletterSubscriber.objects.get(pk=subscriber_id)
    except NewsletterSubscriber.DoesNotExist:
        logger.warning('newsletter confirmation skipped: subscriber %s missing', subscriber_id)
        return False

    base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/')
    context = {
        'site_name': getattr(settings, 'SITE_NAME', 'DjangoVerseHub'),
        'confirm_url': base_url + reverse('core:newsletter_confirm', args=[subscriber.confirmation_token]),
        'unsubscribe_url': base_url + reverse('core:newsletter_unsubscribe', args=[subscriber.confirmation_token]),
    }
    try:
        send_mail(
            subject=f"Confirm your {context['site_name']} newsletter subscription",
            message=render_to_string('core/emails/newsletter_confirm.txt', context),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[subscriber.email],
            html_message=render_to_string('core/emails/newsletter_confirm.html', context),
        )
    except Exception as exc:  # pragma: no cover - network failure path
        logger.exception('newsletter confirmation failed for %s', subscriber.email)
        raise self.retry(exc=exc)
    return True
