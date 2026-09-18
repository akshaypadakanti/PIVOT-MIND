from __future__ import annotations

import logging
from django.core.management import call_command
from django.db import connection

logger = logging.getLogger(__name__)

_db_migrated_checked = False


def ensure_db_migrated():
    """
    Ensures database tables (e.g. agent_pivotmindanalysis) exist.
    Runs Django migrations automatically if tables are missing (e.g. on serverless/Vercel /tmp DB).
    """
    global _db_migrated_checked
    if _db_migrated_checked:
        return

    try:
        tables = connection.introspection.table_names()
        if "agent_pivotmindanalysis" not in tables:
            logger.info("Table 'agent_pivotmindanalysis' missing. Auto-running migrations...")
            call_command("migrate", interactive=False)
        _db_migrated_checked = True
    except Exception as exc:
        logger.error("Failed to auto-migrate database: %s", exc, exc_info=True)
