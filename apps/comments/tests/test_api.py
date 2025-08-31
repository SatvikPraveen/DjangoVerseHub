# File: DjangoVerseHub/apps/comments/tests/test_api.py

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework.authtoken.models import Token
from apps.comments.models import Comment, CommentLike
from apps.articles.models import Article

User = get_user_model()


class CommentAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()
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
        self.token = Token.objects.create(user=self.user)
        self.other_token = Token.objects.create(user=self.other_user)
        
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

    def test_get_comments_list(self):
        url = reverse('comments:comment-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['content'], 'Test comment content')

    def test_get_comment_detail(self):
        url = reverse('comments:comment-detail', kwargs={'pk': self.comment.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['content'], 'Test comment content')
        self.assertIn('author', response.data)
        self.assertIn('can_edit', response.data)
        self.assertIn('can_delete', response.data)

    def test_create_comment_authenticated(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        url = reverse('comments:comment-list')
        
        content_type = ContentType.objects.get_for_model(self.article)
        data = {
            'content': 'New comment via API',
            'content_type': f'{content_type.app_label}.{content_type.model}',
            'object_id': str(self.article.id)
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Comment.objects.count(), 2)
        new_comment = Comment.objects.get(content='New comment via API')
        self.assertEqual(new_comment.author, self.user)

    def test_create_comment_unauthenticated(self):
        url = reverse('comments:comment-list')
        data = {
            'content': 'Unauthorized comment',
            'content_type': 'articles.article',
            'object_id': str(self.article.id)
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_comment_invalid_data(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        url = reverse('comments:comment-list')
        
        data = {
            'content': 'Hi',  # Too short
            'content_type': 'articles.article',
            'object_id': str(self.article.id)
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('content', response.data)

    def test_create_comment_invalid_content_type(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        url = reverse('comments:comment-list')
        
        data = {
            'content': 'Valid comment content',
            'content_type': 'invalid.model',
            'object_id': str(self.article.id)
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('content_type', response.data)

    def test_create_comment_nonexistent_object(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        url = reverse('comments:comment-list')
        
        data = {
            'content': 'Comment on nonexistent object',
            'content_type': 'articles.article',
            'object_id': 'nonexistent-id'
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('object_id', response.data)

    def test_create_reply_comment(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.other_token.key)
        url = reverse('comments:comment-list')
        
        content_type = ContentType.objects.get_for_model(self.article)
        data = {
            'content': 'This is a reply to the comment',
            'content_type': f'{content_type.app_label}.{content_type.model}',
            'object_id': str(self.article.id),
            'parent': self.comment.id
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        reply = Comment.objects.get(content='This is a reply to the comment')
        self.assertEqual(reply.parent, self.comment)

    def test_create_reply_too_deep(self):
        # Create nested replies up to depth limit
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
        
        # Try to create 4th level reply
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        url = reverse('comments:comment-list')
        
        content_type = ContentType.objects.get_for_model(self.article)
        data = {
            'content': 'Reply 4 - too deep',
            'content_type': f'{content_type.app_label}.{content_type.model}',
            'object_id': str(self.article.id),
            'parent': reply3.id
        }
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('parent', response.data)

    def test_update_comment_owner(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        url = reverse('comments:comment-detail', kwargs={'pk': self.comment.pk})
        
        data = {'content': 'Updated comment content'}
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.comment.refresh_from_db()
        self.assertEqual(self.comment.content, 'Updated comment content')
        self.assertTrue(self.comment.is_edited)

    def test_update_comment_not_owner(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.other_token.key)
        url = reverse('comments:comment-detail', kwargs={'pk': self.comment.pk})
        
        data = {'content': 'Unauthorized update'}
        response = self.client.patch(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_comment_owner(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        url = reverse('comments:comment-detail', kwargs={'pk': self.comment.pk})
        
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.comment.refresh_from_db()
        self.assertFalse(self.comment.is_active)  # Soft deleted

    def test_delete_comment_not_owner(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.other_token.key)
        url = reverse('comments:comment-detail', kwargs={'pk': self.comment.pk})
        
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_like_comment_action(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.other_token.key)
        url = reverse('comments:comment-like', kwargs={'pk': self.comment.pk})
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['liked'])
        self.assertEqual(response.data['likes_count'], 1)
        
        # Check like was created
        self.assertTrue(CommentLike.objects.filter(
            comment=self.comment,
            user=self.other_user
        ).exists())

    def test_unlike_comment_action(self):
        # Create existing like
        CommentLike.objects.create(
            comment=self.comment,
            user=self.other_user
        )
        
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.other_token.key)
        url = reverse('comments:comment-like', kwargs={'pk': self.comment.pk})
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['liked'])
        self.assertEqual(response.data['likes_count'], 0)

    def test_flag_comment_action(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.other_token.key)
        url = reverse('comments:comment-flag', kwargs={'pk': self.comment.pk})
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.comment.refresh_from_db()
        self.assertTrue(self.comment.is_flagged)

    def test_tree_action(self):
        # Create nested comments
        reply = Comment.objects.create(
            author=self.other_user,
            content='Reply comment',
            content_object=self.article,
            parent=self.comment
        )
        
        url = reverse('comments:comment-tree')
        content_type = ContentType.objects.get_for_model(self.article)
        response = self.client.get(url, {
            'content_type': f'{content_type.app_label}.{content_type.model}',
            'object_id': str(self.article.id)
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)  # One root comment
        self.assertEqual(len(response.data[0]['replies']), 1)  # One reply

    def test_tree_action_missing_params(self):
        url = reverse('comments:comment-tree')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_stats_action(self):
        url = reverse('comments:comment-stats', kwargs={'pk': self.comment.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('likes_count', response.data)
        self.assertIn('reply_count', response.data)
        self.assertIn('thread_depth', response.data)

    def test_user_comments_action(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + self.token.key)
        url = reverse('comments:comment-user-comments')
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['content'], 'Test comment content')

    def test_filter_comments_by_content_type(self):
        url = reverse('comments:comment-list')
        content_type = ContentType.objects.get_for_model(self.article)
        
        response = self.client.get(url, {'content_type': content_type.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_filter_comments_by_object_id(self):
        url = reverse('comments:comment-list')
        
        response = self.client.get(url, {'object_id': self.article.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_search_comments(self):
        url = reverse('comments:comment-list')
        
        response = self.client.get(url, {'search': 'Test'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)