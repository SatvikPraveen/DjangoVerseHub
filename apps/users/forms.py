# File: DjangoVerseHub/apps/users/forms.py

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import CustomUser, Profile
from .utils import authenticate_by_identifier


class CustomUserCreationForm(UserCreationForm):
    """Custom user creation form with email and additional fields"""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "Enter your email address"}),
    )
    username = forms.CharField(
        max_length=150, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Choose a username"})
    )
    first_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "First name (optional)"}),
    )
    last_name = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Last name (optional)"}),
    )
    terms_accepted = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        error_messages={"required": "You must accept the terms and conditions."},
    )

    class Meta:
        model = CustomUser
        fields = ("email", "username", "first_name", "last_name", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].widget.attrs.update({"class": "form-control", "placeholder": "Create a password"})
        self.fields["password2"].widget.attrs.update({"class": "form-control", "placeholder": "Confirm your password"})

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and CustomUser.objects.filter(email__iexact=email).exists():
            raise ValidationError(_("A user with this email already exists."))
        return email

    def clean_username(self):
        username = self.cleaned_data.get("username")
        if username and CustomUser.objects.filter(username__iexact=username).exists():
            raise ValidationError(_("A user with this username already exists."))

        # Check for prohibited usernames
        prohibited = ["admin", "administrator", "root", "api", "www", "mail"]
        if username and username.lower() in prohibited:
            raise ValidationError(_("This username is not allowed."))

        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class CustomLoginForm(AuthenticationForm):
    """Custom login form with email/username support"""

    username = forms.CharField(
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Email or Username", "autofocus": True})
    )
    password = forms.CharField(widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Password"}))
    remember_me = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username is not None and password:
            self.user_cache = authenticate_by_identifier(self.request, username, password)
            if self.user_cache is None:
                raise ValidationError(_("Please enter a correct email/username and password."), code="invalid_login")
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class ProfileForm(forms.ModelForm):
    """Form for updating user profile"""

    class Meta:
        model = Profile
        fields = [
            "full_name",
            "bio",
            "avatar",
            "cover_image",
            "gender",
            "location",
            "website",
            "twitter",
            "linkedin",
            "github",
            "theme",
            "timezone",
            "language",
            "is_public",
            "show_email",
            "show_real_name",
            "email_notifications",
            "push_notifications",
            "marketing_emails",
        ]
        widgets = {
            "full_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Your full name"}),
            "bio": forms.Textarea(
                attrs={"class": "form-control", "rows": 4, "placeholder": "Tell us about yourself..."}
            ),
            "avatar": forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "cover_image": forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "gender": forms.Select(attrs={"class": "form-select"}),
            "location": forms.TextInput(attrs={"class": "form-control", "placeholder": "Your location"}),
            "website": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://yourwebsite.com"}),
            "twitter": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://twitter.com/username"}),
            "linkedin": forms.URLInput(
                attrs={"class": "form-control", "placeholder": "https://linkedin.com/in/username"}
            ),
            "github": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://github.com/username"}),
            "theme": forms.Select(attrs={"class": "form-select"}),
            "timezone": forms.TextInput(attrs={"class": "form-control", "placeholder": "UTC"}),
            "language": forms.TextInput(attrs={"class": "form-control", "placeholder": "en"}),
            "is_public": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "show_email": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "show_real_name": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "email_notifications": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "push_notifications": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "marketing_emails": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    # Fields with model defaults that a partial form submission may omit.
    _DEFAULTED_FIELDS = ("theme", "timezone", "language")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self._DEFAULTED_FIELDS:
            self.fields[name].required = False

    def _default_for(self, name):
        value = self.cleaned_data.get(name)
        if value in (None, ""):
            return Profile._meta.get_field(name).get_default()
        return value

    def clean_theme(self):
        return self._default_for("theme")

    def clean_timezone(self):
        return self._default_for("timezone")

    def clean_language(self):
        return self._default_for("language")

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar:
            if avatar.size > 5 * 1024 * 1024:  # 5MB limit
                raise ValidationError(_("Avatar file size must be under 5MB."))

            if not getattr(avatar, "content_type", "image/").startswith("image/"):
                raise ValidationError(_("Avatar must be an image file."))

        return avatar

    def clean_cover_image(self):
        cover_image = self.cleaned_data.get("cover_image")
        if cover_image:
            if cover_image.size > 10 * 1024 * 1024:  # 10MB limit
                raise ValidationError(_("Cover image file size must be under 10MB."))

            if not getattr(cover_image, "content_type", "image/").startswith("image/"):
                raise ValidationError(_("Cover image must be an image file."))

        return cover_image


class UserUpdateForm(forms.ModelForm):
    """Form for updating basic user information"""

    class Meta:
        model = CustomUser
        fields = ["first_name", "last_name", "phone_number", "date_of_birth"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "First name"}),
            "last_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Last name"}),
            "phone_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "+1234567890"}),
            "date_of_birth": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }

    def clean_phone_number(self):
        phone = self.cleaned_data.get("phone_number")
        if phone:
            # Basic phone validation
            import re

            phone_pattern = re.compile(r"^\+?[\d\s\-\(\)]{10,}$")
            if not phone_pattern.match(phone):
                raise ValidationError(_("Enter a valid phone number."))
        return phone


class PasswordChangeForm(forms.Form):
    """Custom password change form"""

    current_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Current password"})
    )
    new_password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "New password"})
    )
    new_password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Confirm new password"})
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        current_password = self.cleaned_data.get("current_password")
        if not self.user.check_password(current_password):
            raise ValidationError(_("Your current password is incorrect."))
        return current_password

    def clean_new_password2(self):
        password1 = self.cleaned_data.get("new_password1")
        password2 = self.cleaned_data.get("new_password2")

        if password1 and password2 and password1 != password2:
            raise ValidationError(_("The two password fields didn't match."))

        return password2

    def save(self):
        password = self.cleaned_data["new_password1"]
        self.user.set_password(password)
        self.user.save()
        return self.user
