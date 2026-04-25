"""F.17 — Gitea ergonomics: batch files, tree, search, compare, releases, fork.

Tests cover both the client-level additions and the handler wrappers.
All network calls are mocked through ``client.request`` so the tests
exercise validation, error shaping, and payload construction without
hitting a real Gitea instance.
"""

from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock

import pytest

from plugins.gitea.client import GiteaClient
from plugins.gitea.handlers import repositories as repo_handlers


@pytest.fixture
def client():
    """A GiteaClient with its ``request`` method replaced by an AsyncMock."""
    c = GiteaClient(site_url="https://git.example.com", token="ghs_test")
    c.request = AsyncMock()  # type: ignore[assignment]
    return c


# ---------------------------------------------------------------------------
# _normalise_file_content: error messages + round-trip
# ---------------------------------------------------------------------------


class TestNormaliseFileContent:
    @pytest.mark.unit
    def test_plaintext_roundtrips(self):
        out = GiteaClient._normalise_file_content("hello world", False)
        assert base64.b64decode(out) == b"hello world"

    @pytest.mark.unit
    def test_bytes_input_accepted(self):
        out = GiteaClient._normalise_file_content(b"\x00\x01\x02", False)
        assert base64.b64decode(out) == b"\x00\x01\x02"

    @pytest.mark.unit
    def test_base64_input_validates_roundtrip(self):
        b64 = base64.b64encode(b"precise").decode()
        out = GiteaClient._normalise_file_content(b64, True)
        assert base64.b64decode(out) == b"precise"

    @pytest.mark.unit
    def test_invalid_base64_raises_actionable_error(self):
        # F.17 feedback #10: make the error message tell the user how to
        # recover rather than just echoing the decoder's byte offset.
        with pytest.raises(ValueError) as exc:
            GiteaClient._normalise_file_content("###not base64###", True)
        msg = str(exc.value)
        assert "not valid base64" in msg
        assert "content_is_base64=False" in msg

    @pytest.mark.unit
    def test_data_url_prefix_rejected_with_hint(self):
        with pytest.raises(ValueError) as exc:
            GiteaClient._normalise_file_content("data:text/plain;base64,aGVsbG8=", True)
        assert "data:" in str(exc.value)
        assert "Strip" in str(exc.value)

    @pytest.mark.unit
    def test_non_string_non_bytes_rejected(self):
        with pytest.raises(ValueError):
            GiteaClient._normalise_file_content(12345, False)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Client-level endpoints
# ---------------------------------------------------------------------------


class TestClientEndpoints:
    @pytest.mark.asyncio
    async def test_change_files_forwards_to_batch_endpoint(self, client):
        client.request.return_value = {"commit": {"sha": "abc"}}
        payload = {"message": "m", "files": [{"operation": "create", "path": "x"}]}
        await client.change_files("o", "r", payload)
        client.request.assert_called_once_with("POST", "repos/o/r/contents", json_data=payload)

    @pytest.mark.asyncio
    async def test_get_tree_passes_recursive_flag(self, client):
        client.request.return_value = {"tree": []}
        await client.get_tree("o", "r", "main", recursive=True, page=2, per_page=50)
        call = client.request.call_args
        assert call.args == ("GET", "repos/o/r/git/trees/main")
        assert call.kwargs["params"] == {"page": 2, "per_page": 50, "recursive": "true"}

    @pytest.mark.asyncio
    async def test_get_tree_omits_recursive_when_false(self, client):
        client.request.return_value = {"tree": []}
        await client.get_tree("o", "r")
        params = client.request.call_args.kwargs["params"]
        assert "recursive" not in params

    @pytest.mark.asyncio
    async def test_search_code_scoped_to_repo(self, client):
        client.request.return_value = {"ok": True, "data": []}
        await client.search_code(keyword="func", owner="o", repo="r")
        assert client.request.call_args.args == ("GET", "repos/o/r/search/code")

    @pytest.mark.asyncio
    async def test_search_code_instance_wide(self, client):
        client.request.return_value = {"ok": True, "data": []}
        await client.search_code(keyword="func")
        assert client.request.call_args.args == ("GET", "repos/search/code")

    @pytest.mark.asyncio
    async def test_compare_uses_triple_dot_separator(self, client):
        client.request.return_value = {"commits": []}
        await client.compare("o", "r", "main", "feature-x")
        assert client.request.call_args.args == ("GET", "repos/o/r/compare/main...feature-x")

    @pytest.mark.asyncio
    async def test_create_release_forwards_payload(self, client):
        client.request.return_value = {"id": 1}
        await client.create_release("o", "r", {"tag_name": "v1.0", "draft": False})
        assert client.request.call_args.args == ("POST", "repos/o/r/releases")

    @pytest.mark.asyncio
    async def test_fork_payload_omits_none_fields(self, client):
        client.request.return_value = {"id": 1}
        await client.fork_repository("o", "r")
        # Empty payload — no organization, no name.
        assert client.request.call_args.kwargs["json_data"] == {}

        client.request.reset_mock()
        await client.fork_repository("o", "r", organization="new-org", name="new-name")
        assert client.request.call_args.kwargs["json_data"] == {
            "organization": "new-org",
            "name": "new-name",
        }


# ---------------------------------------------------------------------------
# Handlers: validation + JSON shape
# ---------------------------------------------------------------------------


class TestCreateFilesHandler:
    @pytest.mark.asyncio
    async def test_happy_path_batches_operations(self, client):
        client.request.return_value = {"commit": {"sha": "abc"}}
        out = json.loads(
            await repo_handlers.create_files(
                client,
                owner="o",
                repo="r",
                files=[
                    {"operation": "create", "path": "a.txt", "content": "hi"},
                    {
                        "operation": "update",
                        "path": "b.txt",
                        "content": "bye",
                        "sha": "deadbeef",
                    },
                    {"operation": "delete", "path": "c.txt", "sha": "cafebabe"},
                ],
                message="batch commit",
                branch="main",
            )
        )
        assert out["success"] is True
        assert "Batched 3 file" in out["message"]
        # Client got a single batch call.
        body = client.request.call_args.kwargs["json_data"]
        assert body["branch"] == "main"
        assert body["message"] == "batch commit"
        assert len(body["files"]) == 3
        # content is base64-encoded on the way out.
        for f in body["files"][:2]:
            assert base64.b64decode(f["content"])

    @pytest.mark.asyncio
    async def test_rejects_invalid_operation(self, client):
        out = json.loads(
            await repo_handlers.create_files(
                client,
                owner="o",
                repo="r",
                files=[{"operation": "rename", "path": "a.txt", "content": "x"}],
                message="m",
            )
        )
        assert out["success"] is False
        assert out["errors"][0]["error"].startswith("invalid_operation")
        client.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_requires_sha(self, client):
        out = json.loads(
            await repo_handlers.create_files(
                client,
                owner="o",
                repo="r",
                files=[{"operation": "update", "path": "a.txt", "content": "x"}],
                message="m",
            )
        )
        assert out["success"] is False
        assert out["errors"][0]["error"] == "missing_sha_for_update"
        client.request.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_requires_sha(self, client):
        out = json.loads(
            await repo_handlers.create_files(
                client,
                owner="o",
                repo="r",
                files=[{"operation": "delete", "path": "a.txt"}],
                message="m",
            )
        )
        assert out["success"] is False
        assert out["errors"][0]["error"] == "missing_sha_for_delete"

    @pytest.mark.asyncio
    async def test_bad_base64_surfaces_actionable_error(self, client):
        out = json.loads(
            await repo_handlers.create_files(
                client,
                owner="o",
                repo="r",
                files=[
                    {
                        "operation": "create",
                        "path": "a.txt",
                        "content": "###garbage###",
                        "content_is_base64": True,
                    }
                ],
                message="m",
            )
        )
        assert out["success"] is False
        assert "content_is_base64=False" in out["errors"][0]["error"]


class TestTreeAndSearchHandlers:
    @pytest.mark.asyncio
    async def test_get_tree_passthrough(self, client):
        client.request.return_value = {"tree": [{"path": "x"}]}
        out = json.loads(await repo_handlers.get_tree(client, "o", "r", sha="main", recursive=True))
        assert out["success"] is True
        assert out["tree"]["tree"][0]["path"] == "x"

    @pytest.mark.asyncio
    async def test_search_code_passthrough(self, client):
        client.request.return_value = {"ok": True, "data": [{"path": "hit"}]}
        out = json.loads(
            await repo_handlers.search_code(client, keyword="foo", owner="o", repo="r")
        )
        assert out["success"] is True
        assert out["result"]["data"][0]["path"] == "hit"

    @pytest.mark.asyncio
    async def test_compare_passthrough(self, client):
        client.request.return_value = {"commits": [{"sha": "c1"}]}
        out = json.loads(await repo_handlers.compare(client, "o", "r", "main", "x"))
        assert out["success"] is True
        assert out["compare"]["commits"][0]["sha"] == "c1"


class TestReleaseAndForkHandlers:
    @pytest.mark.asyncio
    async def test_list_releases_passthrough(self, client):
        client.request.return_value = [{"tag_name": "v1"}]
        out = json.loads(await repo_handlers.list_releases(client, "o", "r"))
        assert out["success"] is True
        assert out["releases"][0]["tag_name"] == "v1"

    @pytest.mark.asyncio
    async def test_create_release_forwards_optional_fields(self, client):
        client.request.return_value = {"id": 42}
        await repo_handlers.create_release(
            client, "o", "r", tag_name="v1.0", name="1.0", body="hi", prerelease=True
        )
        body = client.request.call_args.kwargs["json_data"]
        assert body["tag_name"] == "v1.0"
        assert body["name"] == "1.0"
        assert body["body"] == "hi"
        assert body["prerelease"] is True

    @pytest.mark.asyncio
    async def test_create_release_without_optional_fields(self, client):
        client.request.return_value = {"id": 42}
        await repo_handlers.create_release(client, "o", "r", tag_name="v1.0")
        body = client.request.call_args.kwargs["json_data"]
        assert body["tag_name"] == "v1.0"
        assert "name" not in body
        assert "body" not in body

    @pytest.mark.asyncio
    async def test_fork_repository_with_org(self, client):
        client.request.return_value = {"full_name": "neworg/r"}
        out = json.loads(
            await repo_handlers.fork_repository(client, "o", "r", organization="neworg")
        )
        assert out["success"] is True
        assert out["fork"]["full_name"] == "neworg/r"
