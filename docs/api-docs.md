# DjangoVerseHub API Documentation

## Overview

The DjangoVerseHub API is a RESTful API built with Django REST Framework that provides programmatic access to articles, users, comments, and other platform features.

**Base URL:** `https://api.djangoversehub.com/v1/`  
**Authentication:** Token-based and Session-based  
**Response Format:** JSON  
**API Version:** v1

## Table of Contents

- [Authentication](#authentication)
- [Rate Limiting](#rate-limiting)
- [Error Handling](#error-handling)
- [Pagination](#pagination)
- [Filtering & Search](#filtering--search)
- [Endpoints](#endpoints)
  - [Articles](#articles)
  - [Users](#users)
  - [Comments](#comments)
  - [Categories](#categories)
  - [Tags](#tags)
  - [Notifications](#notifications)
- [Webhooks](#webhooks)
- [SDKs](#sdks)

## Authentication

### Token Authentication

```http
Authorization: Token your-api-token-here
```

### Obtaining a Token

```http
POST /api/v1/auth/token/
Content-Type: application/json

{
    "username": "your_username",
    "password": "your_password"
}
```

**Response:**

```json
{
  "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b",
  "user": {
    "id": 1,
    "username": "john_doe",
    "email": "john@example.com"
  }
}
```

### Session Authentication

For web applications, you can use Django's built-in session authentication by including CSRF tokens.

## Rate Limiting

API requests are rate-limited per user:

- **Authenticated users:** 1000 requests per hour
- **Anonymous users:** 100 requests per hour

Rate limit headers are included in responses:

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1640995200
```

## Error Handling

### Standard HTTP Status Codes

- `200` - OK
- `201` - Created
- `204` - No Content
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `429` - Too Many Requests
- `500` - Internal Server Error

### Error Response Format

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "The request data is invalid",
    "details": {
      "title": ["This field is required."],
      "content": ["This field may not be blank."]
    }
  }
}
```

## Pagination

All list endpoints support cursor-based pagination:

```http
GET /api/v1/articles/?limit=20&offset=40
```

**Response:**

```json
{
    "count": 150,
    "next": "http://api.djangoversehub.com/v1/articles/?limit=20&offset=60",
    "previous": "http://api.djangoversehub.com/v1/articles/?limit=20&offset=20",
    "results": [...]
}
```

## Filtering & Search

### Query Parameters

- `search` - Full-text search across title and content
- `ordering` - Sort by field (prefix with `-` for descending)
- `category` - Filter by category slug
- `tags` - Filter by tag names (comma-separated)
- `author` - Filter by author username
- `status` - Filter by publication status

**Example:**

```http
GET /api/v1/articles/?search=django&category=tutorials&ordering=-created_at
```

## Endpoints

## Articles

### List Articles

```http
GET /api/v1/articles/
```

**Parameters:**

- `search` (string) - Search query
- `category` (string) - Category slug
- `tags` (string) - Comma-separated tag names
- `author` (string) - Author username
- `status` (string) - `published`, `draft`
- `limit` (int) - Results per page (default: 20, max: 100)
- `offset` (int) - Pagination offset

**Response:**

```json
{
  "count": 42,
  "next": "http://api.djangoversehub.com/v1/articles/?offset=20",
  "previous": null,
  "results": [
    {
      "id": 1,
      "title": "Getting Started with Django",
      "slug": "getting-started-with-django",
      "excerpt": "Learn the basics of Django web framework...",
      "content": "Django is a high-level Python web framework...",
      "author": {
        "id": 1,
        "username": "john_doe",
        "display_name": "John Doe",
        "avatar_url": "https://example.com/avatars/john.jpg"
      },
      "category": {
        "id": 1,
        "name": "Tutorials",
        "slug": "tutorials"
      },
      "tags": [
        {
          "id": 1,
          "name": "django",
          "slug": "django"
        },
        {
          "id": 2,
          "name": "python",
          "slug": "python"
        }
      ],
      "status": "published",
      "featured": false,
      "views_count": 1250,
      "likes_count": 45,
      "comments_count": 12,
      "reading_time": 5,
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T14:20:00Z",
      "published_at": "2024-01-15T12:00:00Z",
      "url": "https://djangoversehub.com/articles/getting-started-with-django/",
      "api_url": "https://api.djangoversehub.com/v1/articles/1/"
    }
  ]
}
```

### Get Article

```http
GET /api/v1/articles/{id}/
```

**Response:**

```json
{
    "id": 1,
    "title": "Getting Started with Django",
    "slug": "getting-started-with-django",
    "excerpt": "Learn the basics of Django web framework...",
    "content": "Django is a high-level Python web framework...",
    "author": {
        "id": 1,
        "username": "john_doe",
        "display_name": "John Doe",
        "avatar_url": "https://example.com/avatars/john.jpg",
        "bio": "Django developer with 5 years of experience",
        "website": "https://johndoe.dev"
    },
    "category": {
        "id": 1,
        "name": "Tutorials",
        "slug": "tutorials",
        "description": "Step-by-step tutorials and guides"
    },
    "tags": [...],
    "status": "published",
    "featured": false,
    "views_count": 1250,
    "likes_count": 45,
    "comments_count": 12,
    "reading_time": 5,
    "meta": {
        "description": "Learn Django web framework basics...",
        "keywords": ["django", "python", "web development"]
    },
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T14:20:00Z",
    "published_at": "2024-01-15T12:00:00Z"
}
```

### Create Article

```http
POST /api/v1/articles/
Authorization: Token your-token
Content-Type: application/json
```

**Request Body:**

```json
{
  "title": "My New Django Tutorial",
  "content": "This is the content of my article...",
  "excerpt": "A brief description...",
  "category": 1,
  "tags": ["django", "tutorial"],
  "status": "draft",
  "meta": {
    "description": "Custom meta description",
    "keywords": ["django", "python"]
  }
}
```

**Response:** `201 Created`

```json
{
    "id": 42,
    "title": "My New Django Tutorial",
    "slug": "my-new-django-tutorial",
    "status": "draft",
    "created_at": "2024-01-20T15:30:00Z",
    ...
}
```

### Update Article

```http
PUT /api/v1/articles/{id}/
Authorization: Token your-token
Content-Type: application/json
```

**Request Body:**

```json
{
  "title": "Updated Article Title",
  "content": "Updated content...",
  "status": "published"
}
```

### Delete Article

```http
DELETE /api/v1/articles/{id}/
Authorization: Token your-token
```

**Response:** `204 No Content`

### Article Actions

#### Like Article

```http
POST /api/v1/articles/{id}/like/
Authorization: Token your-token
```

#### Unlike Article

```http
DELETE /api/v1/articles/{id}/like/
Authorization: Token your-token
```

#### Bookmark Article

```http
POST /api/v1/articles/{id}/bookmark/
Authorization: Token your-token
```

#### Share Article

```http
POST /api/v1/articles/{id}/share/
Content-Type: application/json

{
    "platform": "twitter"  // twitter, facebook, linkedin
}
```

## Users

### List Users

```http
GET /api/v1/users/
```

**Parameters:**

- `search` - Search by username or display name
- `ordering` - Sort by field (default: `-date_joined`)
- `is_active` - Filter by active status

**Response:**

```json
{
  "count": 25,
  "results": [
    {
      "id": 1,
      "username": "john_doe",
      "display_name": "John Doe",
      "avatar_url": "https://example.com/avatars/john.jpg",
      "bio": "Django developer",
      "location": "San Francisco, CA",
      "website": "https://johndoe.dev",
      "github_url": "https://github.com/johndoe",
      "twitter_url": "https://twitter.com/johndoe",
      "date_joined": "2023-06-15T10:00:00Z",
      "stats": {
        "articles_count": 12,
        "comments_count": 45,
        "likes_received": 123,
        "followers_count": 89
      }
    }
  ]
}
```

### Get User Profile

```http
GET /api/v1/users/{id}/
```

### Update User Profile

```http
PATCH /api/v1/users/{id}/
Authorization: Token your-token
Content-Type: application/json
```

**Request Body:**

```json
{
  "display_name": "John Smith",
  "bio": "Updated bio...",
  "location": "New York, NY",
  "website": "https://johnsmith.dev"
}
```

### User Articles

```http
GET /api/v1/users/{id}/articles/
```

### User Followers

```http
GET /api/v1/users/{id}/followers/
```

### User Following

```http
GET /api/v1/users/{id}/following/
```

### Follow User

```http
POST /api/v1/users/{id}/follow/
Authorization: Token your-token
```

### Unfollow User

```http
DELETE /api/v1/users/{id}/follow/
Authorization: Token your-token
```

## Comments

### List Comments

```http
GET /api/v1/comments/
```

**Parameters:**

- `article` - Filter by article ID
- `parent` - Filter by parent comment ID
- `author` - Filter by author username

### Get Comment

```http
GET /api/v1/comments/{id}/
```

**Response:**

```json
{
  "id": 1,
  "content": "Great article! Thanks for sharing.",
  "author": {
    "id": 2,
    "username": "jane_doe",
    "display_name": "Jane Doe",
    "avatar_url": "https://example.com/avatars/jane.jpg"
  },
  "article": {
    "id": 1,
    "title": "Getting Started with Django",
    "slug": "getting-started-with-django"
  },
  "parent": null,
  "replies_count": 3,
  "likes_count": 5,
  "created_at": "2024-01-16T09:15:00Z",
  "updated_at": "2024-01-16T09:15:00Z"
}
```

### Create Comment

```http
POST /api/v1/comments/
Authorization: Token your-token
Content-Type: application/json
```

**Request Body:**

```json
{
  "content": "This is my comment on the article.",
  "article": 1,
  "parent": null // Optional: ID of parent comment for replies
}
```

### Update Comment

```http
PATCH /api/v1/comments/{id}/
Authorization: Token your-token
```

### Delete Comment

```http
DELETE /api/v1/comments/{id}/
Authorization: Token your-token
```

### Like Comment

```http
POST /api/v1/comments/{id}/like/
Authorization: Token your-token
```

## Categories

### List Categories

```http
GET /api/v1/categories/
```

**Response:**

```json
{
  "results": [
    {
      "id": 1,
      "name": "Tutorials",
      "slug": "tutorials",
      "description": "Step-by-step tutorials and guides",
      "color": "#007bff",
      "icon": "book",
      "articles_count": 25,
      "created_at": "2023-01-01T00:00:00Z"
    }
  ]
}
```

### Get Category

```http
GET /api/v1/categories/{id}/
```

### Category Articles

```http
GET /api/v1/categories/{id}/articles/
```

## Tags

### List Tags

```http
GET /api/v1/tags/
```

**Parameters:**

- `search` - Search tag names
- `popular` - Show only popular tags

**Response:**

```json
{
  "results": [
    {
      "id": 1,
      "name": "django",
      "slug": "django",
      "description": "Django web framework",
      "color": "#092e20",
      "articles_count": 45,
      "followers_count": 123
    }
  ]
}
```

### Get Tag

```http
GET /api/v1/tags/{id}/
```

### Tag Articles

```http
GET /api/v1/tags/{id}/articles/
```

### Follow Tag

```http
POST /api/v1/tags/{id}/follow/
Authorization: Token your-token
```

## Notifications

### List Notifications

```http
GET /api/v1/notifications/
Authorization: Token your-token
```

**Parameters:**

- `read` - Filter by read status (true/false)
- `type` - Filter by notification type

**Response:**

```json
{
  "count": 10,
  "unread_count": 3,
  "results": [
    {
      "id": 1,
      "type": "article_liked",
      "title": "Someone liked your article",
      "message": "John Doe liked your article 'Getting Started with Django'",
      "icon": "heart",
      "color": "danger",
      "url": "https://djangoversehub.com/articles/getting-started-with-django/",
      "read": false,
      "created_at": "2024-01-20T10:30:00Z",
      "data": {
        "article_id": 1,
        "user_id": 2
      }
    }
  ]
}
```

### Mark Notification as Read

```http
PATCH /api/v1/notifications/{id}/
Authorization: Token your-token
Content-Type: application/json

{
    "read": true
}
```

### Mark All as Read

```http
POST /api/v1/notifications/mark_all_read/
Authorization: Token your-token
```

## Search

### Global Search

```http
GET /api/v1/search/
```

**Parameters:**

- `q` (required) - Search query
- `type` - Filter by content type (articles, users, tags)

**Response:**

```json
{
    "query": "django tutorial",
    "results": {
        "articles": {
            "count": 15,
            "results": [...],
            "more_url": "https://api.djangoversehub.com/v1/articles/?search=django+tutorial"
        },
        "users": {
            "count": 3,
            "results": [...],
            "more_url": "https://api.djangoversehub.com/v1/users/?search=django+tutorial"
        },
        "tags": {
            "count": 2,
            "results": [...],
            "more_url": "https://api.djangoversehub.com/v1/tags/?search=django+tutorial"
        }
    }
}
```

## Statistics

### Platform Statistics

```http
GET /api/v1/stats/
```

**Response:**

```json
{
  "users": {
    "total": 1250,
    "active_today": 45,
    "active_this_week": 321,
    "new_this_month": 89
  },
  "articles": {
    "total": 458,
    "published": 421,
    "drafts": 37,
    "views_total": 125000,
    "published_this_month": 28
  },
  "comments": {
    "total": 2341,
    "this_month": 145
  },
  "engagement": {
    "likes_total": 8945,
    "bookmarks_total": 1234,
    "shares_total": 567
  }
}
```

## Webhooks

### Setting up Webhooks

Webhooks allow you to receive real-time notifications when events occur in DjangoVerseHub.

**Supported Events:**

- `article.published`
- `article.updated`
- `comment.created`
- `user.registered`
- `user.followed`

**Webhook Configuration:**

```http
POST /api/v1/webhooks/
Authorization: Token your-token
Content-Type: application/json

{
    "url": "https://yourapp.com/webhooks/djangoversehub",
    "events": ["article.published", "comment.created"],
    "secret": "your-webhook-secret"
}
```

**Webhook Payload Example:**

```json
{
    "event": "article.published",
    "timestamp": "2024-01-20T15:30:00Z",
    "data": {
        "article": {
            "id": 42,
            "title": "New Django Tutorial",
            "author": {...},
            "url": "https://djangoversehub.com/articles/new-django-tutorial/"
        }
    }
}
```

## SDKs

### Python SDK

```bash
pip install djangoversehub-sdk
```

```python
from djangoversehub import Client

client = Client(token='your-api-token')

# Get articles
articles = client.articles.list(category='tutorials')

# Create article
article = client.articles.create({
    'title': 'My New Article',
    'content': 'Article content...',
    'status': 'published'
})
```

### JavaScript SDK

```bash
npm install @djangoversehub/sdk
```

```javascript
import { DjangoVerseHubClient } from "@djangoversehub/sdk";

const client = new DjangoVerseHubClient({
  token: "your-api-token",
});

// Get articles
const articles = await client.articles.list({
  category: "tutorials",
});

// Create article
const article = await client.articles.create({
  title: "My New Article",
  content: "Article content...",
  status: "published",
});
```

## OpenAPI Specification

The complete OpenAPI 3.0 specification is available at:

- **JSON:** `https://api.djangoversehub.com/v1/schema.json`
- **YAML:** `https://api.djangoversehub.com/v1/schema.yaml`
- **Interactive Docs:** `https://api.djangoversehub.com/v1/docs/`
- **ReDoc:** `https://api.djangoversehub.com/v1/redoc/`

## Support

- **API Status:** [status.djangoversehub.com](https://status.djangoversehub.com)
- **Support:** [support@djangoversehub.com](mailto:support@djangoversehub.com)
- **Discord:** [Join our Discord](https://discord.gg/djangoversehub)
- **GitHub:** [Issues and Feature Requests](https://github.com/djangoversehub/api/issues)
