"""Issue #120 — generic taxonomy-term multilingual adapter calls."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest

from plugins.wordpress.handlers.taxonomy import TaxonomyHandler, get_tool_specifications


def _term_payload(term_id: int = 42) -> dict:
    return {
        "id": term_id,
        "name": "Reports",
        "slug": "reports",
        "description": "",
        "parent": 0,
    }


@pytest.fixture
def client():
    return SimpleNamespace(post=AsyncMock(), get=AsyncMock(), delete=AsyncMock())


@pytest.fixture
def handler(client):
    return TaxonomyHandler(client)


def test_taxonomy_specs_include_generic_language_fields():
    specs = {spec["name"]: spec for spec in get_tool_specifications()}

    for name in ("create_category", "create_tag", "create_taxonomy_term"):
        props = specs[name]["schema"]["properties"]
        assert "language" in props
        assert "translation_of" in props

    assert specs["set_term_language"]["schema"]["required"] == ["taxonomy", "term_id"]


@pytest.mark.asyncio
async def test_create_category_applies_language_without_sending_it_to_stock_rest(handler, client):
    client.post.side_effect = [
        {"already_existed": False, "provider": "wpml", "lookup_only": True},
        _term_payload(12),
        {"term_id": 12, "provider": "wpml", "applied": True, "linked": True},
    ]

    raw = await handler.create_category(name="Reports", language="fa", translation_of=7)
    out = json.loads(raw)

    assert out["language"]["provider"] == "wpml"
    assert client.post.await_args_list == [
        call(
            "airano-mcp/v1/term-language",
            json_data={
                "taxonomy": "categories",
                "language": "fa",
                "translation_of": 7,
                "lookup_only": True,
            },
            use_custom_namespace=True,
        ),
        call("categories", json_data={"name": "Reports"}),
        call(
            "airano-mcp/v1/term-language",
            json_data={
                "taxonomy": "categories",
                "term_id": 12,
                "language": "fa",
                "translation_of": 7,
            },
            use_custom_namespace=True,
        ),
    ]


@pytest.mark.asyncio
async def test_create_tag_without_language_uses_stock_rest_only(handler, client):
    client.post.return_value = _term_payload(13)

    raw = await handler.create_tag(name="News", language=None, translation_of=None)
    out = json.loads(raw)

    assert out["id"] == 13
    assert "language" not in out
    client.post.assert_awaited_once_with("tags", json_data={"name": "News"})


@pytest.mark.asyncio
async def test_create_category_returns_existing_translation_without_creating_duplicate(
    handler, client
):
    client.post.return_value = {
        "term_id": 79,
        "taxonomy": "categories",
        "provider": "wpml",
        "language": "fa",
        "translation_of": 30,
        "already_existed": True,
        "lookup_only": True,
        "term": {"id": 79, "name": "گزارش‌ها", "slug": "reports-fa"},
    }

    raw = await handler.create_category(name="گزارش‌ها", language="fa", translation_of=30)
    out = json.loads(raw)

    assert out["id"] == 79
    assert out["created"] is False
    assert out["already_existed"] is True
    assert out["language"]["term_id"] == 79
    client.post.assert_awaited_once_with(
        "airano-mcp/v1/term-language",
        json_data={
            "taxonomy": "categories",
            "language": "fa",
            "translation_of": 30,
            "lookup_only": True,
        },
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_create_tag_returns_existing_translation_without_creating_duplicate(handler, client):
    client.post.return_value = {
        "term_id": 88,
        "taxonomy": "tags",
        "provider": "polylang",
        "language": "fa",
        "translation_of": 31,
        "already_existed": True,
        "lookup_only": True,
        "term": {"id": 88, "name": "اخبار", "slug": "news-fa"},
    }

    raw = await handler.create_tag(name="اخبار", language="fa", translation_of=31)
    out = json.loads(raw)

    assert out["id"] == 88
    assert out["created"] is False
    assert out["already_existed"] is True
    client.post.assert_awaited_once_with(
        "airano-mcp/v1/term-language",
        json_data={
            "taxonomy": "tags",
            "language": "fa",
            "translation_of": 31,
            "lookup_only": True,
        },
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_create_taxonomy_term_applies_language(handler, client):
    client.post.side_effect = [
        _term_payload(14),
        {"term_id": 14, "provider": "polylang", "applied": True},
    ]

    raw = await handler.create_taxonomy_term(
        taxonomy="product_cat",
        name="Audio",
        language="en",
    )
    out = json.loads(raw)

    assert out["language"]["provider"] == "polylang"
    assert client.post.await_args_list == [
        call("product_cat", json_data={"name": "Audio"}),
        call(
            "airano-mcp/v1/term-language",
            json_data={"taxonomy": "product_cat", "term_id": 14, "language": "en"},
            use_custom_namespace=True,
        ),
    ]


@pytest.mark.asyncio
async def test_set_term_language_calls_companion_route(handler, client):
    client.post.return_value = {"term_id": 14, "provider": "wpml", "applied": True}

    raw = await handler.set_term_language(
        taxonomy="categories",
        term_id=14,
        language="fa",
        translation_of=3,
    )
    out = json.loads(raw)

    assert out["applied"] is True
    client.post.assert_awaited_once_with(
        "airano-mcp/v1/term-language",
        json_data={
            "taxonomy": "categories",
            "term_id": 14,
            "language": "fa",
            "translation_of": 3,
        },
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_update_category_falls_back_for_translated_slug_conflict(handler, client):
    client.post.side_effect = [
        RuntimeError('[SERVER_ERROR] The slug "reports-fa" is already in use by another term.'),
        _term_payload(12),
    ]

    raw = await handler.update_category(category_id=12, name="Reports FA")
    out = json.loads(raw)

    assert out["id"] == 12
    assert client.post.await_args_list == [
        call("categories/12", json_data={"name": "Reports FA"}),
        call(
            "airano-mcp/v1/term-update",
            json_data={"taxonomy": "categories", "term_id": 12, "name": "Reports FA"},
            use_custom_namespace=True,
        ),
    ]


@pytest.mark.asyncio
async def test_update_tag_normal_path_does_not_call_fallback(handler, client):
    client.post.return_value = _term_payload(15)

    await handler.update_tag(tag_id=15, description="Fresh")

    client.post.assert_awaited_once_with("tags/15", json_data={"description": "Fresh"})
