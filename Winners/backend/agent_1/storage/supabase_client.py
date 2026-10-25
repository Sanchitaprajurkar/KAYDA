"""Client manager for structured case data persistence with graceful fallback."""

import logging
from typing import Optional, Any
from agent_1.config import settings

logger = logging.getLogger(__name__)

try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False
    Client = Any

_supabase_client: Optional[Any] = None


def get_supabase_client() -> Optional[Any]:
    """Retrieve or initialize singleton Supabase/PostgreSQL client."""
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    if not HAS_SUPABASE or not getattr(settings, 'SUPABASE_URL', None) or not getattr(settings, 'SUPABASE_KEY', None):
        logger.info("Supabase client not present/configured; operating in local JSON / Neon PostgreSQL storage mode.")
        return None

    try:
        _supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        return _supabase_client
    except Exception as e:
        logger.warning(f"Could not connect to Supabase (using local/Neon fallback): {e}")
        return None
