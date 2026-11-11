"""MCP tool annotations derived from authoritative ToolDefinition fields.

Every endpoint that lists tools — the per-user ``/u/{user_id}/{alias}/mcp``
endpoint and every FastMCP endpoint (``/mcp``, ``/{plugin}/mcp``,
``/project/{id}/mcp``) — emits the same hints from this one module, so AI
clients see consistent safety metadata whichever URL they use.

Rules (hints are never guessed from tool names at runtime):

* ``title`` — plugin display name + humanized action (``"WordPress: List posts"``).
* ``readOnlyHint`` — ``True`` iff the tool's required scope is ``read``. Scope
  is the real access gate, so the hint is exact (audited: no read-scoped tool
  mutates).
* ``destructiveHint`` — for non-read tools only. ``False`` only when the spec
  says ``destructive: False`` or the tool is in the reviewed
  :data:`ADDITIVE_TOOLS` allowlist (pure creates/uploads that never modify or
  remove existing data). Every other write tool is reported as destructive —
  the MCP default — so a missing entry errs on the cautious side.
* ``idempotentHint`` — the explicit ``idempotent`` field, for non-read tools.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from core.tool_registry import ToolDefinition

# Plugin-type -> human display name, for titles.
PLUGIN_TITLE_PREFIX: dict[str, str] = {
    "wordpress_specialist": "WordPress",
    "wordpress": "WordPress",
    "woocommerce": "WooCommerce",
    "google_search_console": "Search Console",
    "openpanel": "OpenPanel",
    "cloudflare": "Cloudflare",
    "coolify": "Coolify",
    "supabase": "Supabase",
    "gitea": "Gitea",
    "gmail": "Gmail",
    "n8n": "n8n",
}

# Reviewed allowlist of write tools that only ADD new records and never
# modify, overwrite or remove existing ones. Keep this explicit: a tool that
# can update existing content (upserts, "create or update", publish of an
# existing draft, settings writes) must NOT be listed here.
ADDITIVE_TOOLS: frozenset[str] = frozenset(
    {
        # WordPress core content (new records only; media uploads are NOT
        # listed: attach_to_post / set_featured modify an existing post).
        "wordpress_create_post",
        "wordpress_create_page",
        "wordpress_create_custom_post",
        "wordpress_create_category",
        "wordpress_create_tag",
        "wordpress_create_taxonomy_term",
        "wordpress_create_comment",
        "wordpress_upload_media_chunked_start",
        "wordpress_upload_media_chunked_chunk",
        # WooCommerce (create_order is NOT listed: it reduces stock levels).
        "woocommerce_create_product",
        "woocommerce_create_product_category",
        "woocommerce_create_product_attribute",
        "woocommerce_create_product_variation",
        "woocommerce_create_coupon",
        "woocommerce_create_customer",
        # Gitea (create_files / webhooks / PR reviews are NOT listed).
        "gitea_create_repository",
        "gitea_create_issue",
        "gitea_create_issue_comment",
        "gitea_create_pr_comment",
        "gitea_create_pull_request",
        "gitea_create_branch",
        "gitea_create_tag",
        "gitea_create_label",
        "gitea_create_milestone",
        "gitea_create_release",
        # n8n (user / project-membership tools grant access: NOT listed).
        "n8n_create_workflow",
        "n8n_create_credential",
        "n8n_create_tag",
        "n8n_create_variable",
        # Cloudflare (DNS records are NOT listed: they change resolution).
        "cloudflare_create_kv_namespace",
        "cloudflare_create_r2_bucket",
    }
)


def humanize_title(tool_def: ToolDefinition) -> str:
    """Return ``"<Plugin>: <Action>"`` for display."""
    name = tool_def.name
    prefix = f"{tool_def.plugin_type}_"
    action = name[len(prefix) :] if name.startswith(prefix) else name
    display = PLUGIN_TITLE_PREFIX.get(tool_def.plugin_type, tool_def.plugin_type)
    action_label = action.replace("_", " ").strip().capitalize()
    return f"{display}: {action_label}" if action_label else display


def is_destructive(tool_def: ToolDefinition) -> bool:
    """Whether a (non-read) tool may modify or remove existing data."""
    explicit = getattr(tool_def, "destructive", None)
    if explicit is not None:
        return bool(explicit)
    return tool_def.name not in ADDITIVE_TOOLS


def tool_annotations(tool_def: ToolDefinition) -> dict[str, Any]:
    """Build the MCP ``ToolAnnotations`` dict for a tool definition."""
    read_only = tool_def.required_scope == "read"
    annotations: dict[str, Any] = {
        "title": humanize_title(tool_def),
        "readOnlyHint": read_only,
    }
    if not read_only:
        annotations["destructiveHint"] = is_destructive(tool_def)
        annotations["idempotentHint"] = bool(tool_def.idempotent)
    return annotations
