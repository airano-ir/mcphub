"""Shared raw-binary upload primitive for WordPress media library.

WP REST `/wp/v2/media` expects the raw binary file body with a `Content-Disposition`
header (NOT multipart/form-data). Metadata fields like alt_text/caption/title must
be set via a follow-up `POST /media/{id}` JSON call.

F.5a.7: when the airano-mcp companion plugin is present AND the file size
exceeds the site's advertised ``upload_max_filesize``, prefer the companion
``POST /airano-mcp/v1/upload-chunk`` route which reads the body via
``php://input`` (bypasses ``upload_max_filesize``). On any failure from the
companion route we fall back to the standard ``/wp/v2/media`` path so we
never regress the default upload behaviour.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp

from plugins.wordpress.client import WordPressClient
from plugins.wordpress.handlers._media_security import (
    ALLOWED_MIMES,
    DEFAULT_MAX_BYTES,
    UploadError,
    content_disposition,
    safe_filename,
    sniff_mime,
    validate_mime,
    validate_size,
)

_logger = logging.getLogger("mcphub.wordpress.media")

_UPLOAD_TIMEOUT = 120  # seconds

# Endpoint suffix (under /wp-json/) for the companion upload-chunk route.
_COMPANION_UPLOAD_ENDPOINT = "airano-mcp/v1/upload-chunk"
# F.5a.8.5: single-call upload + attach + featured via companion v2.9.0+.
_COMPANION_UPLOAD_AND_ATTACH_ENDPOINT = "airano-mcp/v1/upload-and-attach"


async def _should_use_companion(client: WordPressClient, size: int) -> bool:
    """F.5a.7: decide whether to prefer the companion upload-chunk route.

    True when the cached probe result marks the companion helper as available
    AND the payload size exceeds the site's advertised ``upload_max_filesize``
    (falling back to the effective ceiling when that specific key is unset).

    We only consult the *cached* probe — never trigger a fresh probe from the
    upload path — so a cold cache simply degrades to the standard route.
    """
    try:
        from plugins.wordpress.handlers.media_probe import get_cached_limits
    except Exception:  # pragma: no cover - defensive
        return False

    try:
        cached = await get_cached_limits(client)
    except Exception as exc:  # noqa: BLE001
        _logger.debug("Companion probe lookup failed: %s", exc)
        return False
    if not cached or not cached.get("companion_available"):
        return False

    limits_bytes = cached.get("limits_bytes") or {}
    ceiling = (
        limits_bytes.get("upload_max_filesize")
        or limits_bytes.get("wp_max_upload_size")
        or limits_bytes.get("effective_ceiling")
    )
    if ceiling is None or ceiling <= 0:
        return False
    return size > ceiling


async def _companion_has_upload_and_attach(client: WordPressClient) -> bool:
    """F.5a.8.5: does the cached capability probe advertise the
    ``upload_and_attach`` route?

    We only check the cached result — never force a fresh probe from
    the upload path. If the cache is cold, we conservatively return
    False and the caller falls back to the 3-step path; the probe
    will warm up on the next dashboard visit.
    """
    try:
        from plugins.wordpress.handlers.capabilities import get_cached_capabilities
    except Exception:  # pragma: no cover
        return False
    try:
        cached = await get_cached_capabilities(client)
    except Exception as exc:  # noqa: BLE001
        _logger.debug("Companion capability cache lookup failed: %s", exc)
        return False
    if not cached or not cached.get("companion_available"):
        return False
    routes = cached.get("routes") or {}
    return bool(routes.get("upload_and_attach"))


async def _companion_upload_and_attach(
    client: WordPressClient,
    data: bytes,
    *,
    sniffed: str,
    disposition: str,
    attach_to_post: int | None,
    set_featured: bool,
    title: str | None,
    alt_text: str | None,
    caption: str | None,
    description: str | None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Upload + metadata + attach + featured in a single companion call.

    Raises ``UploadError`` on any non-2xx response so the caller can
    fall back to ``wp/v2/media`` + separate metadata calls.
    """
    params: dict[str, str] = {}
    if attach_to_post and attach_to_post > 0:
        params["attach_to_post"] = str(int(attach_to_post))
    if set_featured and attach_to_post and attach_to_post > 0:
        params["set_featured"] = "true"
    if title:
        params["title"] = str(title)
    if alt_text:
        params["alt_text"] = str(alt_text)
    if caption:
        params["caption"] = str(caption)
    if description:
        params["description"] = str(description)

    url = f"{client.site_url}/wp-json/{_COMPANION_UPLOAD_AND_ATTACH_ENDPOINT}"
    headers = {
        "Authorization": client.auth_header,
        "Content-Type": sniffed,
        "Content-Disposition": disposition,
    }
    # F.X.fix #7: pass the caller's idempotency key through to the
    # companion so a retry after client timeout returns the original
    # attachment instead of creating an "-2.webp" orphan.
    if idempotency_key:
        headers["Idempotency-Key"] = str(idempotency_key)
    timeout = aiohttp.ClientTimeout(total=_UPLOAD_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, data=data, headers=headers, params=params) as response:
            text = await response.text()
            if response.status >= 400:
                raise UploadError(
                    f"COMPANION_{response.status}",
                    f"Companion upload-and-attach failed: HTTP {response.status}",
                    {"status": response.status, "body": text[:500]},
                )
            try:
                return await response.json(content_type=None)
            except Exception as e:
                raise UploadError(
                    "COMPANION_BAD_RESPONSE",
                    f"Companion upload-and-attach returned non-JSON response: {e}",
                    {"body": text[:500]},
                ) from e


async def _companion_raw_upload(
    client: WordPressClient,
    data: bytes,
    *,
    sniffed: str,
    disposition: str,
) -> dict[str, Any]:
    """Upload via the companion ``POST /airano-mcp/v1/upload-chunk`` route.

    Raises ``UploadError`` on any non-2xx response so the caller can fall
    back to the standard /wp/v2/media path.
    """
    url = f"{client.site_url}/wp-json/{_COMPANION_UPLOAD_ENDPOINT}"
    headers = {
        "Authorization": client.auth_header,
        "Content-Type": sniffed,
        "Content-Disposition": disposition,
    }
    timeout = aiohttp.ClientTimeout(total=_UPLOAD_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, data=data, headers=headers) as response:
            text = await response.text()
            if response.status >= 400:
                raise UploadError(
                    f"COMPANION_{response.status}",
                    f"Companion upload-chunk failed: HTTP {response.status}",
                    {"status": response.status, "body": text[:500]},
                )
            try:
                return await response.json(content_type=None)
            except Exception as e:
                raise UploadError(
                    "COMPANION_BAD_RESPONSE",
                    f"Companion upload returned non-JSON response: {e}",
                    {"body": text[:500]},
                ) from e


async def wp_raw_upload(
    client: WordPressClient,
    data: bytes,
    *,
    filename: str | None,
    mime_hint: str | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    allowed_mimes: set[str] = ALLOWED_MIMES,
    # F.5a.8.5: optional attach + featured + metadata params. When any of
    # these is provided AND the companion's upload-and-attach route is
    # advertised in the cached capability probe, we POST to the single-
    # call endpoint instead of doing the 3-step REST dance. Returned
    # dict is marked ``_upload_route="companion_unified"`` so the caller
    # (``_apply_metadata_and_attach``) can skip the separate metadata /
    # featured-image calls.
    attach_to_post: int | None = None,
    set_featured: bool = False,
    title: str | None = None,
    alt_text: str | None = None,
    caption: str | None = None,
    description: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Upload raw bytes to WP media library. Returns the attachment dict from WP.

    When the companion plugin advertises limits smaller than the payload, we
    POST to ``/airano-mcp/v1/upload-chunk`` first and only fall back to
    ``/wp/v2/media`` if the companion route errors.

    F.5a.8.5: when ``attach_to_post`` or any metadata field is set AND the
    companion advertises the ``upload_and_attach`` route, we prefer the
    single-call path which bundles upload + metadata + attach + featured
    into one PHP request.
    """
    validate_size(data, max_bytes=max_bytes)
    sniffed = sniff_mime(data, hint=mime_hint)
    validate_mime(sniffed, allowed=allowed_mimes)

    ascii_name, encoded = safe_filename(filename, mime=sniffed)
    disposition = content_disposition(ascii_name, encoded)

    # F.5a.8.5 unified route: tried first when the caller wants metadata
    # applied AND the companion supports it. Falls back to the legacy
    # path on any error (companion 4xx/5xx, route not advertised, etc.).
    has_metadata_intent = (
        any(v is not None for v in (attach_to_post, title, alt_text, caption, description))
        or set_featured
    )
    if has_metadata_intent and await _companion_has_upload_and_attach(client):
        try:
            result = await _companion_upload_and_attach(
                client,
                data,
                sniffed=sniffed,
                disposition=disposition,
                attach_to_post=attach_to_post,
                set_featured=set_featured,
                title=title,
                alt_text=alt_text,
                caption=caption,
                description=description,
                idempotency_key=idempotency_key,
            )
            result["_upload_route"] = "companion_unified"
            return result
        except UploadError as exc:
            _logger.warning(
                "Companion upload-and-attach failed (%s); falling back to "
                "/upload-chunk + separate metadata calls",
                exc.code,
            )

    # F.5a.7 route selection (non-fatal; falls back to /wp/v2/media on error).
    if await _should_use_companion(client, len(data)):
        try:
            result = await _companion_raw_upload(
                client,
                data,
                sniffed=sniffed,
                disposition=disposition,
            )
            result["_upload_route"] = "companion"
            return result
        except UploadError as exc:
            _logger.warning(
                "Companion upload-chunk failed (%s); falling back to /wp/v2/media",
                exc.code,
            )

    url = f"{client.api_base}/media"
    headers = {
        "Authorization": client.auth_header,
        "Content-Type": sniffed,
        "Content-Disposition": disposition,
    }

    timeout = aiohttp.ClientTimeout(total=_UPLOAD_TIMEOUT)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, data=data, headers=headers) as response:
            text = await response.text()
            if response.status == 413:
                raise UploadError(
                    "WP_413",
                    "WordPress rejected upload (413 Payload Too Large). "
                    "Site's upload_max_filesize / post_max_size is below the file size.",
                    {"status": 413, "body": text[:500]},
                )
            if response.status in (401, 403):
                raise UploadError(
                    "WP_AUTH",
                    f"WordPress rejected auth ({response.status}). Verify Application Password.",
                    {"status": response.status, "body": text[:500]},
                )
            if response.status >= 400:
                raise UploadError(
                    f"WP_{response.status}",
                    f"WordPress upload failed: HTTP {response.status}",
                    {"status": response.status, "body": text[:500]},
                )
            try:
                result = await response.json(content_type=None)
                if isinstance(result, dict):
                    result["_upload_route"] = "rest"
                return result
            except Exception as e:
                raise UploadError(
                    "WP_BAD_RESPONSE",
                    f"WP upload returned non-JSON response: {e}",
                    {"body": text[:500]},
                ) from e


async def wp_update_media_metadata(
    client: WordPressClient,
    media_id: int,
    *,
    title: str | None = None,
    alt_text: str | None = None,
    caption: str | None = None,
    description: str | None = None,
    post: int | None = None,
) -> dict[str, Any]:
    """Apply metadata fields via POST /media/{id}. Only sends non-None fields."""
    payload: dict[str, Any] = {}
    if title is not None:
        payload["title"] = title
    if alt_text is not None:
        payload["alt_text"] = alt_text
    if caption is not None:
        payload["caption"] = caption
    if description is not None:
        payload["description"] = description
    if post is not None:
        payload["post"] = post
    if not payload:
        return {}
    return await client.post(f"media/{media_id}", json_data=payload)


async def wp_set_featured_media(
    client: WordPressClient, post_id: int, media_id: int
) -> dict[str, Any]:
    """Set a post's featured image."""
    return await client.post(f"posts/{post_id}", json_data={"featured_media": media_id})


async def fetch_url_bytes(
    url: str,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    timeout_sec: int = 60,
    user_agent: str = "MCPHub-MediaUploader/1.0",
    resolved_ip: str | None = None,
) -> tuple[bytes, str | None, str]:
    """Download up to `max_bytes` from URL. Streams and enforces the limit.

    Returns (data, content_type, filename_guess).
    """
    filename_guess = url.rsplit("/", 1)[-1].split("?")[0] or "download"
    headers = {"User-Agent": user_agent}
    timeout = aiohttp.ClientTimeout(total=timeout_sec)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, headers=headers, allow_redirects=True) as resp:
            if resp.status >= 400:
                raise UploadError(
                    "URL_FETCH_FAILED",
                    f"Download failed: HTTP {resp.status}",
                    {"status": resp.status, "url": url},
                )
            declared_ct = resp.headers.get("Content-Type")
            # Stream read with byte cap
            buf = bytearray()
            async for chunk in resp.content.iter_chunked(64 * 1024):
                buf.extend(chunk)
                if len(buf) > max_bytes:
                    raise UploadError(
                        "TOO_LARGE",
                        f"Remote file exceeds limit of {max_bytes} bytes while streaming.",
                        {"max": max_bytes, "url": url},
                    )
            _ = asyncio  # keep import for callers if needed
            return bytes(buf), declared_ct, filename_guess
