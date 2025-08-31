# File: DjangoVerseHub/apps/articles/serializers.py

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Article, Category, Tag

User = get_user_model()


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for Category model"""
    
    article_count = serializers.ReadOnlyField()
    
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'image', 'article_count', 'created_at']
        read_only_fields = ['slug', 'created_at']


class TagSerializer(serializers.ModelSerializer):
    """Serializer for Tag model"""
    
    article_count = serializers.ReadOnlyField()
    
    class Meta:
        model = Tag
        fields = ['id', 'name', 'slug', 'article_count', 'created_at']
        read_only_fields = ['slug', 'created_at']


class AuthorSerializer(serializers.ModelSerializer):
    """Serializer for article author"""
    
    full_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'full_name', 'avatar_url', 'date_joined']
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    
    def get_avatar_url(self, obj):
        if hasattr(obj, 'profile') and obj.profile.avatar:
            return obj.profile.get_avatar_url()
        return '/static/images/default-avatar.png'


class ArticleListSerializer(serializers.ModelSerializer):
    """Serializer for article list view"""
    
    author = AuthorSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    featured_image_url = serializers.SerializerMethodField()
    comment_count = serializers.ReadOnlyField()
    reading_time = serializers.ReadOnlyField()
    is_published = serializers.ReadOnlyField()
    
    class Meta:
        model = Article
        fields = [
            'id', 'title', 'slug', 'author', 'category', 'tags',
            'summary', 'featured_image_url', 'status', 'is_featured',
            'views_count', 'likes_count', 'comment_count', 'reading_time',
            'is_published', 'published_at', 'created_at', 'updated_at'
        ]
    
    def get_featured_image_url(self, obj):
        return obj.get_featured_image_url()


class ArticleDetailSerializer(serializers.ModelSerializer):
    """Serializer for article detail view"""
    
    author = AuthorSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    featured_image_url = serializers.SerializerMethodField()
    comment_count = serializers.ReadOnlyField()
    reading_time = serializers.ReadOnlyField()
    is_published = serializers.ReadOnlyField()
    related_articles = serializers.SerializerMethodField()
    
    class Meta:
        model = Article
        fields = [
            'id', 'title', 'slug', 'author', 'category', 'tags',
            'summary', 'content', 'featured_image_url', 'status', 
            'is_featured', 'allow_comments', 'views_count', 'likes_count',
            'shares_count', 'comment_count', 'reading_time', 'is_published',
            'meta_description', 'meta_keywords', 'published_at', 
            'created_at', 'updated_at', 'related_articles'
        ]
    
    def get_featured_image_url(self, obj):
        return obj.get_featured_image_url()
    
    def get_related_articles(self, obj):
        related = obj.get_related_articles(limit=3)
        return ArticleListSerializer(related, many=True, context=self.context).data


class ArticleCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating articles"""
    
    tags = serializers.PrimaryKeyRelatedField(
        many=True, 
        queryset=Tag.objects.all(), 
        required=False
    )
    
    class Meta:
        model = Article
        fields = [
            'title', 'summary', 'content', 'category', 'tags',
            'featured_image', 'status', 'is_featured', 'allow_comments',
            'meta_description', 'meta_keywords'
        ]
    
    def validate_title(self, value):
        if len(value.strip()) < 5:
            raise serializers.ValidationError("Title must be at least 5 characters long.")
        return value
    
    def validate_content(self, value):
        if len(value.strip()) < 100:
            raise serializers.ValidationError("Content must be at least 100 characters long.")
        return value
    
    def validate_featured_image(self, value):
        if value:
            if value.size > 5 * 1024 * 1024:  # 5MB
                raise serializers.ValidationError("Image file too large ( > 5MB )")
        return value
    
    def create(self, validated_data):
        tags_data = validated_data.pop('tags', [])
        article = Article.objects.create(**validated_data)
        article.tags.set(tags_data)
        return article
    
    def update(self, instance, validated_data):
        tags_data = validated_data.pop('tags', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        if tags_data is not None:
            instance.tags.set(tags_data)
        
        return instance


class ArticleStatsSerializer(serializers.ModelSerializer):
    """Serializer for article statistics"""
    
    comment_count = serializers.ReadOnlyField()
    reading_time = serializers.ReadOnlyField()
    
    class Meta:
        model = Article
        fields = [
            'id', 'title', 'views_count', 'likes_count', 'shares_count',
            'comment_count', 'reading_time', 'created_at', 'published_at'
        ]


class PopularArticleSerializer(serializers.ModelSerializer):
    """Serializer for popular articles"""
    
    author_name = serializers.SerializerMethodField()
    category_name = serializers.SerializerMethodField()
    featured_image_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Article
        fields = [
            'id', 'title', 'slug', 'author_name', 'category_name',
            'featured_image_url', 'views_count', 'likes_count',
            'created_at', 'published_at'
        ]
    
    def get_author_name(self, obj):
        return obj.author.get_full_name()
    
    def get_category_name(self, obj):
        return obj.category.name if obj.category else None
    
    def get_featured_image_url(self, obj):
        return obj.get_featured_image_url()


class ArticleSearchSerializer(serializers.ModelSerializer):
    """Serializer for search results"""
    
    author = AuthorSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    featured_image_url = serializers.SerializerMethodField()
    highlight_title = serializers.SerializerMethodField()
    highlight_summary = serializers.SerializerMethodField()
    highlight_content = serializers.SerializerMethodField()
    
    class Meta:
        model = Article
        fields = [
            'id', 'title', 'slug', 'author', 'category', 'tags',
            'summary', 'featured_image_url', 'views_count', 'likes_count',
            'created_at', 'published_at', 'highlight_title', 
            'highlight_summary', 'highlight_content'
        ]
    
    def get_featured_image_url(self, obj):
        return obj.get_featured_image_url()
    
    def get_highlight_title(self, obj):
        return getattr(obj, 'headline_title', obj.title)
    
    def get_highlight_summary(self, obj):
        return getattr(obj, 'headline_summary', obj.summary)
    
    def get_highlight_content(self, obj):
        return getattr(obj, 'headline_content', obj.content[:200] + '...')


class CategoryCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating categories"""
    
    class Meta:
        model = Category
        fields = ['name', 'description', 'image', 'is_active']
    
    def validate_name(self, value):
        if Category.objects.filter(name__iexact=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError("Category with this name already exists.")
        return value


class TagCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating tags"""
    
    class Meta:
        model = Tag
        fields = ['name']
    
    def validate_name(self, value):
        value = value.lower().strip()
        if Tag.objects.filter(name__iexact=value).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError("Tag with this name already exists.")
        return value