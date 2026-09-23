# File: DjangoVerseHub/apps/api/exceptions.py
"""
Uniform API error envelope.

Every error response looks like:
    {"error": {"code": "validation_error", "message": "...", "details": {...}, "request_id": "..."}}
"""

import logging

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler

from django_verse_hub.middleware import get_request_id

logger = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is None:
        if isinstance(exc, IntegrityError):
            logger.warning('integrity error in %s: %s', context.get('view'), exc)
            response = Response(status=status.HTTP_409_CONFLICT)
            code, message, details = 'conflict', 'The request conflicts with existing data.', None
        else:
            return None  # let Django render a 500
    else:
        code = getattr(exc, 'default_code', None) or 'error'
        if isinstance(exc, ValidationError):
            code = 'validation_error'
            message = 'Invalid input.'
            details = response.data
        elif isinstance(exc, (Http404,)):
            code, message, details = 'not_found', 'Not found.', None
        elif isinstance(exc, PermissionDenied):
            code, message, details = 'permission_denied', 'You do not have permission to perform this action.', None
        elif isinstance(exc, APIException):
            detail = response.data.get('detail') if isinstance(response.data, dict) else response.data
            message = str(detail) if detail is not None else exc.default_detail
            details = None if isinstance(response.data, dict) and set(response.data) == {'detail'} else response.data
        else:
            message, details = str(exc), None

    payload = {'error': {'code': code, 'message': message, 'request_id': get_request_id()}}
    if details is not None:
        payload['error']['details'] = details
    response.data = payload
    return response
