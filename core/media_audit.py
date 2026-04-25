"""F.5a.6.4 — Audit-log emission for media uploads.

One ``media.upload`` entry is written per **successful** upload regardless
of source (base64 / url / chunked / ai:<provider>). Failures are intentionally
NOT logged here — they surface to the caller as typed ``UploadError`` JSON
and to the dashboard via the existing tool-call audit emitted by the
ToolRouter wrapper. Logging failures twice would double-count error rates.

GDPR: never log raw bytes, base64, prompts, or URLs that may carry tokens.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def log_media_upload(
    *,
    site: str | None,
    user_id: str | None,
    mime: str | None,
    size_bytes: int,
    source: str,
    media_id: int | None,
    cost_usd: float | None = None,
) -> None:
    """Emit a single ``media.upload`` audit entry. Best-effort — never raises.

    Args:
        site: Site URL or alias (whichever the handler has on hand).
        user_id: Calling user id (None for admin / env-fallback).
        mime: Sniffed MIME type after security validation.
        size_bytes: Final uploaded byte count (post-optimization).
        source: One of ``"base64"``, ``"url"``, ``"chunked"``, ``"ai:<provider>"``.
        media_id: WordPress media library id of the resulting attachment.
        cost_usd: Provider cost in USD for AI-generated uploads only.
    """
    try:
        from core.audit_log import get_audit_logger

        audit = get_audit_logger()
    except Exception:  # noqa: BLE001
        return

    params: dict[str, Any] = {
        "site": site,
        "mime": mime,
        "size_bytes": int(size_bytes),
        "source": source,
        "media_id": media_id,
    }
    if cost_usd is not None:
        params["cost_usd"] = round(float(cost_usd), 6)

    try:
        audit.log_tool_call(
            tool_name="media.upload",
            site=site,
            params=params,
            result_summary=(f"{source} {size_bytes}B {mime or '?'} -> media_id={media_id}"),
            user_id=user_id,
        )
    except Exception:  # noqa: BLE001
        logger.debug("media.upload audit emit failed", exc_info=True)
