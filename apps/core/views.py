# File: DjangoVerseHub/apps/core/views.py
"""
Site-level views: landing page, global search, informational pages,
contact/feedback forms, newsletter opt-in and robots.txt.
"""

import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_http_methods, require_POST
from django.views.generic import TemplateView

from apps.articles.models import Article, Category, Tag
from apps.articles.search import ArticleSearchManager

from .forms import ContactForm, FeedbackForm, NewsletterSignupForm
from .models import NewsletterSubscriber

logger = logging.getLogger(__name__)
User = get_user_model()

HOME_CACHE_KEY = 'core:home:v1'
HOME_CACHE_TTL = 120


def _home_context():
    """Query-heavy home page data, cached briefly and shared by all visitors."""
    data = cache.get(HOME_CACHE_KEY)
    if data is not None:
        return data

    published = Article.published.select_related('author', 'category').prefetch_related('tags')
    data = {
        'featured_articles': list(published.filter(is_featured=True)[:3]),
        'latest_articles': list(published.order_by('-published_at')[:6]),
        'popular_articles': list(published.order_by('-views_count', '-published_at')[:5]),
        'categories': list(
            Category.objects.filter(is_active=True)
            .annotate(num_articles=Count('articles', filter=Q(articles__status='published')))
            .order_by('-num_articles', 'name')[:8]
        ),
        'popular_tags': list(
            Tag.objects.annotate(num_articles=Count('articles', filter=Q(articles__status='published')))
            .filter(num_articles__gt=0)
            .order_by('-num_articles', 'name')[:15]
        ),
        'stats': {
            'articles': published.count(),
            'authors': User.objects.filter(articles__status='published').distinct().count(),
            'members': User.objects.filter(is_active=True).count(),
        },
    }
    cache.set(HOME_CACHE_KEY, data, HOME_CACHE_TTL)
    return data


def home_view(request):
    context = _home_context()
    context['newsletter_form'] = NewsletterSignupForm()
    return render(request, 'core/home.html', context)


@require_http_methods(['GET'])
def search_view(request):
    """Global search across articles, people and tags."""
    query = request.GET.get('q', '').strip()[:200]
    scope = request.GET.get('scope', 'all')
    if scope not in {'all', 'articles', 'people', 'tags'}:
        scope = 'all'

    articles = users = tags = []
    if query:
        if scope in {'all', 'articles'}:
            articles = ArticleSearchManager.basic_search(query)
        if scope in {'all', 'people'}:
            users = (
                User.objects.filter(is_active=True)
                .filter(
                    Q(username__icontains=query)
                    | Q(first_name__icontains=query)
                    | Q(last_name__icontains=query)
                    | Q(profile__bio__icontains=query)
                )
                .select_related('profile')
                .order_by('username')
            )
        if scope in {'all', 'tags'}:
            tags = Tag.objects.filter(name__icontains=query).order_by('name')

    limit = 5 if scope == 'all' else 20
    page_number = request.GET.get('page', 1)

    def _page(qs):
        if not query:
            return None
        return Paginator(qs, limit).get_page(page_number)

    context = {
        'query': query,
        'scope': scope,
        'articles_page': _page(articles) if scope in {'all', 'articles'} else None,
        'users_page': _page(users) if scope in {'all', 'people'} else None,
        'tags_page': _page(tags) if scope in {'all', 'tags'} else None,
    }
    context['total_results'] = sum(
        p.paginator.count for p in (context['articles_page'], context['users_page'], context['tags_page']) if p
    )
    return render(request, 'core/search.html', context)


class StaticPageView(TemplateView):
    """Informational pages rendered from a template with a title."""

    page_title = ''

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = self.page_title
        return context


class GettingStartedView(StaticPageView):
    template_name = 'core/pages/getting_started.html'
    page_title = _('Getting Started')


class GuidelinesView(StaticPageView):
    template_name = 'core/pages/guidelines.html'
    page_title = _('Community Guidelines')


class FAQView(StaticPageView):
    template_name = 'core/pages/faq.html'
    page_title = _('Frequently Asked Questions')


class APIDocsView(StaticPageView):
    template_name = 'core/pages/api.html'
    page_title = _('API')


class PrivacyView(StaticPageView):
    template_name = 'core/pages/privacy.html'
    page_title = _('Privacy Policy')


class TermsView(StaticPageView):
    template_name = 'core/pages/terms.html'
    page_title = _('Terms of Service')


class CookiesView(StaticPageView):
    template_name = 'core/pages/cookies.html'
    page_title = _('Cookie Policy')


def _handle_message_form(request, form_class, template_name, page_title, success_message):
    if request.method == 'POST':
        form = form_class(request.POST, user=request.user)
        if form.is_valid():
            message = form.save(request=request)
            logger.info('core.%s.submitted id=%s email=%s', message.kind, message.pk, message.email)
            messages.success(request, success_message)
            return redirect(reverse('core:home'))
    else:
        form = form_class(user=request.user)
    return render(request, template_name, {'form': form, 'page_title': page_title})


def contact_view(request):
    return _handle_message_form(
        request,
        ContactForm,
        'core/contact.html',
        _('Contact Us'),
        _('Thanks for reaching out. We will get back to you soon.'),
    )


def feedback_view(request):
    return _handle_message_form(
        request,
        FeedbackForm,
        'core/feedback.html',
        _('Send Feedback'),
        _('Thank you for your feedback!'),
    )


@require_POST
def newsletter_signup_view(request):
    form = NewsletterSignupForm(request.POST)
    wants_json = request.headers.get('x-requested-with') == 'XMLHttpRequest' or 'application/json' in request.headers.get('accept', '')

    if not form.is_valid():
        if wants_json:
            return JsonResponse({'success': False, 'errors': form.errors}, status=400)
        messages.error(request, _('Please enter a valid email address.'))
        return redirect(request.META.get('HTTP_REFERER') or reverse('core:home'))

    subscriber, created = form.save(user=request.user)
    if created or not subscriber.is_confirmed:
        from .tasks import send_newsletter_confirmation

        send_newsletter_confirmation.delay(subscriber.pk)
        text = _('Almost done! Check your inbox to confirm your subscription.')
    else:
        text = _('You are already subscribed. Thank you!')

    if wants_json:
        return JsonResponse({'success': True, 'message': text, 'created': created})
    messages.success(request, text)
    return redirect(request.META.get('HTTP_REFERER') or reverse('core:home'))


def newsletter_confirm_view(request, token):
    subscriber = get_object_or_404(NewsletterSubscriber, confirmation_token=token)
    if not subscriber.is_confirmed:
        subscriber.confirm()
    messages.success(request, _('Your subscription is confirmed. Welcome aboard!'))
    return redirect(reverse('core:home'))


def newsletter_unsubscribe_view(request, token):
    subscriber = get_object_or_404(NewsletterSubscriber, confirmation_token=token)
    if request.method == 'POST':
        subscriber.unsubscribe()
        messages.info(request, _('You have been unsubscribed.'))
        return redirect(reverse('core:home'))
    return render(request, 'core/newsletter_unsubscribe.html', {'subscriber': subscriber})


@cache_page(60 * 60)
def robots_txt(request):
    lines = [
        'User-agent: *',
        'Disallow: /admin/',
        'Disallow: /api/',
        'Disallow: /accounts/',
        'Disallow: /notifications/',
        'Disallow: /users/settings/',
        '',
        f'Sitemap: {request.build_absolute_uri(reverse("core:sitemap"))}',
    ]
    return HttpResponse('\n'.join(lines), content_type='text/plain')
