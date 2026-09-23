# File: DjangoVerseHub/apps/core/sitemaps.py

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.articles.models import Article, Category, Tag


class StaticViewSitemap(Sitemap):
    priority = 0.5
    changefreq = 'monthly'

    def items(self):
        return [
            'core:home',
            'core:getting-started',
            'core:guidelines',
            'core:faq',
            'core:api',
            'core:contact',
            'core:privacy',
            'core:terms',
            'core:cookies',
            'articles:list',
            'articles:category_list',
            'articles:tags',
        ]

    def location(self, item):
        return reverse(item)


class ArticleSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.8

    def items(self):
        return Article.published.all().only('slug', 'updated_at')

    def lastmod(self, obj):
        return obj.updated_at


class CategorySitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        return Category.objects.filter(is_active=True)


class TagSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.4

    def items(self):
        return Tag.objects.all()


sitemaps = {
    'static': StaticViewSitemap,
    'articles': ArticleSitemap,
    'categories': CategorySitemap,
    'tags': TagSitemap,
}
