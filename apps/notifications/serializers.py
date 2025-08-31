# File: DjangoVerseHub/apps/notifications/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Notification

User = get_user_model()


class NotificationSenderSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']


class NotificationSerializer(serializers.ModelSerializer):
    sender = NotificationSenderSerializer(read_only=True)
    time_since = serializers.SerializerMethodField()
    content_object_data = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'message', 'sender',
            'is_read', 'created_at', 'read_at', 'time_since',
            'content_object_data'
        ]
        read_only_fields = ['id', 'created_at']

    def get_time_since(self, obj):
        from django.utils.timesince import timesince
        return timesince(obj.created_at)

    def get_content_object_data(self, obj):
        if obj.content_object:
            if hasattr(obj.content_object, 'get_absolute_url'):
                return {
                    'url': obj.content_object.get_absolute_url(),
                    'title': str(obj.content_object)
                }
        return None


class NotificationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            'recipient', 'sender', 'notification_type', 
            'message', 'content_type', 'object_id'
        ]

    def create(self, validated_data):
        return Notification.objects.create(**validated_data)