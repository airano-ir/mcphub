"""Policy metadata and explicit-site gating for the unified tool generator."""

from core.tool_generator import ToolGenerator


async def _noop(**_kwargs):
    return None


class _SiteManager:
    def __init__(self, sites):
        self.sites = sites
        self.calls = []

    def list_sites(self, plugin_type):
        self.calls.append(plugin_type)
        return list(self.sites.get(plugin_type, []))


class _Plugin:
    @staticmethod
    def get_tool_specifications():
        return []

    async def update_order(self, **_kwargs):
        return {"ok": True}


def test_generator_preserves_explicit_execution_metadata():
    manager = _SiteManager({"woocommerce": []})
    generator = ToolGenerator(manager)
    spec = {
        "name": "update_order",
        "method_name": "update_order",
        "description": "Update an order",
        "schema": {"type": "object", "properties": {}},
        "scope": "write",
        "category": "commerce.write",
        "sensitivity": "sensitive",
        "risk": "high",
        "requires_confirmation": True,
        "supports_dry_run": True,
        "idempotent": True,
        "retry_policy": {"max_attempts": 2, "backoff_seconds": 1.0},
    }

    tool = generator._create_tool_from_spec(_Plugin, "woocommerce", spec)

    assert tool.required_scope == "write"
    assert tool.category == "commerce.write"
    assert tool.sensitivity == "sensitive"
    assert tool.risk == "high"
    assert tool.requires_confirmation is True
    assert tool.supports_dry_run is True
    assert tool.idempotent is True
    assert tool.retry_policy == {"max_attempts": 2, "backoff_seconds": 1.0}


def test_woocommerce_generation_never_uses_wordpress_sites_implicitly():
    manager = _SiteManager({"wordpress": ["wp-main"], "woocommerce": []})
    generator = ToolGenerator(manager)

    schema = generator._add_site_parameter(
        {"type": "object", "properties": {}, "required": []}, "woocommerce"
    )

    assert manager.calls == ["woocommerce"]
    assert schema["properties"]["site"].get("enum") is None
