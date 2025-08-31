# File: DjangoVerseHub/apps/comments/tests/test_models.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from apps.comments.models import Comment, CommentLike
from apps.articles.models import Article

User = get_user_model()


class CommentModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        self.other_user = User.objects.create_user(
            email='other@example.com',
            first_name='Other',
            last_name='User'
        )
        
        # Create an article to comment on
        self.article = Article.objects.create(
            title='Test Article',
            content='Test content' * 20,
            author=self.user,
            status='published'
        )
        
        self.comment = Comment.objects.create(
            author=self.user,
            content='This is a test comment.',
            content_object=self.article
        )

    def test_comment_creation(self):
        self.assertEqual(self.comment.author, self.user)
        self.assertEqual(self.comment.content, 'This is a test comment.')
        self.assertEqual(self.comment.content_object, self.article)
        self.assertTrue(self.comment.is_active)
        self.assertFalse(self.comment.is_flagged)
        self.assertFalse(self.comment.is_edited)

    def test_comment_str(self):
        expected_str = f'{self.user.get_full_name()}: This is a test comment....'
        self.assertEqual(str(self.comment), expected_str)

    def test_comment_absolute_url(self):
        expected_url = f"{self.article.get_absolute_url()}#comment-{self.comment.id}"
        self.assertEqual(self.comment.get_absolute_url(), expected_url)

    def test_is_root_property(self):
        self.assertTrue(self.comment.is_root)
        
        # Create a reply
        reply = Comment.objects.create(
            author=self.other_user,
            content='This is a reply.',
            content_object=self.article,
            parent=self.comment
        )
        
        self.assertFalse(reply.is_root)

    def test_reply_count_property(self):
        self.assertEqual(self.comment.reply_count, 0)
        
        # Add a reply
        Comment.objects.create(
            author=self.other_user,
            content='This is a reply.',
            content_object=self.article,
            parent=self.comment
        )
        
        # Refresh from database
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.reply_count, 1)

    def test_get_thread_depth(self):
        self.assertEqual(self.comment.get_thread_depth(), 0)
        
        # Create nested replies
        reply1 = Comment.objects.create(
            author=self.other_user,
            content='Reply level 1',
            content_object=self.article,
            parent=self.comment
        )
        self.assertEqual(reply1.get_thread_depth(), 1)
        
        reply2 = Comment.objects.create(
            author=self.user,
            content='Reply level 2',
            content_object=self.article,
            parent=reply1
        )
        self.assertEqual(reply2.get_thread_depth(), 2)

    def test_total_replies_property(self):
        self.assertEqual(self.comment.total_replies, 0)
        
        # Add nested replies
        reply1 = Comment.objects.create(
            author=self.other_user,
            content='Reply 1',
            content_object=self.article,
            parent=self.comment
        )
        
        reply2 = Comment.objects.create(
            author=self.user,
            content='Reply 2',
            content_object=self.article,
            parent=reply1
        )
        
        # Should count all nested replies
        self.assertEqual(self.comment.total_replies, 2)

    def test_can_edit_method(self):
        # Author can edit within time window
        self.assertTrue(self.comment.can_edit(self.user))
        
        # Other user cannot edit
        self.assertFalse(self.comment.can_edit(self.other_user))
        
        # Staff can edit
        staff_user = User.objects.create_user(
            email='staff@example.com',
            first_name='Staff',
            last_name='User',
            is_staff=True
        )
        self.assertTrue(self.comment.can_edit(staff_user))

    def test_can_delete_method(self):
        # Author can delete
        self.assertTrue(self.comment.can_delete(self.user))
        
        # Other user cannot delete
        self.assertFalse(self.comment.can_delete(self.other_user))
        
        # Staff can delete
        staff_user = User.objects.create_user(
            email='staff@example.com',
            first_name='Staff',
            last_name='User',
            is_staff=True
        )
        self.assertTrue(self.comment.can_delete(staff_user))

    def test_mark_as_edited(self):
        self.assertFalse(self.comment.is_edited)
        
        self.comment.mark_as_edited()
        self.assertTrue(self.comment.is_edited)

    def test_flag_method(self):
        self.assertFalse(self.comment.is_flagged)
        
        self.comment.flag()
        self.assertTrue(self.comment.is_flagged)

    def test_soft_delete(self):
        self.assertTrue(self.comment.is_active)
        self.assertEqual(self.comment.content, 'This is a test comment.')
        
        self.comment.soft_delete()
        self.assertFalse(self.comment.is_active)
        self.assertEqual(self.comment.content, '[Comment deleted]')

    def test_validation_parent_same_object(self):
        # Create comment on different object
        other_article = Article.objects.create(
            title='Other Article',
            content='Other content' * 20,
            author=self.user,
            status='published'
        )
        
        other_comment = Comment.objects.create(
            author=self.user,
            content='Comment on other article',
            content_object=other_article
        )
        
        # Try to create reply with wrong parent
        with self.assertRaises(ValidationError):
            invalid_reply = Comment(
                author=self.other_user,
                content='Invalid reply',
                content_object=self.article,  # Different object
                parent=other_comment  # Parent on different object
            )
            invalid_reply.clean()

    def test_validation_thread_depth(self):
        # Create deep nested thread
        reply1 = Comment.objects.create(
            author=self.other_user,
            content='Reply 1',
            content_object=self.article,
            parent=self.comment
        )
        
        reply2 = Comment.objects.create(
            author=self.user,
            content='Reply 2',
            content_object=self.article,
            parent=reply1
        )
        
        reply3 = Comment.objects.create(
            author=self.other_user,
            content='Reply 3',
            content_object=self.article,
            parent=reply2
        )
        
        # Try to create 4th level reply (should fail)
        with self.assertRaises(ValidationError):
            invalid_reply = Comment(
                author=self.user,
                content='Reply 4 - too deep',
                content_object=self.article,
                parent=reply3
            )
            invalid_reply.clean()


class CommentManagerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        
        self.article = Article.objects.create(
            title='Test Article',
            content='Test content' * 20,
            author=self.user,
            status='published'
        )
        
        # Create active comment
        self.active_comment = Comment.objects.create(
            author=self.user,
            content='Active comment',
            content_object=self.article,
            is_active=True
        )
        
        # Create inactive comment
        self.inactive_comment = Comment.objects.create(
            author=self.user,
            content='Inactive comment',
            content_object=self.article,
            is_active=False
        )

    def test_active_manager(self):
        active_comments = Comment.objects.active()
        self.assertIn(self.active_comment, active_comments)
        self.assertNotIn(self.inactive_comment, active_comments)

    def test_for_object_manager(self):
        article_comments = Comment.objects.for_object(self.article)
        self.assertIn(self.active_comment, article_comments)
        self.assertNotIn(self.inactive_comment, article_comments)  # Inactive filtered out

    def test_root_comments_manager(self):
        # Create a reply
        reply = Comment.objects.create(
            author=self.user,
            content='Reply comment',
            content_object=self.article,
            parent=self.active_comment
        )
        
        root_comments = Comment.objects.root_comments()
        self.assertIn(self.active_comment, root_comments)
        self.assertIn(self.inactive_comment, root_comments)
        self.assertNotIn(reply, root_comments)

    def test_thread_comments_manager(self):
        # Create replies
        reply1 = Comment.objects.create(
            author=self.user,
            content='Reply 1',
            content_object=self.article,
            parent=self.active_comment
        )
        
        reply2 = Comment.objects.create(
            author=self.user,
            content='Reply 2',
            content_object=self.article,
            parent=self.active_comment
        )
        
        thread_comments = Comment.objects.thread_comments(self.active_comment)
        self.assertIn(reply1, thread_comments)
        self.assertIn(reply2, thread_comments)
        self.assertNotIn(self.active_comment, thread_comments)


class CommentLikeModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        
        self.article = Article.objects.create(
            title='Test Article',
            content='Test content' * 20,
            author=self.user,
            status='published'
        )
        
        self.comment = Comment.objects.create(
            author=self.user,
            content='Test comment',
            content_object=self.article
        )

    def test_comment_like_creation(self):
        like = CommentLike.objects.create(
            comment=self.comment,
            user=self.user
        )
        
        self.assertEqual(like.comment, self.comment)
        self.assertEqual(like.user, self.user)
        self.assertIsNotNone(like.created_at)

    def test_comment_like_str(self):
        like = CommentLike.objects.create(
            comment=self.comment,
            user=self.user
        )
        
        expected_str = f'{self.user.get_full_name()} likes {self.comment}'
        self.assertEqual(str(like), expected_str)

    def test_unique_together_constraint(self):
        # Create first like
        CommentLike.objects.create(
            comment=self.comment,
            user=self.user
        )
        
        # Try to create duplicate like
        with self.assertRaises(Exception):  # IntegrityError
            CommentLike.objects.create(
                comment=self.comment,
                user=self.user
            )