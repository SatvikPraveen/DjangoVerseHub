# File: DjangoVerseHub/apps/api/views.py
"""
Cross-cutting API endpoints: root, health, stats, auth, search, dashboard, trending.
Resource endpoints live in each app's viewsets and are mounted through apps.api.routers.
"""

import json
from datetime import timedelta

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db.models import Count, Q, Sum
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.reverse import reverse
from rest_framework.views import APIView

from apps.articles.models import Article, Category, Tag
from apps.comments.models import Comment
from apps.notifications.models import Notification
from apps.users.models import CustomUser

from .serializers import (
    AuthUserSerializer,
    LoginSerializer,
    SearchArticleSerializer,
    SearchQuerySerializer,
    SearchTagSerializer,
    SearchUserSerializer,
    TokenResponseSerializer,
)
from .throttling import LoginRateThrottle, SearchRateThrottle

STATS_CACHE_KEY = 'api:stats:v2'
TRENDING_CACHE_KEY = 'api:trending:v2'


@extend_schema(tags=['meta'], responses={200: dict})
@api_view(['GET'])
@permission_classes([AllowAny])
def api_root(request, format=None):
    """Entry point listing the main collections and auth options."""
    return Response(
        {
            'name': 'DjangoVerseHub API',
            'version': getattr(settings, 'APP_VERSION', 'unknown'),
            'endpoints': {
                'users': reverse('api:user-list', request=request, format=format),
                'profiles': reverse('api:profile-list', request=request, format=format),
                'articles': reverse('api:article-list', request=request, format=format),
                'categories': reverse('api:category-list', request=request, format=format),
                'tags': reverse('api:tag-list', request=request, format=format),
                'comments': reverse('api:comment-list', request=request, format=format),
                'notifications': reverse('api:notification-list', request=request, format=format),
                'search': reverse('api:search', request=request, format=format),
                'trending': reverse('api:trending', request=request, format=format),
                'stats': reverse('api:api_stats', request=request, format=format),
                'health': reverse('api:health_check', request=request, format=format),
            },
            'authentication': {
                'token': 'Authorization: Token <key>  (POST /api/v1/auth/token/)',
                'jwt': 'Authorization: Bearer <access>  (POST /api/v1/auth/jwt/create/)',
                'session': 'Cookie-based, for the web client',
            },
            'docs': reverse('api:schema_swagger_ui', request=request, format=format),
            'schema': reverse('api:schema', request=request, format=format),
        }
    )


@extend_schema(tags=['meta'], responses={200: dict, 503: dict})
@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """API health check: delegates to the project readiness probe."""
    from django_verse_hub.health import readiness

    probe = readiness(request._request)
    data = json.loads(probe.content)
    data['timestamp'] = timezone.now().isoformat()
    return Response(data, status=probe.status_code)


def _compute_stats():
    thirty_days_ago = timezone.now() - timedelta(days=30)
    return {
        'users': {
            'total': CustomUser.objects.count(),
            'active': CustomUser.objects.filter(is_active=True).count(),
            'verified': CustomUser.objects.filter(email_verified=True).count(),
            'new_last_30_days': CustomUser.objects.filter(date_joined__gte=thirty_days_ago).count(),
        },
        'articles': {
            'total': Article.objects.count(),
            'published': Article.published.count(),
            'new_last_30_days': Article.objects.filter(created_at__gte=thirty_days_ago).count(),
            'total_views': Article.published.aggregate(total=Sum('views_count'))['total'] or 0,
        },
        'comments': {
            'total': Comment.objects.filter(is_active=True).count(),
            'new_last_30_days': Comment.objects.filter(is_active=True, created_at__gte=thirty_days_ago).count(),
        },
        'categories': Category.objects.filter(is_active=True).count(),
        'tags': Tag.objects.count(),
        'notifications': Notification.objects.count(),
        'generated_at': timezone.now().isoformat(),
    }


@extend_schema(tags=['meta'], responses={200: dict})
@api_view(['GET'])
@permission_classes([AllowAny])
def api_stats(request):
    """Platform-wide statistics, cached for five minutes."""
    stats = cache.get(STATS_CACHE_KEY)
    if stats is None:
        stats = _compute_stats()
        cache.set(STATS_CACHE_KEY, stats, 300)
    return Response(stats)


class SearchAPIView(APIView):
    """Global search across published articles, active users and tags."""

    permission_classes = [AllowAny]
    throttle_classes = [SearchRateThrottle]

    @extend_schema(
        tags=['search'],
        parameters=[
            OpenApiParameter('q', str, required=True, description='Search terms'),
            OpenApiParameter('type', str, enum=['all', 'articles', 'users', 'tags']),
            OpenApiParameter('limit', int, description='Max results per collection (1-50)'),
        ],
        responses={200: dict},
    )
    def get(self, request, format=None):
        params = SearchQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        query = params.validated_data['q'].strip()
        search_type = params.validated_data['type']
        limit = params.validated_data['limit']

        results = {}
        if search_type in ('all', 'articles'):
            articles = (
                Article.published.filter(
                    Q(title__icontains=query) | Q(summary__icontains=query) | Q(content__icontains=query)
                )
                .select_related('author', 'category')
                .order_by('-published_at')[:limit]
            )
            results['articles'] = SearchArticleSerializer(articles, many=True).data

        if search_type in ('all', 'users'):
            users = (
                CustomUser.objects.filter(is_active=True)
                .filter(
                    Q(username__icontains=query)
                    | Q(first_name__icontains=query)
                    | Q(last_name__icontains=query)
                    | Q(profile__bio__icontains=query)
                )
                .filter(Q(profile__is_public=True) | Q(profile__isnull=True))
                .select_related('profile')
                .order_by('username')
                .distinct()[:limit]
            )
            results['users'] = SearchUserSerializer(users, many=True).data

        if search_type in ('all', 'tags'):
            tags = (
                Tag.objects.filter(name__icontains=query)
                .annotate(num_articles=Count('articles', filter=Q(articles__status='published')))
                .order_by('-num_articles', 'name')[:limit]
            )
            results['tags'] = SearchTagSerializer(tags, many=True).data

        return Response(
            {
                'query': query,
                'type': search_type,
                'results': results,
                'total_results': sum(len(items) for items in results.values()),
            }
        )


class LoginAPIView(GenericAPIView):
    """Exchange email + password for a DRF token (kept for simple clients; prefer JWT)."""

    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]
    serializer_class = LoginSerializer

    @extend_schema(tags=['auth'], responses={200: TokenResponseSerializer})
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key, 'user': AuthUserSerializer(user).data})


class LogoutAPIView(APIView):
    """Revoke the caller's DRF token. JWT clients should discard their tokens client-side."""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=['auth'], request=None, responses={204: None})
    def post(self, request, *args, **kwargs):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=['users'], responses={200: dict})
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_dashboard(request):
    """Aggregate counters for the signed-in user's dashboard."""
    user = request.user
    week_ago = timezone.now() - timedelta(days=7)
    article_stats = Article.objects.filter(author=user).aggregate(
        total=Count('id'),
        published=Count('id', filter=Q(status='published')),
        views=Sum('views_count'),
        likes=Sum('likes_count'),
    )
    return Response(
        {
            'user': AuthUserSerializer(user).data,
            'stats': {
                'total_articles': article_stats['total'],
                'published_articles': article_stats['published'],
                'draft_articles': article_stats['total'] - article_stats['published'],
                'total_views': article_stats['views'] or 0,
                'total_likes': article_stats['likes'] or 0,
                'total_comments': Comment.objects.filter(author=user, is_active=True).count(),
                'unread_notifications': Notification.objects.filter(recipient=user, is_read=False).count(),
                'recent_notifications': Notification.objects.filter(recipient=user, created_at__gte=week_ago).count(),
                'followers': user.followers_count,
                'following': user.following_count,
            },
        }
    )


def _compute_trending():
    week_ago = timezone.now() - timedelta(days=7)
    article_type = ContentType.objects.get_for_model(Article)

    recent_comment_counts = dict(
        Comment.objects.filter(content_type=article_type, is_active=True, created_at__gte=week_ago)
        .values_list('object_id')
        .annotate(n=Count('id'))
        .values_list('object_id', 'n')
    )
    articles = list(
        Article.published.filter(published_at__gte=week_ago).select_related('author').order_by('-views_count')[:50]
    )
    for article in articles:
        article.recent_comments = recent_comment_counts.get(str(article.pk), 0)
        article.trend_score = article.views_count + 5 * article.likes_count + 10 * article.recent_comments
    articles.sort(key=lambda a: a.trend_score, reverse=True)

    popular_tags = (
        Tag.objects.annotate(num_articles=Count('articles', filter=Q(articles__status='published')))
        .filter(num_articles__gt=0)
        .order_by('-num_articles', 'name')[:20]
    )
    active_authors = (
        CustomUser.objects.filter(is_active=True, articles__status='published', articles__published_at__gte=week_ago)
        .annotate(num_articles=Count('articles', distinct=True))
        .order_by('-num_articles', 'username')[:10]
    )
    return {
        'trending_articles': [
            {
                'id': str(a.id),
                'title': a.title,
                'slug': a.slug,
                'url': a.get_absolute_url(),
                'author': a.author.get_full_name() or a.author.username,
                'views': a.views_count,
                'likes': a.likes_count,
                'recent_comments': a.recent_comments,
                'score': a.trend_score,
                'published_at': a.published_at.isoformat() if a.published_at else None,
            }
            for a in articles[:10]
        ],
        'popular_tags': [{'name': t.name, 'slug': t.slug, 'article_count': t.num_articles} for t in popular_tags],
        'active_authors': [
            {'id': str(u.id), 'username': u.username, 'full_name': u.get_full_name(), 'article_count': u.num_articles}
            for u in active_authors
        ],
        'generated_at': timezone.now().isoformat(),
    }


class TrendingContentAPIView(APIView):
    """Articles, tags and authors trending over the last seven days (cached 15 minutes)."""

    permission_classes = [AllowAny]

    @extend_schema(tags=['search'], responses={200: dict})
    def get(self, request, format=None):
        data = cache.get(TRENDING_CACHE_KEY)
        if data is None:
            data = _compute_trending()
            cache.set(TRENDING_CACHE_KEY, data, 900)
        return Response(data)
