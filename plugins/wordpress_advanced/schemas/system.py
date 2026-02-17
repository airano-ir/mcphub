"""
System Operations Schemas

Pydantic models for WordPress system operations including:
- System information
- Disk usage
- Cron management
- Cache operations
- Error logs
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator


class SystemInfoResponse(BaseModel):
    """Comprehensive system information"""

    php_version: str = Field(description="PHP version")
    mysql_version: str = Field(description="MySQL/MariaDB version")
    wordpress_version: str = Field(description="WordPress core version")
    server_software: str = Field(description="Web server software")
    memory_limit: str = Field(description="PHP memory limit")
    max_execution_time: int = Field(description="Max execution time in seconds")
    upload_max_filesize: str = Field(description="Maximum upload file size")
    post_max_size: str = Field(description="Maximum POST size")
    max_input_vars: int = Field(description="Maximum input variables")
    php_extensions: list[str] = Field(default=[], description="Loaded PHP extensions")
    wp_debug: bool = Field(description="WP_DEBUG constant status")
    wp_debug_log: bool = Field(description="WP_DEBUG_LOG constant status")
    multisite: bool = Field(description="WordPress Multisite enabled")
    active_plugins: int = Field(description="Number of active plugins")
    active_theme: str = Field(description="Active theme name")


class PHPInfoResponse(BaseModel):
    """PHP configuration details"""

    version: str
    sapi: str = Field(description="Server API (e.g., fpm-fcgi, apache2handler)")
    extensions: list[str] = Field(description="Loaded PHP extensions")
    ini_settings: dict[str, str] = Field(description="Important php.ini settings")
    disabled_functions: list[str] = Field(default=[], description="Disabled PHP functions")


class DiskUsageResponse(BaseModel):
    """Disk usage statistics"""

    total_size_mb: float = Field(description="Total disk usage in MB")
    wordpress_size_mb: float = Field(description="WordPress installation size")
    uploads_size_mb: float = Field(description="wp-content/uploads size")
    plugins_size_mb: float = Field(description="wp-content/plugins size")
    themes_size_mb: float = Field(description="wp-content/themes size")
    database_size_mb: float = Field(description="Database size")
    available_space_mb: float | None = Field(
        default=None, description="Available disk space (if accessible)"
    )
    breakdown: dict[str, float] = Field(default={}, description="Detailed breakdown by directory")


class CronEvent(BaseModel):
    """WordPress cron event information"""

    hook: str = Field(description="Cron hook name")
    timestamp: int = Field(description="Unix timestamp of next run")
    schedule: str = Field(description="Schedule type (hourly, daily, etc.)")
    interval: int | None = Field(
        default=None, description="Interval in seconds for recurring events"
    )
    args: list[Any] = Field(default=[], description="Arguments passed to the hook")


class CronListResponse(BaseModel):
    """List of all cron events"""

    events: list[CronEvent] = Field(description="List of cron events")
    total: int = Field(description="Total number of events")
    schedules: dict[str, dict[str, Any]] = Field(default={}, description="Available cron schedules")


class CronRunParams(BaseModel):
    """Parameters for manually running a cron job"""

    hook: str = Field(..., min_length=1, max_length=255, description="Cron hook name to execute")
    args: list[Any] = Field(default=[], description="Optional arguments to pass to the hook")

    @classmethod
    @field_validator("hook")
    def validate_hook(cls, v):
        """Validate hook name format"""
        # Hook names should be alphanumeric with underscores, hyphens
        if not v.replace("_", "").replace("-", "").replace(".", "").isalnum():
            raise ValueError(
                "Hook name can only contain letters, numbers, underscores, " "hyphens, and dots"
            )
        return v


class ErrorLogParams(BaseModel):
    """Parameters for retrieving error log"""

    lines: int = Field(
        default=100, ge=1, le=1000, description="Number of log lines to retrieve (max 1000)"
    )
    filter: str | None = Field(
        default=None, description="Filter logs by keyword (case-insensitive)"
    )
    level: str | None = Field(
        default=None, description="Filter by error level (error, warning, notice)"
    )

    @classmethod
    @field_validator("level")
    def validate_level(cls, v):
        """Validate error level"""
        if v and v.lower() not in ["error", "warning", "notice", "fatal"]:
            raise ValueError("level must be: error, warning, notice, or fatal")
        return v.lower() if v else v


class ErrorLogEntry(BaseModel):
    """Single error log entry"""

    timestamp: str = Field(description="Error timestamp")
    level: str = Field(description="Error level (error, warning, etc.)")
    message: str = Field(description="Error message")
    file: str | None = Field(default=None, description="File where error occurred")
    line: int | None = Field(default=None, description="Line number")


class ErrorLogResponse(BaseModel):
    """Error log retrieval response"""

    entries: list[ErrorLogEntry] = Field(description="Log entries")
    total_lines: int = Field(description="Total lines in log file")
    filtered_lines: int = Field(description="Number of entries returned")
    log_size_mb: float = Field(description="Log file size in MB")


class CacheStats(BaseModel):
    """Cache statistics"""

    cache_type: str = Field(description="Type of object cache (Redis, Memcached, etc.)")
    cache_enabled: bool = Field(description="Is persistent object cache enabled")
    transients_count: int = Field(description="Number of transients in database")
    opcache_enabled: bool = Field(description="Is OPcache enabled")
    opcache_memory_usage: dict[str, Any] | None = Field(
        default=None, description="OPcache memory usage statistics"
    )
