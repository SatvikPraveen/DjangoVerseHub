# File: DjangoVerseHub/apps/articles/forms.py

from django import forms
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from .models import Article, Category, Tag


class ArticleForm(forms.ModelForm):
    """Form for creating and editing articles"""
    
    title = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter article title...'
        })
    )
    
    summary = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Brief summary of your article...'
        })
    )
    
    content = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 15,
            'placeholder': 'Write your article content here...'
        })
    )
    
    category = forms.ModelChoiceField(
        queryset=Category.objects.active(),
        required=False,
        empty_label="Select a category",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    tags = forms.ModelMultipleChoiceField(
        queryset=Tag.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    
    featured_image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )
    
    meta_description = forms.CharField(
        max_length=160,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'SEO meta description...'
        })
    )
    
    meta_keywords = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Comma-separated keywords...'
        })
    )

    class Meta:
        model = Article
        fields = [
            'title', 'summary', 'content', 'category', 'tags',
            'featured_image', 'status', 'is_featured', 'allow_comments',
            'meta_description', 'meta_keywords'
        ]
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'is_featured': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'allow_comments': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # If user is not staff, remove featured option
        if self.user and not self.user.is_staff:
            del self.fields['is_featured']

    def clean_title(self):
        title = self.cleaned_data.get('title')
        if len(title.strip()) < 5:
            raise ValidationError(_('Title must be at least 5 characters long.'))
        return title

    def clean_content(self):
        content = self.cleaned_data.get('content')
        if len(content.strip()) < 100:
            raise ValidationError(_('Content must be at least 100 characters long.'))
        return content

    def clean_featured_image(self):
        featured_image = self.cleaned_data.get('featured_image')
        if featured_image:
            if featured_image.size > 5 * 1024 * 1024:  # 5MB
                raise ValidationError(_('Image file too large ( > 5MB )'))
            
            if not featured_image.content_type.startswith('image/'):
                raise ValidationError(_('Please upload a valid image file.'))
        
        return featured_image

    def save(self, commit=True):
        article = super().save(commit=False)
        
        if self.user:
            article.author = self.user
        
        if commit:
            article.save()
            self.save_m2m()
        
        return article


class ArticleSearchForm(forms.Form):
    """Form for searching articles"""
    
    q = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search articles...'
        })
    )
    
    category = forms.ModelChoiceField(
        queryset=Category.objects.active(),
        required=False,
        empty_label="All categories",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    tag = forms.ModelChoiceField(
        queryset=Tag.objects.all(),
        required=False,
        empty_label="All tags",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    status = forms.ChoiceField(
        choices=[('', 'All statuses')] + Article.STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    ordering = forms.ChoiceField(
        choices=[
            ('-created_at', 'Newest first'),
            ('created_at', 'Oldest first'),
            ('-views_count', 'Most viewed'),
            ('-likes_count', 'Most liked'),
            ('title', 'Title A-Z'),
            ('-title', 'Title Z-A'),
        ],
        required=False,
        initial='-created_at',
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class CategoryForm(forms.ModelForm):
    """Form for creating and editing categories"""
    
    name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Category name...'
        })
    )
    
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Category description...'
        })
    )
    
    image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Category
        fields = ['name', 'description', 'image', 'is_active']
        widgets = {
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if Category.objects.filter(name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise ValidationError(_('Category with this name already exists.'))
        return name

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            if image.size > 2 * 1024 * 1024:  # 2MB
                raise ValidationError(_('Image file too large ( > 2MB )'))
            
            if not image.content_type.startswith('image/'):
                raise ValidationError(_('Please upload a valid image file.'))
        
        return image


class TagForm(forms.ModelForm):
    """Form for creating and editing tags"""
    
    name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Tag name...'
        })
    )

    class Meta:
        model = Tag
        fields = ['name']

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if Tag.objects.filter(name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise ValidationError(_('Tag with this name already exists.'))
        return name.lower()


class ArticleFilterForm(forms.Form):
    """Form for filtering articles in admin-like interfaces"""
    
    author = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Filter by author...'
        })
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    min_views = forms.IntegerField(
        required=False,
        min_value=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Minimum views...'
        })
    )
    
    featured_only = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )