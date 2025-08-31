# File: DjangoVerseHub/apps/articles/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from .models import Article, Category, Tag


class ArticleTagInline(admin.TabularInline):
    """Inline for article tags"""
    model = Article.tags.through
    extra = 3


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin for Category model"""
    list_display = ['name', 'slug', 'article_count_display', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'article_count_display']

    def article_count_display(self, obj):
        count = obj.article_count
        if count > 0:
            url = reverse('admin:articles_article_changelist') + f'?category__id__exact={obj.id}'
            return format_html('<a href="{}">{}</a>', url, count)
        return count
    article_count_display.short_description = _('Articles')


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """Admin for Tag model"""
    list_display = ['name', 'slug', 'article_count_display', 'created_at']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'article_count_display']

    def article_count_display(self, obj):
        count = obj.article_count
        if count > 0:
            url = reverse('admin:articles_article_changelist') + f'?tags__id__exact={obj.id}'
            return format_html('<a href="{}">{}</a>', url, count)
        return count
    article_count_display.short_description = _('Articles')


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    """Admin for Article model"""
    list_display = [
        'title', 'author', 'category', 'status', 'is_featured', 
        'views_count', 'likes_count', 'published_at', 'created_at'
    ]
    list_filter = [
        'status', 'is_featured', 'allow_comments', 'category', 
        'created_at', 'published_at', 'tags'
    ]
    search_fields = ['title', 'content', 'summary', 'author__email']
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ['tags']
    raw_id_fields = ['author']
    readonly_fields = [
        'id', 'views_count', 'likes_count', 'shares_count', 
        'created_at', 'updated_at', 'reading_time_display'
    ]
    date_hierarchy = 'created_at'
    actions = ['make_published', 'make_draft', 'make_featured', 'remove_featured']

    fieldsets = (
        (_('Content'), {
            'fields': ('title', 'slug', 'author', 'category', 'tags')
        }),
        (_('Article Content'), {
            'fields': ('summary', 'content', 'featured_image')
        }),
        (_('Publishing'), {
            'fields': ('status', 'published_at', 'is_featured', 'allow_comments')
        }),
        (_('SEO'), {
            'fields': ('meta_description', 'meta_keywords'),
            'classes': ('collapse',)
        }),
        (_('Statistics'), {
            'fields': ('views_count', 'likes_count', 'shares_count', 'reading_time_display'),
            'classes': ('collapse',)
        }),
        (_('Metadata'), {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def reading_time_display(self, obj):
        return f"{obj.reading_time} min"
    reading_time_display.short_description = _('Reading Time')

    def make_published(self, request, queryset):
        count = queryset.update(status='published')
        self.message_user(request, f'{count} articles marked as published.')
    make_published.short_description = _('Mark selected articles as published')

    def make_draft(self, request, queryset):
        count = queryset.update(status='draft')
        self.message_user(request, f'{count} articles marked as draft.')
    make_draft.short_description = _('Mark selected articles as draft')

    def make_featured(self, request, queryset):
        count = queryset.update(is_featured=True)
        self.message_user(request, f'{count} articles marked as featured.')
    make_featured.short_description = _('Mark selected articles as featured')

    def remove_featured(self, request, queryset):
        count = queryset.update(is_featured=False)
        self.message_user(request, f'{count} articles removed from featured.')
    remove_featured.short_description = _('Remove from featured')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('author', 'category')