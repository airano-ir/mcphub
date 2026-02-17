"""
Enhanced Health Monitoring System for MCP Server (Phase 7.2)

This module provides comprehensive health monitoring capabilities including:
- Response time tracking
- Error rate monitoring
- Historical metrics storage
- Alert thresholds
- Dependency health checks
- System uptime tracking

Author: Coolify MCP Team
Version: 7.2
"""

import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from core.audit_log import AuditLogger
from core.project_manager import ProjectManager

logger = logging.getLogger(__name__)

@dataclass
class HealthMetric:
    """Individual health metric data point."""

    timestamp: datetime
    project_id: str
    response_time_ms: float
    success: bool
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "project_id": self.project_id,
            "response_time_ms": self.response_time_ms,
            "success": self.success,
            "error_message": self.error_message,
        }

@dataclass
class SystemMetrics:
    """System-wide metrics."""

    uptime_seconds: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_response_time_ms: float
    error_rate_percent: float
    requests_per_minute: float

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

@dataclass
class ProjectHealthStatus:
    """Comprehensive health status for a project."""

    project_id: str
    healthy: bool
    last_check: datetime
    response_time_ms: float
    error_rate_percent: float
    recent_errors: list[str] = field(default_factory=list)
    alerts: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "project_id": self.project_id,
            "healthy": self.healthy,
            "last_check": self.last_check.isoformat(),
            "response_time_ms": self.response_time_ms,
            "error_rate_percent": self.error_rate_percent,
            "recent_errors": self.recent_errors,
            "alerts": self.alerts,
            "details": self.details,
        }

@dataclass
class AlertThreshold:
    """Alert threshold configuration."""

    name: str
    metric: str  # "response_time_ms", "error_rate_percent", etc.
    threshold: float
    comparison: str  # "gt" (greater than), "lt" (less than), "eq" (equal)
    severity: str = "warning"  # "info", "warning", "critical"

    def check(self, value: float) -> bool:
        """Check if value exceeds threshold."""
        if self.comparison == "gt":
            return value > self.threshold
        elif self.comparison == "lt":
            return value < self.threshold
        elif self.comparison == "eq":
            return value == self.threshold
        return False

class HealthMonitor:
    """
    Enhanced health monitoring system with metrics tracking and alerting.

    Features:
    - Real-time health checks
    - Response time tracking
    - Error rate monitoring
    - Historical metrics (last 24 hours)
    - Alert thresholds
    - System uptime tracking
    """

    def __init__(
        self,
        project_manager: ProjectManager,
        audit_logger: AuditLogger | None = None,
        metrics_retention_hours: int = 24,
        max_metrics_per_project: int = 1000,
    ):
        """
        Initialize health monitor.

        Args:
            project_manager: Project manager instance
            audit_logger: Optional audit logger for logging health events
            metrics_retention_hours: Hours to retain historical metrics
            max_metrics_per_project: Maximum metrics to store per project
        """
        self.project_manager = project_manager
        self.audit_logger = audit_logger
        self.metrics_retention_hours = metrics_retention_hours
        self.max_metrics_per_project = max_metrics_per_project

        # Metrics storage (in-memory)
        # Using deque for efficient FIFO operations
        self.metrics_history: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=max_metrics_per_project)
        )

        # Request counters
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0

        # Response time tracking
        self.response_times: deque = deque(maxlen=1000)  # Last 1000 requests

        # System start time
        self.start_time = time.time()

        # Alert thresholds (configurable)
        self.alert_thresholds: dict[str, list[AlertThreshold]] = defaultdict(list)
        self._setup_default_thresholds()

        # Request rate tracking (for requests per minute)
        self.request_timestamps: deque = deque(maxlen=1000)

        logger.info("HealthMonitor initialized (Phase 7.2)")

    def _setup_default_thresholds(self):
        """Setup default alert thresholds."""
        # Response time threshold: > 5000ms (5 seconds) is critical
        self.alert_thresholds["global"].append(
            AlertThreshold(
                name="High Response Time",
                metric="response_time_ms",
                threshold=5000.0,
                comparison="gt",
                severity="critical",
            )
        )

        # Error rate threshold: > 10% is warning, > 25% is critical
        self.alert_thresholds["global"].append(
            AlertThreshold(
                name="High Error Rate",
                metric="error_rate_percent",
                threshold=10.0,
                comparison="gt",
                severity="warning",
            )
        )

        self.alert_thresholds["global"].append(
            AlertThreshold(
                name="Critical Error Rate",
                metric="error_rate_percent",
                threshold=25.0,
                comparison="gt",
                severity="critical",
            )
        )

    def add_alert_threshold(
        self,
        project_id: str,
        name: str,
        metric: str,
        threshold: float,
        comparison: str = "gt",
        severity: str = "warning",
    ):
        """
        Add a custom alert threshold for a project.

        Args:
            project_id: Project ID or "global" for all projects
            name: Alert name
            metric: Metric to check
            threshold: Threshold value
            comparison: Comparison operator ("gt", "lt", "eq")
            severity: Alert severity ("info", "warning", "critical")
        """
        alert = AlertThreshold(name, metric, threshold, comparison, severity)
        self.alert_thresholds[project_id].append(alert)
        logger.info(f"Added alert threshold '{name}' for {project_id}")

    def record_request(
        self,
        project_id: str,
        response_time_ms: float,
        success: bool,
        error_message: str | None = None,
    ):
        """
        Record a request metric.

        Args:
            project_id: Project that handled the request
            response_time_ms: Response time in milliseconds
            success: Whether request succeeded
            error_message: Error message if failed
        """
        # Create metric
        metric = HealthMetric(
            timestamp=datetime.now(UTC),
            project_id=project_id,
            response_time_ms=response_time_ms,
            success=success,
            error_message=error_message,
        )

        # Store in history
        self.metrics_history[project_id].append(metric)

        # Update counters
        self.total_requests += 1
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

        # Track response time
        self.response_times.append(response_time_ms)

        # Track request timestamp for rate calculation
        self.request_timestamps.append(time.time())

        # Log to audit if available
        if self.audit_logger:
            self.audit_logger.log_system_event(
                event="health_metric_recorded",
                details={
                    "project_id": project_id,
                    "response_time_ms": response_time_ms,
                    "success": success,
                    "error_message": error_message,
                },
            )

    def _cleanup_old_metrics(self, project_id: str):
        """Remove metrics older than retention period."""
        if project_id not in self.metrics_history:
            return

        cutoff_time = datetime.now(UTC) - timedelta(hours=self.metrics_retention_hours)
        metrics = self.metrics_history[project_id]

        # Remove old metrics from the front of deque
        while metrics and metrics[0].timestamp < cutoff_time:
            metrics.popleft()

    def get_project_metrics(self, project_id: str, hours: int = 1) -> dict[str, Any]:
        """
        Get metrics for a specific project.

        Args:
            project_id: Project ID
            hours: Number of hours of history to analyze

        Returns:
            Dictionary with metrics
        """
        self._cleanup_old_metrics(project_id)

        if project_id not in self.metrics_history:
            return {"project_id": project_id, "total_requests": 0, "error": "No metrics available"}

        # Filter metrics by time window
        cutoff_time = datetime.now(UTC) - timedelta(hours=hours)
        metrics = [m for m in self.metrics_history[project_id] if m.timestamp >= cutoff_time]

        if not metrics:
            return {"project_id": project_id, "total_requests": 0, "time_window_hours": hours}

        # Calculate statistics
        total_requests = len(metrics)
        successful = sum(1 for m in metrics if m.success)
        failed = total_requests - successful
        error_rate = (failed / total_requests * 100) if total_requests > 0 else 0.0

        # Response time statistics
        response_times = [m.response_time_ms for m in metrics]
        avg_response = sum(response_times) / len(response_times) if response_times else 0.0
        min_response = min(response_times) if response_times else 0.0
        max_response = max(response_times) if response_times else 0.0

        # Recent errors (last 5)
        recent_errors = [m.error_message for m in metrics if not m.success and m.error_message][-5:]

        return {
            "project_id": project_id,
            "time_window_hours": hours,
            "total_requests": total_requests,
            "successful_requests": successful,
            "failed_requests": failed,
            "error_rate_percent": round(error_rate, 2),
            "response_time": {
                "average_ms": round(avg_response, 2),
                "min_ms": round(min_response, 2),
                "max_ms": round(max_response, 2),
            },
            "recent_errors": recent_errors,
        }

    def _check_alerts(self, project_id: str, metrics: dict[str, Any]) -> list[str]:
        """
        Check if any alert thresholds are exceeded.

        Args:
            project_id: Project ID
            metrics: Current metrics

        Returns:
            List of alert messages
        """
        alerts = []

        # Check global thresholds
        for threshold in self.alert_thresholds["global"]:
            if threshold.metric in metrics:
                value = metrics[threshold.metric]
                if threshold.check(value):
                    alerts.append(
                        f"[{threshold.severity.upper()}] {threshold.name}: "
                        f"{threshold.metric}={value} (threshold: {threshold.threshold})"
                    )

        # Check project-specific thresholds
        for threshold in self.alert_thresholds.get(project_id, []):
            if threshold.metric in metrics:
                value = metrics[threshold.metric]
                if threshold.check(value):
                    alerts.append(
                        f"[{threshold.severity.upper()}] {threshold.name}: "
                        f"{threshold.metric}={value} (threshold: {threshold.threshold})"
                    )

        return alerts

    async def check_project_health(
        self, project_id: str, include_metrics: bool = True
    ) -> ProjectHealthStatus:
        """
        Perform comprehensive health check on a project.

        Args:
            project_id: Project ID to check
            include_metrics: Whether to include historical metrics

        Returns:
            ProjectHealthStatus object
        """
        start_time = time.time()

        try:
            # Get plugin instance
            plugin = self.project_manager.projects.get(project_id)
            if not plugin:
                return ProjectHealthStatus(
                    project_id=project_id,
                    healthy=False,
                    last_check=datetime.now(UTC),
                    response_time_ms=0.0,
                    error_rate_percent=100.0,
                    recent_errors=["Project not found"],
                    alerts=["CRITICAL: Project not found"],
                )

            # Perform health check
            health_result = await plugin.health_check()
            response_time_ms = (time.time() - start_time) * 1000

            # Handle both dict and string (JSON) responses
            if isinstance(health_result, str):
                try:
                    import json

                    health_result = json.loads(health_result)
                except (json.JSONDecodeError, TypeError):
                    # If not valid JSON, treat as error message
                    health_result = {"healthy": False, "message": health_result}

            # Ensure health_result is a dict
            if not isinstance(health_result, dict):
                health_result = {"healthy": False, "message": str(health_result)}

            # Record this health check
            is_healthy = health_result.get("healthy", False) or health_result.get("success", False)
            self.record_request(
                project_id=project_id,
                response_time_ms=response_time_ms,
                success=is_healthy,
                error_message=(
                    health_result.get("message") or health_result.get("error")
                    if not is_healthy
                    else None
                ),
            )

            # Get metrics if requested
            metrics_data = {}
            error_rate = 0.0
            recent_errors = []

            if include_metrics:
                metrics_data = self.get_project_metrics(project_id, hours=1)
                error_rate = metrics_data.get("error_rate_percent", 0.0)
                recent_errors = metrics_data.get("recent_errors", [])

            # Check alerts
            alert_check_data = {
                "response_time_ms": response_time_ms,
                "error_rate_percent": error_rate,
            }
            alerts = self._check_alerts(project_id, alert_check_data)

            return ProjectHealthStatus(
                project_id=project_id,
                healthy=is_healthy,
                last_check=datetime.now(UTC),
                response_time_ms=response_time_ms,
                error_rate_percent=error_rate,
                recent_errors=recent_errors,
                alerts=alerts,
                details=health_result,
            )

        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            error_msg = str(e)

            # Record failed health check
            self.record_request(
                project_id=project_id,
                response_time_ms=response_time_ms,
                success=False,
                error_message=error_msg,
            )

            return ProjectHealthStatus(
                project_id=project_id,
                healthy=False,
                last_check=datetime.now(UTC),
                response_time_ms=response_time_ms,
                error_rate_percent=100.0,
                recent_errors=[error_msg],
                alerts=[f"CRITICAL: Health check failed - {error_msg}"],
            )

    async def check_all_projects_health(self, include_metrics: bool = True) -> dict[str, Any]:
        """
        Check health of all projects.

        Args:
            include_metrics: Whether to include historical metrics

        Returns:
            Dictionary with overall health status
        """
        health_statuses = {}

        # Check each project
        for project_id in self.project_manager.projects.keys():
            status = await self.check_project_health(project_id, include_metrics)
            health_statuses[project_id] = status.to_dict()

        # Calculate summary
        total_projects = len(health_statuses)
        healthy_projects = sum(1 for s in health_statuses.values() if s["healthy"])
        unhealthy_projects = total_projects - healthy_projects

        # Collect all alerts
        all_alerts = []
        for status in health_statuses.values():
            all_alerts.extend(status.get("alerts", []))

        return {
            "timestamp": datetime.now(UTC).isoformat(),
            "status": (
                "healthy"
                if unhealthy_projects == 0
                else ("degraded" if healthy_projects > 0 else "unhealthy")
            ),
            "summary": {
                "total_projects": total_projects,
                "healthy": healthy_projects,
                "unhealthy": unhealthy_projects,
            },
            "alerts": all_alerts,
            "projects": health_statuses,
        }

    def get_system_metrics(self) -> SystemMetrics:
        """
        Get overall system metrics.

        Returns:
            SystemMetrics object
        """
        # Calculate uptime
        uptime_seconds = time.time() - self.start_time

        # Calculate average response time
        avg_response_time = (
            sum(self.response_times) / len(self.response_times) if self.response_times else 0.0
        )

        # Calculate error rate
        error_rate = (
            (self.failed_requests / self.total_requests * 100) if self.total_requests > 0 else 0.0
        )

        # Calculate requests per minute
        now = time.time()
        one_minute_ago = now - 60
        recent_requests = sum(1 for ts in self.request_timestamps if ts >= one_minute_ago)

        return SystemMetrics(
            uptime_seconds=uptime_seconds,
            total_requests=self.total_requests,
            successful_requests=self.successful_requests,
            failed_requests=self.failed_requests,
            average_response_time_ms=round(avg_response_time, 2),
            error_rate_percent=round(error_rate, 2),
            requests_per_minute=recent_requests,
        )

    def get_uptime(self) -> dict[str, Any]:
        """
        Get system uptime information.

        Returns:
            Dictionary with uptime details
        """
        uptime_seconds = time.time() - self.start_time
        uptime_minutes = uptime_seconds / 60
        uptime_hours = uptime_minutes / 60
        uptime_days = uptime_hours / 24

        return {
            "start_time": datetime.fromtimestamp(self.start_time, tz=UTC).isoformat(),
            "current_time": datetime.now(UTC).isoformat(),
            "uptime_seconds": round(uptime_seconds, 2),
            "uptime_minutes": round(uptime_minutes, 2),
            "uptime_hours": round(uptime_hours, 2),
            "uptime_days": round(uptime_days, 2),
            "uptime_formatted": self._format_uptime(uptime_seconds),
        }

    def _format_uptime(self, seconds: float) -> str:
        """Format uptime as human-readable string."""
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        parts.append(f"{secs}s")

        return " ".join(parts)

    def export_metrics(self, output_path: str | None = None, format: str = "json") -> str:
        """
        Export all metrics to file.

        Args:
            output_path: Output file path (default: logs/metrics_export.json)
            format: Export format ("json" only for now)

        Returns:
            Path to exported file
        """
        if output_path is None:
            output_path = "logs/metrics_export.json"

        # Prepare export data
        export_data = {
            "export_time": datetime.now(UTC).isoformat(),
            "system_metrics": self.get_system_metrics().to_dict(),
            "uptime": self.get_uptime(),
            "projects": {},
        }

        # Add per-project metrics
        for project_id in self.metrics_history.keys():
            export_data["projects"][project_id] = {
                "metrics": self.get_project_metrics(project_id, hours=24),
                "history": [m.to_dict() for m in self.metrics_history[project_id]],
            }

        # Write to file
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Metrics exported to {output_path}")
        return str(output_file)

    def reset_metrics(self):
        """Reset all metrics (use with caution)."""
        self.metrics_history.clear()
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.response_times.clear()
        self.request_timestamps.clear()
        logger.warning("All metrics have been reset")

# Singleton instance
_health_monitor: HealthMonitor | None = None

def get_health_monitor() -> HealthMonitor | None:
    """Get the global health monitor instance."""
    return _health_monitor

def initialize_health_monitor(
    project_manager: ProjectManager, audit_logger: AuditLogger | None = None, **kwargs
) -> HealthMonitor:
    """
    Initialize the global health monitor.

    Args:
        project_manager: Project manager instance
        audit_logger: Optional audit logger
        **kwargs: Additional configuration options

    Returns:
        HealthMonitor instance
    """
    global _health_monitor
    _health_monitor = HealthMonitor(project_manager, audit_logger, **kwargs)
    return _health_monitor
