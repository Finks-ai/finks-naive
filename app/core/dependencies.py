from fastapi import Depends
from .database import DatabaseService, get_db_service
from .config import Settings, get_settings

def get_database() -> DatabaseService:
    """FastAPI dependency for database service."""
    return get_db_service()

def get_app_settings() -> Settings:
    """FastAPI dependency for application settings."""
    return get_settings()