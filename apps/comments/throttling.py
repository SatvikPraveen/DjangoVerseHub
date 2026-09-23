# File: DjangoVerseHub/apps/comments/throttling.py

from rest_framework.settings import api_settings
from rest_framework.throttling import UserRateThrottle


class CommentCreateThrottle(UserRateThrottle):
    """
    Per-user rate limit for creating comments through the API.

    Configure the rate in settings::

        REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['comments'] = '30/hour'

    When the 'comments' key is absent the throttle is disabled instead of
    raising ImproperlyConfigured on every request. The rate is read from
    ``api_settings`` at request time so ``override_settings`` works in tests.
    """
    scope = 'comments'

    def get_rate(self):
        rates = api_settings.DEFAULT_THROTTLE_RATES or {}
        return rates.get(self.scope)
