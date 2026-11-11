"""HTTP binary intake for Gitea upload sessions."""

from __future__ import annotations

import logging
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse

from core.gitea_upload_sessions import get_gitea_upload_metadata, is_gitea_upload_mime
from core.upload_sessions import (
    UploadSessionError,
    get_upload_session_store,
    make_session_owner_id,
)

logger = logging.getLogger(__name__)


def _error(
    code: str,
    message: str,
    *,
    status_code: int,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    payload: dict[str, Any] = {"error_code": code, "message": message}
    if details:
        payload["details"] = details
    return JSONResponse(payload, status_code=status_code)


def _scope_allows(scopes: list[str], required: str) -> bool:
    from core.tool_access import UNIVERSAL_SCOPE_TIERS

    allowed: set[str] = set()
    for scope in scopes:
        allowed |= UNIVERSAL_SCOPE_TIERS.get(scope.strip(), set())
    return required in allowed


async def _authenticate_user_gitea_upload(
    request: Request,
    *,
    user_id: str,
    alias: str,
) -> tuple[dict[str, Any] | None, JSONResponse | None]:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, _error("UNAUTHORIZED", "Missing Authorization header.", status_code=401)

    token = auth_header[7:].strip()
    key_scopes: list[str] = []
    key_site_id: str | None = None

    if token.startswith("mhu_"):
        try:
            from core.user_keys import get_user_key_manager

            key_info = await get_user_key_manager().validate_key(token)
        except RuntimeError:
            return None, _error(
                "AUTH_UNAVAILABLE",
                "Authentication service unavailable.",
                status_code=503,
            )
        if key_info is None:
            return None, _error("UNAUTHORIZED", "Invalid API key.", status_code=401)
        if key_info["user_id"] != user_id:
            return None, _error(
                "FORBIDDEN",
                "API key does not match user.",
                status_code=403,
            )
        key_scopes = key_info.get("scopes", "read").split()
        key_site_id = key_info.get("site_id")
    else:
        try:
            import jwt as pyjwt

            from core.oauth import get_token_manager

            jwt_payload = get_token_manager().validate_access_token(token)
            sub = jwt_payload.get("sub", "")
            if not sub.startswith("user:"):
                return None, _error(
                    "FORBIDDEN",
                    "Token is not authorized for user endpoints.",
                    status_code=403,
                )
            if sub[len("user:") :] != user_id:
                return None, _error("FORBIDDEN", "Token user mismatch.", status_code=403)
            key_scopes = jwt_payload.get("scope", "read").split()
        except pyjwt.ExpiredSignatureError:
            return None, _error("UNAUTHORIZED", "Token expired.", status_code=401)
        except Exception:
            return None, _error("UNAUTHORIZED", "Invalid token.", status_code=401)

    if not _scope_allows(key_scopes, "write"):
        return None, _error(
            "INSUFFICIENT_SCOPE",
            "Gitea binary intake requires write scope.",
            status_code=403,
        )

    try:
        from core.database import get_database

        db = get_database()
        site = await db.get_site_by_alias(user_id, alias)
    except RuntimeError:
        return None, _error("DB_UNAVAILABLE", "Database unavailable.", status_code=503)

    if site is None:
        return None, _error("NOT_FOUND", f"Site '{alias}' not found.", status_code=404)
    if site.get("status") == "disabled":
        return None, _error("FORBIDDEN", "Site is disabled.", status_code=403)
    if key_site_id and key_site_id != site["id"]:
        return None, _error(
            "FORBIDDEN",
            "API key is scoped to a different site.",
            status_code=403,
        )
    if site.get("plugin_type") != "gitea":
        return None, _error(
            "UNSUPPORTED_SITE_TYPE",
            "Gitea binary intake is available for Gitea sites only.",
            status_code=404,
        )

    try:
        user_record = await db.get_user_by_id(user_id)
    except Exception:
        user_record = None
    is_admin_user = False
    if user_record:
        from core.admin_utils import is_admin_email

        is_admin_user = user_record.get("role") == "admin" or is_admin_email(
            user_record.get("email")
        )

    if not is_admin_user:
        from core.plugin_visibility import is_plugin_public
        from core.user_endpoints import _check_user_rate_limit

        if not is_plugin_public(site["plugin_type"]):
            return None, _error(
                "FORBIDDEN",
                f"Plugin '{site['plugin_type']}' is not currently available.",
                status_code=403,
            )
        allowed, rate_msg = _check_user_rate_limit(user_id)
        if not allowed:
            return None, _error("RATE_LIMITED", rate_msg, status_code=429)

    from core.tool_access import SCOPE_CUSTOM, UNIVERSAL_SCOPE_TIERS

    site_scope = site.get("tool_scope") or "admin"
    if site_scope and site_scope != SCOPE_CUSTOM:
        if "write" not in UNIVERSAL_SCOPE_TIERS.get(site_scope, set()):
            return None, _error(
                "INSUFFICIENT_SITE_SCOPE",
                "This site's tool scope does not allow Gitea binary uploads.",
                status_code=403,
            )

    try:
        toggles = await db.get_site_tool_toggles(site["id"])
        for tool_name in (
            "gitea_upload_start",
            "gitea_upload_chunk",
            "gitea_upload_finish",
        ):
            if toggles.get(tool_name, True) is False:
                return None, _error(
                    "TOOL_DISABLED",
                    f"Tool '{tool_name}' is disabled for this site.",
                    status_code=403,
                )
    except Exception as exc:
        logger.warning("Failed to check gitea-intake tool toggles: %s", exc)

    return site, None


def _session_status_for_error(code: str) -> int:
    return {
        "NO_SESSION": 404,
        "EXPIRED": 410,
        "BAD_STATE": 409,
        "CHUNK_ORDER": 409,
        "CHUNK_OVERFLOW": 413,
        "SESSION_TOO_LARGE": 413,
        "QUOTA_EXCEEDED": 429,
    }.get(code, 400)


async def user_gitea_upload_handler(request: Request) -> JSONResponse:
    """Stream raw bytes into a user-owned Gitea upload session.

    Route: ``PUT /u/{user_id}/{alias}/gitea-upload/{session_id}``
    """
    user_id = request.path_params.get("user_id", "")
    alias = request.path_params.get("alias", "")
    session_id = request.path_params.get("session_id", "")

    if not user_id or not alias or not session_id:
        return _error("BAD_REQUEST", "Invalid Gitea upload path.", status_code=400)

    site, auth_error = await _authenticate_user_gitea_upload(
        request,
        user_id=user_id,
        alias=alias,
    )
    if auth_error is not None:
        return auth_error
    assert site is not None

    index_header = request.headers.get("x-mcphub-chunk-index")
    if index_header is None:
        index = None
    else:
        try:
            index = int(index_header)
        except ValueError:
            return _error(
                "BAD_CHUNK_INDEX",
                "X-MCPHub-Chunk-Index must be an integer.",
                status_code=400,
            )

    store = get_upload_session_store()
    sess = await store.get(session_id)
    if sess is None:
        return _error("NO_SESSION", f"Session {session_id} not found.", status_code=404)
    if not is_gitea_upload_mime(sess.mime):
        return _error(
            "BAD_SESSION_TYPE",
            "Session is not a Gitea binary upload session.",
            status_code=409,
        )

    meta = await get_gitea_upload_metadata(store.db, session_id)
    if meta is None:
        return _error(
            "BAD_SESSION_TYPE",
            "Gitea upload metadata is missing for this session.",
            status_code=409,
        )
    if meta.plugin_type != "gitea" or meta.site_id != site["id"] or meta.alias != alias:
        return _error(
            "FORBIDDEN",
            "Upload session is scoped to a different Gitea site.",
            status_code=403,
        )

    allowed_owners = {make_session_owner_id(user_id, site["id"])}
    if sess.user_id not in allowed_owners:
        return _error(
            "FORBIDDEN",
            "Upload session does not belong to this user/site.",
            status_code=403,
        )

    try:
        updated = await store.append_stream(
            session_id,
            request.stream(),
            index=index,
            chunk_sha256=request.headers.get("x-mcphub-chunk-sha256"),
        )
    except UploadSessionError as exc:
        return JSONResponse(exc.to_dict(), status_code=_session_status_for_error(exc.code))
    except Exception as exc:  # noqa: BLE001
        logger.exception("HTTP Gitea intake failed for session %s", session_id)
        return _error("INTERNAL", f"Binary Gitea intake failed: {exc}", status_code=500)

    payload = updated.to_public_dict()
    payload.update(meta.to_public_dict())
    payload.update(
        {
            "ready_to_finish": updated.received_bytes == updated.total_bytes,
            "finish_tool": "gitea_upload_finish",
            "message": (
                "Bytes accepted. Call gitea_upload_finish when " "ready_to_finish is true."
            ),
        }
    )
    return JSONResponse(payload)
