# File: DjangoVerseHub/apps/articles/tests/test_comment_relation.py

from django.contrib.auth import get_user_model
from django.db.models import Count
from django.test import TestCase

from apps.articles.models import Article
from apps.comments.models import Comment

User = get_user_model()


class CommentJoinTests(TestCase):
    """object_id is a UUIDField, so generic-relation joins must actually match rows."""

    def test_count_annotation_matches_rows(self):
        user = User.objects.create_user(email='j@example.com', username='j', password='x')
        article = Article.objects.create(title='Joined', content='...', author=user, status='published')
        Comment.objects.create(content_object=article, author=user, content='one')
        Comment.objects.create(content_object=article, author=user, content='two')

        annotated = Article.objects.annotate(n=Count('comments')).get(pk=article.pk)
        self.assertEqual(annotated.n, 2)
        self.assertEqual(article.comments.count(), 2)

        article.delete()
        self.assertEqual(Comment.objects.count(), 0)
