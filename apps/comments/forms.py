# File: DjangoVerseHub/apps/comments/forms.py

from django import forms
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from .models import Comment
import re


class CommentForm(forms.ModelForm):
    """Form for creating comments"""
    
    content = forms.CharField(
        max_length=1000,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Share your thoughts...',
            'required': True
        }),
        help_text=_('Maximum 1000 characters')
    )

    class Meta:
        model = Comment
        fields = ['content']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.content_object = kwargs.pop('content_object', None)
        self.parent = kwargs.pop('parent', None)
        super().__init__(*args, **kwargs)

    def clean_content(self):
        """Validate comment content"""
        content = self.cleaned_data.get('content', '').strip()
        
        if len(content) < 3:
            raise ValidationError(_('Comment must be at least 3 characters long.'))
        
        # Check for spam patterns
        if self._is_spam(content):
            raise ValidationError(_('Comment appears to be spam.'))
        
        # Check for excessive caps
        if len(re.findall(r'[A-Z]', content)) / max(len(content), 1) > 0.8:
            raise ValidationError(_('Please don\'t use excessive capital letters.'))
        
        return content

    def _is_spam(self, content):
        """Basic spam detection"""
        spam_patterns = [
            r'https?://[^\s]+',  # URLs
            r'www\.[^\s]+',
            r'\b(buy|sale|discount|offer|free|win|prize)\b',  # Common spam words
            r'(.)\1{4,}',  # Repeated characters
        ]
        
        content_lower = content.lower()
        for pattern in spam_patterns:
            if re.search(pattern, content_lower):
                return True
        
        return False

    def save(self, commit=True):
        comment = super().save(commit=False)
        
        if self.user:
            comment.author = self.user
        
        if self.content_object:
            comment.content_object = self.content_object
        
        if self.parent:
            comment.parent = self.parent
            # Ensure parent is on same object
            comment.content_type = self.parent.content_type
            comment.object_id = self.parent.object_id
        
        if commit:
            comment.save()
        
        return comment


class CommentEditForm(forms.ModelForm):
    """Form for editing comments"""
    
    content = forms.CharField(
        max_length=1000,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4
        })
    )

    class Meta:
        model = Comment
        fields = ['content']

    def clean_content(self):
        """Validate edited content"""
        content = self.cleaned_data.get('content', '').strip()
        
        if len(content) < 3:
            raise ValidationError(_('Comment must be at least 3 characters long.'))
        
        return content

    def save(self, commit=True):
        comment = super().save(commit=False)
        
        # Mark as edited if content changed
        if self.has_changed():
            comment.mark_as_edited()
        
        if commit:
            comment.save()
        
        return comment


class CommentReplyForm(CommentForm):
    """Form specifically for replying to comments"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['content'].widget.attrs.update({
            'placeholder': 'Reply to this comment...',
            'rows': 3
        })

    def clean(self):
        """Additional validation for replies"""
        cleaned_data = super().clean()
        
        if self.parent and self.parent.get_thread_depth() >= 3:
            raise ValidationError(_('Cannot reply to comments more than 3 levels deep.'))
        
        return cleaned_data


class CommentModerationForm(forms.ModelForm):
    """Form for moderating comments (admin use)"""
    
    moderation_reason = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Reason for moderation action...'
        })
    )

    class Meta:
        model = Comment
        fields = ['is_active', 'is_flagged', 'moderation_reason']
        widgets = {
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_flagged': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CommentSearchForm(forms.Form):
    """Form for searching comments"""
    
    q = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search comments...'
        })
    )
    
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
    
    is_flagged = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class CommentFlagForm(forms.Form):
    """Form for flagging inappropriate comments"""
    
    REASON_CHOICES = [
        ('spam', _('Spam')),
        ('offensive', _('Offensive language')),
        ('harassment', _('Harassment')),
        ('off_topic', _('Off topic')),
        ('copyright', _('Copyright violation')),
        ('other', _('Other')),
    ]
    
    reason = forms.ChoiceField(
        choices=REASON_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    details = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Additional details (optional)...'
        })
    )

    def __init__(self, *args, **kwargs):
        self.comment = kwargs.pop('comment', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def save(self):
        """Process the flag report"""
        if self.comment:
            self.comment.flag()
            
            # Here you could create a FlagReport model to track flag details
            # FlagReport.objects.create(
            #     comment=self.comment,
            #     reporter=self.user,
            #     reason=self.cleaned_data['reason'],
            #     details=self.cleaned_data.get('details', '')
            # )
        
        return self.comment