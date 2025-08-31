# File: DjangoVerseHub/apps/api/views.py

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import GenericAPIView
from django.contrib.auth import authenticate, login
from django.core.cache import cache
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from apps.users.models import CustomUser
from apps.articles.models import Article, Category, Tag
from apps.comments.models import Comment
from apps.notifications.models import Notification


@api_view(['GET'])
@permission_classes([AllowAny])
def api_root(request, format=None):
    """
    API root endpoint with basic information
    """
    return Response({
        'message': 'Welcome to DjangoVerseHub API',
        'version': '1.0',
        'endpoints': {
            'users': '/api/v1/users/',
            'articles': '/api/v1/articles/',
            'comments': '/api/v1/comments/',
            'categories': '/api/v1/categories/',
            'tags': '/api/v1/tags/',
            'notifications': '/api/v1/notifications/',
            'stats': '/api/v1/stats/',
            'health': '/api/v1/health/',
        },
        'authentication': {
            'token': 'Include "Authorization: Token <your-token>" header',
            'session': 'Use session authentication for web clients'
        },
        'docs': '/api/docs/',
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    API health check endpoint
    """
    return Response({
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'services': {
            'database': 'operational',
            'cache': 'operational',
        }
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def api_stats(request):
    """
    General API statistics endpoint
    """
    cache_key = 'api_stats'
    stats = cache.get(cache_key)
    
    if stats is None:
        stats = {
            'total_users': CustomUser.objects.count(),
            'active_users': CustomUser.objects.filter(is_active=True).count(),
            'verified_users': CustomUser.objects.filter(is_verified=True).count(),
            'total_articles': Article.objects.count(),
            'published_articles': Article.objects.filter(status='published').count(),
            'total_comments': Comment.objects.count(),
            'total_categories': Category.objects.count(),
            'total_tags': Tag.objects.count(),
            'total_notifications': Notification.objects.count(),
        }
        
        # Recent activity (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        stats.update({
            'recent_users': CustomUser.objects.filter(date_joined__gte=thirty_days_ago).count(),
            'recent_articles': Article.objects.filter(created_at__gte=thirty_days_ago).count(),
            'recent_comments': Comment.objects.filter(created_at__gte=thirty_days_ago).count(),
        })
        
        # Cache for 5 minutes
        cache.set(cache_key, stats, 300)
    
    return Response(stats)


class SearchAPIView(APIView):
    """
    Global search API endpoint
    """
    permission_classes = [AllowAny]

    def get(self, request, format=None):
        query = request.query_params.get('q', '')
        search_type = request.query_params.get('type', 'all')
        
        if not query:
            return Response({'error': 'Query parameter "q" is required'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        results = {}
        
        if search_type in ['all', 'articles']:
            articles = Article.objects.filter(
                Q(title__icontains=query) | Q(content__icontains=query),
                status='published'
            ).select_related('author', 'category')[:10]
            
            results['articles'] = [{
                'id': str(article.id),
                'title': article.title,
                'slug': article.slug,
                'author': article.author.get_full_name(),
                'category': article.category.name if article.category else None,
                'created_at': article.created_at.isoformat(),
            } for article in articles]
        
        if search_type in ['all', 'users']:
            users = CustomUser.objects.filter(
                Q(first_name__icontains=query) | Q(last_name__icontains=query),
                is_active=True
            ).select_related('profile')[:10]
            
            results['users'] = [{
                'id': str(user.id),
                'full_name': user.get_full_name(),
                'avatar_url': user.profile.get_avatar_url() if hasattr(user, 'profile') else None,
                'date_joined': user.date_joined.isoformat(),
            } for user in users]
        
        if search_type in ['all', 'tags']:
            tags = Tag.objects.filter(name__icontains=query)[:10]
            results['tags'] = [{
                'name': tag.name,
                'slug': tag.slug,
                'article_count': tag.article_count,
            } for tag in tags]
        
        return Response({
            'query': query,
            'results': results,
            'total_results': sum(len(result_list) for result_list in results.values())
        })


class LoginAPIView(GenericAPIView):
    """
    API login endpoint
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not email or not password:
            return Response({
                'error': 'Email and password are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user = authenticate(request, username=email, password=password)
        
        if user:
            if not user.is_active:
                return Response({
                    'error': 'User account is disabled'
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Create or get auth token
            from rest_framework.authtoken.models import Token
            token, created = Token.objects.get_or_create(user=user)
            
            return Response({
                'token': token.key,
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'full_name': user.get_full_name(),
                    'is_verified': user.is_verified,
                }
            })
        
        return Response({
            'error': 'Invalid credentials'
        }, status=status.HTTP_400_BAD_REQUEST)


class LogoutAPIView(APIView):
    """
    API logout endpoint
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            # Delete the auth token
            request.user.auth_token.delete()
            return Response({'message': 'Successfully logged out'})
        except:
            return Response({'message': 'No active token found'})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_dashboard(request):
    """
    User dashboard data endpoint
    """
    user = request.user
    
    # Get user's articles
    user_articles = Article.objects.filter(author=user).count()
    published_articles = Article.objects.filter(author=user, status='published').count()
    
    # Get user's comments
    user_comments = Comment.objects.filter(author=user).count()
    
    # Get recent notifications
    recent_notifications = Notification.objects.filter(
        recipient=user,
        created_at__gte=timezone.now() - timedelta(days=7)
    ).count()
    
    return Response({
        'user': {
            'id': str(user.id),
            'full_name': user.get_full_name(),
            'email': user.email,
            'date_joined': user.date_joined.isoformat(),
            'is_verified': user.is_verified,
        },
        'stats': {
            'total_articles': user_articles,
            'published_articles': published_articles,
            'draft_articles': user_articles - published_articles,
            'total_comments': user_comments,
            'recent_notifications': recent_notifications,
        }
    })


class TrendingContentAPIView(APIView):
    """
    Trending content endpoint
    """
    permission_classes = [AllowAny]

    def get(self, request, format=None):
        cache_key = 'trending_content'
        data = cache.get(cache_key)
        
        if data is None:
            # Get trending articles (most commented in last 7 days)
            seven_days_ago = timezone.now() - timedelta(days=7)
            trending_articles = Article.objects.filter(
                status='published',
                created_at__gte=seven_days_ago
            ).annotate(
                comment_count=Count('comments')
            ).order_by('-comment_count')[:10]
            
            # Get popular tags
            popular_tags = Tag.objects.annotate(
                article_count=Count('articles')
            ).order_by('-article_count')[:20]
            
            # Get active users
            active_users = CustomUser.objects.filter(
                last_login__gte=seven_days_ago,
                is_active=True
            ).annotate(
                article_count=Count('articles')
            ).order_by('-article_count')[:10]
            
            data = {
                'trending_articles': [{
                    'id': str(article.id),
                    'title': article.title,
                    'slug': article.slug,
                    'author': article.author.get_full_name(),
                    'comment_count': article.comment_count,
                    'created_at': article.created_at.isoformat(),
                } for article in trending_articles],
                
                'popular_tags': [{
                    'name': tag.name,
                    'slug': tag.slug,
                    'article_count': tag.article_count,
                } for tag in popular_tags],
                
                'active_users': [{
                    'id': str(user.id),
                    'full_name': user.get_full_name(),
                    'article_count': user.article_count,
                } for user in active_users],
            }
            
            # Cache for 30 minutes
            cache.set(cache_key, data, 1800)
        
        return Response(data)