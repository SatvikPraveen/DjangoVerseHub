# File: DjangoVerseHub/apps/users/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import CustomUser, Profile
from .forms import CustomUserCreationForm


class CustomUserChangeForm(UserChangeForm):
    """Custom user change form for admin"""
    class Meta:
        model = CustomUser
        fields = '__all__'


class ProfileInline(admin.StackedInline):
    """Inline admin for Profile model"""
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('full_name', 'bio', 'avatar', 'cover_image')
        }),
        ('Personal Details', {
            'fields': ('gender', 'location', 'website'),
            'classes': ('collapse',)
        }),
        ('Social Links', {
            'fields': ('twitter', 'linkedin', 'github'),
            'classes': ('collapse',)
        }),
        ('Preferences', {
            'fields': ('theme', 'timezone', 'language'),
            'classes': ('collapse',)
        }),
        ('Privacy Settings', {
            'fields': ('is_public', 'show_email', 'show_real_name'),
            'classes': ('collapse',)
        }),
        ('Notifications', {
            'fields': ('email_notifications', 'push_notifications', 'marketing_emails'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    """Custom User Admin with enhanced functionality"""
    
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm
    
    list_display = [
        'email', 'username', 'get_full_name', 'is_active', 
        'is_staff', 'email_verified', 'login_count', 'date_joined',
        'profile_link', 'avatar_preview'
    ]
    
    list_filter = [
        'is_active', 'is_staff', 'is_superuser', 'email_verified',
        'date_joined', 'last_login'
    ]
    
    search_fields = ['email', 'username', 'first_name', 'last_name']
    
    readonly_fields = [
        'date_joined', 'last_login', 'login_count', 
        'last_login_ip', 'id'
    ]
    
    ordering = ['-date_joined']
    
    fieldsets = (
        (None, {'fields': ('id', 'email', 'password')}),
        ('Personal info', {
            'fields': ('username', 'first_name', 'last_name', 'phone_number', 'date_of_birth')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        ('Important dates', {
            'fields': ('last_login', 'date_joined')
        }),
        ('Additional Info', {
            'fields': ('email_verified', 'login_count', 'last_login_ip'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2'),
        }),
    )
    
    inlines = [ProfileInline]
    
    def get_full_name(self, obj):
        return obj.get_full_name() or '-'
    get_full_name.short_description = 'Full Name'
    
    def profile_link(self, obj):
        if hasattr(obj, 'profile'):
            url = reverse('admin:users_profile_change', args=[obj.profile.pk])
            return format_html('<a href="{}">View Profile</a>', url)
        return '-'
    profile_link.short_description = 'Profile'
    
    def avatar_preview(self, obj):
        if hasattr(obj, 'profile') and obj.profile.avatar:
            return format_html(
                '<img src="{}" width="30" height="30" style="border-radius: 50%;" />',
                obj.profile.avatar.url
            )
        return '-'
    avatar_preview.short_description = 'Avatar'
    
    actions = ['verify_email', 'unverify_email', 'activate_users', 'deactivate_users']
    
    def verify_email(self, request, queryset):
        count = queryset.update(email_verified=True)
        self.message_user(request, f'{count} users email verified.')
    verify_email.short_description = 'Verify email for selected users'
    
    def unverify_email(self, request, queryset):
        count = queryset.update(email_verified=False)
        self.message_user(request, f'{count} users email unverified.')
    unverify_email.short_description = 'Unverify email for selected users'
    
    def activate_users(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} users activated.')
    activate_users.short_description = 'Activate selected users'
    
    def deactivate_users(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} users deactivated.')
    deactivate_users.short_description = 'Deactivate selected users'


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    """Profile Admin"""
    
    list_display = [
        'user_link', 'display_name', 'location', 'is_public',
        'avatar_preview', 'created_at', 'updated_at'
    ]
    
    list_filter = [
        'is_public', 'gender', 'theme', 'email_notifications',
        'created_at', 'updated_at'
    ]
    
    search_fields = [
        'user__username', 'user__email', 'full_name', 
        'bio', 'location'
    ]
    
    readonly_fields = ['created_at', 'updated_at', 'avatar_preview', 'cover_preview']
    
    fieldsets = (
        ('User', {
            'fields': ('user',)
        }),
        ('Basic Information', {
            'fields': ('full_name', 'bio', 'avatar', 'avatar_preview', 'cover_image', 'cover_preview')
        }),
        ('Personal Details', {
            'fields': ('gender', 'location', 'website'),
        }),
        ('Social Links', {
            'fields': ('twitter', 'linkedin', 'github'),
        }),
        ('Preferences', {
            'fields': ('theme', 'timezone', 'language'),
        }),
        ('Privacy Settings', {
            'fields': ('is_public', 'show_email', 'show_real_name'),
        }),
        ('Notifications', {
            'fields': ('email_notifications', 'push_notifications', 'marketing_emails'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_link(self, obj):
        url = reverse('admin:users_customuser_change', args=[obj.user.pk])
        return format_html('<a href="{}">{}</a>', url, obj.user.username)
    user_link.short_description = 'User'
    user_link.admin_order_field = 'user__username'
    
    def avatar_preview(self, obj):
        if obj.avatar:
            return format_html(
                '<img src="{}" width="60" height="60" style="border-radius: 8px;" />',
                obj.avatar.url
            )
        return 'No avatar'
    avatar_preview.short_description = 'Avatar Preview'
    
    def cover_preview(self, obj):
        if obj.cover_image:
            return format_html(
                '<img src="{}" width="120" height="40" style="border-radius: 4px;" />',
                obj.cover_image.url
            )
        return 'No cover image'
    cover_preview.short_description = 'Cover Preview'