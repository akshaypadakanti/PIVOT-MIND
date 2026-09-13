import os
import sys

# Ensure root project directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.wsgi import get_wsgi_application
from django.core.management import call_command
from pathlib import Path

app = get_wsgi_application()

# On Vercel, auto-initialize /tmp/db.sqlite3 database schema
try:
    if os.getenv("VERCEL") == "1" or "VERCEL" in os.environ:
        db_path = Path("/tmp/db.sqlite3")
        if not db_path.exists():
            call_command("migrate", interactive=False)
except Exception:
    pass
