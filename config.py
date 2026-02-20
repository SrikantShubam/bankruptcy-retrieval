"""
Configuration for Worktree A - Pure CourtListener RECAP API Pipeline
"""
import sys
from dotenv import load_dotenv

# Add the shared directory to the path
sys.path.insert(0, '../bankruptcy-retrieval')

# Import shared configurations
from shared.config import (
    COURTLISTENER_API_TOKEN,
    COURTLISTENER_BASE_URL,
    OPENROUTER_API_KEY,
    NVIDIA_NIM_API_KEY,
    GATEKEEPER_PROVIDER,
    GATEKEEPER_SCORE_THRESHOLD,
    MAX_API_CALLS_PER_DAY,
    DOWNLOAD_DIR,
    PRIORITY_KEYWORDS,
    MAX_KEYWORD_QUERIES_PER_DEAL,
    MAX_PDF_BYTES,
    COURT_SLUG_MAP,
    get_court_slug
)

# Worktree A specific configurations
RATE_LIMIT_STATE_FILE = "rate_limit_state.json"

# Export the constants needed for Worktree A
__all__ = [
    'COURTLISTENER_API_TOKEN',
    'COURTLISTENER_BASE_URL',
    'OPENROUTER_API_KEY',
    'NVIDIA_NIM_API_KEY',
    'GATEKEEPER_PROVIDER',
    'GATEKEEPER_SCORE_THRESHOLD',
    'MAX_API_CALLS_PER_DAY',
    'DOWNLOAD_DIR',
    'PRIORITY_KEYWORDS',
    'MAX_KEYWORD_QUERIES_PER_DEAL',
    'MAX_PDF_BYTES',
    'COURT_SLUG_MAP',
    'get_court_slug',
    'RATE_LIMIT_STATE_FILE'
]