# File: DjangoVerseHub/apps/comments/serializers.py

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from .models import Comment, CommentLike

User = get_user_model()


class CommentAuthorSerializer(serializers.ModelSerializer):
    """Serializer for comment author"""
    
    full_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'full_name', 'avatar_url']
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    
    def get_avatar_url(self, obj):
        if hasattr(obj, 'profile') and obj.profile.avatar:
            return obj.profile.get_avatar_url()
        return '/static/images/default-avatar.png'


class CommentSerializer(serializers.ModelSerializer):
    """Serializer for Comment model"""
    
    author = CommentAuthorSerializer(read_only=True)
    reply_count = serializers.ReadOnlyField()
    total_replies = serializers.ReadOnlyField()
    thread_depth = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    content_object_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Comment
        fields = [
            'id', 'author', 'content', 'parent', 'is_active', 'is_flagged',
            'is_edited', 'likes_count', 'reply_count', 'total_replies',
            'thread_depth', 'can_edit', 'can_delete', 'is_liked',
            'content_object_name', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'author', 'is_active', 'is_flagged', 'is_edited', 'likes_count',
            'created_at', 'updated_at'
        ]

    def get_thread_depth(self, obj):
        return obj.get_thread_depth()

    def get_can_edit(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.can_edit(request.user)
        return False

    def get_can_delete(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.can_delete(request.user)
        return False

    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return CommentLike.objects.filter(
                comment=obj, 
                user=request.user
            ).exists()
        return False

    def get_content_object_name(self, obj):
        if obj.content_object:
            return str(obj.content_object)
        return None


class CommentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating comments"""
    
    content_type = serializers.CharField(write_only=True)
    object_id = serializers.CharField(write_only=True)
    
    class Meta:
        model = Comment
        fields = ['content', 'parent', 'content_type', 'object_id']

    def validate_content(self, value):
        """Validate comment content"""
        content = value.strip()
        
        if len(content) < 3:
            raise serializers.ValidationError("Comment must be at least 3 characters long.")
        
        if len(content) > 1000:
            raise serializers.ValidationError("Comment cannot exceed 1000 characters.")
        
        return content

    def validate(self, attrs):
        """Validate the entire comment data"""
        content_type_str = attrs.get('content_type')
        object_id = attrs.get('object_id')
        parent = attrs.get('parent')
        
        # Validate content type
        try:
            app_label, model = content_type_str.split('.')
            content_type = ContentType.objects.get(
                app_label=app_label, 
                model=model
            )
            attrs['content_type'] = content_type
        except (ValueError, ContentType.DoesNotExist):
            raise serializers.ValidationError({
                'content_type': 'Invalid content type format. Use "app_label.model"'
            })
        
        # Validate that the target object exists
        model_class = content_type.model_class()
        try:
            target_object = model_class.objects.get(pk=object_id)
            attrs['target_object'] = target_object
        except model_class.DoesNotExist:
            raise serializers.ValidationError({
                'object_id': 'Target object does not exist'
            })
        
        # Validate parent comment if provided
        if parent:
            if parent.content_type != content_type or str(parent.object_id) != object_id:
                raise serializers.ValidationError({
                    'parent': 'Parent comment must be on the same object'
                })
            
            if parent.get_thread_depth() >= 3:
                raise serializers.ValidationError({
                    'parent': 'Cannot reply to comments more than 3 levels deep'
                })
        
        return attrs

    def create(self, validated_data):
        validated_data.pop('target_object', None)  # Remove helper field
        validated_data['author'] = self.context['request'].user
        return Comment.objects.create(**validated_data)


class CommentUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating comments"""
    
    class Meta:
        model = Comment
        fields = ['content']

    def validate_content(self, value):
        """Validate updated content"""
        content = value.strip()
        
        if len(content) < 3:
            raise serializers.ValidationError("Comment must be at least 3 characters long.")
        
        return content

    def update(self, instance, validated_data):
        # Check if content changed
        if instance.content != validated_data.get('content', instance.content):
            instance.mark_as_edited()
        
        return super().update(instance, validated_data)


class CommentTreeSerializer(serializers.ModelSerializer):
    """Serializer for nested comment threads"""
    
    author = CommentAuthorSerializer(read_only=True)
    replies = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    
    class Meta:
        model = Comment
        fields = [
            'id', 'author', 'content', 'is_edited', 'likes_count',
            'can_edit', 'can_delete', 'is_liked', 'replies',
            'created_at', 'updated_at'
        ]

    def get_replies(self, obj):
        """Get nested replies"""
        replies = obj.replies.filter(is_active=True).order_by('created_at')
        return CommentTreeSerializer(
            replies, 
            many=True, 
            context=self.context
        ).data

    def get_can_edit(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.can_edit(request.user)
        return False

    def get_can_delete(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.can_delete(request.user)
        return False

    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return CommentLike.objects.filter(
                comment=obj, 
                user=request.user
            ).exists()
        return False


class CommentLikeSerializer(serializers.ModelSerializer):
    """Serializer for comment likes"""
    
    user = CommentAuthorSerializer(read_only=True)
    
    class Meta:
        model = CommentLike
        fields = ['id', 'user', 'created_at']
        read_only_fields = ['created_at']


class CommentStatsSerializer(serializers.ModelSerializer):
    """Serializer for comment statistics"""
    
    reply_count = serializers.ReadOnlyField()
    total_replies = serializers.ReadOnlyField()
    thread_depth = serializers.SerializerMethodField()
    
    class Meta:
        model = Comment
        fields = [
            'id', 'likes_count', 'reply_count', 'total_replies', 
            'thread_depth', 'created_at'
        ]
    
    def get_thread_depth(self, obj):
        return obj.get_thread_depth()