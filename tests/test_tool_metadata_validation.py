"""Tests for policy metadata carried by generated tool definitions."""

import pytest

from core.tool_registry import ToolDefinition, ToolRegistry


async def _noop(**_kwargs):
    return None


def test_tool_definition_exposes_execution_safety_metadata():
    tool = ToolDefinition(
        name="woocommerce_update_order",
        description="update",
        handler=_noop,
        plugin_type="woocommerce",
        required_scope="write",
        category="commerce.write",
        sensitivity="normal",
        risk="high",
        requires_confirmation=True,
        supports_dry_run=True,
        idempotent=True,
        retry_policy={"max_attempts": 2, "backoff_seconds": 1.0},
    )

    assert tool.risk == "high"
    assert tool.requires_confirmation is True
    assert tool.supports_dry_run is True
    assert tool.idempotent is True
    assert tool.retry_policy["max_attempts"] == 2


def test_target_registry_validation_rejects_incomplete_high_risk_metadata():
    registry = ToolRegistry()
    tool = ToolDefinition(
        name="woocommerce_delete_order",
        description="delete",
        handler=_noop,
        plugin_type="woocommerce",
        required_scope="admin",
        category="commerce.write",
        sensitivity="normal",
    )
    registry.register(tool)

    with pytest.raises(ValueError, match="metadata"):
        registry.validate_target_metadata({"woocommerce"})


def test_legacy_validation_can_be_explicitly_skipped():
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="legacy_tool",
            description="legacy",
            handler=_noop,
            plugin_type="other",
        )
    )

    assert registry.validate_target_metadata({"woocommerce"}) == []
