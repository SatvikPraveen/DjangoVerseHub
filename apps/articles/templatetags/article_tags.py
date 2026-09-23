# File: DjangoVerseHub/apps/articles/templatetags/article_tags.py

import json

from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

from apps.core.markdown import markdown_to_text

register = template.Library()


def build_article_json_ld(article, request=None):
    """schema.org BlogPosting structured data for an article."""
    absolute = request.build_absolute_uri if request is not None else (lambda path: path)
    author = article.author
    data = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": article.title[:110],
        "description": article.meta_description or article.summary or markdown_to_text(article.content, 160),
        "url": absolute(article.get_absolute_url()),
        "mainEntityOfPage": absolute(article.get_absolute_url()),
        "datePublished": (article.published_at or article.created_at).isoformat(),
        "dateModified": article.updated_at.isoformat(),
        "author": {
            "@type": "Person",
            "name": author.get_full_name() or author.username,
            "url": absolute(author.get_absolute_url()),
        },
        "publisher": {"@type": "Organization", "name": getattr(settings, "SITE_NAME", "DjangoVerseHub")},
        "keywords": ", ".join(tag.name for tag in article.tags.all()),
        "wordCount": len(article.content.split()),
        "interactionStatistic": [
            {
                "@type": "InteractionCounter",
                "interactionType": "https://schema.org/LikeAction",
                "userInteractionCount": article.likes_count,
            },
            {
                "@type": "InteractionCounter",
                "interactionType": "https://schema.org/ViewAction",
                "userInteractionCount": article.views_count,
            },
        ],
    }
    if article.category_id:
        data["articleSection"] = article.category.name
    if article.featured_image:
        data["image"] = absolute(article.featured_image.url)
    return data


@register.simple_tag(takes_context=True)
def article_json_ld(context, article):
    data = build_article_json_ld(article, context.get("request"))
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return mark_safe(f'<script type="application/ld+json">{payload}</script>')
