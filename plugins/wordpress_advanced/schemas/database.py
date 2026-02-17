"""
Database Operations Schemas

Pydantic models for WordPress database operations including:
- Database export/import
- Backup/restore
- Optimization and repair
- Search and query operations
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator

class DatabaseExportParams(BaseModel):
    """Parameters for database export"""

    tables: list[str] | None = Field(
        default=None, description="Specific tables to export (default: all tables)"
    )
    exclude_tables: list[str] | None = Field(
        default=None, description="Tables to exclude from export"
    )
    add_drop_table: bool = Field(default=True, description="Include DROP TABLE statements")

    @classmethod
    @field_validator("tables", "exclude_tables")
    def validate_table_names(cls, v):
        """Validate table names - no special characters"""
        if v:
            for table in v:
                if not table.replace("_", "").isalnum():
                    raise ValueError(f"Invalid table name: {table}")
        return v

class DatabaseImportParams(BaseModel):
    """Parameters for database import"""

    file_path: str | None = Field(default=None, description="Path to SQL file on server")
    url: str | None = Field(default=None, description="URL to download SQL file from")
    skip_optimization: bool = Field(
        default=False, description="Skip database optimization after import"
    )

    @classmethod
    @field_validator("url")
    def validate_url(cls, v):
        """Validate URL format"""
        if v and not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v

class DatabaseBackupParams(BaseModel):
    """Parameters for creating database backup"""

    description: str | None = Field(
        default=None, max_length=255, description="Optional description for this backup"
    )
    compress: bool = Field(default=True, description="Compress backup with gzip")
    include_uploads: bool = Field(
        default=False, description="Also backup wp-content/uploads directory"
    )

class DatabaseRestoreParams(BaseModel):
    """Parameters for restoring database"""

    backup_id: str | None = Field(default=None, description="Backup ID to restore")
    timestamp: str | None = Field(
        default=None, description="Backup timestamp (alternative to backup_id)"
    )
    confirm: bool = Field(default=False, description="Confirmation required (safety check)")

    @classmethod
    @field_validator("confirm")
    def validate_confirmation(cls, v):
        """Require explicit confirmation for restore"""
        if not v:
            raise ValueError("Confirmation required: set confirm=true")
        return v

class DatabaseSearchParams(BaseModel):
    """Parameters for searching database"""

    search_string: str = Field(
        ..., min_length=1, max_length=255, description="String to search for in database"
    )
    tables: list[str] | None = Field(
        default=None, description="Specific tables to search (default: all tables)"
    )
    regex: bool = Field(default=False, description="Use regex pattern matching")
    case_sensitive: bool = Field(default=False, description="Case-sensitive search")
    max_results: int = Field(default=100, ge=1, le=1000, description="Maximum results to return")

class DatabaseQueryParams(BaseModel):
    """Parameters for executing SQL query"""

    query: str = Field(
        ..., min_length=1, max_length=10000, description="SQL query to execute (SELECT only)"
    )
    max_rows: int = Field(default=1000, ge=1, le=10000, description="Maximum rows to return")

    @classmethod
    @field_validator("query")
    def validate_query(cls, v):
        """
        Validate query is safe (read-only SELECT)

        Security: Only allow SELECT, SHOW, DESCRIBE statements
        Prevent: INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, etc.
        """
        query_upper = v.strip().upper()

        # Allowed statement types
        allowed_starts = ("SELECT", "SHOW", "DESCRIBE", "DESC", "EXPLAIN")

        if not any(query_upper.startswith(cmd) for cmd in allowed_starts):
            raise ValueError("Only SELECT, SHOW, DESCRIBE, and EXPLAIN queries allowed")

        # Forbidden keywords (prevent nested destructive queries)
        forbidden = [
            "INSERT",
            "UPDATE",
            "DELETE",
            "DROP",
            "ALTER",
            "CREATE",
            "TRUNCATE",
            "REPLACE",
            "GRANT",
            "REVOKE",
        ]

        for keyword in forbidden:
            if keyword in query_upper:
                raise ValueError(f"Forbidden keyword in query: {keyword}")

        return v

class DatabaseSizeResponse(BaseModel):
    """Response model for database size information"""

    total_size_mb: float = Field(description="Total database size in MB")
    tables: list[dict[str, Any]] = Field(description="List of tables with size information")
    row_count: int = Field(description="Total row count across all tables")

class DatabaseTableInfo(BaseModel):
    """Information about a database table"""

    name: str
    engine: str
    rows: int
    data_size_mb: float
    index_size_mb: float
    total_size_mb: float
    collation: str

class DatabaseRepairResult(BaseModel):
    """Result of database repair operation"""

    table: str
    status: str  # 'OK', 'Repaired', 'Failed'
    message: str | None = None

class DatabaseBackupInfo(BaseModel):
    """Information about a database backup"""

    backup_id: str
    timestamp: str
    size_mb: float
    compressed: bool
    description: str | None = None
    location: str
    tables_count: int
