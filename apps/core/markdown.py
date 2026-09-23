# File: DjangoVerseHub/apps/core/markdown.py
"""
Markdown rendering with HTML sanitisation.

User content is rendered with python-markdown and then passed through nh3
(an ammonia/Rust based sanitiser) with an explicit allow-list, so authors can
use headings, code blocks, tables and links while script tags, event handler
attributes and javascript: URLs never reach the page. Rendered output is
cached by content hash because rendering is pure.
"""

import hashlib

import markdown as _markdown
import nh3

from django.core.cache import cache

MARKDOWN_EXTENSIONS = ["fenced_code", "tables", "sane_lists", "smarty", "toc", "nl2br"]
MARKDOWN_EXTENSION_CONFIGS = {"toc": {"permalink": False, "toc_depth": "2-4"}}

_BASE_TAGS = {
    "p",
    "br",
    "strong",
    "em",
    "b",
    "i",
    "u",
    "s",
    "del",
    "code",
    "pre",
    "blockquote",
    "ul",
    "ol",
    "li",
    "a",
    "hr",
    "span",
    "sup",
    "sub",
    "kbd",
}
_ARTICLE_TAGS = _BASE_TAGS | {
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "img",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "figure",
    "figcaption",
    "details",
    "summary",
    "dl",
    "dt",
    "dd",
}

_BASE_ATTRIBUTES = {
    "a": {"href", "title"},
    "code": {"class"},
    "pre": {"class"},
    "span": {"class"},
    "li": {"value"},
    "ol": {"start"},
}
_ARTICLE_ATTRIBUTES = {
    **_BASE_ATTRIBUTES,
    "img": {"src", "alt", "title", "width", "height", "loading"},
    "th": {"align", "colspan", "rowspan"},
    "td": {"align", "colspan", "rowspan"},
    "h1": {"id"},
    "h2": {"id"},
    "h3": {"id"},
    "h4": {"id"},
    "h5": {"id"},
    "h6": {"id"},
}

PROFILES = {
    "article": {"tags": _ARTICLE_TAGS, "attributes": _ARTICLE_ATTRIBUTES},
    "comment": {"tags": _BASE_TAGS, "attributes": _BASE_ATTRIBUTES},
}

_URL_SCHEMES = {"http", "https", "mailto"}
_CACHE_TTL = 60 * 60 * 24


def _attribute_filter(tag, attribute, value):
    # Only allow language-* classes on code blocks so authors can't inject arbitrary styling hooks.
    if tag in {"code", "pre", "span"} and attribute == "class":
        classes = [c for c in value.split() if c.startswith("language-") or c in {"highlight", "codehilite"}]
        return " ".join(classes) or None
    return value


def sanitize_html(html, profile="article"):
    """Strip everything that is not on the allow-list for the given profile."""
    spec = PROFILES[profile]
    return nh3.clean(
        html,
        tags=spec["tags"],
        attributes=spec["attributes"],
        url_schemes=_URL_SCHEMES,
        link_rel="nofollow noopener noreferrer",
        attribute_filter=_attribute_filter,
        strip_comments=True,
    )


def render_markdown(text, profile="article", use_cache=True):
    """Convert Markdown text to sanitised HTML. Safe to mark as safe in templates."""
    if not text:
        return ""
    key = None
    if use_cache:
        digest = hashlib.sha256(f"{profile}:{text}".encode()).hexdigest()
        key = f"md:{digest}"
        cached = cache.get(key)
        if cached is not None:
            return cached

    html = _markdown.markdown(
        text,
        extensions=MARKDOWN_EXTENSIONS,
        extension_configs=MARKDOWN_EXTENSION_CONFIGS,
        output_format="html",
    )
    clean = sanitize_html(html, profile=profile)
    if key:
        cache.set(key, clean, _CACHE_TTL)
    return clean


def markdown_to_text(text, limit=None):
    """Plain-text version of Markdown (for summaries, feeds and search indexes)."""
    from django.utils.html import strip_tags

    plain = " ".join(strip_tags(render_markdown(text, use_cache=False)).split())
    if limit and len(plain) > limit:
        plain = plain[: limit - 1].rstrip() + "…"
    return plain
