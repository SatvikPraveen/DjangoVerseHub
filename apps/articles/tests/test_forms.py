# File: DjangoVerseHub/apps/articles/tests/test_forms.py

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from apps.articles.forms import ArticleForm, ArticleSearchForm, CategoryForm, TagForm
from apps.articles.models import Category, Tag
import tempfile
from PIL import Image
import os

User = get_user_model()


class ArticleFormTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )
        self.category = Category.objects.create(name='Tech')
        self.tag = Tag.objects.create(name='Django')

    def test_article_form_valid_data(self):
        form_data = {
            'title': 'Test Article Title',
            'summary': 'This is a test summary',
            'content': 'This is the test content for the article.' * 10,
            'category': self.category.id,
            'tags': [self.tag.id],
            'status': 'published',
            'allow_comments': True,
            'meta_description': 'Test meta description',
            'meta_keywords': 'test, article, keywords'
        }
        form = ArticleForm(data=form_data, user=self.user)
        self.assertTrue(form.is_valid())

    def test_article_form_title_validation(self):
        # Test too short title
        form_data = {
            'title': 'Short',  # Less than 5 characters
            'content': 'This is test content.' * 10,
        }
        form = ArticleForm(data=form_data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)

    def test_article_form_content_validation(self):
        # Test too short content
        form_data = {
            'title': 'Valid Title Here',
            'content': 'Too short',  # Less than 100 characters
        }
        form = ArticleForm(data=form_data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn('content', form.errors)

    def test_article_form_featured_image_validation(self):
        # Create a temporary image file
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
            image = Image.new('RGB', (100, 100), color='red')
            image.save(tmp_file, 'JPEG')
            tmp_file.seek(0)
            
            # Create a file that's too large (simulate 6MB file)
            large_content = b'x' * (6 * 1024 * 1024)  # 6MB
            large_file = SimpleUploadedFile(
                "large_image.jpg", 
                large_content, 
                content_type="image/jpeg"
            )
            
            form_data = {
                'title': 'Test Article with Image',
                'content': 'This is test content.' * 10,
            }
            form = ArticleForm(
                data=form_data, 
                files={'featured_image': large_file}, 
                user=self.user
            )
            self.assertFalse(form.is_valid())
            self.assertIn('featured_image', form.errors)
        
        # Clean up
        try:
            os.unlink(tmp_file.name)
        except:
            pass

    def test_article_form_save(self):
        form_data = {
            'title': 'Test Article Save',
            'content': 'This is test content for save method.' * 10,
            'status': 'published',
            'allow_comments': True
        }
        form = ArticleForm(data=form_data, user=self.user)
        self.assertTrue(form.is_valid())
        
        article = form.save()
        self.assertEqual(article.title, 'Test Article Save')
        self.assertEqual(article.author, self.user)

    def test_article_form_non_staff_user(self):
        # Non-staff user should not see is_featured field
        form = ArticleForm(user=self.user)
        self.assertNotIn('is_featured', form.fields)
        
        # Staff user should see is_featured field
        self.user.is_staff = True
        form = ArticleForm(user=self.user)
        self.assertIn('is_featured', form.fields)


class ArticleSearchFormTest(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Tech')
        self.tag = Tag.objects.create(name='Python')

    def test_search_form_valid_data(self):
        form_data = {
            'q': 'Django tutorial',
            'category': self.category.id,
            'tag': self.tag.id,
            'status': 'published',
            'ordering': '-created_at'
        }
        form = ArticleSearchForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_search_form_empty_data(self):
        form = ArticleSearchForm(data={})
        self.assertTrue(form.is_valid())  # All fields are optional

    def test_search_form_fields(self):
        form = ArticleSearchForm()
        expected_fields = ['q', 'category', 'tag', 'status', 'ordering']
        for field in expected_fields:
            self.assertIn(field, form.fields)


class CategoryFormTest(TestCase):
    def test_category_form_valid_data(self):
        form_data = {
            'name': 'Technology',
            'description': 'Articles about technology',
            'is_active': True
        }
        form = CategoryForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_category_form_name_validation(self):
        # Create existing category
        Category.objects.create(name='Existing Category')
        
        # Try to create another with same name
        form_data = {
            'name': 'Existing Category',
            'description': 'Test description'
        }
        form = CategoryForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

    def test_category_form_image_validation(self):
        # Create a file that's too large
        large_content = b'x' * (3 * 1024 * 1024)  # 3MB
        large_file = SimpleUploadedFile(
            "large_image.jpg", 
            large_content, 
            content_type="image/jpeg"
        )
        
        form_data = {
            'name': 'Test Category',
            'description': 'Test description'
        }
        form = CategoryForm(
            data=form_data, 
            files={'image': large_file}
        )
        self.assertFalse(form.is_valid())
        self.assertIn('image', form.errors)

    def test_category_form_save(self):
        form_data = {
            'name': 'New Category',
            'description': 'New category description',
            'is_active': True
        }
        form = CategoryForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        category = form.save()
        self.assertEqual(category.name, 'New Category')
        self.assertTrue(category.is_active)


class TagFormTest(TestCase):
    def test_tag_form_valid_data(self):
        form_data = {'name': 'Django'}
        form = TagForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_tag_form_name_validation(self):
        # Create existing tag
        Tag.objects.create(name='existing-tag')
        
        # Try to create another with same name (case insensitive)
        form_data = {'name': 'Existing-Tag'}
        form = TagForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

    def test_tag_form_name_lowercase(self):
        form_data = {'name': 'UPPERCASE-TAG'}
        form = TagForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        # Check that clean_name converts to lowercase
        cleaned_name = form.clean_name()
        self.assertEqual(cleaned_name, 'uppercase-tag')

    def test_tag_form_save(self):
        form_data = {'name': 'Python'}
        form = TagForm(data=form_data)
        self.assertTrue(form.is_valid())
        
        tag = form.save()
        self.assertEqual(tag.name, 'python')  # Should be lowercase


class ArticleFilterFormTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            first_name='Test',
            last_name='User'
        )

    def test_filter_form_valid_data(self):
        from apps.articles.forms import ArticleFilterForm
        form_data = {
            'author': 'test@example.com',
            'date_from': '2023-01-01',
            'date_to': '2023-12-31',
            'min_views': 100,
            'featured_only': True
        }
        form = ArticleFilterForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_filter_form_empty_data(self):
        from apps.articles.forms import ArticleFilterForm
        form = ArticleFilterForm(data={})
        self.assertTrue(form.is_valid())  # All fields are optional

    def test_filter_form_fields(self):
        from apps.articles.forms import ArticleFilterForm
        form = ArticleFilterForm()
        expected_fields = ['author', 'date_from', 'date_to', 'min_views', 'featured_only']
        for field in expected_fields:
            self.assertIn(field, form.fields)