# File: DjangoVerseHub/apps/comments/serializers.py

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import (
    MAX_THREAD_DEPTH,
    REMOVED_PLACEHOLDER,
    Comment,
    CommentLike,
    target_accepts_comments,
)

User = get_user_model()

DEFAULT_AVATAR = "/static/images/default-avatar.png"


class CommentAuthorSerializer(serializers.ModelSerializer):
    """Public representation of a comment author."""

    full_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "full_name", "avatar_url"]

    def get_full_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_avatar_url(self, obj):
        profile = getattr(obj, "profile", None)
        if profile is not None:
            return profile.get_avatar_url()
        return DEFAULT_AVATAR


class _ViewerFieldsMixin:
    """Fields that depend on the requesting user."""

    def _user(self):
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            return request.user
        return None

    def get_can_edit(self, obj):
        user = self._user()
        return bool(user) and obj.can_edit(user)

    def get_can_delete(self, obj):
        user = self._user()
        return bool(user) and obj.can_delete(user)

    def get_liked(self, obj):
        user = self._user()
        if user is None:
            return False
        liked_ids = self.context.get("liked_ids")
        if liked_ids is not None:
            return obj.id in liked_ids
        return CommentLike.objects.filter(comment=obj, user=user).exists()

    def _hide_moderation_fields(self, data):
        user = self._user()
        if not (user and user.is_staff):
            data.pop("is_flagged", None)
        return data


class CommentSerializer(_ViewerFieldsMixin, serializers.ModelSerializer):
    """Read serializer for a single comment."""

    author = CommentAuthorSerializer(read_only=True)
    reply_count = serializers.ReadOnlyField()
    total_replies = serializers.ReadOnlyField()
    thread_depth = serializers.IntegerField(source="depth", read_only=True)
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    liked = serializers.SerializerMethodField()
    content_object_name = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "author",
            "content",
            "parent",
            "is_active",
            "is_flagged",
            "is_edited",
            "likes_count",
            "reply_count",
            "total_replies",
            "thread_depth",
            "can_edit",
            "can_delete",
            "liked",
            "content_object_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_content_object_name(self, obj):
        target = obj.content_object
        return str(target) if target is not None else None

    def to_representation(self, instance):
        return self._hide_moderation_fields(super().to_representation(instance))


class CommentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating comments"""

    content_type = serializers.CharField(write_only=True, help_text='"app_label.model", e.g. "articles.article"')
    object_id = serializers.CharField(write_only=True)
    parent = serializers.PrimaryKeyRelatedField(
        queryset=Comment.objects.filter(is_active=True), required=False, allow_null=True
    )

    class Meta:
        model = Comment
        fields = ["content", "parent", "content_type", "object_id"]

    def validate_content(self, value):
        content = value.strip()
        if len(content) < 3:
            raise serializers.ValidationError("Comment must be at least 3 characters long.")
        if len(content) > 1000:
            raise serializers.ValidationError("Comment cannot exceed 1000 characters.")
        return content

    def validate(self, attrs):
        content_type_str = attrs.get("content_type") or ""
        object_id = attrs.get("object_id")
        parent = attrs.get("parent")

        try:
            app_label, model = content_type_str.lower().split(".")
            content_type = ContentType.objects.get(app_label=app_label, model=model)
        except (ValueError, ContentType.DoesNotExist):
            raise serializers.ValidationError({"content_type": 'Invalid content type format. Use "app_label.model"'})

        model_class = content_type.model_class()
        if model_class is None:
            raise serializers.ValidationError({"content_type": "Unknown content type"})

        try:
            target = model_class._default_manager.get(pk=object_id)
        except (ObjectDoesNotExist, ValueError, TypeError, DjangoValidationError):
            raise serializers.ValidationError({"object_id": "Target object does not exist"})

        if not target_accepts_comments(target):
            raise serializers.ValidationError({"object_id": "This object does not accept comments"})

        if parent is not None:
            if parent.content_type_id != content_type.id or str(parent.object_id) != str(target.pk):
                raise serializers.ValidationError({"parent": "Parent comment must be on the same object"})
            if parent.get_thread_depth() >= MAX_THREAD_DEPTH:
                raise serializers.ValidationError(
                    {"parent": f"Cannot reply to comments more than {MAX_THREAD_DEPTH} levels deep"}
                )

        attrs["content_type"] = content_type
        attrs["object_id"] = str(target.pk)
        return attrs

    def create(self, validated_data):
        # ``author`` is injected by the view via serializer.save(author=...)
        return Comment.objects.create(**validated_data)

    def to_representation(self, instance):
        return CommentSerializer(instance, context=self.context).data


class CommentUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating comments (content only)."""

    class Meta:
        model = Comment
        fields = ["content"]

    def validate_content(self, value):
        content = value.strip()
        if len(content) < 3:
            raise serializers.ValidationError("Comment must be at least 3 characters long.")
        if len(content) > 1000:
            raise serializers.ValidationError("Comment cannot exceed 1000 characters.")
        return content

    def update(self, instance, validated_data):
        content = validated_data.get("content", instance.content)
        if content != instance.content:
            instance.content = content
            instance.is_edited = True
            instance.save(update_fields=["content", "is_edited", "updated_at"])
        return instance

    def to_representation(self, instance):
        return CommentSerializer(instance, context=self.context).data


class CommentTreeSerializer(_ViewerFieldsMixin, serializers.ModelSerializer):
    """Nested representation of a thread. Expects nodes from build_comment_tree."""

    author = CommentAuthorSerializer(read_only=True)
    replies = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    liked = serializers.SerializerMethodField()
    is_placeholder = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "author",
            "content",
            "depth",
            "is_active",
            "is_placeholder",
            "is_edited",
            "likes_count",
            "can_edit",
            "can_delete",
            "liked",
            "replies",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_is_placeholder(self, obj):
        return bool(getattr(obj, "is_placeholder", False))

    def get_replies(self, obj):
        nodes = getattr(obj, "child_nodes", None)
        if nodes is None:  # fallback when used outside a prebuilt tree
            nodes = obj.replies.filter(is_active=True).select_related("author", "author__profile")
        return CommentTreeSerializer(nodes, many=True, context=self.context).data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data["is_placeholder"]:
            data["content"] = REMOVED_PLACEHOLDER
            data["author"] = None
            data["can_edit"] = data["can_delete"] = data["liked"] = False
        return data


class CommentStatsSerializer(serializers.ModelSerializer):
    """Engagement statistics for a comment."""

    reply_count = serializers.ReadOnlyField()
    total_replies = serializers.ReadOnlyField()
    thread_depth = serializers.IntegerField(source="depth", read_only=True)
    flag_count = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = ["id", "likes_count", "reply_count", "total_replies", "thread_depth", "flag_count", "created_at"]

    def get_flag_count(self, obj):
        request = self.context.get("request")
        if request is not None and request.user.is_staff:
            return obj.flags.count()
        return None
