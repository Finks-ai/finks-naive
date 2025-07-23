"""
Settings Service - Manages configuration generation and access.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from .models import (
    ConfigContent,
    ConfigFileInfo,
    ConfigType,
    RefreshRequest,
    RefreshResponse,
    RefreshResult,
    RefreshStatus,
    SettingsInfo,
)


class SettingsService:
    """Service for managing application settings and configurations."""

    def __init__(self) -> None:
        self.root_dir = Path(__file__).parent.parent.parent.parent
        self.settings_dir = self.root_dir / "settings"
        self.scripts_dir = self.root_dir / "scripts"
        self._last_refresh: datetime | None = None
        self._refresh_lock = asyncio.Lock()

        # Ensure settings directory exists
        self.settings_dir.mkdir(exist_ok=True)

        # Configuration mappings (now using internal utils)
        self.config_mappings: dict[ConfigType, dict[str, Any]] = {
            ConfigType.SEARCH_SPACE_CATEGORICAL: {
                "handler": self._refresh_search_space,
                "output": "search_space_categorical.yaml",
                "requires": [],  # Requires DB connection
            },
            ConfigType.SEARCH_SPACE_ANALYSIS: {
                "handler": self._refresh_search_space,
                "output": "search_space_analysis.yaml",
                "requires": [],
            },
        }

    async def refresh_configs(self, request: RefreshRequest) -> RefreshResponse:
        """Refresh requested configuration files."""
        async with self._refresh_lock:
            start_time = datetime.now()
            results = []

            # Determine which configs to refresh
            if ConfigType.ALL in request.config_types:
                configs_to_refresh = [ConfigType.SEARCH_SPACE_CATEGORICAL, ConfigType.SEARCH_SPACE_ANALYSIS]
            else:
                configs_to_refresh = request.config_types

            # Refresh each configuration
            for config_type in configs_to_refresh:
                if config_type in self.config_mappings:
                    result = await self._refresh_single_config(config_type, request.force)
                    results.append(result)
                else:
                    # For configs without scripts (manual files)
                    results.append(
                        RefreshResult(
                            config_type=config_type,
                            status=RefreshStatus.FAILED,
                            message=f"No refresh script available for {config_type.value}",
                            duration_ms=0,
                            error="Manual configuration file",
                        )
                    )

            # Update last refresh time
            self._last_refresh = datetime.now()

            # Calculate overall status
            if all(r.status == RefreshStatus.SUCCESS for r in results):
                overall_status = RefreshStatus.SUCCESS
            elif any(r.status == RefreshStatus.SUCCESS for r in results):
                overall_status = RefreshStatus.PARTIAL
            else:
                overall_status = RefreshStatus.FAILED

            total_duration = (datetime.now() - start_time).total_seconds() * 1000

            return RefreshResponse(
                overall_status=overall_status,
                results=results,
                total_duration_ms=total_duration,
                timestamp=datetime.now(),
            )

    async def _refresh_single_config(self, config_type: ConfigType, force: bool) -> RefreshResult:
        """Refresh a single configuration file."""
        start_time = datetime.now()
        config_info = self.config_mappings[config_type]

        try:
            # Check if dependencies exist
            requires = config_info.get("requires", [])
            if not isinstance(requires, list):
                requires = []
            for dep in requires:
                dep_path = self.settings_dir / str(dep)
                if not dep_path.exists():
                    return RefreshResult(
                        config_type=config_type,
                        status=RefreshStatus.FAILED,
                        message=f"Missing dependency: {dep}",
                        duration_ms=0,
                        error=f"Required file {dep} not found",
                    )

            # Check if recent refresh (unless forced)
            output = config_info.get("output", "")
            if not isinstance(output, str):
                output = str(output)
            output_path = self.settings_dir / output
            if not force and output_path.exists():
                file_age = datetime.now() - datetime.fromtimestamp(output_path.stat().st_mtime)
                if file_age.total_seconds() < 300:  # 5 minutes
                    return RefreshResult(
                        config_type=config_type,
                        status=RefreshStatus.SUCCESS,
                        message="Recently updated, skipping refresh",
                        duration_ms=0,
                    )

            # Call the handler function
            handler = config_info.get("handler")
            if not callable(handler):
                raise ValueError(f"Handler for {config_type.value} is not callable")

            logger.info(f"Running refresh handler for {config_type.value}")

            # Run handler in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            success: bool = await loop.run_in_executor(None, handler)

            duration_ms = (datetime.now() - start_time).total_seconds() * 1000

            if success:
                return RefreshResult(
                    config_type=config_type,
                    status=RefreshStatus.SUCCESS,
                    message=f"Successfully refreshed {config_type.value}",
                    duration_ms=duration_ms,
                )
            else:
                return RefreshResult(
                    config_type=config_type,
                    status=RefreshStatus.FAILED,
                    message=f"Failed to refresh {config_type.value}",
                    duration_ms=duration_ms,
                    error="Handler returned False",
                )

        except Exception as e:
            duration_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Error refreshing {config_type.value}: {e}")
            return RefreshResult(
                config_type=config_type,
                status=RefreshStatus.FAILED,
                message="Exception during refresh",
                duration_ms=duration_ms,
                error=str(e),
            )

    def get_settings_info(self) -> SettingsInfo:
        """Get information about current settings."""
        config_files = []

        # List all YAML files in settings directory
        for yaml_file in self.settings_dir.glob("*.yaml"):
            stat = yaml_file.stat()

            # Determine config type
            config_type = self._get_config_type_from_filename(yaml_file.name)

            config_files.append(
                ConfigFileInfo(
                    name=yaml_file.name,
                    path=str(yaml_file.relative_to(self.root_dir)),
                    last_modified=datetime.fromtimestamp(stat.st_mtime),
                    size_bytes=stat.st_size,
                    config_type=config_type,
                )
            )

        return SettingsInfo(
            config_files=config_files,
            last_refresh=self._last_refresh,
            auto_refresh_enabled=False,  # TODO: Implement auto-refresh
            refresh_interval_hours=24,
        )

    def _get_config_type_from_filename(self, filename: str) -> ConfigType:
        """Map filename to config type."""
        mapping = {
            "field_instructions.yaml": ConfigType.FIELD_INSTRUCTIONS,
            "field_categories.yaml": ConfigType.FIELD_CATEGORIES,
            "unavailable_fields.yaml": ConfigType.UNAVAILABLE_FIELDS,
            "search_space_categorical.yaml": ConfigType.SEARCH_SPACE_CATEGORICAL,
            "search_space_analysis.yaml": ConfigType.SEARCH_SPACE_ANALYSIS,
        }
        return mapping.get(filename, ConfigType.ALL)

    def get_config(self, config_type: ConfigType) -> ConfigContent | None:
        """Get the content of a specific configuration."""
        filename_mapping = {
            ConfigType.FIELD_INSTRUCTIONS: "field_instructions.yaml",
            ConfigType.FIELD_CATEGORIES: "field_categories.yaml",
            ConfigType.UNAVAILABLE_FIELDS: "unavailable_fields.yaml",
            ConfigType.SEARCH_SPACE_CATEGORICAL: "search_space_categorical.yaml",
            ConfigType.SEARCH_SPACE_ANALYSIS: "search_space_analysis.yaml",
        }

        filename = filename_mapping.get(config_type)
        if not filename:
            return None

        filepath = self.settings_dir / filename
        if not filepath.exists():
            return None

        try:
            with open(filepath) as f:
                content = yaml.safe_load(f)

            # Add metadata
            stat = filepath.stat()
            metadata = {
                "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "size_bytes": stat.st_size,
                "path": str(filepath.relative_to(self.root_dir)),
            }

            return ConfigContent(config_type=config_type, content=content, metadata=metadata)
        except Exception as e:
            logger.error(f"Error loading config {config_type.value}: {e}")
            return None

    def get_all_configs(self) -> dict[str, ConfigContent]:
        """Get all configuration contents."""
        configs = {}
        for config_type in ConfigType:
            if config_type != ConfigType.ALL:
                config = self.get_config(config_type)
                if config:
                    configs[config_type.value] = config
        return configs

    def _refresh_search_space(self) -> bool:
        """Refresh search space configurations from database."""
        from .utils.fetch_search_space import generate_search_space_configs

        return generate_search_space_configs(self.settings_dir)


# Service instance
settings_service = SettingsService()
