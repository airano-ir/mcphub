"""
Tests that CoolifyClient issues the HTTP verb and path Coolify actually routes.

These exist because of issue #136: Coolify v4.3.1 migrated its action endpoints
from GET to POST, and every action tool broke with

    405: "This endpoint has changed to a POST request."

The rest of the Coolify suite mocks the client methods themselves, so nothing
asserted the wire format and the breakage was invisible to CI. Assert it here.

Ground truth is Coolify's own `routes/api.php` at v4.3.1, where the old GET
routes are still registered but point at `OtherController::post_required`.
"""

from unittest.mock import AsyncMock

import pytest

from plugins.coolify.client import CoolifyClient


@pytest.fixture
def client(monkeypatch):
    """Client whose `request` is captured instead of performing HTTP."""
    c = CoolifyClient(site_url="https://coolify.test.com", token="test-token-123")
    c.request = AsyncMock(return_value={"ok": True})
    return c


# (client method, kwargs, expected HTTP verb, expected endpoint)
ACTION_CALLS = [
    ("start_application", {"uuid": "app-1"}, "POST", "applications/app-1/start"),
    ("stop_application", {"uuid": "app-1"}, "POST", "applications/app-1/stop"),
    ("restart_application", {"uuid": "app-1"}, "POST", "applications/app-1/restart"),
    ("start_database", {"uuid": "db-1"}, "POST", "databases/db-1/start"),
    ("stop_database", {"uuid": "db-1"}, "POST", "databases/db-1/stop"),
    ("restart_database", {"uuid": "db-1"}, "POST", "databases/db-1/restart"),
    ("start_service", {"uuid": "svc-1"}, "POST", "services/svc-1/start"),
    ("stop_service", {"uuid": "svc-1"}, "POST", "services/svc-1/stop"),
    ("restart_service", {"uuid": "svc-1"}, "POST", "services/svc-1/restart"),
    ("validate_server", {"uuid": "srv-1"}, "POST", "servers/srv-1/validate"),
]


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "kwargs", "verb", "endpoint"), ACTION_CALLS)
async def test_action_endpoints_use_post(client, method, kwargs, verb, endpoint):
    """Action endpoints must POST — Coolify 405s on GET since v4.3.1."""
    await getattr(client, method)(**kwargs)

    args = client.request.await_args.args
    assert args[0] == verb, f"{method} must use {verb}, got {args[0]}"
    assert args[1] == endpoint


@pytest.mark.unit
@pytest.mark.asyncio
async def test_deploy_uses_post_with_query_params(client):
    """`/deploy` is POST, but its arguments stay in the query string, not a body."""
    await client.deploy(uuid="app-1", force=True)

    args = client.request.await_args.args
    kwargs = client.request.await_args.kwargs
    assert args[0] == "POST"
    assert args[1] == "deploy"
    assert kwargs["params"] == {"uuid": "app-1", "force": "true"}
    assert "json_data" not in kwargs


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stop_application_keeps_query_params(client):
    """Verb changed to POST; docker_cleanup remains a query param."""
    await client.stop_application("app-1", docker_cleanup=False)

    assert client.request.await_args.kwargs["params"] == {"docker_cleanup": "false"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_deploy_pr_preview_params(client):
    """`pr`/`pull_request_id`/`docker_tag` (v4.3.1 additions) go in the query string too."""
    await client.deploy(uuid="app-1", pull_request_id=42, docker_tag="pr-42")

    args = client.request.await_args.args
    kwargs = client.request.await_args.kwargs
    assert args[0] == "POST"
    assert args[1] == "deploy"
    assert kwargs["params"] == {
        "uuid": "app-1",
        "pull_request_id": 42,
        "docker_tag": "pr-42",
    }


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_server_default_sends_no_body(client):
    """Plain validation (install=False) sends no JSON body."""
    await client.validate_server("srv-1")

    args = client.request.await_args.args
    kwargs = client.request.await_args.kwargs
    assert args[0] == "POST"
    assert args[1] == "servers/srv-1/validate"
    assert kwargs["json_data"] is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_validate_server_install_sends_body(client):
    """install=True (v4.3.1 addition) is sent as a JSON body, not a query param."""
    await client.validate_server("srv-1", install=True)

    kwargs = client.request.await_args.kwargs
    assert kwargs["json_data"] == {"install": True}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_get_environment_uses_catch_all_route(client):
    """Environment reads live at /projects/{uuid}/{name}.

    `/projects/{uuid}/environments/{name}` only accepts PATCH and DELETE.
    """
    await client.get_environment("proj-1", "production")

    args = client.request.await_args.args
    assert args[0] == "GET"
    assert args[1] == "projects/proj-1/production"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_list_backup_executions_is_scoped_to_a_backup(client):
    """There is no instance-wide backup-executions route."""
    await client.list_backup_executions("db-1", "sb-1")

    args = client.request.await_args.args
    assert args[0] == "GET"
    assert args[1] == "databases/db-1/backups/sb-1/executions"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_docker_compose_create_reports_removal(client):
    """The dockercompose create route is gone; fail with a pointer, not a bare 404."""
    with pytest.raises(Exception, match="dockercompose"):
        await client.create_application_docker_compose({"name": "x"})

    client.request.assert_not_awaited()
