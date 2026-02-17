"""
Middleware for Multi-Endpoint Architecture

Provides authentication, rate limiting, and audit logging
that works with the multi-endpoint architecture.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_headers
from fastmcp.server.middleware import Middleware, MiddlewareContext

from core.api_keys import get_api_key_manager
from core.audit_log import EventType, LogLevel, get_audit_logger
from core.auth import get_auth_manager
from core.context import clear_api_key_context, set_api_key_context
from core.rate_limiter import get_rate_limiter

from .config import EndpointConfig

logger = logging.getLogger(__name__)

@dataclass
class AuthContext:
    """Authentication context for a request"""

    key_id: str | None = None
    project_id: str | None = None
    scope: str = "read"
    is_master_key: bool = False
    is_oauth_token: bool = False
    client_ip: str | None = None

class EndpointAuthMiddleware(Middleware):
    """
    Authentication middleware for multi-endpoint architecture.

    Validates API keys/tokens and enforces endpoint-specific access rules.
    """

    def __init__(self, endpoint_config: EndpointConfig):
        """
        Initialize middleware with endpoint configuration.

        Args:
            endpoint_config: Configuration for this endpoint
        """
        self.config = endpoint_config
        self.auth_manager = get_auth_manager()
        self.api_key_manager = get_api_key_manager()

    async def on_call_tool(self, context: MiddlewareContext, call_next: Callable):
        """
        Handle tool call with authentication and authorization.

        Args:
            context: Middleware context
            call_next: Next middleware in chain
        """
        tool_name = getattr(context.message, "name", "unknown")
        start_time = time.time()

        try:
            # Extract and validate authentication
            auth_context = await self._authenticate(context)

            # Check endpoint access
            self._check_endpoint_access(auth_context)

            # Check tool access
            self._check_tool_access(tool_name, auth_context)

            # Set context for downstream handlers
            if auth_context.key_id:
                set_api_key_context(
                    key_id=auth_context.key_id,
                    project_id=auth_context.project_id or "*",
                    scope=auth_context.scope,
                    is_global=auth_context.project_id == "*",
                )

            # Call the actual tool
            result = await call_next(context)

            # Log success
            self._log_success(tool_name, auth_context, start_time)

            return result

        except ToolError:
            raise
        except Exception as e:
            self._log_error(tool_name, str(e), start_time)
            raise ToolError(f"Authentication error: {str(e)}")
        finally:
            clear_api_key_context()

    async def _authenticate(self, context: MiddlewareContext) -> AuthContext:
        """
        Extract and validate authentication from request.

        Args:
            context: Middleware context

        Returns:
            AuthContext with authentication details
        """
        auth_context = AuthContext()

        # Get headers
        try:
            headers = get_http_headers()
        except Exception:
            headers = {}

        # Extract client IP
        auth_context.client_ip = headers.get("x-forwarded-for", "unknown")

        # Get authorization header
        auth_header = headers.get("authorization", "")

        if not auth_header:
            # No auth provided
            if self.config.require_master_key:
                raise ToolError("Master API key required for this endpoint")
            return auth_context

        # Parse authorization
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
        else:
            token = auth_header

        # Check token type
        if token.startswith("sk-"):
            # Master API key
            if self.auth_manager.validate_master_key(token):
                auth_context.is_master_key = True
                auth_context.project_id = "*"
                auth_context.scope = "admin"
                auth_context.key_id = "master"
                return auth_context
            else:
                raise ToolError("Invalid master API key")

        elif token.startswith("cmp_"):
            # Project API key
            key = self.api_key_manager.get_key_by_token(token)
            if not key:
                raise ToolError("Invalid API key")

            if key.revoked:
                raise ToolError("API key has been revoked")

            if key.is_expired():
                raise ToolError("API key has expired")

            auth_context.key_id = key.key_id
            auth_context.project_id = key.project_id
            auth_context.scope = key.scope
            return auth_context

        else:
            # Possibly OAuth token (JWT)
            try:
                from core.oauth import get_token_manager

                token_manager = get_token_manager()
                payload = token_manager.validate_access_token(token)

                if payload:
                    auth_context.is_oauth_token = True
                    auth_context.project_id = payload.get("project_id", "*")
                    auth_context.scope = payload.get("scope", "read")
                    auth_context.key_id = f"oauth_{payload.get('sub', 'unknown')}"
                    return auth_context
            except Exception:
                pass

            raise ToolError("Invalid authentication token")

    def _check_endpoint_access(self, auth_context: AuthContext):
        """
        Check if auth context allows access to this endpoint.

        Args:
            auth_context: Authentication context
        """
        # Master key always has access
        if auth_context.is_master_key:
            return

        # Check if endpoint requires master key
        if self.config.require_master_key:
            raise ToolError(f"Endpoint {self.config.path} requires master API key")

        # Check scope requirements
        if self.config.allowed_scopes:
            # Check if any of the user's scopes are allowed
            user_scopes = set(auth_context.scope.split())
            if not user_scopes & self.config.allowed_scopes:
                raise ToolError(
                    f"Insufficient scope. Required: {self.config.allowed_scopes}, "
                    f"Got: {user_scopes}"
                )

        # Check plugin type access
        if auth_context.project_id and auth_context.project_id != "*":
            # Extract plugin type from project_id (e.g., "wordpress_site4" -> "wordpress")
            if "_" in auth_context.project_id:
                key_plugin_type = auth_context.project_id.split("_")[0]

                # Check if endpoint allows this plugin type
                if self.config.plugin_types and key_plugin_type not in self.config.plugin_types:
                    raise ToolError(
                        f"API key for {key_plugin_type} cannot access "
                        f"{self.config.endpoint_type.value} endpoint"
                    )

    def _check_tool_access(self, tool_name: str, auth_context: AuthContext):
        """
        Check if auth context allows access to specific tool.

        Args:
            tool_name: Name of the tool
            auth_context: Authentication context
        """
        # Master key has access to all tools
        if auth_context.is_master_key:
            return

        # Check tool blacklist
        if not self.config.allows_tool(tool_name):
            raise ToolError(f"Access denied to tool: {tool_name}")

        # Check site filter for project endpoints
        if self.config.site_filter:
            # Tool must be for the configured site
            # This is handled by parameter injection in the wrapper
            pass

    def _log_success(self, tool_name: str, auth_context: AuthContext, start_time: float):
        """Log successful tool execution"""
        duration_ms = int((time.time() - start_time) * 1000)
        logger.debug(
            f"Tool {tool_name} executed successfully "
            f"(key={auth_context.key_id}, duration={duration_ms}ms)"
        )

    def _log_error(self, tool_name: str, error: str, start_time: float):
        """Log tool execution error"""
        duration_ms = int((time.time() - start_time) * 1000)
        logger.warning(f"Tool {tool_name} failed: {error} (duration={duration_ms}ms)")

class EndpointRateLimitMiddleware(Middleware):
    """
    Rate limiting middleware for multi-endpoint architecture.
    """

    def __init__(self, endpoint_config: EndpointConfig):
        self.config = endpoint_config
        self.rate_limiter = get_rate_limiter()

    async def on_call_tool(self, context: MiddlewareContext, call_next: Callable):
        """Apply rate limiting before tool execution"""
        # Get client identifier
        try:
            headers = get_http_headers()
            client_id = headers.get("authorization", "anonymous")[:50]
        except Exception:
            client_id = "unknown"

        # Check rate limit
        allowed, info = self.rate_limiter.check_rate_limit(client_id)

        if not allowed:
            raise ToolError(
                f"Rate limit exceeded. Retry after {info.get('retry_after', 60)} seconds"
            )

        # Proceed with request
        return await call_next(context)

class EndpointAuditMiddleware(Middleware):
    """
    Audit logging middleware for multi-endpoint architecture.
    """

    def __init__(self, endpoint_config: EndpointConfig):
        self.config = endpoint_config
        self.audit_logger = get_audit_logger()

    async def on_call_tool(self, context: MiddlewareContext, call_next: Callable):
        """Log tool execution to audit log"""
        tool_name = getattr(context.message, "name", "unknown")
        start_time = time.time()

        try:
            result = await call_next(context)

            # Log success
            self.audit_logger.log(
                level=LogLevel.INFO,
                event_type=EventType.TOOL_CALL,
                message=f"Tool executed: {tool_name}",
                details={
                    "tool": tool_name,
                    "endpoint": self.config.path,
                    "duration_ms": int((time.time() - start_time) * 1000),
                    "success": True,
                },
            )

            return result

        except Exception as e:
            # Log failure
            self.audit_logger.log(
                level=LogLevel.WARNING,
                event_type=EventType.TOOL_CALL,
                message=f"Tool failed: {tool_name}",
                details={
                    "tool": tool_name,
                    "endpoint": self.config.path,
                    "duration_ms": int((time.time() - start_time) * 1000),
                    "success": False,
                    "error": str(e),
                },
            )
            raise

def create_endpoint_middleware(endpoint_config: EndpointConfig) -> list:
    """
    Create middleware stack for an endpoint.

    Args:
        endpoint_config: Endpoint configuration

    Returns:
        List of middleware instances
    """
    return [
        EndpointAuthMiddleware(endpoint_config),
        EndpointRateLimitMiddleware(endpoint_config),
        EndpointAuditMiddleware(endpoint_config),
    ]
