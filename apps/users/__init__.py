# File: DjangoVerseHub/apps/users/__init__.py

default_app_config = 'apps.users.apps.UsersConfig'

# Load signals when the app is ready
def ready():
    import apps.users.signals