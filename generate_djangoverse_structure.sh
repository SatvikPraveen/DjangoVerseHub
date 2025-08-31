#!/bin/bash

# DjangoVerseHub Project Structure Generator
# Author: DjangoVerseHub Team
# Description: Generates the complete optimized project structure for DjangoVerseHub
# Usage: chmod +x generate_djangoverse_structure.sh && ./generate_djangoverse_structure.sh

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project name
PROJECT_NAME="DjangoVerseHub"

echo -e "${BLUE}🚀 Generating ${PROJECT_NAME} Project Structure...${NC}"
echo -e "${YELLOW}⚡ Creating optimized Django project structure${NC}"
echo ""

# Function to create directory and log it
create_dir() {
    mkdir -p "$1"
    echo -e "${GREEN}✅ Created directory: ${NC}$1"
}

# Function to create file and log it
create_file() {
    touch "$1"
    echo -e "${GREEN}✅ Created file: ${NC}$1"
}

# Create main project directory
create_dir "$PROJECT_NAME"
cd "$PROJECT_NAME"

# Create root level files
create_file "manage.py"
create_file "pyproject.toml"
create_file ".env.example"
create_file ".gitignore"
create_file "README.md"
create_file "Dockerfile"
create_file "docker-compose.yml"

echo -e "${BLUE}📦 Creating requirements structure...${NC}"
# Create requirements directory and files
create_dir "requirements"
create_file "requirements/base.txt"
create_file "requirements/dev.txt"
create_file "requirements/prod.txt"
create_file "requirements/test.txt"

echo -e "${BLUE}📚 Creating documentation structure...${NC}"
# Create docs directory and files
create_dir "docs"
create_file "docs/architecture-diagram.svg"
create_file "docs/ER-diagram.svg"
create_file "docs/api-docs.md"
create_file "docs/concept-index.md"
create_file "docs/setup-guide.md"

echo -e "${BLUE}⚙️ Creating Django project configuration...${NC}"
# Create main Django project directory
create_dir "django_verse_hub"
create_file "django_verse_hub/__init__.py"
create_file "django_verse_hub/asgi.py"
create_file "django_verse_hub/wsgi.py"
create_file "django_verse_hub/urls.py"
create_file "django_verse_hub/middleware.py"
create_file "django_verse_hub/permissions.py"
create_file "django_verse_hub/utils.py"

# Create settings directory and files
create_dir "django_verse_hub/settings"
create_file "django_verse_hub/settings/__init__.py"
create_file "django_verse_hub/settings/base.py"
create_file "django_verse_hub/settings/dev.py"
create_file "django_verse_hub/settings/prod.py"
create_file "django_verse_hub/settings/logging.py"
create_file "django_verse_hub/settings/caching.py"
create_file "django_verse_hub/settings/security.py"
create_file "django_verse_hub/settings/email.py"
create_file "django_verse_hub/settings/celery.py"

echo -e "${BLUE}📱 Creating Django apps structure...${NC}"
# Create apps directory
create_dir "apps"

# Users app
echo -e "${YELLOW}👤 Creating users app...${NC}"
create_dir "apps/users"
create_file "apps/users/__init__.py"
create_file "apps/users/admin.py"
create_file "apps/users/apps.py"
create_file "apps/users/cache.py"
create_file "apps/users/forms.py"
create_file "apps/users/managers.py"
create_file "apps/users/models.py"
create_file "apps/users/serializers.py"
create_file "apps/users/signals.py"
create_file "apps/users/urls.py"
create_file "apps/users/utils.py"
create_file "apps/users/views.py"

create_dir "apps/users/migrations"
create_file "apps/users/migrations/__init__.py"

create_dir "apps/users/templates/users"
create_file "apps/users/templates/users/login.html"
create_file "apps/users/templates/users/signup.html"
create_file "apps/users/templates/users/profile.html"
create_file "apps/users/templates/users/password_reset.html"

create_dir "apps/users/tests"
create_file "apps/users/tests/test_models.py"
create_file "apps/users/tests/test_forms.py"
create_file "apps/users/tests/test_views.py"
create_file "apps/users/tests/test_api.py"

# Articles app
echo -e "${YELLOW}📝 Creating articles app...${NC}"
create_dir "apps/articles"
create_file "apps/articles/__init__.py"
create_file "apps/articles/admin.py"
create_file "apps/articles/apps.py"
create_file "apps/articles/cache.py"
create_file "apps/articles/forms.py"
create_file "apps/articles/managers.py"
create_file "apps/articles/models.py"
create_file "apps/articles/pagination.py"
create_file "apps/articles/search.py"
create_file "apps/articles/serializers.py"
create_file "apps/articles/urls.py"
create_file "apps/articles/views.py"

create_dir "apps/articles/migrations"
create_file "apps/articles/migrations/__init__.py"

create_dir "apps/articles/templates/articles"
create_file "apps/articles/templates/articles/article_list.html"
create_file "apps/articles/templates/articles/article_detail.html"
create_file "apps/articles/templates/articles/article_create.html"
create_file "apps/articles/templates/articles/article_edit.html"

create_dir "apps/articles/tests"
create_file "apps/articles/tests/test_views.py"
create_file "apps/articles/tests/test_models.py"
create_file "apps/articles/tests/test_api.py"
create_file "apps/articles/tests/test_forms.py"
create_file "apps/articles/tests/test_cache.py"

# Comments app
echo -e "${YELLOW}💬 Creating comments app...${NC}"
create_dir "apps/comments"
create_file "apps/comments/__init__.py"
create_file "apps/comments/admin.py"
create_file "apps/comments/apps.py"
create_file "apps/comments/forms.py"
create_file "apps/comments/models.py"
create_file "apps/comments/serializers.py"
create_file "apps/comments/signals.py"
create_file "apps/comments/urls.py"
create_file "apps/comments/views.py"

create_dir "apps/comments/migrations"
create_file "apps/comments/migrations/__init__.py"

create_dir "apps/comments/templates/comments"
create_file "apps/comments/templates/comments/comment_list.html"
create_file "apps/comments/templates/comments/comment_thread.html"
create_file "apps/comments/templates/comments/comment_form.html"

create_dir "apps/comments/tests"
create_file "apps/comments/tests/test_views.py"
create_file "apps/comments/tests/test_models.py"
create_file "apps/comments/tests/test_api.py"

# Notifications app
echo -e "${YELLOW}🔔 Creating notifications app...${NC}"
create_dir "apps/notifications"
create_file "apps/notifications/__init__.py"
create_file "apps/notifications/admin.py"
create_file "apps/notifications/consumers.py"
create_file "apps/notifications/models.py"
create_file "apps/notifications/routing.py"
create_file "apps/notifications/serializers.py"
create_file "apps/notifications/signals.py"
create_file "apps/notifications/urls.py"
create_file "apps/notifications/views.py"

create_dir "apps/notifications/templates/notifications"
create_file "apps/notifications/templates/notifications/notification_list.html"
create_file "apps/notifications/templates/notifications/notifications_ws.html"

create_dir "apps/notifications/tests"
create_file "apps/notifications/tests/test_consumers.py"
create_file "apps/notifications/tests/test_models.py"
create_file "apps/notifications/tests/test_signals.py"

# API app
echo -e "${YELLOW}🔌 Creating API app...${NC}"
create_dir "apps/api"
create_file "apps/api/__init__.py"
create_file "apps/api/permissions.py"
create_file "apps/api/pagination.py"
create_file "apps/api/throttling.py"
create_file "apps/api/urls.py"
create_file "apps/api/views.py"
create_file "apps/api/routers.py"

echo -e "${BLUE}🎨 Creating static files structure...${NC}"
# Create static directory structure
create_dir "static/css"
create_file "static/css/base.css"
create_file "static/css/forms.css"
create_file "static/css/components.css"

create_dir "static/js"
create_file "static/js/main.js"
create_file "static/js/notifications.js"
create_file "static/js/api.js"
create_file "static/js/cache-sw.js"

create_dir "static/images/banners"
create_file "static/images/logo.svg"
create_file "static/images/banners/hero.svg"
create_file "static/images/banners/features.svg"

echo -e "${BLUE}🖼️ Creating templates structure...${NC}"
# Create templates directory structure
create_dir "templates"
create_file "templates/base.html"

create_dir "templates/includes"
create_file "templates/includes/navbar.html"
create_file "templates/includes/footer.html"
create_file "templates/includes/pagination.html"

create_dir "templates/includes/cache"
create_file "templates/includes/cache/user_sidebar.html"
create_file "templates/includes/cache/popular_articles.html"

create_dir "templates/errors"
create_file "templates/errors/400.html"
create_file "templates/errors/403.html"
create_file "templates/errors/404.html"
create_file "templates/errors/500.html"

echo -e "${BLUE}🗂️ Creating media directories...${NC}"
# Create media directories
create_dir "media/avatars"
create_dir "media/article_images"
create_dir "media/attachments"

echo -e "${BLUE}🧪 Creating tests structure...${NC}"
# Create centralized tests directory
create_dir "tests"
create_file "tests/__init__.py"
create_file "tests/test_settings.py"
create_file "tests/test_urls.py"
create_file "tests/test_integration.py"
create_file "tests/test_performance.py"

echo -e "${BLUE}📜 Creating management commands...${NC}"
# Create scripts directory with management commands
create_dir "scripts/management/commands"
create_file "scripts/__init__.py"
create_file "scripts/management/__init__.py"
create_file "scripts/management/commands/__init__.py"
create_file "scripts/management/commands/generate_demo_data.py"
create_file "scripts/management/commands/cleanup_unused_media.py"
create_file "scripts/management/commands/send_bulk_notifications.py"

echo -e "${BLUE}🔄 Creating CI/CD workflows...${NC}"
# Create GitHub workflows
create_dir ".github/workflows"
create_file ".github/workflows/ci.yml"
create_file ".github/workflows/cd.yml"
create_file ".github/workflows/security.yml"

echo ""
echo -e "${GREEN}🎉 DjangoVerseHub project structure generated successfully!${NC}"
echo ""
echo -e "${BLUE}📊 Project Statistics:${NC}"

# Count directories and files
TOTAL_DIRS=$(find . -type d | wc -l)
TOTAL_FILES=$(find . -type f | wc -l)

echo -e "${YELLOW}   • Total directories created: ${NC}$TOTAL_DIRS"
echo -e "${YELLOW}   • Total files created: ${NC}$TOTAL_FILES"
echo ""

echo -e "${BLUE}🚀 Next Steps:${NC}"
echo -e "${YELLOW}   1. Navigate to the project: ${NC}cd $PROJECT_NAME"
echo -e "${YELLOW}   2. Initialize git repository: ${NC}git init"
echo -e "${YELLOW}   3. Create virtual environment: ${NC}python -m venv venv"
echo -e "${YELLOW}   4. Activate virtual environment: ${NC}source venv/bin/activate"
echo -e "${YELLOW}   5. Start building your Django mastery hub!${NC}"
echo ""

echo -e "${GREEN}✨ Happy coding with DjangoVerseHub! ✨${NC}"