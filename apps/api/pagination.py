# File: DjangoVerseHub/apps/api/pagination.py

from rest_framework.pagination import PageNumberPagination, CursorPagination
from rest_framework.response import Response
from collections import OrderedDict


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for API results"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count', self.page.paginator.count),
            ('total_pages', self.page.paginator.num_pages),
            ('current_page', self.page.number),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))


class LargeResultsSetPagination(PageNumberPagination):
    """Pagination for large result sets"""
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 200

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count', self.page.paginator.count),
            ('total_pages', self.page.paginator.num_pages),
            ('current_page', self.page.number),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('page_size', self.page_size),
            ('results', data)
        ]))


class SmallResultsSetPagination(PageNumberPagination):
    """Pagination for small result sets"""
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count', self.page.paginator.count),
            ('total_pages', self.page.paginator.num_pages),
            ('current_page', self.page.number),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))


class CustomCursorPagination(CursorPagination):
    """Cursor pagination for time-ordered data"""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    ordering = '-created_at'
    cursor_query_param = 'cursor'
    
    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))


class ArticlePagination(StandardResultsSetPagination):
    """Pagination specifically for articles"""
    page_size = 15
    max_page_size = 100


class CommentPagination(StandardResultsSetPagination):
    """Pagination specifically for comments"""
    page_size = 25
    max_page_size = 100


class UserPagination(StandardResultsSetPagination):
    """Pagination specifically for users"""
    page_size = 30
    max_page_size = 100


class NotificationPagination(StandardResultsSetPagination):
    """Pagination specifically for notifications"""
    page_size = 20
    max_page_size = 50