"""
Audit Logging System

Comprehensive audit logging for all MCP operations.
Tracks tool calls, authentication attempts, and system events.

Features:
- Structured JSON logging
- Log rotation support
- Query and filter capabilities
- Export to JSON/CSV
- GDPR-compliant (no sensitive data in logs)
"""

import json
import logging
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

class LogLevel(Enum):
    """Log severity levels."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class EventType(Enum):
    """Types of events to log."""

    TOOL_CALL = "tool_call"
    AUTHENTICATION = "authentication"
    HEALTH_CHECK = "health_check"
    ERROR = "error"
    SYSTEM = "system"

class AuditLogger:
    """
    Audit logging system for MCP operations.

    Logs all important events to a structured JSON log file with
    rotation support and query capabilities.
    """

    def __init__(
        self,
        log_dir: str = "logs",
        log_file: str = "audit.log",
        max_file_size_mb: int = 10,
        backup_count: int = 5,
    ):
        """
        Initialize audit logger.

        Args:
            log_dir: Directory for log files
            log_file: Log file name
            max_file_size_mb: Max size before rotation (MB)
            backup_count: Number of backup files to keep
        """
        # Setup Python logger for internal logging
        self.logger = logging.getLogger("AuditLogger")

        # Try to create log directory, fallback to /tmp if permission denied
        self.log_dir = Path(log_dir)

        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            # Fallback to /tmp/logs for Docker containers
            self.logger.warning(f"Permission denied for {log_dir}, using /tmp/logs instead")
            self.log_dir = Path("/tmp/logs")
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.logger.error(f"Failed to create log directory: {e}, using /tmp/logs")
            self.log_dir = Path("/tmp/logs")
            try:
                self.log_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e2:
                self.logger.critical(f"Cannot create any log directory: {e2}, logging disabled")
                # Set to None to disable file logging
                self.log_dir = None

        if self.log_dir:
            self.log_file = self.log_dir / log_file
            self.max_file_size = max_file_size_mb * 1024 * 1024  # Convert to bytes
            self.backup_count = backup_count
            self.logger.info(f"Audit logger initialized: {self.log_file}")
        else:
            self.log_file = None
            self.max_file_size = 0
            self.backup_count = 0
            self.logger.warning("Audit logging to file is disabled due to permission errors")

    def _rotate_logs_if_needed(self) -> None:
        """Rotate log files if size exceeds limit."""
        if not self.log_file or not self.log_file.exists():
            return

        if self.log_file.stat().st_size >= self.max_file_size:
            # Rotate existing backup files
            for i in range(self.backup_count - 1, 0, -1):
                old_backup = self.log_dir / f"{self.log_file.name}.{i}"
                new_backup = self.log_dir / f"{self.log_file.name}.{i + 1}"

                if old_backup.exists():
                    if new_backup.exists():
                        new_backup.unlink()  # Delete oldest if at limit
                    old_backup.rename(new_backup)

            # Move current log to .1
            backup = self.log_dir / f"{self.log_file.name}.1"
            if backup.exists():
                backup.unlink()
            self.log_file.rename(backup)

            self.logger.info(f"Log rotated: {self.log_file}")

    def _write_log_entry(self, entry: dict[str, Any]) -> None:
        """
        Write a log entry to file.

        Args:
            entry: Log entry dictionary
        """
        # Skip if logging is disabled
        if not self.log_file:
            return

        self._rotate_logs_if_needed()

        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                # Write as JSON line
                json.dump(entry, f, ensure_ascii=False)
                f.write("\n")
        except Exception as e:
            self.logger.error(f"Failed to write audit log: {e}", exc_info=True)

    def log_tool_call(
        self,
        tool_name: str,
        site: str | None = None,
        project_id: str | None = None,
        params: dict[str, Any] | None = None,
        result_summary: str | None = None,
        error: str | None = None,
        duration_ms: int | None = None,
        user_id: str | None = None,
    ) -> None:
        """
        Log a tool call.

        Args:
            tool_name: Name of the tool called
            site: Site ID or alias (for unified tools)
            project_id: Full project ID (for per-site tools)
            params: Tool parameters (sensitive data should be filtered)
            result_summary: Brief summary of result (not full response)
            error: Error message if failed
            duration_ms: Execution duration in milliseconds
            user_id: User identifier (if available)
        """
        # Filter sensitive data from params
        safe_params = self._filter_sensitive_data(params) if params else None

        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": EventType.TOOL_CALL.value,
            "level": LogLevel.ERROR.value if error else LogLevel.INFO.value,
            "tool_name": tool_name,
            "site": site,
            "project_id": project_id,
            "params": safe_params,
            "result_summary": result_summary,
            "error": error,
            "duration_ms": duration_ms,
            "user_id": user_id,
            "success": error is None,
        }

        self._write_log_entry(entry)

    def log_authentication(
        self,
        success: bool,
        project_id: str | None = None,
        reason: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        """
        Log an authentication attempt.

        Args:
            success: Whether authentication succeeded
            project_id: Project being accessed (if known)
            reason: Failure reason if unsuccessful
            ip_address: Client IP address
        """
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": EventType.AUTHENTICATION.value,
            "level": LogLevel.WARNING.value if not success else LogLevel.INFO.value,
            "success": success,
            "project_id": project_id,
            "reason": reason,
            "ip_address": ip_address,
        }

        self._write_log_entry(entry)

    def log_error(
        self,
        error_type: str,
        error_message: str,
        context: dict[str, Any] | None = None,
        stack_trace: str | None = None,
    ) -> None:
        """
        Log an error event.

        Args:
            error_type: Type of error (e.g., 'ValidationError', 'APIError')
            error_message: Error message
            context: Additional context
            stack_trace: Stack trace if available
        """
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": EventType.ERROR.value,
            "level": LogLevel.ERROR.value,
            "error_type": error_type,
            "error_message": error_message,
            "context": context,
            "stack_trace": stack_trace,
        }

        self._write_log_entry(entry)

    def log_system_event(
        self, event: str, details: dict[str, Any] | None = None, level: LogLevel = LogLevel.INFO
    ) -> None:
        """
        Log a system event.

        Args:
            event: Event description
            details: Event details
            level: Log level
        """
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": EventType.SYSTEM.value,
            "level": level.value,
            "event": event,
            "details": details,
        }

        self._write_log_entry(entry)

    def _filter_sensitive_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Filter sensitive data from logs (GDPR compliance).

        Args:
            data: Data to filter

        Returns:
            Filtered data with sensitive fields masked
        """
        if not data:
            return {}

        sensitive_keys = {
            "password",
            "app_password",
            "token",
            "api_key",
            "secret",
            "credential",
            "auth",
            "private_key",
            "access_token",
            "refresh_token",
        }

        filtered = {}
        for key, value in data.items():
            # Check if key contains sensitive words
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                filtered[key] = "[REDACTED]"
            elif isinstance(value, dict):
                filtered[key] = self._filter_sensitive_data(value)
            else:
                filtered[key] = value

        return filtered

    def get_logs(
        self,
        event_type: EventType | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        level: LogLevel | None = None,
        project_id: str | None = None,
        tool_name: str | None = None,
        success_only: bool | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Query audit logs with filters.

        Args:
            event_type: Filter by event type
            start_time: Start of time range
            end_time: End of time range
            level: Filter by log level
            project_id: Filter by project
            tool_name: Filter by tool name
            success_only: Only successful operations
            limit: Maximum number of entries to return

        Returns:
            List of log entries matching filters
        """
        if not self.log_file or not self.log_file.exists():
            return []

        results = []

        try:
            with open(self.log_file, encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue

                    try:
                        entry = json.loads(line)

                        # Apply filters
                        if event_type and entry.get("event_type") != event_type.value:
                            continue

                        if level and entry.get("level") != level.value:
                            continue

                        if project_id and entry.get("project_id") != project_id:
                            continue

                        if tool_name and entry.get("tool_name") != tool_name:
                            continue

                        if success_only is not None:
                            if entry.get("success") != success_only:
                                continue

                        # Time range filter
                        if start_time or end_time:
                            entry_time = datetime.fromisoformat(entry.get("timestamp", ""))

                            if start_time and entry_time < start_time:
                                continue

                            if end_time and entry_time > end_time:
                                continue

                        results.append(entry)

                        if len(results) >= limit:
                            break

                    except json.JSONDecodeError:
                        self.logger.warning(f"Invalid JSON in log: {line[:50]}...")
                        continue

        except Exception as e:
            self.logger.error(f"Error reading logs: {e}", exc_info=True)

        return results

    def export_logs(self, output_path: str, format: str = "json", **filter_kwargs) -> bool:
        """
        Export logs to a file.

        Args:
            output_path: Output file path
            format: Export format ('json' or 'csv')
            **filter_kwargs: Filters to apply (same as get_logs)

        Returns:
            True if successful
        """
        logs = self.get_logs(**filter_kwargs)

        try:
            if format == "json":
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(logs, f, indent=2, ensure_ascii=False)

            elif format == "csv":
                import csv

                if not logs:
                    return False

                # Get all unique keys from logs
                keys = set()
                for log in logs:
                    keys.update(log.keys())

                with open(output_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=sorted(keys))
                    writer.writeheader()
                    writer.writerows(logs)

            else:
                raise ValueError(f"Unsupported format: {format}")

            self.logger.info(f"Exported {len(logs)} logs to {output_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error exporting logs: {e}", exc_info=True)
            return False

    def get_recent_entries(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get the most recent log entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of recent log entries (newest first)
        """
        if not self.log_file or not self.log_file.exists():
            return []

        entries = []

        try:
            with open(self.log_file, encoding="utf-8") as f:
                # Read all lines and get the last N
                lines = f.readlines()

            # Process lines in reverse order
            for line in reversed(lines):
                if not line.strip():
                    continue

                try:
                    entry = json.loads(line)

                    # Format the entry for display
                    formatted_entry = {
                        "timestamp": entry.get("timestamp", ""),
                        "event_type": entry.get("event_type", "unknown"),
                        "level": entry.get("level", "INFO"),
                        "message": self._format_log_message(entry),
                        "metadata": {
                            "project_id": entry.get("project_id"),
                            "tool_name": entry.get("tool_name"),
                            "site": entry.get("site"),
                            "duration_ms": entry.get("duration_ms"),
                            "success": entry.get("success"),
                        },
                    }

                    entries.append(formatted_entry)

                    if len(entries) >= limit:
                        break

                except json.JSONDecodeError:
                    continue

        except Exception as e:
            self.logger.error(f"Error reading recent logs: {e}", exc_info=True)

        return entries

    def _format_log_message(self, entry: dict[str, Any]) -> str:
        """Format a log entry into a human-readable message."""
        event_type = entry.get("event_type", "")

        if event_type == EventType.TOOL_CALL.value:
            tool_name = entry.get("tool_name", "unknown")
            if entry.get("error"):
                return f"{tool_name} failed: {entry.get('error', '')[:50]}"
            return f"{tool_name}"

        elif event_type == EventType.AUTHENTICATION.value:
            if entry.get("success"):
                return "Authentication successful"
            return f"Authentication failed: {entry.get('reason', 'unknown')}"

        elif event_type == EventType.ERROR.value:
            return f"{entry.get('error_type', 'Error')}: {entry.get('error_message', '')[:50]}"

        elif event_type == EventType.SYSTEM.value:
            return entry.get("event", "System event")

        return entry.get("event", entry.get("message", "Unknown event"))

    def get_statistics(self) -> dict[str, Any]:
        """
        Get statistics about audit logs.

        Returns:
            Dictionary with statistics
        """
        all_logs = self.get_logs(limit=10000)  # Get recent logs

        if not all_logs:
            return {"total_entries": 0, "by_type": {}, "by_level": {}, "success_rate": 0.0}

        # Count by type
        by_type = {}
        by_level = {}
        successful = 0
        total_with_success_field = 0

        for entry in all_logs:
            # Count by type
            event_type = entry.get("event_type", "unknown")
            by_type[event_type] = by_type.get(event_type, 0) + 1

            # Count by level
            level = entry.get("level", "unknown")
            by_level[level] = by_level.get(level, 0) + 1

            # Success rate
            if "success" in entry:
                total_with_success_field += 1
                if entry["success"]:
                    successful += 1

        success_rate = (
            (successful / total_with_success_field * 100) if total_with_success_field > 0 else 0.0
        )

        # Calculate log file size
        log_file_size_mb = 0
        if self.log_file and self.log_file.exists():
            log_file_size_mb = round(self.log_file.stat().st_size / (1024 * 1024), 2)

        return {
            "total_entries": len(all_logs),
            "by_type": by_type,
            "by_level": by_level,
            "success_rate": round(success_rate, 2),
            "log_file_size_mb": log_file_size_mb,
        }

# Global audit logger instance
_audit_logger: AuditLogger | None = None

def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
