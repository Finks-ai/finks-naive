"""
Models for settings module.
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class ConfigType(str, Enum):
    """Types of configuration files."""
    FIELD_INSTRUCTIONS = "field_instructions"
    FIELD_CATEGORIES = "field_categories"
    UNAVAILABLE_FIELDS = "unavailable_fields"
    SEARCH_SPACE_CATEGORICAL = "search_space_categorical"
    SEARCH_SPACE_ANALYSIS = "search_space_analysis"
    ALL = "all"


class RefreshStatus(str, Enum):
    """Status of refresh operation."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    RUNNING = "running"


class ConfigFileInfo(BaseModel):
    """Information about a configuration file."""
    name: str
    path: str
    last_modified: datetime
    size_bytes: int
    config_type: ConfigType


class RefreshResult(BaseModel):
    """Result of a configuration refresh operation."""
    config_type: ConfigType
    status: RefreshStatus
    message: str
    duration_ms: float
    error: Optional[str] = None
    
    
class RefreshRequest(BaseModel):
    """Request to refresh configurations."""
    config_types: List[ConfigType] = Field(
        default=[ConfigType.ALL],
        description="Which configurations to refresh"
    )
    force: bool = Field(
        default=False,
        description="Force refresh even if recently updated"
    )


class RefreshResponse(BaseModel):
    """Response from configuration refresh."""
    overall_status: RefreshStatus
    results: List[RefreshResult]
    total_duration_ms: float
    timestamp: datetime


class SettingsInfo(BaseModel):
    """Information about current settings."""
    config_files: List[ConfigFileInfo]
    last_refresh: Optional[datetime]
    auto_refresh_enabled: bool
    refresh_interval_hours: int


class ConfigContent(BaseModel):
    """Content of a configuration file."""
    config_type: ConfigType
    content: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)