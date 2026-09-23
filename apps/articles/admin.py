# File: DjangoVerseHub/apps/articles/admin.py

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Article, ArticleLike, ArticleRevision, Bookmark, Category, Tag


class ArticleCountAdminMixin:
    """Shared 'Articles' column linking to the filtered article changelist."""

    filter_param = ''

    def get_queryset(self, request):
        return super().get_queryset(request).with_article_count()

    def article_count_display(self, obj):
        count = obj.article_count
        if count > 0:
            url = reverse('admin:articles_article_changelist') + f'?{self.filter_param}={obj.id}'
            return format_html('<a href="{}">{}</a>', url, count)
        return count
    article_count_display.short_description = _('Articles')
    article_count_display.admin_order_field = 'article_count'


@admin.register(Category)
class CategoryAdmin(ArticleCountAdminMixin, admin.ModelAdmin):
    """Admin for Category model"""
    filter_param = 'category__id__exact'
    list_display = ['name', 'slug', 'article_count_display', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at']


@admin.register(Tag)
class TagAdmin(ArticleCountAdminMixin, admin.ModelAdmin):
    """Admin for Tag model"""
    filter_param = 'tags__id__exact'
    list_display = ['name', 'slug', 'article_count_display', 'created_at']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at']


class ArticleRevisionInline(admin.TabularInline):
    model = ArticleRevision
    extra = 0
    can_delete = False
    fields = ['created_at', 'editor', 'title']
    readonly_fields = ['created_at', 'editor', 'title']
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    """Admin for Article model"""
    list_display = [
        'title', 'author', 'category', 'status', 'is_featured',
        'views_count', 'likes_count', 'published_at', 'created_at',
    ]
    list_filter = [
        'status', 'is_featured', 'allow_comments', 'category',
        'created_at', 'published_at', 'tags',
    ]
    search_fields = ['title', 'content', 'summary', 'author__email']
    prepopulated_fields = {'slug': ('title',)}
    filter_horizontal = ['tags']
    raw_id_fields = ['author']
    readonly_fields = [
        'id', 'views_count', 'likes_count', 'shares_count',
        'created_at', 'updated_at', 'reading_time_display',
    ]
    date_hierarchy = 'created_at'
    actions = ['make_published', 'make_draft', 'make_featured', 'remove_featured']
    inlines = [ArticleRevisionInline]

    fieldsets = (
        (_('Content'), {'fields': ('title', 'slug', 'author', 'category', 'tags')}),
        (_('Article Content'), {'fields': ('summary', 'content', 'featured_image')}),
        (_('Publishing'), {'fields': ('status', 'published_at', 'is_featured', 'allow_comments')}),
        (_('SEO'), {'fields': ('meta_description', 'meta_keywords'), 'classes': ('collapse',)}),
        (_('Statistics'), {
            'fields': ('views_count', 'likes_count', 'shares_count', 'reading_time_display'),
            'classes': ('collapse',),
        }),
        (_('Metadata'), {'fields': ('id', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('author', 'category')

    def save_model(self, request, obj, form, change):
        obj.save(editor=request.user)

    def reading_time_display(self, obj):
        return f'{obj.reading_time} min'
    reading_time_display.short_description = _('Reading Time')

    @admin.action(description=_('Mark selected articles as published'))
    def make_published(self, request, queryset):
        # Go through save() so published_at is set consistently
        count = 0
        for article in queryset.exclude(status='published'):
            article.status = 'published'
            article.save(editor=request.user)
            count += 1
        self.message_user(request, f'{count} articles marked as published.')

    @admin.action(description=_('Mark selected articles as draft'))
    def make_draft(self, request, queryset):
        count = queryset.update(status='draft', published_at=None)
        self.message_user(request, f'{count} articles marked as draft.')

    @admin.action(description=_('Mark selected articles as featured'))
    def make_featured(self, request, queryset):
        count = queryset.update(is_featured=True)
        self.message_user(request, f'{count} articles marked as featured.')

    @admin.action(description=_('Remove from featured'))
    def remove_featured(self, request, queryset):
        count = queryset.update(is_featured=False)
        self.message_user(request, f'{count} articles removed from featured.')


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ['user', 'article', 'created_at']
    search_fields = ['user__email', 'article__title']
    raw_id_fields = ['user', 'article']
    date_hierarchy = 'created_at'


@admin.register(ArticleLike)
class ArticleLikeAdmin(admin.ModelAdmin):
    list_display = ['user', 'article', 'created_at']
    search_fields = ['user__email', 'article__title']
    raw_id_fields = ['user', 'article']
    date_hierarchy = 'created_at'


@admin.register(ArticleRevision)
class ArticleRevisionAdmin(admin.ModelAdmin):
    list_display = ['article', 'title', 'editor', 'created_at']
    search_fields = ['article__title', 'title']
    raw_id_fields = ['article', 'editor']
    readonly_fields = ['article', 'editor', 'title', 'summary', 'content', 'created_at']
    date_hierarchy = 'created_at'

    def has_add_permission(self, request):
        return False
