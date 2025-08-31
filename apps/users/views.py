# File: DjangoVerseHub/apps/users/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, DetailView, UpdateView, CreateView
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, HttpResponseForbidden
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.authtoken.models import Token

from .models import CustomUser, Profile
from .forms import CustomUserCreationForm, CustomLoginForm, ProfileForm, UserUpdateForm, PasswordChangeForm
from .serializers import (
    UserSerializer, ProfileSerializer, UserRegistrationSerializer,
    UserLoginSerializer, PasswordChangeSerializer, UserListSerializer
)
from .cache import UserCache
from .utils import get_client_info, send_welcome_email


# Web Views
def signup_view(request):
    """User registration view"""
    if request.user.is_authenticated:
        return redirect('users:profile', pk=request.user.pk)
    
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Log the user in
            login(request, user)
            
            # Update login stats
            client_info = get_client_info(request)
            user.update_login_stats(client_info['ip_address'])
            
            messages.success(request, 'Account created successfully! Welcome aboard!')
            return redirect('users:profile', pk=user.pk)
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'users/signup.html', {'form': form})


def login_view(request):
    """User login view"""
    if request.user.is_authenticated:
        return redirect('users:profile', pk=request.user.pk)
    
    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            
            # Update login stats
            client_info = get_client_info(request)
            user.update_login_stats(client_info['ip_address'])
            
            # Handle remember me
            if form.cleaned_data.get('remember_me'):
                request.session.set_expiry(1209600)  # 2 weeks
            
            messages.success(request, f'Welcome back, {user.get_short_name()}!')
            
            # Redirect to next or profile
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            return redirect('users:profile', pk=user.pk)
    else:
        form = CustomLoginForm()
    
    return render(request, 'users/login.html', {'form': form})


def logout_view(request):
    """User logout view"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('users:login')


class UserListView(ListView):
    """List all users (public profiles)"""
    model = CustomUser
    template_name = 'users/user_list.html'
    context_object_name = 'users'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = CustomUser.objects.filter(
            is_active=True,
            profile__is_public=True
        ).select_related('profile').order_by('-date_joined')
        
        # Search functionality
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(username__icontains=query) |
                Q(profile__full_name__icontains=query) |
                Q(profile__bio__icontains=query)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        return context


class ProfileDetailView(DetailView):
    """View user profile"""
    model = CustomUser
    template_name = 'users/profile.html'
    context_object_name = 'profile_user'
    
    def get_object(self, queryset=None):
        user = get_object_or_404(CustomUser, pk=self.kwargs['pk'])
        
        # Check if profile is public or if viewing own profile
        if not user.profile.is_public and user != self.request.user:
            return HttpResponseForbidden("This profile is private.")
        
        return user
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.object
        
        # Get cached profile data
        profile_data = UserCache.get_user_profile(user.id)
        context['profile_data'] = profile_data
        
        # Check if viewing own profile
        context['is_own_profile'] = self.request.user == user
        
        return context


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    """Update user profile"""
    model = Profile
    form_class = ProfileForm
    template_name = 'users/profile_edit.html'
    
    def get_object(self, queryset=None):
        return self.request.user.profile
    
    def get_success_url(self):
        return reverse('users:profile', kwargs={'pk': self.request.user.pk})
    
    def form_valid(self, form):
        messages.success(self.request, 'Profile updated successfully!')
        return super().form_valid(form)


@login_required
def profile_settings_view(request):
    """User profile settings"""
    user_form = UserUpdateForm(instance=request.user)
    profile_form = ProfileForm(instance=request.user.profile)
    password_form = PasswordChangeForm(request.user)
    
    if request.method == 'POST':
        if 'update_profile' in request.POST:
            user_form = UserUpdateForm(request.POST, instance=request.user)
            profile_form = ProfileForm(request.POST, request.FILES, instance=request.user.profile)
            
            if user_form.is_valid() and profile_form.is_valid():
                user_form.save()
                profile_form.save()
                messages.success(request, 'Profile updated successfully!')
                return redirect('users:settings')
        
        elif 'change_password' in request.POST:
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                password_form.save()
                messages.success(request, 'Password changed successfully!')
                return redirect('users:settings')
    
    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'password_form': password_form,
    }
    
    return render(request, 'users/settings.html', context)


# API ViewSets
class UserViewSet(viewsets.ModelViewSet):
    """API ViewSet for User operations"""
    queryset = CustomUser.objects.filter(is_active=True)
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return UserListSerializer
        elif self.action == 'create':
            return UserRegistrationSerializer
        return UserSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Only allow users to see public profiles or their own
        if self.request.user.is_authenticated:
            queryset = queryset.filter(
                Q(profile__is_public=True) | Q(id=self.request.user.id)
            )
        else:
            queryset = queryset.filter(profile__is_public=True)
        
        return queryset.select_related('profile')
    
    def perform_create(self, serializer):
        user = serializer.save()
        # Create auth token
        Token.objects.create(user=user)
    
    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def me(self, request):
        """Get current user's profile"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def register(self, request):
        """Register new user"""
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token, created = Token.objects.get_or_create(user=user)
            
            return Response({
                'user': UserSerializer(user).data,
                'token': token.key
            }, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def login(self, request):
        """User login endpoint"""
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            token, created = Token.objects.get_or_create(user=user)
            
            # Update login stats
            client_info = get_client_info(request)
            user.update_login_stats(client_info['ip_address'])
            
            return Response({
                'user': UserSerializer(user).data,
                'token': token.key
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def logout(self, request):
        """User logout endpoint"""
        try:
            request.user.auth_token.delete()
        except:
            pass
        return Response({'message': 'Successfully logged out'})
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def change_password(self, request):
        """Change user password"""
        serializer = PasswordChangeSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Password changed successfully'})
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProfileViewSet(viewsets.ModelViewSet):
    """API ViewSet for Profile operations"""
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter based on privacy settings
        if self.request.user.is_authenticated:
            queryset = queryset.filter(
                Q(is_public=True) | Q(user=self.request.user)
            )
        else:
            queryset = queryset.filter(is_public=True)
        
        return queryset.select_related('user')
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['list', 'retrieve']:
            permission_classes = [permissions.AllowAny]
        else:
            permission_classes = [permissions.IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    def get_object(self):
        """Override to handle own profile access"""
        if self.kwargs.get('pk') == 'me':
            return self.request.user.profile
        return super().get_object()
    
    def perform_update(self, serializer):
        # Only allow users to update their own profile
        if serializer.instance.user != self.request.user:
            raise PermissionError("You can only update your own profile")
        serializer.save()
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search profiles"""
        query = request.GET.get('q', '')
        if not query:
            return Response({'results': []})
        
        profiles = Profile.objects.get_public_profiles().search_profiles(query)[:20]
        serializer = self.get_serializer(profiles, many=True)
        
        return Response({
            'results': serializer.data,
            'count': len(serializer.data)
        })
    
    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Get profile statistics"""
        profile = self.get_object()
        
        # Only allow viewing own stats or public profiles
        if profile.user != request.user and not profile.is_public:
            return Response({'error': 'Permission denied'}, status=403)
        
        from .utils import UserStatsCalculator
        stats = UserStatsCalculator.get_user_activity_stats(profile.user)
        completion = UserStatsCalculator.calculate_profile_completion(profile)
        
        return Response({
            'activity_stats': stats,
            'profile_completion': completion
        })