"""Application Handler — manages Coolify applications, lifecycle, and env vars."""

import json
from typing import Any

from plugins.coolify.client import CoolifyClient
from plugins.coolify.handlers._utils import (
    decode_payload_fields,
    encode_payload_fields,
    normalize_github_repository_slug,
    summarize_items,
    validate_coolify_description,
)

APPLICATION_COMPACT_FIELDS = [
    "uuid",
    "name",
    "status",
    "build_pack",
    "project_uuid",
    "environment_name",
    "fqdn",
    "domains",
    "git_repository",
    "git_branch",
]

CUSTOM_LABEL_FIELDS = {"custom_labels"}


def get_tool_specifications() -> list[dict[str, Any]]:
    """Return tool specifications for ToolGenerator."""
    return [
        {
            "name": "list_applications",
            "category": "read",
            "method_name": "list_applications",
            "description": (
                "List Coolify applications with compact output by default. "
                "Use include_details=true for full Coolify payloads."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "tag": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Filter by tag name",
                    },
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Case-insensitive filter matched against name, UUID, fqdn, or domains",
                    },
                    "limit": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Maximum number of applications to return after filtering",
                        "minimum": 1,
                        "maximum": 200,
                    },
                    "fields": {
                        "anyOf": [
                            {
                                "type": "array",
                                "items": {"type": "string"},
                                "minItems": 1,
                                "maxItems": 50,
                            },
                            {"type": "null"},
                        ],
                        "description": "Specific fields to return. Ignored when include_details=true.",
                    },
                    "include_details": {
                        "type": "boolean",
                        "description": "Return full Coolify application objects instead of compact summaries",
                        "default": False,
                    },
                },
            },
            "scope": "read",
        },
        {
            "name": "get_application",
            "category": "read",
            "method_name": "get_application",
            "description": "Get details of a specific Coolify application by UUID.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Application UUID",
                        "minLength": 1,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "read",
        },
        {
            "name": "list_github_apps",
            "category": "read",
            "method_name": "list_github_apps",
            "description": "List configured Coolify GitHub Apps for private repository deployments.",
            "schema": {
                "type": "object",
                "properties": {},
            },
            "scope": "read",
        },
        {
            "name": "create_application_public",
            "category": "crud",
            "method_name": "create_application_public",
            "description": (
                "Create a Coolify application from a public Git repository. "
                "Requires project_uuid, server_uuid, environment, git_repository, "
                "git_branch, build_pack, and ports_exposes."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "project_uuid": {
                        "type": "string",
                        "description": "Project UUID",
                    },
                    "server_uuid": {
                        "type": "string",
                        "description": "Server UUID",
                    },
                    "environment_name": {
                        "type": "string",
                        "description": "Environment name (e.g., 'production')",
                    },
                    "git_repository": {
                        "type": "string",
                        "description": "Git repository URL",
                    },
                    "git_branch": {
                        "type": "string",
                        "description": "Git branch name",
                    },
                    "build_pack": {
                        "type": "string",
                        "description": "Build pack type",
                        "enum": ["nixpacks", "static", "dockerfile", "dockercompose"],
                    },
                    "ports_exposes": {
                        "type": "string",
                        "description": "Exposed ports (e.g., '3000')",
                    },
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Application name",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Application description",
                    },
                    "domains": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Comma-separated domain URLs",
                    },
                    "instant_deploy": {
                        "type": "boolean",
                        "description": "Deploy immediately after creation",
                        "default": False,
                    },
                },
                "required": [
                    "project_uuid",
                    "server_uuid",
                    "environment_name",
                    "git_repository",
                    "git_branch",
                    "build_pack",
                    "ports_exposes",
                ],
            },
            "scope": "write",
        },
        {
            "name": "create_application_private_github_app",
            "category": "crud",
            "method_name": "create_application_private_github_app",
            "description": (
                "Create a Coolify application from a private GitHub repository using "
                "an already configured Coolify GitHub App. Use github_app_uuid, or "
                "source_uuid as a backwards-compatible alias."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "github_app_uuid": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Configured Coolify GitHub App UUID",
                    },
                    "source_uuid": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Alias for github_app_uuid used by older issue notes",
                    },
                    "project_uuid": {
                        "type": "string",
                        "description": "Project UUID",
                    },
                    "server_uuid": {
                        "type": "string",
                        "description": "Server UUID",
                    },
                    "environment_name": {
                        "type": "string",
                        "description": "Environment name (e.g., 'production')",
                    },
                    "git_repository": {
                        "type": "string",
                        "description": "GitHub repository slug owner/repo or a github.com URL",
                    },
                    "git_branch": {
                        "type": "string",
                        "description": "Git branch name",
                    },
                    "build_pack": {
                        "type": "string",
                        "description": "Build pack type",
                        "enum": ["nixpacks", "static", "dockerfile", "dockercompose"],
                    },
                    "ports_exposes": {
                        "type": "string",
                        "description": "Exposed ports (e.g., '3000')",
                    },
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Application name",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Application description",
                    },
                    "domains": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Comma-separated domain URLs",
                    },
                    "instant_deploy": {
                        "type": "boolean",
                        "description": "Deploy immediately after creation",
                        "default": False,
                    },
                },
                "required": [
                    "project_uuid",
                    "server_uuid",
                    "environment_name",
                    "git_repository",
                    "git_branch",
                    "build_pack",
                    "ports_exposes",
                ],
                "anyOf": [
                    {"required": ["github_app_uuid"]},
                    {"required": ["source_uuid"]},
                ],
            },
            "scope": "write",
        },
        {
            "name": "create_application_dockerfile",
            "category": "crud",
            "method_name": "create_application_dockerfile",
            "description": (
                "Create a Coolify application from a Dockerfile (without git). "
                "Requires project_uuid, server_uuid, environment, and dockerfile content."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "project_uuid": {
                        "type": "string",
                        "description": "Project UUID",
                    },
                    "server_uuid": {
                        "type": "string",
                        "description": "Server UUID",
                    },
                    "destination_uuid": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Optional Coolify destination UUID when the server has multiple destinations",
                    },
                    "environment_name": {
                        "type": "string",
                        "description": "Environment name",
                    },
                    "dockerfile": {
                        "type": "string",
                        "description": "Dockerfile content",
                    },
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Application name",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Application description",
                    },
                    "domains": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Comma-separated domain URLs",
                    },
                    "ports_exposes": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Exposed ports",
                    },
                    "instant_deploy": {
                        "type": "boolean",
                        "description": "Deploy immediately",
                        "default": False,
                    },
                },
                "required": [
                    "project_uuid",
                    "server_uuid",
                    "environment_name",
                    "dockerfile",
                ],
            },
            "scope": "write",
        },
        {
            "name": "create_application_docker_image",
            "category": "crud",
            "method_name": "create_application_docker_image",
            "description": (
                "Create a Coolify application from a Docker image. "
                "Requires project_uuid, server_uuid, environment, "
                "docker_registry_image_name, and ports_exposes."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "project_uuid": {
                        "type": "string",
                        "description": "Project UUID",
                    },
                    "server_uuid": {
                        "type": "string",
                        "description": "Server UUID",
                    },
                    "destination_uuid": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Optional Coolify destination UUID when the server has multiple destinations",
                    },
                    "environment_name": {
                        "type": "string",
                        "description": "Environment name",
                    },
                    "docker_registry_image_name": {
                        "type": "string",
                        "description": "Docker image name (e.g., 'nginx')",
                    },
                    "ports_exposes": {
                        "type": "string",
                        "description": "Exposed ports",
                    },
                    "docker_registry_image_tag": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Docker image tag (default: latest)",
                    },
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Application name",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Application description",
                    },
                    "domains": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Comma-separated domain URLs",
                    },
                    "instant_deploy": {
                        "type": "boolean",
                        "description": "Deploy immediately",
                        "default": False,
                    },
                },
                "required": [
                    "project_uuid",
                    "server_uuid",
                    "environment_name",
                    "docker_registry_image_name",
                    "ports_exposes",
                ],
            },
            "scope": "write",
        },
        {
            "name": "create_application_compose",
            "category": "crud",
            "method_name": "create_application_compose",
            "description": (
                "REMOVED by Coolify — this endpoint no longer exists and every call fails. "
                "Use coolify_create_service for raw Compose, or "
                "coolify_create_application_public with build_pack='dockercompose' for a "
                "git-backed Compose app."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "project_uuid": {
                        "type": "string",
                        "description": "Project UUID",
                    },
                    "server_uuid": {
                        "type": "string",
                        "description": "Server UUID",
                    },
                    "environment_name": {
                        "type": "string",
                        "description": "Environment name",
                    },
                    "docker_compose_raw": {
                        "type": "string",
                        "description": "Raw Docker Compose YAML content",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Application description",
                    },
                    "domains": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Comma-separated domain URLs",
                    },
                    "ports_exposes": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Exposed ports",
                    },
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Application name",
                    },
                    "instant_deploy": {
                        "type": "boolean",
                        "description": "Deploy immediately",
                        "default": False,
                    },
                },
                "required": [
                    "project_uuid",
                    "server_uuid",
                    "environment_name",
                    "docker_compose_raw",
                ],
            },
            "scope": "write",
        },
        {
            "name": "update_application",
            "category": "crud",
            "method_name": "update_application",
            "description": (
                "Update a Coolify application settings. Supports name, description, "
                "domains, build settings, health checks, resource limits, and more."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Application UUID",
                        "minLength": 1,
                    },
                    "name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Application name",
                    },
                    "description": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Application description",
                    },
                    "domains": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Comma-separated domain URLs",
                    },
                    "clear_domains": {
                        "type": "boolean",
                        "description": "Clear all application domains by sending domains as an empty string",
                        "default": False,
                    },
                    "git_repository": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Git repository slug or URL",
                    },
                    "git_branch": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Git branch",
                    },
                    "git_commit_sha": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Specific Git commit SHA",
                    },
                    "docker_registry_image_name": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Docker registry image name",
                    },
                    "docker_registry_image_tag": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Docker registry image tag",
                    },
                    "build_pack": {
                        "anyOf": [
                            {
                                "type": "string",
                                "enum": [
                                    "nixpacks",
                                    "static",
                                    "dockerfile",
                                    "dockercompose",
                                ],
                            },
                            {"type": "null"},
                        ],
                        "description": "Build pack type",
                    },
                    "static_image": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Static build image",
                    },
                    "install_command": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Install command",
                    },
                    "build_command": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Build command",
                    },
                    "start_command": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Start command",
                    },
                    "ports_exposes": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Exposed ports",
                    },
                    "ports_mappings": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Port mappings",
                    },
                    "base_directory": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Base directory for builds",
                    },
                    "publish_directory": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Publish directory for static builds",
                    },
                    "health_check_enabled": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Enable Coolify health checks",
                    },
                    "health_check_path": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Health check path",
                    },
                    "health_check_port": {
                        "anyOf": [{"type": "string"}, {"type": "integer"}, {"type": "null"}],
                        "description": "Health check port",
                    },
                    "health_check_host": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Health check host header",
                    },
                    "health_check_method": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Health check HTTP method",
                    },
                    "health_check_return_code": {
                        "anyOf": [{"type": "integer"}, {"type": "string"}, {"type": "null"}],
                        "description": "Expected health check HTTP status code",
                    },
                    "health_check_scheme": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Health check scheme",
                        "enum": ["http", "https", None],
                    },
                    "health_check_response_text": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Expected health check response text",
                    },
                    "health_check_interval": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Health check interval in seconds",
                    },
                    "health_check_timeout": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Health check timeout in seconds",
                    },
                    "health_check_retries": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Health check retry count",
                    },
                    "health_check_start_period": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Health check start period in seconds",
                    },
                    "limits_memory": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Container memory limit, e.g. 512m",
                    },
                    "limits_memory_swap": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Container memory swap limit",
                    },
                    "limits_memory_swappiness": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "Container memory swappiness",
                    },
                    "limits_memory_reservation": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Container memory reservation",
                    },
                    "limits_cpus": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "CPU limit, e.g. 0.5",
                    },
                    "limits_cpuset": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "CPU set",
                    },
                    "limits_cpu_shares": {
                        "anyOf": [{"type": "integer"}, {"type": "null"}],
                        "description": "CPU shares",
                    },
                    "custom_labels": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": (
                            "Plain-text newline-separated Docker labels. The MCP plugin "
                            "base64-encodes this for Coolify. Prefer native basic-auth "
                            "fields for HTTP basic auth."
                        ),
                    },
                    "custom_docker_run_options": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Custom docker run options",
                    },
                    "pre_deployment_command": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Command to run before deployment",
                    },
                    "pre_deployment_command_container": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Container for pre-deployment command",
                    },
                    "post_deployment_command": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Command to run after deployment",
                    },
                    "post_deployment_command_container": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Container for post-deployment command",
                    },
                    "dockerfile": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Dockerfile content",
                    },
                    "dockerfile_location": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Dockerfile path in repository",
                    },
                    "dockerfile_target_build": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Dockerfile target build stage",
                    },
                    "docker_compose_location": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Docker Compose file path in repository",
                    },
                    "docker_compose": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Rendered Docker Compose content",
                    },
                    "docker_compose_raw": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Raw Docker Compose content",
                    },
                    "docker_compose_custom_start_command": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Custom Docker Compose start command",
                    },
                    "docker_compose_custom_build_command": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Custom Docker Compose build command",
                    },
                    "docker_compose_domains": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Docker Compose domain mapping",
                    },
                    "watch_paths": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Comma-separated watch paths for deployments",
                    },
                    "redirect": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Redirect behavior",
                    },
                    "custom_nginx_configuration": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Custom Nginx configuration",
                    },
                    "is_http_basic_auth_enabled": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Enable Coolify native HTTP basic auth",
                    },
                    "http_basic_auth_username": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Coolify native HTTP basic auth username",
                    },
                    "http_basic_auth_password": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Coolify native HTTP basic auth password",
                    },
                    "is_auto_deploy_enabled": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Enable auto-deploy on push",
                    },
                    "is_force_https_enabled": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Force HTTPS",
                    },
                    "is_gzip_enabled": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Enable gzip",
                    },
                    "is_stripprefix_enabled": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Enable strip-prefix middleware",
                    },
                    "is_log_drain_enabled": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Enable log drain",
                    },
                    "is_preview_deployments_enabled": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Enable preview deployments",
                    },
                    "instant_deploy": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Deploy instantly",
                    },
                },
                "required": ["uuid"],
            },
            "scope": "write",
        },
        {
            "name": "delete_application",
            "category": "system",
            "method_name": "delete_application",
            "description": (
                "Delete a Coolify application permanently. "
                "Optionally clean up configs, volumes, and networks."
            ),
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Application UUID",
                        "minLength": 1,
                    },
                    "delete_configurations": {
                        "type": "boolean",
                        "description": "Delete configurations",
                        "default": True,
                    },
                    "delete_volumes": {
                        "type": "boolean",
                        "description": "Delete volumes",
                        "default": True,
                    },
                    "docker_cleanup": {
                        "type": "boolean",
                        "description": "Run Docker cleanup",
                        "default": True,
                    },
                    "delete_connected_networks": {
                        "type": "boolean",
                        "description": "Delete connected networks",
                        "default": True,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "admin",
        },
        {
            "name": "start_application",
            "category": "lifecycle",
            "method_name": "start_application",
            "description": "Deploy/start a Coolify application. Triggers a new deployment.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Application UUID",
                        "minLength": 1,
                    },
                    "force": {
                        "type": "boolean",
                        "description": "Force rebuild without cache",
                        "default": False,
                    },
                    "instant_deploy": {
                        "type": "boolean",
                        "description": "Skip deployment queue",
                        "default": False,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "write",
        },
        {
            "name": "stop_application",
            "category": "lifecycle",
            "method_name": "stop_application",
            "description": "Stop a running Coolify application.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Application UUID",
                        "minLength": 1,
                    },
                    "docker_cleanup": {
                        "type": "boolean",
                        "description": "Prune networks and volumes",
                        "default": True,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "write",
        },
        {
            "name": "restart_application",
            "category": "lifecycle",
            "method_name": "restart_application",
            "description": "Restart a Coolify application.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Application UUID",
                        "minLength": 1,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "write",
        },
        {
            "name": "get_application_logs",
            "category": "read_sensitive",
            "sensitivity": "sensitive",
            "method_name": "get_application_logs",
            "description": "Get logs for a Coolify application.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Application UUID",
                        "minLength": 1,
                    },
                    "lines": {
                        "type": "integer",
                        "description": "Number of log lines to retrieve",
                        "default": 100,
                        "minimum": 1,
                        "maximum": 10000,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "read",
        },
        {
            "name": "list_application_envs",
            "category": "read_sensitive",
            "sensitivity": "sensitive",
            "method_name": "list_application_envs",
            "description": "List environment variables for a Coolify application.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Application UUID",
                        "minLength": 1,
                    },
                },
                "required": ["uuid"],
            },
            "scope": "read",
        },
        {
            "name": "create_application_env",
            "category": "env",
            "sensitivity": "sensitive",
            "method_name": "create_application_env",
            "description": "Create an environment variable for a Coolify application.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Application UUID",
                        "minLength": 1,
                    },
                    "key": {
                        "type": "string",
                        "description": "Environment variable key",
                        "minLength": 1,
                    },
                    "value": {
                        "type": "string",
                        "description": "Environment variable value",
                    },
                    "is_preview": {
                        "type": "boolean",
                        "description": "Preview deployment only",
                        "default": False,
                    },
                    "is_literal": {
                        "type": "boolean",
                        "description": "Treat as literal (no variable interpolation)",
                        "default": False,
                    },
                    "is_multiline": {
                        "type": "boolean",
                        "description": "Allow multiline value",
                        "default": False,
                    },
                    "is_shown_once": {
                        "type": "boolean",
                        "description": "Show value only once",
                        "default": False,
                    },
                    "is_runtime": {
                        "type": "boolean",
                        "description": "Expose the variable at runtime",
                        "default": True,
                    },
                    "is_buildtime": {
                        "type": "boolean",
                        "description": "Expose the variable at build time",
                        "default": True,
                    },
                    "comment": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Optional Coolify env var comment",
                    },
                },
                "required": ["uuid", "key", "value"],
            },
            "scope": "write",
        },
        {
            "name": "update_application_env",
            "category": "env",
            "sensitivity": "sensitive",
            "method_name": "update_application_env",
            "description": "Update an environment variable for a Coolify application.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Application UUID",
                        "minLength": 1,
                    },
                    "key": {
                        "type": "string",
                        "description": "Environment variable key",
                        "minLength": 1,
                    },
                    "value": {
                        "type": "string",
                        "description": "New value",
                    },
                    "is_preview": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Preview deployment only",
                    },
                    "is_literal": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Treat as literal",
                    },
                    "is_multiline": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Allow multiline",
                    },
                    "is_shown_once": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Show only once",
                    },
                    "is_runtime": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Expose the variable at runtime",
                    },
                    "is_buildtime": {
                        "anyOf": [{"type": "boolean"}, {"type": "null"}],
                        "description": "Expose the variable at build time",
                    },
                    "comment": {
                        "anyOf": [{"type": "string"}, {"type": "null"}],
                        "description": "Optional Coolify env var comment",
                    },
                },
                "required": ["uuid", "key", "value"],
            },
            "scope": "write",
        },
        {
            "name": "update_application_envs_bulk",
            "category": "env",
            "sensitivity": "sensitive",
            "method_name": "update_application_envs_bulk",
            "description": "Bulk update environment variables for a Coolify application.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Application UUID",
                        "minLength": 1,
                    },
                    "data": {
                        "type": "array",
                        "description": "Array of env var objects with key, value, and flags",
                        "items": {
                            "type": "object",
                            "properties": {
                                "key": {"type": "string"},
                                "value": {"type": "string"},
                                "is_preview": {"type": "boolean"},
                                "is_literal": {"type": "boolean"},
                                "is_multiline": {"type": "boolean"},
                                "is_shown_once": {"type": "boolean"},
                                "is_runtime": {"type": "boolean"},
                                "is_buildtime": {"type": "boolean"},
                                "comment": {"type": "string"},
                            },
                            "required": ["key", "value"],
                        },
                    },
                },
                "required": ["uuid", "data"],
            },
            "scope": "write",
        },
        {
            "name": "delete_application_env",
            "category": "env",
            "sensitivity": "sensitive",
            "method_name": "delete_application_env",
            "description": "Delete an environment variable from a Coolify application.",
            "schema": {
                "type": "object",
                "properties": {
                    "uuid": {
                        "type": "string",
                        "description": "Application UUID",
                        "minLength": 1,
                    },
                    "env_uuid": {
                        "type": "string",
                        "description": "Environment variable UUID",
                        "minLength": 1,
                    },
                },
                "required": ["uuid", "env_uuid"],
            },
            "scope": "write",
        },
    ]


# --- Handler Functions ---


def _prepare_application_create_payload(
    kwargs: dict[str, Any],
    *,
    normalize_repository: bool = True,
) -> tuple[dict[str, Any], list[str]]:
    data = {k: v for k, v in kwargs.items() if v is not None}
    warnings: list[str] = []
    validate_coolify_description(data.get("description"))
    if normalize_repository and "git_repository" in data:
        data["git_repository"], warning = normalize_github_repository_slug(data["git_repository"])
        if warning:
            warnings.append(warning)
    return data, warnings


async def list_applications(
    client: CoolifyClient,
    tag: str | None = None,
    name: str | None = None,
    limit: int | None = None,
    fields: list[str] | None = None,
    include_details: bool = False,
) -> str:
    """List all applications."""
    apps = await client.list_applications(tag=tag)
    applications, total, truncated = summarize_items(
        apps,
        compact_fields=APPLICATION_COMPACT_FIELDS,
        fields=fields,
        limit=limit,
        name=name,
        include_details=include_details,
    )
    result = {
        "success": True,
        "count": len(applications),
        "total": total,
        "truncated": truncated,
        "applications": applications,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def get_application(client: CoolifyClient, uuid: str) -> str:
    """Get application details."""
    app = await client.get_application(uuid)
    app = decode_payload_fields(app, CUSTOM_LABEL_FIELDS)
    result = {"success": True, "application": app}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def list_github_apps(client: CoolifyClient) -> str:
    """List configured GitHub Apps."""
    apps = await client.list_github_apps()
    result = {"success": True, "count": len(apps), "github_apps": apps}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def create_application_public(client: CoolifyClient, **kwargs) -> str:
    """Create application from public repository."""
    data, warnings = _prepare_application_create_payload(kwargs)
    app = await client.create_application_public(data)
    result = {
        "success": True,
        "message": "Application created successfully",
        "application": app,
    }
    if warnings:
        result["warnings"] = warnings
    return json.dumps(result, indent=2, ensure_ascii=False)


async def create_application_private_github_app(client: CoolifyClient, **kwargs) -> str:
    """Create application from a private GitHub repository via a configured GitHub App."""
    data, warnings = _prepare_application_create_payload(kwargs)
    if data.get("github_app_uuid") is None and data.get("source_uuid") is not None:
        data["github_app_uuid"] = data.pop("source_uuid")
        warnings.append("Mapped source_uuid to Coolify's github_app_uuid field.")
    data.pop("source_uuid", None)
    if not data.get("github_app_uuid"):
        raise ValueError("github_app_uuid is required (source_uuid is accepted as an alias)")

    app = await client.create_application_private_github_app(data)
    result = {
        "success": True,
        "message": "Private GitHub App application created successfully",
        "application": app,
    }
    if warnings:
        result["warnings"] = warnings
    return json.dumps(result, indent=2, ensure_ascii=False)


async def create_application_dockerfile(client: CoolifyClient, **kwargs) -> str:
    """Create application from Dockerfile."""
    data, warnings = _prepare_application_create_payload(kwargs, normalize_repository=False)
    app = await client.create_application_dockerfile(data)
    result = {
        "success": True,
        "message": "Application created from Dockerfile",
        "application": app,
    }
    if warnings:
        result["warnings"] = warnings
    return json.dumps(result, indent=2, ensure_ascii=False)


async def create_application_docker_image(client: CoolifyClient, **kwargs) -> str:
    """Create application from Docker image."""
    data, warnings = _prepare_application_create_payload(kwargs, normalize_repository=False)
    app = await client.create_application_docker_image(data)
    result = {
        "success": True,
        "message": "Application created from Docker image",
        "application": app,
    }
    if warnings:
        result["warnings"] = warnings
    return json.dumps(result, indent=2, ensure_ascii=False)


async def create_application_compose(client: CoolifyClient, **kwargs) -> str:
    """Create application from Docker Compose."""
    data, warnings = _prepare_application_create_payload(kwargs, normalize_repository=False)
    app = await client.create_application_docker_compose(data)
    result = {
        "success": True,
        "message": "Application created from Docker Compose",
        "application": app,
    }
    if warnings:
        result["warnings"] = warnings
    return json.dumps(result, indent=2, ensure_ascii=False)


async def update_application(client: CoolifyClient, uuid: str, **kwargs) -> str:
    """Update application settings."""
    data = {k: v for k, v in kwargs.items() if v is not None and k != "uuid"}
    warnings: list[str] = []
    if data.pop("clear_domains", False):
        data["domains"] = ""
        warnings.append("Clearing domains by sending domains as an empty string.")

    validate_coolify_description(data.get("description"))
    if "git_repository" in data:
        data["git_repository"], warning = normalize_github_repository_slug(data["git_repository"])
        if warning:
            warnings.append(warning)

    data = encode_payload_fields(data, CUSTOM_LABEL_FIELDS)
    app = await client.update_application(uuid, data)
    app = decode_payload_fields(app, CUSTOM_LABEL_FIELDS)
    result = {
        "success": True,
        "message": f"Application '{uuid}' updated successfully",
        "application": app,
    }
    if warnings:
        result["warnings"] = warnings
    return json.dumps(result, indent=2, ensure_ascii=False)


async def delete_application(
    client: CoolifyClient,
    uuid: str,
    delete_configurations: bool = True,
    delete_volumes: bool = True,
    docker_cleanup: bool = True,
    delete_connected_networks: bool = True,
) -> str:
    """Delete an application."""
    result_data = await client.delete_application(
        uuid,
        delete_configurations=delete_configurations,
        delete_volumes=delete_volumes,
        docker_cleanup=docker_cleanup,
        delete_connected_networks=delete_connected_networks,
    )
    result = {"success": True, "message": f"Application '{uuid}' deleted", "data": result_data}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def start_application(
    client: CoolifyClient,
    uuid: str,
    force: bool = False,
    instant_deploy: bool = False,
) -> str:
    """Deploy/start application."""
    result_data = await client.start_application(uuid, force=force, instant_deploy=instant_deploy)
    result = {
        "success": True,
        "message": f"Application '{uuid}' deployment queued",
        "data": result_data,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def stop_application(client: CoolifyClient, uuid: str, docker_cleanup: bool = True) -> str:
    """Stop application."""
    result_data = await client.stop_application(uuid, docker_cleanup=docker_cleanup)
    result = {"success": True, "message": f"Application '{uuid}' stopping", "data": result_data}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def restart_application(client: CoolifyClient, uuid: str) -> str:
    """Restart application."""
    result_data = await client.restart_application(uuid)
    result = {"success": True, "message": f"Application '{uuid}' restarting", "data": result_data}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def get_application_logs(client: CoolifyClient, uuid: str, lines: int = 100) -> str:
    """Get application logs."""
    logs = await client.get_application_logs(uuid, lines=lines)
    result = {"success": True, "logs": logs}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def list_application_envs(client: CoolifyClient, uuid: str) -> str:
    """List application environment variables."""
    envs = await client.list_application_envs(uuid)
    result = {"success": True, "count": len(envs), "envs": envs}
    return json.dumps(result, indent=2, ensure_ascii=False)


async def create_application_env(
    client: CoolifyClient,
    uuid: str,
    key: str,
    value: str,
    is_preview: bool = False,
    is_literal: bool = False,
    is_multiline: bool = False,
    is_shown_once: bool = False,
    is_runtime: bool = True,
    is_buildtime: bool = True,
    comment: str | None = None,
) -> str:
    """Create application environment variable."""
    data = {
        "key": key,
        "value": value,
        "is_preview": is_preview,
        "is_literal": is_literal,
        "is_multiline": is_multiline,
        "is_shown_once": is_shown_once,
        "is_runtime": is_runtime,
        "is_buildtime": is_buildtime,
    }
    if comment is not None:
        data["comment"] = comment
    result_data = await client.create_application_env(uuid, data)
    result = {
        "success": True,
        "message": f"Env var '{key}' created",
        "data": result_data,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def update_application_env(
    client: CoolifyClient,
    uuid: str,
    key: str,
    value: str,
    is_preview: bool | None = None,
    is_literal: bool | None = None,
    is_multiline: bool | None = None,
    is_shown_once: bool | None = None,
    is_runtime: bool | None = None,
    is_buildtime: bool | None = None,
    comment: str | None = None,
) -> str:
    """Update application environment variable."""
    data: dict[str, Any] = {"key": key, "value": value}
    if is_preview is not None:
        data["is_preview"] = is_preview
    if is_literal is not None:
        data["is_literal"] = is_literal
    if is_multiline is not None:
        data["is_multiline"] = is_multiline
    if is_shown_once is not None:
        data["is_shown_once"] = is_shown_once
    if is_runtime is not None:
        data["is_runtime"] = is_runtime
    if is_buildtime is not None:
        data["is_buildtime"] = is_buildtime
    if comment is not None:
        data["comment"] = comment
    result_data = await client.update_application_env(uuid, data)
    result = {
        "success": True,
        "message": f"Env var '{key}' updated",
        "data": result_data,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def update_application_envs_bulk(client: CoolifyClient, uuid: str, data: list[dict]) -> str:
    """Bulk update application environment variables."""
    result_data = await client.update_application_envs_bulk(uuid, data)
    result = {
        "success": True,
        "message": f"Bulk update {len(data)} env vars",
        "data": result_data,
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


async def delete_application_env(client: CoolifyClient, uuid: str, env_uuid: str) -> str:
    """Delete application environment variable."""
    await client.delete_application_env(uuid, env_uuid)
    result = {"success": True, "message": f"Env var '{env_uuid}' deleted"}
    return json.dumps(result, indent=2, ensure_ascii=False)
