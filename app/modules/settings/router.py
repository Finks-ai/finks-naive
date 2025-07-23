"""
Settings router - API endpoints for configuration management.
"""

from fastapi import APIRouter, HTTPException

from .models import ConfigContent, ConfigType, RefreshRequest, RefreshResponse, SettingsInfo
from .service import settings_service

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/", response_model=SettingsInfo)
async def get_settings_info() -> SettingsInfo:
    """
    Get information about current settings and configuration files.

    Returns details about all configuration files including:
    - File names and paths
    - Last modified timestamps
    - File sizes
    - Configuration types
    """
    return settings_service.get_settings_info()


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_configs(request: RefreshRequest) -> RefreshResponse:
    """
    Refresh configuration files by regenerating them from source data.

    This endpoint runs the appropriate scripts to regenerate:
    - field_instructions.yaml from filters.csv
    - search_space_categorical.yaml from database
    - search_space_analysis.yaml from database

    Use config_types to specify which configs to refresh, or use "all" for everything.
    """
    try:
        return await settings_service.refresh_configs(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Refresh failed: {e!s}") from e


@router.get("/config/{config_type}")
async def get_config(config_type: ConfigType) -> ConfigContent:
    """
    Get the content of a specific configuration file.

    Available config types:
    - field_instructions
    - field_categories
    - unavailable_fields
    - search_space_categorical
    - search_space_analysis
    """
    config = settings_service.get_config(config_type)
    if not config:
        raise HTTPException(status_code=404, detail=f"Configuration {config_type.value} not found")
    return config


@router.get("/configs")
async def get_all_configs() -> dict[str, ConfigContent]:
    """
    Get all configuration contents at once.

    Returns a dictionary mapping config type to its content and metadata.
    """
    return settings_service.get_all_configs()


@router.post("/refresh/{config_type}", response_model=RefreshResponse)
async def refresh_single_config(config_type: ConfigType, force: bool = False) -> RefreshResponse:
    """
    Refresh a single configuration file.

    Parameters:
    - config_type: The specific configuration to refresh
    - force: Force refresh even if recently updated
    """
    if config_type == ConfigType.ALL:
        raise HTTPException(status_code=400, detail="Use /refresh endpoint to refresh all configs")

    request = RefreshRequest(config_types=[config_type], force=force)
    return await settings_service.refresh_configs(request)
