# File: DjangoVerseHub/apps/notifications/serializers.py
from django.contrib.auth import get_user_model
from django.utils.timesince import timesince
from rest_framework import serializers

from .models import Notification, NotificationPreference

User = get_user_model()


class NotificationSenderSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'display_name', 'avatar_url']

    def get_display_name(self, obj):
        return obj.get_full_name() or obj.username

    def get_avatar_url(self, obj):
        profile = getattr(obj, 'profile', None)
        return profile.avatar_url if profile is not None else None


class NotificationSerializer(serializers.ModelSerializer):
    sender = NotificationSenderSerializer(read_only=True)
    time_since = serializers.SerializerMethodField()
    url = serializers.SerializerMethodField()
    icon = serializers.CharField(read_only=True)
    color = serializers.CharField(read_only=True)
    content_object_data = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'message', 'sender',
            'is_read', 'created_at', 'read_at', 'time_since',
            'url', 'icon', 'color', 'content_object_data',
        ]
        read_only_fields = fields

    def get_time_since(self, obj):
        return timesince(obj.created_at) if obj.created_at else ''

    def get_url(self, obj):
        return obj.url

    def get_content_object_data(self, obj):
        target = obj.target
        if target is None:
            return None
        return {'url': obj.url, 'title': str(target)}


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            'in_app_like', 'in_app_comment', 'in_app_follow', 'in_app_mention', 'in_app_post',
            'email_like', 'email_comment', 'email_follow', 'email_mention', 'email_post',
            'digest_frequency', 'updated_at',
        ]
        read_only_fields = ['updated_at']
