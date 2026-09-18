import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = get_wsgi_application()

try:
    from agent.db_utils import ensure_db_migrated
    ensure_db_migrated()
except Exception:
    pass

