"""Coolify site-level access policy helpers.

These policies are intentionally optional and backward compatible: existing
Coolify sites that only store ``url`` + ``token`` in their encrypted credentials
keep the current full-instance behaviour. Operators can narrow a Coolify site
by adding policy keys to the encrypted credential payload:

* ``read_only`` / ``coolify_read_only``: truthy values hide and block mutating
  tools regardless of the broader site ``tool_scope`` preset.
* ``project_uuid`` / ``coolify_project_uuid`` / ``allowed_project_uuids`` /
  ``coolify_allowed_project_uuids``: one UUID, comma-separated UUIDs, or a list
  of UUIDs. Tools with a ``project_uuid`` argument are allowed only for those
  projects. Project-bearing read tools remain visible, but their results are
  filtered to same-project resources after execution by resolving project
  environments and comparing resource ``environment_id`` values.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, MutableMapping
from typing import Any, Protocol

from core.tool_registry import ToolDefinition

_READ_ONLY_TRUE_VALUES = {"1", "true", "yes", "y", "on", "read_only", "readonly"}
_PROJECT_POLICY_KEYS = (
    "allowed_project_uuids",
    "coolify_allowed_project_uuids",
    "project_uuid",
    "coolify_project_uuid",
)

# Project-scoped tools that can be safely authorized from their arguments.
# Other tools may return or mutate resources across the whole Coolify instance,
# or accept only opaque resource UUIDs that require extra API lookups to prove
# project membership. Keep those hidden/blocked when a project allowlist is set.
_PROJECT_ARGUMENT_TOOLS = {
    "coolify_get_project",
    "coolify_list_environments",
    "coolify_get_environment",
    "coolify_create_environment",
    "coolify_create_application_public",
    "coolify_create_application_private_github_app",
    "coolify_create_application_dockerfile",
    "coolify_create_application_docker_image",
    "coolify_create_application_docker_compose",
    "coolify_create_service",
    "coolify_create_postgresql",
    "coolify_create_mysql",
    "coolify_create_mariadb",
    "coolify_create_mongodb",
    "coolify_create_redis",
    "coolify_create_clickhouse",
}

# Read tools whose JSON results carry environment_id and can therefore be safely
# filtered after resolving the allowed projects' environment IDs. This makes
# same-project resources visible without leaking other projects.
_PROJECT_RESULT_FILTERED_TOOLS = {
    "coolify_list_applications",
    "coolify_get_application",
    "coolify_list_services",
    "coolify_get_service",
    "coolify_list_databases",
    "coolify_get_database",
}

_PROJECT_VISIBLE_TOOLS = _PROJECT_ARGUMENT_TOOLS | _PROJECT_RESULT_FILTERED_TOOLS

_LIST_RESULT_KEYS = {
    "coolify_list_applications": "applications",
    "coolify_list_services": "services",
    "coolify_list_databases": "databases",
}

_DETAIL_RESULT_KEYS = {
    "coolify_get_application": "application",
    "coolify_get_service": "service",
    "coolify_get_database": "database",
}

_ENVIRONMENT_ID_CACHE_KEY = "environment_ids_by_project_uuid"


class CoolifyEnvironmentClient(Protocol):
    async def list_environments(self, project_uuid: str) -> list[dict[str, Any]]:
        """Return Coolify environments for a project UUID."""


def is_coolify_read_only(credentials: dict[str, Any]) -> bool:
    """Return whether the Coolify site credential payload requests read-only mode."""
    for key in ("read_only", "coolify_read_only"):
        value = credentials.get(key)
        if isinstance(value, bool):
            if value:
                return True
            continue
        if isinstance(value, (int, float)) and value == 1:
            return True
        if isinstance(value, str) and value.strip().lower() in _READ_ONLY_TRUE_VALUES:
            return True
    return False


def allowed_project_uuids(credentials: dict[str, Any]) -> set[str]:
    """Return the configured Coolify project UUID allowlist, if any."""
    allowed: set[str] = set()
    for key in _PROJECT_POLICY_KEYS:
        allowed.update(_coerce_uuid_values(credentials.get(key)))
    return allowed


def _coerce_uuid_values(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        parts = value.replace("\n", ",").split(",")
        return {p.strip() for p in parts if p.strip()}
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray, dict)):
        return {str(v).strip() for v in value if str(v).strip()}
    return {str(value).strip()} if str(value).strip() else set()


def filter_coolify_tools_by_policy(
    tools: list[ToolDefinition],
    credentials: dict[str, Any],
) -> list[ToolDefinition]:
    """Drop Coolify tools disallowed by optional encrypted site policy for tools/list.

    Catalog filtering has no call arguments yet, so project-scoped tools that
    accept a ``project_uuid``/project ``uuid`` remain visible. Project-bearing
    list/get tools also remain visible; their returned resources are filtered
    after execution by ``filter_coolify_result_by_policy``.
    """
    project_limited = bool(allowed_project_uuids(credentials))
    read_only = is_coolify_read_only(credentials)
    visible: list[ToolDefinition] = []
    for tool in tools:
        if tool.plugin_type != "coolify":
            visible.append(tool)
            continue
        if read_only and tool.required_scope != "read":
            continue
        if project_limited and tool.name not in _PROJECT_VISIBLE_TOOLS:
            continue
        visible.append(tool)
    return visible


def is_coolify_tool_allowed(
    tool: ToolDefinition,
    arguments: dict[str, Any],
    credentials: dict[str, Any],
) -> tuple[bool, str | None]:
    """Check whether a Coolify tool call is allowed for this site's policy."""
    if tool.plugin_type != "coolify":
        return True, None

    if is_coolify_read_only(credentials) and tool.required_scope != "read":
        return (
            False,
            "Coolify site is configured read-only; mutating tools are disabled.",
        )

    allowed_projects = allowed_project_uuids(credentials)
    if not allowed_projects:
        return True, None

    if tool.name in _PROJECT_RESULT_FILTERED_TOOLS:
        return True, None

    if tool.name not in _PROJECT_ARGUMENT_TOOLS:
        return (
            False,
            "Coolify site is restricted to specific project UUIDs; this tool cannot "
            "prove project membership from its arguments.",
        )

    project_uuid = arguments.get("project_uuid") or arguments.get("uuid")
    if not project_uuid:
        return False, "Coolify project-restricted site requires a project_uuid argument."
    if str(project_uuid) not in allowed_projects:
        return (
            False,
            f"Project UUID '{project_uuid}' is not allowed for this Coolify site.",
        )
    return True, None


async def filter_coolify_result_by_policy(
    tool_name: str,
    result: Any,
    credentials: dict[str, Any],
    client: CoolifyEnvironmentClient,
    cache: MutableMapping[str, Any] | None = None,
) -> Any:
    """Filter Coolify read results to same-project resources when scoped.

    Real Coolify application/service/database payloads expose numeric
    ``environment_id`` rather than ``project_uuid``. Resolve each allowed
    project's environments with ``list_environments(project_uuid)``, cache those
    numeric IDs for the current request, and compare resource ``environment_id``
    values against that set.
    """
    allowed_projects = allowed_project_uuids(credentials)
    if not allowed_projects or tool_name not in _PROJECT_RESULT_FILTERED_TOOLS:
        return result

    parsed, was_json_string = _parse_json_result(result)
    if parsed is None:
        return result

    allowed_environment_ids = await allowed_environment_ids_for_projects(
        client, allowed_projects, cache
    )

    if tool_name in _LIST_RESULT_KEYS:
        filtered = _filter_list_result(
            parsed, _LIST_RESULT_KEYS[tool_name], allowed_environment_ids
        )
    else:
        filtered = _filter_detail_result(
            parsed, _DETAIL_RESULT_KEYS[tool_name], allowed_environment_ids
        )

    if was_json_string:
        return json.dumps(filtered, indent=2, ensure_ascii=False)
    return filtered


async def allowed_environment_ids_for_projects(
    client: CoolifyEnvironmentClient,
    project_uuids: set[str],
    cache: MutableMapping[str, Any] | None = None,
) -> set[int]:
    """Resolve and cache numeric Coolify environment IDs for allowed projects."""
    env_cache = _environment_cache(cache)
    allowed_ids: set[int] = set()
    for project_uuid in sorted(project_uuids):
        if project_uuid not in env_cache:
            environments = await client.list_environments(project_uuid)
            env_cache[project_uuid] = {
                env_id
                for env in environments
                if (env_id := _coerce_environment_id(env.get("id"))) is not None
            }
        allowed_ids.update(env_cache[project_uuid])
    return allowed_ids


def _environment_cache(cache: MutableMapping[str, Any] | None) -> dict[str, set[int]]:
    if cache is None:
        return {}
    existing = cache.setdefault(_ENVIRONMENT_ID_CACHE_KEY, {})
    if isinstance(existing, dict):
        return existing
    cache[_ENVIRONMENT_ID_CACHE_KEY] = {}
    return cache[_ENVIRONMENT_ID_CACHE_KEY]


def _parse_json_result(result: Any) -> tuple[dict[str, Any] | None, bool]:
    if isinstance(result, dict):
        return result, False
    if not isinstance(result, str):
        return None, False
    try:
        parsed = json.loads(result)
    except json.JSONDecodeError:
        return None, False
    if not isinstance(parsed, dict):
        return None, False
    return parsed, True


def _filter_list_result(
    payload: dict[str, Any],
    collection_key: str,
    allowed_environment_ids: set[int],
) -> dict[str, Any]:
    items = payload.get(collection_key)
    if not isinstance(items, list):
        return payload
    filtered_items = [
        item
        for item in items
        if isinstance(item, dict) and _item_environment_id(item) in allowed_environment_ids
    ]
    filtered = dict(payload)
    filtered[collection_key] = filtered_items
    filtered["count"] = len(filtered_items)
    # The original total may include resources from other projects; do not leak it.
    filtered["total"] = len(filtered_items)
    filtered["truncated"] = False
    if len(filtered_items) != len(items):
        filtered["policy_filtered"] = True
    return filtered


def _filter_detail_result(
    payload: dict[str, Any],
    detail_key: str,
    allowed_environment_ids: set[int],
) -> dict[str, Any]:
    item = payload.get(detail_key)
    if not isinstance(item, dict):
        return payload
    if _item_environment_id(item) in allowed_environment_ids:
        return payload
    return {
        "success": False,
        "error": "Resource is outside the configured Coolify project allowlist.",
        "policy_filtered": True,
    }


def _item_environment_id(item: dict[str, Any]) -> int | None:
    return _coerce_environment_id(item.get("environment_id"))


def _coerce_environment_id(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
