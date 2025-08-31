# File: DjangoVerseHub/apps/comments/tests/test_views.py

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from apps.comments.models import Comment, CommentLike
from apps.articles.models import Article
import json

User = get_user_model()


class CommentViewTest(TestCase):
    def setUp(self):
        self.client = Client()
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
        
        self.article = Article.objects.create(
            title='Test Article',
            content='Test content' * 20,
            author=self.user,
            status='published'
        )
        
        self.comment = Comment.objects.create(
            author=self.user,
            content='Test comment content',
            content_object=self.article
        )

    def test_comment_list_view(self):
        url = reverse('comments:list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test comment content')
        self.assertIn('comments', response.context)

    def test_comment_list_view_search(self):
        url = reverse('comments:list')
        response = self.client.get(url, {'q': 'Test'})
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test comment content')

    def test_comment_list_view_author_filter(self):
        url = reverse('comments:list')
        response = self.client.get(url, {'author': 'Test'})
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test comment content')

    def test_comment_list_view_flagged_filter(self):
        # Flag the comment
        self.comment.is_flagged = True
        self.comment.save()
        
        url = reverse('comments:list')
        response = self.client.get(url, {'is_flagged': 'on'})
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test comment content')

    def test_comment_create_view_anonymous(self):
        url = reverse('comments:create')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_comment_create_view_authenticated(self):
        self.client.force_login(self.user)
        
        content_type = ContentType.objects.get_for_model(self.article)
        url = reverse('comments:create')
        response = self.client.get(url, {
            'content_type': content_type.id,
            'object_id': self.article.id
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Post a Comment')

    def test_comment_create_post_valid(self):
        self.client.force_login(self.user)
        
        content_type = ContentType.objects.get_for_model(self.article)
        url = reverse('comments:create')
        data = {
            'content': 'This is a new test comment.',
        }
        
        # Add content object info via GET params
        response = self.client.post(f"{url}?content_type={content_type.id}&object_id={self.article.id}", data)
        
        self.assertEqual(response.status_code, 302)  # Redirect after creation
        self.assertTrue(Comment.objects.filter(content='This is a new test comment.').exists())

    def test_comment_update_view_owner(self):
        self.client.force_login(self.user)
        url = reverse('comments:edit', kwargs={'pk': self.comment.pk})
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edit')

    def test_comment_update_view_not_owner(self):
        self.client.force_login(self.other_user)
        url = reverse('comments:edit', kwargs={'pk': self.comment.pk})
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_comment_update_post_valid(self):
        self.client.force_login(self.user)
        url = reverse('comments:edit', kwargs={'pk': self.comment.pk})
        
        data = {
            'content': 'Updated comment content.',
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, 302)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.content, 'Updated comment content.')
        self.assertTrue(self.comment.is_edited)

    def test_comment_delete_view_owner(self):
        self.client.force_login(self.user)
        url = reverse('comments:delete', kwargs={'pk': self.comment.pk})
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Are you sure')

    def test_comment_delete_post(self):
        self.client.force_login(self.user)
        url = reverse('comments:delete', kwargs={'pk': self.comment.pk})
        
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        
        # Check soft delete
        self.comment.refresh_from_db()
        self.assertFalse(self.comment.is_active)
        self.assertEqual(self.comment.content, '[Comment deleted]')

    def test_comment_delete_staff_user(self):
        staff_user = User.objects.create_user(
            email='staff@example.com',
            first_name='Staff',
            last_name='User',
            is_staff=True
        )
        
        self.client.force_login(staff_user)
        url = reverse('comments:delete', kwargs={'pk': self.comment.pk})
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_comment_reply_view_authenticated(self):
        self.client.force_login(self.other_user)
        url = reverse('comments:reply', kwargs={'comment_id': self.comment.id})
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reply')

    def test_comment_reply_post_valid(self):
        self.client.force_login(self.other_user)
        url = reverse('comments:reply', kwargs={'comment_id': self.comment.id})
        
        data = {
            'content': 'This is a reply to the comment.',
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, 302)
        
        # Check reply was created
        reply = Comment.objects.filter(parent=self.comment).first()
        self.assertIsNotNone(reply)
        self.assertEqual(reply.content, 'This is a reply to the comment.')
        self.assertEqual(reply.author, self.other_user)

    def test_comment_like_view_ajax(self):
        self.client.force_login(self.other_user)
        url = reverse('comments:like', kwargs={'comment_id': self.comment.id})
        
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertTrue(data['liked'])
        self.assertEqual(data['likes_count'], 1)
        
        # Check like was created
        self.assertTrue(CommentLike.objects.filter(
            comment=self.comment,
            user=self.other_user
        ).exists())

    def test_comment_unlike_ajax(self):
        # Create existing like
        CommentLike.objects.create(
            comment=self.comment,
            user=self.other_user
        )
        
        self.client.force_login(self.other_user)
        url = reverse('comments:like', kwargs={'comment_id': self.comment.id})
        
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        self.assertFalse(data['liked'])
        self.assertEqual(data['likes_count'], 0)
        
        # Check like was removed
        self.assertFalse(CommentLike.objects.filter(
            comment=self.comment,
            user=self.other_user
        ).exists())

    def test_comment_like_invalid_method(self):
        self.client.force_login(self.other_user)
        url = reverse('comments:like', kwargs={'comment_id': self.comment.id})
        
        response = self.client.get(url)  # GET instead of POST
        self.assertEqual(response.status_code, 405)

    def test_comment_flag_view_authenticated(self):
        self.client.force_login(self.other_user)
        url = reverse('comments:flag', kwargs={'comment_id': self.comment.id})
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Flag')

    def test_comment_flag_post_valid(self):
        self.client.force_login(self.other_user)
        url = reverse('comments:flag', kwargs={'comment_id': self.comment.id})
        
        data = {
            'reason': 'spam',
            'details': 'This looks like spam content.',
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, 302)
        
        # Check comment was flagged
        self.comment.refresh_from_db()
        self.assertTrue(self.comment.is_flagged)

    def test_comment_flag_view_anonymous(self):
        url = reverse('comments:flag', kwargs={'comment_id': self.comment.id})
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_comment_flag_view_nonexistent_comment(self):
        self.client.force_login(self.other_user)
        url = reverse('comments:flag', kwargs={'comment_id': 'nonexistent-uuid'})
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)