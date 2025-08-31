# DjangoVerseHub Setup Guide

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Database Setup](#database-setup)
- [Running the Application](#running-the-application)
- [Development Tools](#development-tools)
- [Production Deployment](#production-deployment)
- [Troubleshooting](#troubleshooting)

## Prerequisites

Before setting up DjangoVerseHub, ensure you have the following installed:

### Required Software

- **Python 3.9+** (Recommended: Python 3.11)
- **PostgreSQL 13+** (for production) or SQLite (for development)
- **Redis 6+** (for caching and sessions)
- **Node.js 16+** (for frontend asset compilation)
- **Git** (for version control)

### System Dependencies

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip python3-venv postgresql postgresql-contrib redis-server nodejs npm

# macOS (with Homebrew)
brew install python@3.11 postgresql redis node

# Windows (with Chocolatey)
choco install python postgresql redis nodejs
```

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/djangoversehub.git
cd djangoversehub
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# Linux/macOS:
source venv/bin/activate
# Windows:
venv\Scripts\activate
```

### 3. Install Python Dependencies

```bash
# Install production dependencies
pip install -r requirements.txt

# For development (includes testing and debugging tools)
pip install -r requirements-dev.txt
```

### 4. Install Frontend Dependencies

```bash
# Install Node.js packages for asset compilation
npm install

# Build frontend assets
npm run build
```

## Configuration

### 1. Environment Variables

Create a `.env` file in the project root:

```bash
# Copy the example environment file
cp .env.example .env
```

Edit `.env` with your configuration:

```env
# Django Settings
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_SETTINGS_MODULE=djangoversehub.settings.development

# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/djangoversehub
# For development with SQLite:
# DATABASE_URL=sqlite:///db.sqlite3

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# Email Configuration (for production)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=noreply@djangoversehub.com

# Social Authentication (Optional)
GITHUB_CLIENT_ID=your-github-client-id
GITHUB_CLIENT_SECRET=your-github-client-secret
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# File Storage (for production)
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_STORAGE_BUCKET_NAME=your-s3-bucket-name
AWS_S3_REGION_NAME=us-east-1

# Security Headers (for production)
SECURE_SSL_REDIRECT=False
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
```

### 2. Generate Secret Key

```bash
# Generate a new Django secret key
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## Database Setup

### Development (SQLite)

```bash
# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Load sample data (optional)
python manage.py loaddata fixtures/sample_data.json
```

### Production (PostgreSQL)

```bash
# Create database and user
sudo -u postgres psql
```

```sql
CREATE DATABASE djangoversehub;
CREATE USER djangouser WITH PASSWORD 'your-password';
ALTER ROLE djangouser SET client_encoding TO 'utf8';
ALTER ROLE djangouser SET default_transaction_isolation TO 'read committed';
ALTER ROLE djangouser SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE djangoversehub TO djangouser;
\q
```

```bash
# Update DATABASE_URL in .env, then:
python manage.py migrate
python manage.py createsuperuser
```

## Running the Application

### Development Server

```bash
# Start Django development server
python manage.py runserver

# In another terminal, start Celery worker (for background tasks)
celery -A djangoversehub worker -l info

# In another terminal, start Celery beat (for scheduled tasks)
celery -A djangoversehub beat -l info

# Start Redis (if not running as service)
redis-server
```

### Frontend Development

```bash
# Watch for frontend changes and rebuild assets
npm run dev

# Or build production assets
npm run build
```

### Accessing the Application

- **Main site**: http://127.0.0.1:8000/
- **Admin panel**: http://127.0.0.1:8000/admin/
- **API docs**: http://127.0.0.1:8000/api/docs/

## Development Tools

### Code Quality Tools

```bash
# Format code with Black
black .

# Sort imports with isort
isort .

# Lint with flake8
flake8 .

# Type checking with mypy
mypy .

# Security check with bandit
bandit -r .
```

### Testing

```bash
# Run all tests
python manage.py test

# Run tests with coverage
coverage run --source='.' manage.py test
coverage report
coverage html  # Generate HTML coverage report

# Run specific test module
python manage.py test apps.articles.tests

# Run with pytest (alternative)
pytest
```

### Database Management

```bash
# Create new migration
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Reset database (development only)
python manage.py flush

# Create database backup
python manage.py dumpdata > backup.json

# Load data from backup
python manage.py loaddata backup.json
```

### Cache Management

```bash
# Clear all cache
python manage.py clear_cache

# Clear specific cache
python manage.py clear_cache --cache=default
```

## Production Deployment

### Using Docker

```bash
# Build and run with Docker Compose
docker-compose up -d

# Run migrations in container
docker-compose exec web python manage.py migrate

# Create superuser in container
docker-compose exec web python manage.py createsuperuser
```

### Manual Production Setup

#### 1. Install Production Dependencies

```bash
# Install production web server
pip install gunicorn

# Install production database adapter
pip install psycopg2-binary
```

#### 2. Collect Static Files

```bash
# Set production environment
export DJANGO_SETTINGS_MODULE=djangoversehub.settings.production

# Collect static files
python manage.py collectstatic --noinput
```

#### 3. Configure Web Server (Nginx)

Create `/etc/nginx/sites-available/djangoversehub`:

```nginx
server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /path/to/djangoversehub/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /path/to/djangoversehub/media/;
        expires 1y;
        add_header Cache-Control "public";
    }
}
```

#### 4. Configure Systemd Service

Create `/etc/systemd/system/djangoversehub.service`:

```ini
[Unit]
Description=DjangoVerseHub Django Application
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/path/to/djangoversehub
Environment=DJANGO_SETTINGS_MODULE=djangoversehub.settings.production
ExecStart=/path/to/venv/bin/gunicorn --workers 3 --bind 127.0.0.1:8000 djangoversehub.wsgi:application
Restart=always

[Install]
WantedBy=multi-user.target
```

#### 5. Start Services

```bash
# Enable and start the service
sudo systemctl enable djangoversehub
sudo systemctl start djangoversehub

# Enable and start Nginx
sudo systemctl enable nginx
sudo systemctl start nginx
```

### Environment-Specific Settings

#### Development (`settings/development.py`)

- Debug mode enabled
- SQLite database
- Console email backend
- Django Debug Toolbar
- Hot reloading for templates

#### Production (`settings/production.py`)

- Debug mode disabled
- PostgreSQL database
- SMTP email backend
- Security middleware enabled
- Static file optimization

#### Testing (`settings/testing.py`)

- In-memory database
- Disabled migrations
- Simplified password hashers
- Test-specific configurations

## Troubleshooting

### Common Issues

#### 1. Database Connection Error

```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Check database credentials
psql -U djangouser -d djangoversehub -h localhost
```

#### 2. Static Files Not Loading

```bash
# Collect static files
python manage.py collectstatic

# Check STATIC_URL and STATIC_ROOT in settings
python manage.py shell -c "from django.conf import settings; print(settings.STATIC_URL, settings.STATIC_ROOT)"
```

#### 3. Migration Issues

```bash
# Show migration status
python manage.py showmigrations

# Reset migrations (development only)
python manage.py migrate --fake-initial

# Create new migration for existing model changes
python manage.py makemigrations --empty appname
```

#### 4. Permission Denied Errors

```bash
# Fix file permissions
sudo chown -R www-data:www-data /path/to/djangoversehub
sudo chmod -R 755 /path/to/djangoversehub
```

#### 5. Redis Connection Error

```bash
# Check if Redis is running
redis-cli ping

# Check Redis configuration in settings
python manage.py shell -c "import redis; r = redis.Redis(); print(r.ping())"
```

### Development Tips

1. **Use Django Extensions**: Install `django-extensions` for enhanced management commands
2. **Enable Debug Toolbar**: Add `django-debug-toolbar` for SQL query analysis
3. **Use Django Shell Plus**: `python manage.py shell_plus` for enhanced shell experience
4. **Profile Performance**: Use `django-silk` for request/response profiling
5. **Monitor Logs**: Use structured logging with `django-structlog`

### Performance Optimization

1. **Database Query Optimization**:

   - Use `select_related()` and `prefetch_related()`
   - Add database indexes for frequently queried fields
   - Use `django-debug-toolbar` to identify N+1 queries

2. **Caching Strategy**:

   - Enable template caching for static content
   - Use Redis for session storage
   - Implement view-level caching for expensive operations

3. **Static File Optimization**:
   - Use CDN for static file delivery
   - Enable GZIP compression
   - Optimize images and use WebP format

### Security Checklist

- [ ] Update `SECRET_KEY` in production
- [ ] Set `DEBUG = False` in production
- [ ] Configure `ALLOWED_HOSTS` properly
- [ ] Enable HTTPS and security headers
- [ ] Use environment variables for secrets
- [ ] Regular security updates
- [ ] Configure CORS settings
- [ ] Enable CSRF protection
- [ ] Use secure session cookies
- [ ] Implement rate limiting

## Getting Help

- **Documentation**: Check the `docs/` directory for detailed documentation
- **Issues**: Report bugs on the GitHub issue tracker
- **Community**: Join our Discord server for real-time help
- **Contributing**: See `CONTRIBUTING.md` for contribution guidelines

## Next Steps

After successful setup:

1. Explore the admin interface at `/admin/`
2. Create some test articles and users
3. Configure social authentication providers
4. Set up automated backups
5. Configure monitoring and logging
6. Review security settings for production

For detailed architecture information, see `docs/architecture-diagram.svg` and `docs/concept-index.md`.
