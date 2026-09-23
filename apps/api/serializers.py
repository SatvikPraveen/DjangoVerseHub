# File: DjangoVerseHub/apps/api/serializers.py
"""Serializers for the cross-cutting API endpoints (auth, search, dashboard)."""

from django.contrib.auth import authenticate
from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False, style={"input_type": "password"})

    def validate(self, attrs):
        request = self.context.get("request")
        user = authenticate(request, username=attrs["email"].lower(), password=attrs["password"])
        if user is None:
            raise serializers.ValidationError("Invalid email or password.", code="invalid_credentials")
        if not user.is_active:
            raise serializers.ValidationError("This account is disabled.", code="account_disabled")
        attrs["user"] = user
        return attrs


class AuthUserSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    email = serializers.EmailField(read_only=True)
    username = serializers.CharField(read_only=True)
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    is_verified = serializers.BooleanField(read_only=True)
    is_staff = serializers.BooleanField(read_only=True)


class TokenResponseSerializer(serializers.Serializer):
    token = serializers.CharField(read_only=True)
    user = AuthUserSerializer(read_only=True)


class SearchQuerySerializer(serializers.Serializer):
    q = serializers.CharField(max_length=200)
    type = serializers.ChoiceField(choices=["all", "articles", "users", "tags"], default="all")
    limit = serializers.IntegerField(min_value=1, max_value=50, default=10)


class SearchArticleSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    title = serializers.CharField()
    slug = serializers.CharField()
    summary = serializers.CharField()
    author = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    published_at = serializers.DateTimeField()
    url = serializers.CharField(source="get_absolute_url")

    def get_author(self, obj):
        return obj.author.get_full_name() or obj.author.username

    def get_category(self, obj):
        return obj.category.name if obj.category_id else None


class SearchUserSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    username = serializers.CharField()
    full_name = serializers.CharField(source="get_full_name")
    avatar_url = serializers.SerializerMethodField()
    url = serializers.CharField(source="get_absolute_url")

    def get_avatar_url(self, obj):
        profile = getattr(obj, "profile", None)
        return profile.avatar_url if profile is not None else None


class SearchTagSerializer(serializers.Serializer):
    name = serializers.CharField()
    slug = serializers.CharField()
    article_count = serializers.IntegerField(source="num_articles")
    url = serializers.CharField(source="get_absolute_url")
