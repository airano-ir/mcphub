from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from plugins.wordpress.handlers.menus import MenusHandler, get_tool_specifications


def test_delete_navigation_tool_spec_present():
    specs = get_tool_specifications()
    by_name = {spec["name"]: spec for spec in specs}

    assert "delete_navigation" in by_name
    spec = by_name["delete_navigation"]
    assert spec["method_name"] == "delete_navigation"
    assert "navigation_id" in spec["schema"]["required"]


@pytest.mark.asyncio
async def test_delete_navigation_uses_navigation_endpoint():
    client = AsyncMock()
    client.delete = AsyncMock(return_value={"deleted": True, "previous": {"id": 17}})
    handler = MenusHandler(client)

    raw = await handler.delete_navigation(navigation_id=17, force=True)
    data = json.loads(raw)

    assert data["success"] is True
    assert data["id"] == 17
    assert data["force"] is True
    client.delete.assert_called_once_with("navigation/17", params={"force": "true"})
