# File: DjangoVerseHub/apps/core/templatetags/core_tags.py

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(takes_context=True)
def update_query(context, **kwargs):
    """
    Return the current query string with the given parameters added or replaced.
    A value of None removes the parameter. Output has no leading '?'.

        <a href="?{% update_query page=2 %}">   ->  ?q=django&page=2
    """
    request = context.get("request")
    params = request.GET.copy() if request is not None else {}
    for key, value in kwargs.items():
        if value is None:
            params.pop(key, None)
        else:
            params[key] = value
    return params.urlencode() if hasattr(params, "urlencode") else ""


@register.filter
def initials(user):
    """Two-letter initials for avatar placeholders."""
    if user is None:
        return "?"
    name = (getattr(user, "get_full_name", lambda: "")() or getattr(user, "username", "") or "?").strip()
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return name[:2].upper()


@register.simple_tag
def active_if(current, expected, css_class="active"):
    return css_class if current == expected else ""


@register.filter
def humanize_count(value):
    """1234 -> 1.2K, 1500000 -> 1.5M."""
    try:
        value = int(value)
    except (TypeError, ValueError):
        return value
    for threshold, suffix in ((1_000_000, "M"), (1_000, "K")):
        if value >= threshold:
            text = f"{value / threshold:.1f}".rstrip("0").rstrip(".")
            return f"{text}{suffix}"
    return str(value)


@register.simple_tag
def badge(text, kind="secondary"):
    return format_html('<span class="badge bg-{}">{}</span>', kind, text)


@register.simple_tag
def json_ld(data):
    """Embed a structured-data dict as a JSON-LD script tag."""
    import json

    return mark_safe(f'<script type="application/ld+json">{json.dumps(data)}</script>')  # noqa: S308
