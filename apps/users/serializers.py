# File: DjangoVerseHub/apps/users/serializers.py

from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import CustomUser, Profile


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
        if CustomUser.objects.filter(email=value).exists():
            raise serializers.ValidationError("User with this email already exists.")
        return value

    def validate_username(self, value):
        if CustomUser.objects.filter(username=value).exists():
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
    """Serializer for user login"""
    
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    remember_me = serializers.BooleanField(default=False)

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        if username and password:
            # Try to authenticate with email first, then username
            user = None
            if '@' in username:
                try:
                    user = authenticate(email=username, password=password)
                except:
                    pass
            
            if not user:
                user = authenticate(username=username, password=password)

            if user:
                if not user.is_active:
                    raise serializers.ValidationError("User account is disabled.")
                
                attrs['user'] = user
                return attrs
            else:
                raise serializers.ValidationError("Unable to log in with provided credentials.")
        else:
            raise serializers.ValidationError("Must include username and password.")


class ProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile"""
    
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

    def validate_avatar(self, value):
        if value:
            if value.size > 5 * 1024 * 1024:  # 5MB
                raise serializers.ValidationError("Avatar file size must be under 5MB.")
            
            if not value.content_type.startswith('image/'):
                raise serializers.ValidationError("Avatar must be an image file.")
        
        return value

    def validate_cover_image(self, value):
        if value:
            if value.size > 10 * 1024 * 1024:  # 10MB
                raise serializers.ValidationError("Cover image file size must be under 10MB.")
            
            if not value.content_type.startswith('image/'):
                raise serializers.ValidationError("Cover image must be an image file.")
        
        return value


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user data"""
    
    profile = ProfileSerializer(read_only=True)
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    
    class Meta:
        model = CustomUser
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name',
            'full_name', 'is_active', 'date_joined', 'last_login',
            'email_verified', 'phone_number', 'date_of_birth',
            'login_count', 'profile'
        ]
        read_only_fields = (
            'id', 'date_joined', 'last_login', 'login_count',
            'email_verified', 'is_active'
        )

    def validate_phone_number(self, value):
        if value:
            import re
            phone_pattern = re.compile(r'^\+?[\d\s\-\(\)]{10,}$')
            if not phone_pattern.match(value):
                raise serializers.ValidationError("Enter a valid phone number.")
        return value


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating user information"""
    
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'phone_number', 'date_of_birth']

    def validate_phone_number(self, value):
        if value:
            import re
            phone_pattern = re.compile(r'^\+?[\d\s\-\(\)]{10,}$')
            if not phone_pattern.match(value):
                raise serializers.ValidationError("Enter a valid phone number.")
        return value


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
        user.save()
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
        if hasattr(obj, 'profile') and obj.profile.avatar:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.profile.avatar.url)
            return obj.profile.avatar.url
        return None


class PublicProfileSerializer(serializers.ModelSerializer):
    """Public profile serializer with limited information"""
    
    username = serializers.CharField(source='user.username', read_only=True)
    date_joined = serializers.DateTimeField(source='user.date_joined', read_only=True)
    avatar_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Profile
        fields = [
            'username', 'date_joined', 'full_name', 'bio',
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
                'username': data['username'],
                'avatar_url': data['avatar_url']
            }
        
        return data