# File: DjangoVerseHub/apps/users/serializers.py

import re

from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password

from .models import CustomUser, Profile
from .utils import authenticate_by_identifier


PHONE_PATTERN = re.compile(r'^\+?[\d\s\-\(\)]{10,}$')


def _validate_phone(value):
    if value and not PHONE_PATTERN.match(value):
        raise serializers.ValidationError("Enter a valid phone number.")
    return value


def _is_owner_or_staff(serializer, user):
    """True when the requesting user may see private fields of `user`."""
    request = serializer.context.get('request')
    requester = getattr(request, 'user', None)
    if requester is None or not requester.is_authenticated:
        return False
    return requester.pk == user.pk or requester.is_staff


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""

    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = CustomUser
        fields = ('email', 'username', 'first_name', 'last_name', 'password', 'password_confirm')
        extra_kwargs = {
            'password': {'write_only': True},
            'email': {'required': True},
            'username': {'required': True}
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Passwords don't match.")
        return attrs

    def validate_email(self, value):
        value = CustomUser.objects.normalize_email(value)
        if CustomUser.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("User with this email already exists.")
        return value

    def validate_username(self, value):
        if CustomUser.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("User with this username already exists.")

        prohibited = ['admin', 'administrator', 'root', 'api', 'www', 'mail']
        if value.lower() in prohibited:
            raise serializers.ValidationError("This username is not allowed.")

        return value

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')

        user = CustomUser.objects.create_user(
            password=password,
            **validated_data
        )
        return user


class UserLoginSerializer(serializers.Serializer):
    """Serializer for user login (email or username)"""

    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    remember_me = serializers.BooleanField(default=False)

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        if not (username and password):
            raise serializers.ValidationError("Must include username and password.")

        user = authenticate_by_identifier(self.context.get('request'), username, password)
        if not user:
            raise serializers.ValidationError("Unable to log in with provided credentials.")
        if not user.is_active:
            raise serializers.ValidationError("User account is disabled.")

        attrs['user'] = user
        return attrs


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile"""

    # Only the owner (or staff) sees these in API responses.
    PRIVATE_FIELDS = (
        'email_notifications', 'push_notifications', 'marketing_emails',
        'show_email', 'show_real_name', 'timezone', 'language', 'theme',
    )

    user_id = serializers.UUIDField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    date_joined = serializers.DateTimeField(source='user.date_joined', read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            'user_id', 'username', 'email', 'date_joined', 'full_name',
            'bio', 'avatar', 'avatar_url', 'cover_image', 'gender',
            'location', 'website', 'twitter', 'linkedin', 'github',
            'theme', 'timezone', 'language', 'is_public', 'show_email',
            'show_real_name', 'email_notifications', 'push_notifications',
            'marketing_emails', 'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at')

    def get_avatar_url(self, obj):
        if obj.avatar and hasattr(obj.avatar, 'url'):
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if _is_owner_or_staff(self, instance.user):
            return data

        for name in self.PRIVATE_FIELDS:
            data.pop(name, None)
        if not instance.show_email:
            data.pop('email', None)
        if not instance.show_real_name:
            data.pop('full_name', None)
        return data

    def validate_avatar(self, value):
        if value:
            if value.size > 5 * 1024 * 1024:  # 5MB
                raise serializers.ValidationError("Avatar file size must be under 5MB.")

            if not getattr(value, 'content_type', 'image/').startswith('image/'):
                raise serializers.ValidationError("Avatar must be an image file.")

        return value

    def validate_cover_image(self, value):
        if value:
            if value.size > 10 * 1024 * 1024:  # 10MB
                raise serializers.ValidationError("Cover image file size must be under 10MB.")

            if not getattr(value, 'content_type', 'image/').startswith('image/'):
                raise serializers.ValidationError("Cover image must be an image file.")

        return value


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user data (read side; writes go through UserUpdateSerializer)"""

    PRIVATE_FIELDS = (
        'phone_number', 'date_of_birth', 'login_count', 'last_login', 'email_verified',
    )

    profile = ProfileSerializer(read_only=True)
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    followers_count = serializers.SerializerMethodField()
    following_count = serializers.SerializerMethodField()
    is_following = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name',
            'full_name', 'is_active', 'date_joined', 'last_login',
            'email_verified', 'phone_number', 'date_of_birth',
            'login_count', 'followers_count', 'following_count',
            'is_following', 'profile'
        ]
        read_only_fields = (
            'id', 'email', 'username', 'date_joined', 'last_login',
            'login_count', 'email_verified', 'is_active'
        )

    def get_followers_count(self, obj):
        return getattr(obj, 'followers_total', None) or obj.followers_count

    def get_following_count(self, obj):
        return getattr(obj, 'following_total', None) or obj.following_count

    def get_is_following(self, obj):
        request = self.context.get('request')
        requester = getattr(request, 'user', None)
        if requester is None or not requester.is_authenticated or requester.pk == obj.pk:
            return False
        return requester.is_following(obj)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if _is_owner_or_staff(self, instance):
            return data

        for name in self.PRIVATE_FIELDS:
            data.pop(name, None)
        profile = getattr(instance, 'profile', None)
        if profile is None or not profile.show_email:
            data.pop('email', None)
        return data

    def validate_phone_number(self, value):
        return _validate_phone(value)


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating a user's own basic information"""

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'phone_number', 'date_of_birth']

    def validate_phone_number(self, value):
        return _validate_phone(value)


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer for password change"""

    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("New passwords don't match.")
        return attrs

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        return user


class UserListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for user lists"""

    avatar_url = serializers.SerializerMethodField()
    display_name = serializers.CharField(source='profile.display_name', read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'display_name', 'avatar_url',
            'date_joined', 'is_active'
        ]

    def get_avatar_url(self, obj):
        profile = getattr(obj, 'profile', None)
        if profile is not None and profile.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(profile.avatar.url)
            return profile.avatar.url
        return None


class PublicProfileSerializer(serializers.ModelSerializer):
    """Public profile serializer with limited information"""

    user_id = serializers.UUIDField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    date_joined = serializers.DateTimeField(source='user.date_joined', read_only=True)
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            'user_id', 'username', 'date_joined', 'full_name', 'bio',
            'avatar_url', 'location', 'website', 'twitter',
            'linkedin', 'github'
        ]

    def get_avatar_url(self, obj):
        if obj.avatar and hasattr(obj.avatar, 'url'):
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.avatar.url)
            return obj.avatar.url
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)

        # Filter fields based on privacy settings
        if not instance.show_real_name:
            data.pop('full_name', None)

        if not instance.is_public:
            # Return only basic info for private profiles
            return {
                'user_id': data['user_id'],
                'username': data['username'],
                'avatar_url': data['avatar_url']
            }

        return data
