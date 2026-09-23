# File: DjangoVerseHub/apps/comments/views.py

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db.models import Count, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, ListView, UpdateView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import permissions, status, viewsets
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .forms import CommentEditForm, CommentFlagForm, CommentForm, CommentReplyForm, CommentSearchForm
from .models import (
    Comment, CommentFlag, CommentLike, annotate_total_replies, build_comment_tree,
    target_accepts_comments,
)
from .permissions import IsCommentAuthorOrStaff
from .serializers import (
    CommentCreateSerializer, CommentSerializer, CommentStatsSerializer,
    CommentTreeSerializer, CommentUpdateSerializer,
)
from .throttling import CommentCreateThrottle


def resolve_content_object(content_type_id, object_id):
    """Return the target object for a content_type id + object id, or None."""
    if not content_type_id or not object_id:
        return None
    try:
        content_type = ContentType.objects.get_for_id(int(content_type_id))
        return content_type.get_object_for_this_type(pk=object_id)
    except (ValueError, TypeError, ObjectDoesNotExist, ValidationError):
        return None


def resolve_content_type_string(value):
    """Resolve "app_label.model" to a ContentType, or None."""
    try:
        app_label, model = (value or '').lower().split('.')
        return ContentType.objects.get_by_natural_key(app_label, model)
    except (ValueError, ContentType.DoesNotExist):
        return None


# ---------------------------------------------------------------------------
# Web views
# ---------------------------------------------------------------------------

class CommentListView(ListView):
    """Browse comments. Staff additionally see hidden comments and author emails."""
    model = Comment
    template_name = 'comments/comment_list.html'
    context_object_name = 'comments'
    paginate_by = 20

    def get_queryset(self):
        queryset = Comment.objects.with_author().select_related('content_type', 'parent')
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)

        self.filter_form = CommentSearchForm(self.request.GET or None)
        if self.filter_form.is_valid():
            data = self.filter_form.cleaned_data
            if data.get('q'):
                queryset = queryset.filter(
                    Q(content__icontains=data['q'])
                    | Q(author__first_name__icontains=data['q'])
                    | Q(author__last_name__icontains=data['q'])
                )
            if data.get('author'):
                author_q = (
                    Q(author__first_name__icontains=data['author'])
                    | Q(author__last_name__icontains=data['author'])
                    | Q(author__username__icontains=data['author'])
                )
                if self.request.user.is_staff:
                    author_q |= Q(author__email__icontains=data['author'])
                queryset = queryset.filter(author_q)
            if data.get('date_from'):
                queryset = queryset.filter(created_at__date__gte=data['date_from'])
            if data.get('date_to'):
                queryset = queryset.filter(created_at__date__lte=data['date_to'])
            if data.get('is_flagged'):
                queryset = queryset.filter(is_flagged=True)

        return queryset.annotate(
            active_reply_count=Count('replies', filter=Q(replies__is_active=True))
        ).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filter_form'] = self.filter_form
        query = self.request.GET.copy()
        query.pop('page', None)
        context['querystring'] = query.urlencode()
        return context


class CommentCreateView(LoginRequiredMixin, CreateView):
    """Create a new comment on any object.

    The target is given as ``content_type`` (ContentType id) + ``object_id``
    in the query string or POST body, or as an ``article`` id (the form on
    the article page).
    """
    model = Comment
    form_class = CommentForm
    template_name = 'comments/comment_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.content_object = None
        if request.user.is_authenticated:
            self.content_object = self._get_content_object()
            if self.content_object is None:
                raise Http404('Nothing to comment on')
        return super().dispatch(request, *args, **kwargs)

    def _get_content_object(self):
        params = self.request.POST if self.request.method == 'POST' else self.request.GET
        content_type_id = params.get('content_type') or self.request.GET.get('content_type')
        object_id = params.get('object_id') or self.request.GET.get('object_id')
        target = resolve_content_object(content_type_id, object_id)
        if target is None and params.get('article'):
            content_type = resolve_content_type_string('articles.article')
            if content_type is not None:
                target = resolve_content_object(content_type.id, params.get('article'))
        return target

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['content_object'] = self.content_object
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['content_object'] = self.content_object
        context['content_type_id'] = ContentType.objects.get_for_model(self.content_object).id
        return context

    def form_valid(self, form):
        messages.success(self.request, 'Comment posted successfully!')
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class CommentUpdateView(LoginRequiredMixin, UpdateView):
    """Edit a comment: author within the edit window, or staff."""
    model = Comment
    form_class = CommentEditForm
    template_name = 'comments/comment_edit.html'

    def get_queryset(self):
        queryset = Comment.objects.filter(is_active=True)
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(author=self.request.user)

    def get_object(self, queryset=None):
        comment = super().get_object(queryset)
        if not comment.can_edit(self.request.user):
            raise PermissionDenied('The edit window for this comment has closed.')
        return comment

    def form_valid(self, form):
        messages.success(self.request, 'Comment updated successfully!')
        return super().form_valid(form)

    def get_success_url(self):
        return self.object.get_absolute_url()


class CommentDeleteView(LoginRequiredMixin, DeleteView):
    """Soft-delete a comment: author or staff."""
    model = Comment
    template_name = 'comments/comment_delete.html'

    def get_queryset(self):
        queryset = Comment.objects.filter(is_active=True)
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(author=self.request.user)

    def form_valid(self, form):
        success_url = self.get_success_url()
        self.object.soft_delete()
        messages.success(self.request, 'Comment deleted successfully!')
        return redirect(success_url)

    def get_success_url(self):
        target = self.object.content_object
        if target is not None and hasattr(target, 'get_absolute_url'):
            return target.get_absolute_url()
        return reverse('comments:list')


@login_required
def comment_reply_view(request, comment_id):
    """Reply to a comment"""
    parent_comment = get_object_or_404(
        Comment.objects.select_related('author', 'content_type'), id=comment_id, is_active=True
    )
    if not parent_comment.can_reply:
        messages.error(request, 'This thread is too deep to reply to.')
        return redirect(parent_comment.get_absolute_url())
    if not target_accepts_comments(parent_comment.content_object):
        messages.error(request, 'Comments are closed for this content.')
        return redirect(parent_comment.get_absolute_url())

    form_kwargs = {'user': request.user, 'parent': parent_comment}
    if request.method == 'POST':
        form = CommentReplyForm(request.POST, **form_kwargs)
        if form.is_valid():
            reply = form.save()
            messages.success(request, 'Reply posted successfully!')
            return redirect(reply.get_absolute_url())
    else:
        form = CommentReplyForm(**form_kwargs)

    return render(request, 'comments/comment_reply.html', {
        'form': form,
        'parent_comment': parent_comment,
    })


@login_required
@require_POST
def comment_like_view(request, comment_id):
    """Toggle a like on a comment (AJAX)."""
    comment = get_object_or_404(Comment, id=comment_id, is_active=True)
    liked, likes_count = comment.toggle_like(request.user)
    return JsonResponse({'liked': liked, 'likes_count': likes_count})


@login_required
def comment_flag_view(request, comment_id):
    """Report a comment for moderation."""
    comment = get_object_or_404(Comment.objects.select_related('author'), id=comment_id, is_active=True)
    if comment.author_id == request.user.pk:
        raise PermissionDenied('You cannot flag your own comment.')

    if request.method == 'POST':
        form = CommentFlagForm(request.POST, comment=comment, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Thanks, this comment has been reported for review.')
            return redirect(comment.get_absolute_url())
    else:
        form = CommentFlagForm(comment=comment, user=request.user)

    return render(request, 'comments/comment_flag.html', {
        'form': form,
        'comment': comment,
        'already_flagged': CommentFlag.objects.filter(comment=comment, user=request.user).exists(),
    })


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

class CommentPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class CommentViewSet(viewsets.ModelViewSet):
    """
    Comment API.

    list:    ?content_type=<ContentType id>&object_id=<pk> narrows to one object;
             ?parent=<uuid> lists direct replies; ?search=, ?ordering= supported.
    create:  {"content", "content_type": "app_label.model", "object_id", "parent"?}
    """
    queryset = Comment.objects.all()
    # Token first so unauthenticated writes get 401 + WWW-Authenticate.
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsCommentAuthorOrStaff]
    pagination_class = CommentPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]  # type: ignore[assignment]
    filterset_fields = ['content_type', 'object_id', 'parent']
    search_fields = ['content', 'author__first_name', 'author__last_name', 'author__username']
    ordering_fields = ['created_at', 'likes_count']
    ordering = ['created_at']

    def get_queryset(self):
        queryset = (
            Comment.objects.with_author()
            .select_related('content_type', 'parent')
            .prefetch_related('content_object')
            .annotate(active_reply_count=Count('replies', filter=Q(replies__is_active=True)))
        )
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)
        return queryset

    def get_serializer_class(self):
        if self.action == 'create':
            return CommentCreateSerializer
        if self.action in ('update', 'partial_update'):
            return CommentUpdateSerializer
        if self.action == 'tree':
            return CommentTreeSerializer
        if self.action == 'stats':
            return CommentStatsSerializer
        return CommentSerializer

    def get_throttles(self):
        throttles = super().get_throttles()
        if self.action == 'create':
            throttles.append(CommentCreateThrottle())
        return throttles

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['liked_ids'] = getattr(self, '_liked_ids', None)
        return context

    def _prime_batch(self, comments, totals=True):
        """Resolve per-batch data (viewer likes, reply totals) in O(1) queries."""
        user = self.request.user
        if user.is_authenticated:
            ids = [c.id for c in comments]
            self._liked_ids = set(
                CommentLike.objects.filter(user=user, comment_id__in=ids).values_list('comment_id', flat=True)
            )
        else:
            self._liked_ids = set()
        if totals:
            annotate_total_replies(comments)

    def _paginated_response(self, queryset):
        page = self.paginate_queryset(queryset)
        if page is not None:
            self._prime_batch(page)
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        items = list(queryset)
        self._prime_batch(items)
        return Response(self.get_serializer(items, many=True).data)

    def list(self, request, *args, **kwargs):
        return self._paginated_response(self.filter_queryset(self.get_queryset()))

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def perform_destroy(self, instance):
        instance.soft_delete()

    @action(detail=True, methods=['post'])
    def like(self, request, pk=None):
        """Like/unlike a comment"""
        comment = self.get_object()
        liked, likes_count = comment.toggle_like(request.user)
        return Response({'liked': liked, 'likes_count': likes_count})

    @action(detail=True, methods=['post'])
    def flag(self, request, pk=None):
        """Report a comment. Body: {"reason": <choice>, "details": ""} (both optional)."""
        comment = self.get_object()
        if comment.author_id == request.user.pk:
            return Response({'error': 'You cannot flag your own comment'}, status=status.HTTP_400_BAD_REQUEST)
        reason = request.data.get('reason', CommentFlag.Reason.OTHER)
        if reason not in CommentFlag.Reason.values:
            return Response({'reason': 'Invalid reason'}, status=status.HTTP_400_BAD_REQUEST)
        details = str(request.data.get('details', ''))[:500]
        _flag, created = comment.add_flag(request.user, reason=reason, details=details)
        if not created:
            return Response({'error': 'You have already flagged this comment'}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'message': 'Comment flagged for review'})

    @action(detail=False)
    def tree(self, request):
        """Nested comment threads for one object: ?content_type=app.model&object_id=<pk>."""
        content_type = request.query_params.get('content_type')
        object_id = request.query_params.get('object_id')
        if not content_type or not object_id:
            return Response(
                {'error': 'content_type and object_id are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        ct = resolve_content_type_string(content_type)
        if ct is None:
            return Response({'error': 'Invalid content_type'}, status=status.HTTP_400_BAD_REQUEST)

        comments = list(
            Comment.objects.filter(content_type=ct, object_id=str(object_id)).with_author()
        )
        roots = build_comment_tree(comments)  # also sets _total_replies on every node
        self._prime_batch(comments, totals=False)
        return Response(self.get_serializer(roots, many=True).data)

    @action(detail=True)
    def stats(self, request, pk=None):
        """Get comment statistics"""
        return Response(self.get_serializer(self.get_object()).data)

    @action(detail=False, permission_classes=[permissions.IsAuthenticated])
    def user_comments(self, request):
        """Paginated list of the current user's comments."""
        queryset = self.get_queryset().filter(author=request.user).order_by('-created_at')
        return self._paginated_response(queryset)
