import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# On Vercel, /tmp is the only writable directory. When DB_NAME points there
# and the file doesn't exist yet (cold start), run migrations + seed automatically.
_db_path = os.environ.get('DB_NAME', '')
if _db_path.startswith('/tmp/') and not os.path.exists(_db_path):
    import django
    django.setup()
    from django.core.management import call_command
    call_command('migrate', '--noinput', verbosity=0)
    call_command('setup_deploy')

application = get_wsgi_application()

app = application