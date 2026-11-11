"""Issue #119 — generic post meta passthrough + multilingual adapter calls."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

import pytest

from plugins.wordpress.handlers.posts import PostsHandler


def _post_payload(post_id: int = 42) -> dict:
    return {
        "id": post_id,
        "title": {"rendered": "Hello"},
        "status": "draft",
        "link": f"https://wp.example.com/?p={post_id}",
    }


@pytest.fixture
def client():
    return SimpleNamespace(post=AsyncMock(), get=AsyncMock())


@pytest.fixture
def handler(client):
    return PostsHandler(client)


@pytest.mark.asyncio
async def test_create_post_passes_meta_and_applies_language(handler, client):
    client.post.side_effect = [
        _post_payload(42),
        {"post_id": 42, "provider": "wpml", "applied": True, "linked": True},
    ]

    raw = await handler.create_post(
        title="Hello",
        content="<p>Body</p>",
        meta={"rank_math_title": "SEO title"},
        language="fa",
        translation_of=7,
    )
    out = json.loads(raw)

    assert out["language"]["provider"] == "wpml"
    assert client.post.await_args_list == [
        call(
            "posts",
            json_data={
                "title": "Hello",
                "content": "<p>Body</p>",
                "status": "draft",
                "meta": {"rank_math_title": "SEO title"},
            },
        ),
        call(
            "airano-mcp/v1/post-language",
            json_data={"post_id": 42, "language": "fa", "translation_of": 7},
            use_custom_namespace=True,
        ),
    ]


@pytest.mark.asyncio
async def test_create_page_passes_meta_without_language_call(handler, client):
    client.post.return_value = _post_payload(87)

    await handler.create_page(
        title="About",
        content="<p>About</p>",
        meta={"_yoast_wpseo_metadesc": "About us"},
    )

    client.post.assert_awaited_once_with(
        "pages",
        json_data={
            "title": "About",
            "content": "<p>About</p>",
            "status": "draft",
            "meta": {"_yoast_wpseo_metadesc": "About us"},
        },
    )


@pytest.mark.asyncio
async def test_update_post_sends_meta_to_stock_rest_and_language_to_companion(handler, client):
    client.post.side_effect = [
        _post_payload(42),
        {"post_id": 42, "provider": "polylang", "applied": True, "linked": True},
    ]

    raw = await handler.update_post(
        post_id=42,
        meta={"podcast_episode_id": "ep-1"},
        language="fa",
        translation_of=5,
    )
    out = json.loads(raw)

    assert out["language"]["provider"] == "polylang"
    assert client.post.await_args_list == [
        call("posts/42", json_data={"meta": {"podcast_episode_id": "ep-1"}}),
        call(
            "airano-mcp/v1/post-language",
            json_data={"post_id": 42, "language": "fa", "translation_of": 5},
            use_custom_namespace=True,
        ),
    ]


@pytest.mark.asyncio
async def test_update_post_language_only_fetches_post_and_does_not_empty_update(handler, client):
    client.get.return_value = _post_payload(42)
    client.post.return_value = {"post_id": 42, "provider": "wpml", "applied": True}

    await handler.update_post(post_id=42, language="fa")

    client.get.assert_awaited_once_with("posts/42")
    client.post.assert_awaited_once_with(
        "airano-mcp/v1/post-language",
        json_data={"post_id": 42, "language": "fa"},
        use_custom_namespace=True,
    )


@pytest.mark.asyncio
async def test_language_route_failure_is_structured_notice(handler, client):
    client.post.side_effect = [_post_payload(42), RuntimeError("404 no route")]

    raw = await handler.create_post(
        title="Hello",
        content="Body",
        language="fa",
    )
    out = json.loads(raw)

    assert out["id"] == 42
    assert out["language"]["applied"] is False
    assert out["language"]["notice"]["code"] == "multilingual_route_unavailable"
    assert "404 no route" in out["language"]["notice"]["message"]


@pytest.mark.asyncio
async def test_meta_none_is_omitted(handler, client):
    client.post.return_value = _post_payload(42)

    await handler.create_post(title="Hello", content="Body", meta=None)

    _, kwargs = client.post.await_args
    assert "meta" not in kwargs["json_data"]
