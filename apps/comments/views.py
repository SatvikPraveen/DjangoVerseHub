# File: DjangoVerseHub/apps/comments/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.http import JsonResponse, Http404
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Comment, CommentLike
from .forms import CommentForm, CommentEditForm, CommentReplyForm, CommentFlagForm
from .serializers import (
    CommentSerializer, CommentCreateSerializer, CommentUpdateSerializer,
    CommentTreeSerializer, CommentLikeSerializer, CommentStatsSerializer
)
from django_verse_hub.permissions import IsOwnerOrReadOnly


class CommentListView(ListView):
    """List comments for moderation"""
    model = Comment
    template_name = 'comments/comment_list.html'
    context_object_name = 'comments'
    paginate_by = 20

    def get_queryset(self):
        queryset = Comment.objects.select_related('author', 'content_type')
        
        # Apply filters
        search_query = self.request.GET.get('q')
        if search_query:
            queryset = queryset.filter(
                Q(content__icontains=search_query) |
                Q(author__first_name__icontains=search_query) |
                Q(author__last_name__icontains=search_query)
            )
        
        author_filter = self.request.GET.get('author')
        if author_filter:
            queryset = queryset.filter(
                Q(author__first_name__icontains=author_filter) |
                Q(author__last_name__icontains=author_filter) |
                Q(author__email__icontains=author_filter)
            )
        
        if self.request.GET.get('is_flagged'):
            queryset = queryset.filter(is_flagged=True)
        
        return queryset.order_by('-created_at')


class CommentCreateView(LoginRequiredMixin, CreateView):
    """Create new comment"""
    model = Comment
    form_class = CommentForm
    template_name = 'comments/comment_form.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        
        # Get content object from URL parameters
        content_type_id = self.request.GET.get('content_type')
        object_id = self.request.GET.get('object_id')
        
        if content_type_id and object_id:
            try:
                content_type = ContentType.objects.get(id=content_type_id)
                content_object = content_type.get_object_for_this_type(pk=object_id)
                kwargs['content_object'] = content_object
            except (ContentType.DoesNotExist, content_type.model_class().DoesNotExist):
                pass
        
        return kwargs

    def form_valid(self, form):
        messages.success(self.request, 'Comment posted successfully!')
        return super().form_valid(form)

    def get_success_url(self):
        comment = self.object
        if comment.content_object:
            return comment.content_object.get_absolute_url()
        return reverse_lazy('comments:list')


class CommentUpdateView(LoginRequiredMixin, UpdateView):
    """Update existing comment"""
    model = Comment
    form_class = CommentEditForm
    template_name = 'comments/comment_edit.html'

    def get_queryset(self):
        return Comment.objects.filter(author=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, 'Comment updated successfully!')
        return super().form_valid(form)


class CommentDeleteView(LoginRequiredMixin, DeleteView):
    """Delete comment (soft delete)"""
    model = Comment
    template_name = 'comments/comment_delete.html'

    def get_queryset(self):
        # Allow deletion by author or staff
        if self.request.user.is_staff:
            return Comment.objects.all()
        return Comment.objects.filter(author=self.request.user)

    def delete(self, request, *args, **kwargs):
        comment = self.get_object()
        comment.soft_delete()
        messages.success(request, 'Comment deleted successfully!')
        return redirect(self.get_success_url())

    def get_success_url(self):
        comment = self.object
        if comment.content_object:
            return comment.content_object.get_absolute_url()
        return reverse_lazy('comments:list')


# Function-Based Views
@login_required
def comment_reply_view(request, comment_id):
    """Reply to a comment"""
    parent_comment = get_object_or_404(Comment, id=comment_id, is_active=True)
    
    if request.method == 'POST':
        form = CommentReplyForm(
            request.POST,
            user=request.user,
            content_object=parent_comment.content_object,
            parent=parent_comment
        )
        
        if form.is_valid():
            reply = form.save()
            messages.success(request, 'Reply posted successfully!')
            return redirect(reply.get_absolute_url())
    else:
        form = CommentReplyForm(
            user=request.user,
            content_object=parent_comment.content_object,
            parent=parent_comment
        )
    
    return render(request, 'comments/comment_reply.html', {
        'form': form,
        'parent_comment': parent_comment
    })


@login_required
def comment_like_view(request, comment_id):
    """Like/unlike a comment (AJAX)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)
    
    comment = get_object_or_404(Comment, id=comment_id, is_active=True)
    
    like, created = CommentLike.objects.get_or_create(
        comment=comment,
        user=request.user
    )
    
    if not created:
        # Unlike
        like.delete()
        comment.likes_count = max(0, comment.likes_count - 1)
        liked = False
    else:
        # Like
        comment.likes_count += 1
        liked = True
    
    comment.save(update_fields=['likes_count'])
    
    return JsonResponse({
        'liked': liked,
        'likes_count': comment.likes_count
    })


@login_required
def comment_flag_view(request, comment_id):
    """Flag a comment for moderation"""
    comment = get_object_or_404(Comment, id=comment_id, is_active=True)
    
    if request.method == 'POST':
        form = CommentFlagForm(
            request.POST,
            comment=comment,
            user=request.user
        )
        
        if form.is_valid():
            form.save()
            messages.success(request, 'Comment has been flagged for review.')
            return redirect(comment.get_absolute_url())
    else:
        form = CommentFlagForm(comment=comment, user=request.user)
    
    return render(request, 'comments/comment_flag.html', {
        'form': form,
        'comment': comment
    })


# API ViewSets
class CommentViewSet(viewsets.ModelViewSet):
    """API ViewSet for Comment operations"""
    queryset = Comment.objects.all()
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['content_type', 'object_id', 'parent', 'is_active', 'is_flagged']
    search_fields = ['content', 'author__first_name', 'author__last_name']
    ordering_fields = ['created_at', 'likes_count']
    ordering = ['created_at']

    def get_queryset(self):
        queryset = super().get_queryset()
        
        if self.action == 'list':
            # Only show active comments for list view
            queryset = queryset.filter(is_active=True)
        
        return queryset.select_related('author', 'content_type', 'parent')

    def get_serializer_class(self):
        if self.action == 'create':
            return CommentCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return CommentUpdateSerializer
        elif self.action == 'tree':
            return CommentTreeSerializer
        elif self.action == 'stats':
            return CommentStatsSerializer
        return CommentSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def perform_destroy(self, instance):
        # Soft delete instead of hard delete
        instance.soft_delete()

    @action(detail=True, methods=['post'])
    def like(self, request, pk=None):
        """Like/unlike a comment"""
        comment = self.get_object()
        
        like, created = CommentLike.objects.get_or_create(
            comment=comment,
            user=request.user
        )
        
        if not created:
            like.delete()
            comment.likes_count = max(0, comment.likes_count - 1)
            liked = False
        else:
            comment.likes_count += 1
            liked = True
        
        comment.save(update_fields=['likes_count'])
        
        return Response({
            'liked': liked,
            'likes_count': comment.likes_count
        })

    @action(detail=True, methods=['post'])
    def flag(self, request, pk=None):
        """Flag comment for moderation"""
        comment = self.get_object()
        comment.flag()
        
        return Response({'message': 'Comment flagged for review'})

    @action(detail=False)
    def tree(self, request):
        """Get comments in tree structure"""
        content_type = request.query_params.get('content_type')
        object_id = request.query_params.get('object_id')
        
        if not content_type or not object_id:
            return Response(
                {'error': 'content_type and object_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            app_label, model = content_type.split('.')
            ct = ContentType.objects.get(app_label=app_label, model=model)
        except (ValueError, ContentType.DoesNotExist):
            return Response(
                {'error': 'Invalid content_type'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get root comments (no parent)
        root_comments = Comment.objects.filter(
            content_type=ct,
            object_id=object_id,
            parent=None,
            is_active=True
        ).order_by('created_at')
        
        serializer = self.get_serializer(root_comments, many=True)
        return Response(serializer.data)

    @action(detail=True)
    def stats(self, request, pk=None):
        """Get comment statistics"""
        comment = self.get_object()
        serializer = self.get_serializer(comment)
        return Response(serializer.data)

    @action(detail=False)
    def user_comments(self, request):
        """Get comments by current user"""
        user_comments = Comment.objects.filter(
            author=request.user,
            is_active=True
        ).order_by('-created_at')
        
        serializer = CommentSerializer(user_comments, many=True, context={'request': request})
        return Response(serializer.data)