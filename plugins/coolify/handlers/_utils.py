"""Shared helpers for Coolify handler modules."""

import base64
import binascii
import re
import unicodedata
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlparse

try:
    import yaml  # type: ignore[import-untyped]
except Exception:  # pragma: no cover - optional dependency path
    yaml = None


DESCRIPTION_MAX_LENGTH = 255
DESCRIPTION_ALLOWED_CHARS = set("-_.,!?()'\"+=*@/&")
BASE64_CONFIG_FIELDS = {
    "clickhouse_conf",
    "keydb_conf",
    "mariadb_conf",
    "mongo_conf",
    "mongodb_conf",
    "mysql_conf",
    "postgres_conf",
    "redis_conf",
}


def validate_coolify_description(description: str | None) -> None:
    """Mirror Coolify UI description validation so API writes do not lock later UI edits."""
    if description is None:
        return
    if len(description) > DESCRIPTION_MAX_LENGTH:
        raise ValueError("Coolify description must be 255 characters or fewer")

    invalid = sorted({ch for ch in description if not _is_description_char_allowed(ch)})
    if invalid:
        printable = ", ".join(repr(ch) for ch in invalid[:5])
        raise ValueError(
            "Coolify description contains characters rejected by the Coolify UI: "
            f"{printable}. Allowed: letters, numbers, spaces, -_.,!?()'\"+=*@/&"
        )


def _is_description_char_allowed(ch: str) -> bool:
    if ch in DESCRIPTION_ALLOWED_CHARS or ch.isspace():
        return True
    category = unicodedata.category(ch)
    return category[0] in {"L", "M", "N"}


def normalize_github_repository_slug(value: str | None) -> tuple[str | None, str | None]:
    """Return owner/repo for GitHub URLs; leave other repository strings unchanged."""
    if not value:
        return value, None

    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc.lower() == "github.com":
        slug = parsed.path.strip("/")
        if slug.endswith(".git"):
            slug = slug[:-4]
        if slug and slug.count("/") == 1:
            return slug, f"Normalized git_repository from GitHub URL to '{slug}'."

    return value, None


def encode_text_base64(value: str) -> str:
    """Encode a UTF-8 text value for Coolify fields that use base64 on the wire."""
    if value == "":
        return ""
    return base64.b64encode(value.encode("utf-8")).decode("ascii")


def decode_text_base64(value: str) -> str | None:
    """Decode a base64 UTF-8 text value; return None if the value is not valid base64."""
    if value == "":
        return ""
    try:
        return base64.b64decode(value.encode("ascii"), validate=True).decode("utf-8")
    except (UnicodeDecodeError, ValueError, binascii.Error):
        return None


def encode_payload_fields(data: dict[str, Any], field_names: Iterable[str]) -> dict[str, Any]:
    """Base64-encode selected string fields in a copy of the payload."""
    encoded = dict(data)
    for field in field_names:
        value = encoded.get(field)
        if isinstance(value, str):
            encoded[field] = encode_text_base64(value)
    return encoded


def decode_payload_fields(payload: dict[str, Any], field_names: Iterable[str]) -> dict[str, Any]:
    """Decode selected base64 fields while preserving raw values under *_base64."""
    decoded = dict(payload)
    for field in field_names:
        value = decoded.get(field)
        if not isinstance(value, str):
            continue
        plain = decode_text_base64(value)
        if plain is None:
            continue
        decoded[f"{field}_base64"] = value
        decoded[field] = plain
    return decoded


def summarize_items(
    items: list[dict[str, Any]],
    *,
    compact_fields: list[str],
    fields: list[str] | None = None,
    limit: int | None = None,
    name: str | None = None,
    include_details: bool = False,
) -> tuple[list[dict[str, Any]], int, bool]:
    """Filter and trim list endpoint results to keep MCP responses token-friendly."""
    filtered = [_item for _item in items if _matches_name_filter(_item, name)]
    total = len(filtered)
    if limit is not None:
        filtered = filtered[:limit]

    if include_details:
        summarized = filtered
    else:
        selected_fields = fields or compact_fields
        summarized = [
            {key: item[key] for key in selected_fields if key in item} for item in filtered
        ]

    return summarized, total, len(filtered) < total


def _matches_name_filter(item: dict[str, Any], name: str | None) -> bool:
    if not name:
        return True
    needle = name.lower()
    haystacks = [
        str(item.get("name") or ""),
        str(item.get("uuid") or ""),
        str(item.get("fqdn") or ""),
        str(item.get("domains") or ""),
    ]
    return any(needle in haystack.lower() for haystack in haystacks)


def extract_compose_environment_keys(compose_raw: str | None) -> set[str]:
    """Extract env var names declared under Docker Compose service environment blocks."""
    if not compose_raw:
        return set()

    keys = _extract_compose_environment_keys_yaml(compose_raw)
    if keys:
        return keys
    return _extract_compose_environment_keys_text(compose_raw)


def _extract_compose_environment_keys_yaml(compose_raw: str) -> set[str]:
    if yaml is None:
        return set()
    try:
        parsed = yaml.safe_load(compose_raw)
    except Exception:
        return set()
    if not isinstance(parsed, dict):
        return set()

    services = parsed.get("services", {})
    if not isinstance(services, dict):
        return set()

    keys: set[str] = set()
    for service in services.values():
        if not isinstance(service, dict):
            continue
        env = service.get("environment")
        if isinstance(env, dict):
            keys.update(str(key) for key in env)
        elif isinstance(env, list):
            keys.update(_env_key_from_list_item(item) for item in env)
    return {key for key in keys if key}


def _env_key_from_list_item(item: Any) -> str:
    if not isinstance(item, str):
        return ""
    return item.split("=", 1)[0].strip()


def _extract_compose_environment_keys_text(compose_raw: str) -> set[str]:
    keys: set[str] = set()
    in_environment = False
    environment_indent: int | None = None

    for raw_line in compose_raw.splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue

        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        if stripped == "environment:":
            in_environment = True
            environment_indent = indent
            continue

        if in_environment and environment_indent is not None and indent <= environment_indent:
            in_environment = False
            environment_indent = None

        if not in_environment:
            continue

        list_match = re.match(r"^-\s*([A-Za-z_][A-Za-z0-9_]*)\b", stripped)
        map_match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*:", stripped)
        if list_match:
            keys.add(list_match.group(1))
        elif map_match:
            keys.add(map_match.group(1))

    return keys


def compose_raw_from_service(service: dict[str, Any]) -> str | None:
    """Find the raw compose text in the known Coolify service response shapes."""
    for key in ("docker_compose_raw", "docker_compose", "compose"):
        value = service.get(key)
        if isinstance(value, str):
            return value
    return None
