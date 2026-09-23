# File: DjangoVerseHub/apps/comments/forms.py

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import MAX_THREAD_DEPTH, Comment, CommentFlag, target_accepts_comments
from .moderation import is_shouting


def _validate_content(content):
    content = (content or "").strip()
    if len(content) < 3:
        raise ValidationError(_("Comment must be at least 3 characters long."))
    if len(content) > 1000:
        raise ValidationError(_("Comment cannot exceed 1000 characters."))
    if is_shouting(content):
        raise ValidationError(_("Please don't use excessive capital letters."))
    return content


class CommentForm(forms.ModelForm):
    """Form for creating comments"""

    content = forms.CharField(
        max_length=1000,
        widget=forms.Textarea(
            attrs={"class": "form-control", "rows": 4, "placeholder": "Share your thoughts...", "required": True}
        ),
        help_text=_("Maximum 1000 characters"),
    )

    class Meta:
        model = Comment
        fields = ["content"]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        self.content_object = kwargs.pop("content_object", None)
        self.parent = kwargs.pop("parent", None)
        super().__init__(*args, **kwargs)
        if self.parent is not None and self.content_object is None:
            self.content_object = self.parent.content_object

    def clean_content(self):
        return _validate_content(self.cleaned_data.get("content"))

    def clean(self):
        cleaned_data = super().clean()
        if self.parent is not None:
            if not self.parent.is_active:
                raise ValidationError(_("You cannot reply to a removed comment."))
            if self.parent.get_thread_depth() >= MAX_THREAD_DEPTH:
                raise ValidationError(
                    _("Cannot reply to comments more than %(depth)s levels deep.") % {"depth": MAX_THREAD_DEPTH}
                )
        if self.content_object is None:
            raise ValidationError(_("There is nothing to comment on."))
        if not target_accepts_comments(self.content_object):
            raise ValidationError(_("Comments are closed for this content."))
        return cleaned_data

    def save(self, commit=True):
        comment = super().save(commit=False)
        if self.user is not None:
            comment.author = self.user
        if self.parent is not None:
            comment.parent = self.parent
            comment.content_type = self.parent.content_type
            comment.object_id = self.parent.object_id
        else:
            comment.content_object = self.content_object
        if commit:
            comment.save()
        return comment


class CommentReplyForm(CommentForm):
    """Form specifically for replying to comments"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["content"].widget.attrs.update({"placeholder": "Reply to this comment...", "rows": 3})


class CommentEditForm(forms.ModelForm):
    """Form for editing comments"""

    content = forms.CharField(max_length=1000, widget=forms.Textarea(attrs={"class": "form-control", "rows": 4}))

    class Meta:
        model = Comment
        fields = ["content"]

    def clean_content(self):
        return _validate_content(self.cleaned_data.get("content"))

    def save(self, commit=True):
        comment = super().save(commit=False)
        if "content" in self.changed_data:
            comment.is_edited = True
        if commit:
            comment.save()
        return comment


class CommentSearchForm(forms.Form):
    """Filters for the comment list."""

    q = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Search comments..."}),
    )
    author = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Filter by author..."}),
    )
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}))
    is_flagged = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))


class CommentFlagForm(forms.Form):
    """Form for reporting a comment."""

    reason = forms.ChoiceField(choices=CommentFlag.Reason.choices, widget=forms.Select(attrs={"class": "form-select"}))
    details = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(
            attrs={"class": "form-control", "rows": 3, "placeholder": "Additional details (optional)..."}
        ),
    )

    def __init__(self, *args, **kwargs):
        self.comment = kwargs.pop("comment", None)
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        if self.comment is None or self.user is None:
            raise ValidationError(_("Nothing to flag."))
        if self.comment.author_id == self.user.pk:
            raise ValidationError(_("You cannot flag your own comment."))
        if CommentFlag.objects.filter(comment=self.comment, user=self.user).exists():
            raise ValidationError(_("You have already flagged this comment."))
        return cleaned_data

    def save(self):
        flag, _created = self.comment.add_flag(
            self.user,
            reason=self.cleaned_data["reason"],
            details=self.cleaned_data.get("details", ""),
        )
        return flag
