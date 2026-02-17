"""Tests for Tool Registry (core/tool_registry.py)."""

import pytest

from core.tool_registry import ToolDefinition, ToolRegistry


async def _dummy_handler(**kwargs):
    """Dummy async handler for testing."""
    return {"ok": True}


async def _another_handler(**kwargs):
    return {"ok": True}


@pytest.fixture
def registry():
    return ToolRegistry()


@pytest.fixture
def sample_tool():
    return ToolDefinition(
        name="wordpress_list_posts",
        description="List WordPress posts",
        handler=_dummy_handler,
        plugin_type="wordpress",
        required_scope="read",
    )


class TestToolDefinition:
    """Test ToolDefinition model."""

    def test_basic_creation(self):
        tool = ToolDefinition(
            name="wordpress_get_post",
            description="Get a post",
            handler=_dummy_handler,
            plugin_type="wordpress",
        )
        assert tool.name == "wordpress_get_post"
        assert tool.required_scope == "read"  # default

    def test_custom_scope(self):
        tool = ToolDefinition(
            name="wordpress_create_post",
            description="Create a post",
            handler=_dummy_handler,
            plugin_type="wordpress",
            required_scope="write",
        )
        assert tool.required_scope == "write"

    def test_default_input_schema(self):
        tool = ToolDefinition(
            name="test_tool",
            description="Test",
            handler=_dummy_handler,
            plugin_type="test",
        )
        assert tool.input_schema == {"type": "object", "properties": {}}

    def test_custom_input_schema(self):
        schema = {
            "type": "object",
            "properties": {"site": {"type": "string"}},
            "required": ["site"],
        }
        tool = ToolDefinition(
            name="test_tool",
            description="Test",
            handler=_dummy_handler,
            plugin_type="test",
            input_schema=schema,
        )
        assert tool.input_schema["required"] == ["site"]


class TestToolRegistration:
    """Test tool registration."""

    def test_register_single(self, registry, sample_tool):
        registry.register(sample_tool)
        assert registry.get_count() == 1

    def test_duplicate_name_raises(self, registry, sample_tool):
        registry.register(sample_tool)
        with pytest.raises(ValueError, match="already registered"):
            registry.register(sample_tool)

    def test_register_many(self, registry):
        tools = [
            ToolDefinition(
                name=f"tool_{i}",
                description=f"Tool {i}",
                handler=_dummy_handler,
                plugin_type="test",
            )
            for i in range(5)
        ]
        count = registry.register_many(tools)
        assert count == 5
        assert registry.get_count() == 5

    def test_register_many_skips_duplicates(self, registry, sample_tool):
        registry.register(sample_tool)
        tools = [
            sample_tool,  # duplicate
            ToolDefinition(
                name="wordpress_create_post",
                description="Create post",
                handler=_dummy_handler,
                plugin_type="wordpress",
            ),
        ]
        count = registry.register_many(tools)
        assert count == 1  # only the non-duplicate
        assert registry.get_count() == 2


class TestToolRetrieval:
    """Test tool retrieval and filtering."""

    @pytest.fixture
    def populated_registry(self, registry):
        tools = [
            ToolDefinition(
                name="wordpress_list_posts",
                description="List posts",
                handler=_dummy_handler,
                plugin_type="wordpress",
            ),
            ToolDefinition(
                name="wordpress_create_post",
                description="Create post",
                handler=_dummy_handler,
                plugin_type="wordpress",
                required_scope="write",
            ),
            ToolDefinition(
                name="gitea_list_repos",
                description="List repos",
                handler=_another_handler,
                plugin_type="gitea",
            ),
        ]
        registry.register_many(tools)
        return registry

    def test_get_by_name(self, populated_registry):
        tool = populated_registry.get_by_name("wordpress_list_posts")
        assert tool is not None
        assert tool.description == "List posts"

    def test_get_by_name_not_found(self, populated_registry):
        assert populated_registry.get_by_name("nonexistent") is None

    def test_get_by_plugin_type(self, populated_registry):
        wp_tools = populated_registry.get_by_plugin_type("wordpress")
        assert len(wp_tools) == 2

    def test_get_by_plugin_type_empty(self, populated_registry):
        assert populated_registry.get_by_plugin_type("n8n") == []

    def test_get_all(self, populated_registry):
        all_tools = populated_registry.get_all()
        assert len(all_tools) == 3

    def test_get_count_by_plugin(self, populated_registry):
        counts = populated_registry.get_count_by_plugin()
        assert counts["wordpress"] == 2
        assert counts["gitea"] == 1

    def test_clear(self, populated_registry):
        populated_registry.clear()
        assert populated_registry.get_count() == 0

    def test_repr(self, populated_registry):
        r = repr(populated_registry)
        assert "ToolRegistry" in r
        assert "total=3" in r
