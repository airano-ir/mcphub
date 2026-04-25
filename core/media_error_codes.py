"""F.5a.6.2 — Stable error-code taxonomy for media upload tools.

Every :class:`plugins.wordpress.handlers._media_security.UploadError` and
:class:`core.upload_sessions.UploadSessionError` raised inside the media
stack MUST use one of the codes listed here (or match the dynamic
``WP_<status>`` pattern for upstream WordPress REST responses).

The accompanying test ``tests/plugins/wordpress/test_media_error_taxonomy.py``
scans the source files for raise-site literals and asserts each one is in
this set — so the contract stays stable as the code evolves.

The full reference is in ``docs/media-error-codes.md``.
"""

from __future__ import annotations

import re

#: All stable upload/media error codes. Keep alphabetical within groups.
MEDIA_ERROR_CODES: frozenset[str] = frozenset(
    {
        # --- Input / validation ------------------------------------------
        "BAD_BASE64",
        "BAD_MODE",
        "BAD_ROLE",
        "BAD_SIZE",
        "BAD_SOURCE",
        "EMPTY_FILE",
        "MEDIA_NOT_FOUND",
        "MIME_REJECTED",
        "MISSING_FIELD",
        "SSRF",
        "TOO_LARGE",
        "URL_FETCH_FAILED",
        # --- WordPress REST upstream -------------------------------------
        "WP_413",
        "WP_AUTH",
        "WP_BAD_RESPONSE",
        # F.X.fix-pass4 — WC sites with consumer_key/consumer_secret
        # auth need a separate WP Application Password to upload to
        # /wp/v2/media. Surfaced by media_attach.py when the user
        # hasn't filled wp_username/wp_app_password in Connection
        # Settings.
        "WP_CREDENTIALS_MISSING",
        # WP_<status> (e.g. WP_500) is also allowed — see MEDIA_ERROR_CODE_RE
        # --- Companion plugin upload-chunk route (F.5a.7) ----------------
        "COMPANION_BAD_RESPONSE",
        # COMPANION_<status> (e.g. COMPANION_500) is also allowed — same
        # shape as WP_<status>, see _COMPANION_STATUS_RE.
        # --- Chunked upload session --------------------------------------
        "BAD_STATE",
        "CHECKSUM_MISMATCH",
        "CHUNK_CHECKSUM",
        "CHUNK_ORDER",
        "CHUNK_OVERFLOW",
        "EXPIRED",
        "INCOMPLETE",
        "NO_SESSION",
        "QUOTA_EXCEEDED",
        "SESSION_TOO_LARGE",
        # --- AI generation providers -------------------------------------
        "GENERATION_FAILED",
        "NO_PROVIDER_KEY",
        "PROVIDER_AUTH",
        "PROVIDER_BAD_REQUEST",
        "PROVIDER_BAD_RESPONSE",
        "PROVIDER_QUOTA",
        "PROVIDER_TIMEOUT",
        "PROVIDER_UNAVAILABLE",
        "PROVIDER_UNKNOWN",
        # --- Rate / policy -----------------------------------------------
        "TOOL_RATE_LIMITED",
        # --- Catchall ----------------------------------------------------
        "INTERNAL",
    }
)

#: Dynamic WP REST status codes (e.g. WP_400, WP_500).
_WP_STATUS_RE = re.compile(r"^WP_\d{3}$")

#: Dynamic companion upload-chunk status codes (e.g. COMPANION_400, COMPANION_500).
_COMPANION_STATUS_RE = re.compile(r"^COMPANION_\d{3}$")


def is_valid_code(code: str) -> bool:
    """Return True if ``code`` is a documented media error code."""
    return (
        code in MEDIA_ERROR_CODES
        or bool(_WP_STATUS_RE.match(code))
        or bool(_COMPANION_STATUS_RE.match(code))
    )
