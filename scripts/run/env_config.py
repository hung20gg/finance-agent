"""
Environment configuration loader.
Loads environment variables from parent .env file or local .env file.
This allows centralized configuration while maintaining independence.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

def load_env_config():
    """
    Load environment variables with fallback priority:
    1. Current environment variables (highest priority)
    2. Local .env file (for standalone operation)
    3. Parent directory .env file (for Docker Compose)
    """
    # Get the current file's directory
    current_dir = Path(__file__).resolve().parent
    
    # Try to load from parent .env (for Docker Compose)
    parent_env = current_dir.parent.parent.parent / '.env'
    if parent_env.exists():
        load_dotenv(parent_env, override=False)
    
    # Try to load from local .env (for standalone operation)
    local_env = current_dir.parent / '.env'
    if local_env.exists():
        load_dotenv(local_env, override=False)

def get_env(key: str, default=None):
    """Get environment variable with optional default."""
    return os.getenv(key, default)
