"""Media upload security primitives: MIME sniff, size validation, SSRF guard, filename safety."""

from __future__ import annotations

import ipaddress
import mimetypes
import os
import re
import socket
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlparse

try:
    import magic as _magic  # type: ignore
except Exception:
    _magic = None


class UploadError(Exception):
    """Structured upload error with stable code for JSON responses."""

    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict:
        return {"error_code": self.code, "message": self.message, "details": self.details}


DEFAULT_MAX_BYTES = int(os.environ.get("WP_MEDIA_MAX_MB", "10")) * 1024 * 1024

ALLOWED_MIMES: set[str] = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
    "image/avif",
    "image/heic",
    "image/bmp",
    "image/tiff",
    "application/pdf",
    "video/mp4",
    "video/webm",
    "video/quicktime",
    "audio/mpeg",
    "audio/mp4",
    "audio/webm",
    "audio/ogg",
    "audio/wav",
}

_EXT_MAP = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/avif": ".avif",
    "image/heic": ".heic",
    "application/pdf": ".pdf",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
    "audio/mpeg": ".mp3",
    "audio/mp4": ".m4a",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
}


def _builtin_sniff(data: bytes) -> str | None:
    """Minimal magic-byte sniffer for common media types (libmagic-free fallback)."""
    if not data:
        return None
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data[:4] == b"GIF8":
        return "image/gif"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "audio/wav"
    if data[4:12] in (b"ftypmp42", b"ftypisom", b"ftypMSNV", b"ftypavc1"):
        return "video/mp4"
    if data[4:8] == b"ftyp":
        # Generic ISO BMFF — likely mp4/heic
        brand = data[8:12]
        if brand in (b"heic", b"heix", b"mif1"):
            return "image/heic"
        return "video/mp4"
    if data.startswith(b"\x1aE\xdf\xa3"):
        return "video/webm"
    if data.startswith(b"ID3") or data[:2] == b"\xff\xfb":
        return "audio/mpeg"
    if data.startswith(b"OggS"):
        return "audio/ogg"
    return None


def sniff_mime(data: bytes, *, hint: str | None = None) -> str:
    """Detect MIME from magic bytes. Uses libmagic if available, else built-in sniff."""
    if _magic is not None:
        try:
            detected = _magic.from_buffer(data[:4096], mime=True)
            if detected and detected != "application/octet-stream":
                return detected
        except Exception:
            pass
    built_in = _builtin_sniff(data)
    if built_in:
        return built_in
    if hint and "/" in hint:
        return hint.lower()
    return "application/octet-stream"


def validate_size(data: bytes, *, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
    if len(data) == 0:
        raise UploadError("EMPTY_FILE", "Upload data is empty.")
    if len(data) > max_bytes:
        raise UploadError(
            "TOO_LARGE",
            f"File is {len(data)} bytes; limit is {max_bytes} bytes "
            f"(~{max_bytes // 1024 // 1024} MB). Use chunked upload for larger files.",
            {"size": len(data), "max": max_bytes},
        )


def validate_mime(mime: str, *, allowed: Iterable[str] = ALLOWED_MIMES) -> None:
    if mime not in allowed:
        raise UploadError(
            "MIME_REJECTED",
            f"MIME type '{mime}' is not allowed. " f"Supported: {', '.join(sorted(allowed))}.",
            {"mime": mime},
        )


_FILENAME_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(filename: str | None, *, mime: str) -> tuple[str, str | None]:
    """Return (ascii_filename, rfc5987_encoded_original_if_non_ascii)."""
    original = (filename or "").strip() or "upload"
    # Strip any path components
    original = original.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]

    try:
        original.encode("ascii")
        ascii_name = _FILENAME_SAFE_RE.sub("_", original)
        encoded = None
    except UnicodeEncodeError:
        from urllib.parse import quote

        ascii_name = _FILENAME_SAFE_RE.sub(
            "_", original.encode("ascii", "ignore").decode() or "upload"
        )
        encoded = "UTF-8''" + quote(original, safe="")

    # Ensure extension matches MIME
    ext = _EXT_MAP.get(mime) or (mimetypes.guess_extension(mime) or "")
    if ext and not ascii_name.lower().endswith(ext):
        base = ascii_name.rsplit(".", 1)[0] if "." in ascii_name else ascii_name
        ascii_name = f"{base}{ext}"

    return ascii_name[:255], encoded


def content_disposition(filename_ascii: str, filename_encoded: str | None) -> str:
    """Build Content-Disposition header, optionally with RFC 5987 filename* for non-ASCII."""
    base = f'attachment; filename="{filename_ascii}"'
    if filename_encoded:
        return f"{base}; filename*={filename_encoded}"
    return base


# --- SSRF guard ------------------------------------------------------------

_BLOCKED_HOSTS = {
    "metadata.google.internal",
    "metadata",
    "169.254.169.254",
}


@dataclass
class SSRFCheck:
    allowed: bool
    reason: str | None = None
    resolved_ip: str | None = None


def ssrf_check(url: str, *, allow_http: bool = False) -> SSRFCheck:
    """Reject URLs pointing to private/loopback/link-local/metadata endpoints."""
    try:
        parsed = urlparse(url)
    except Exception as e:
        return SSRFCheck(False, f"URL parse failed: {e}")

    if parsed.scheme not in ("http", "https"):
        return SSRFCheck(False, f"Scheme '{parsed.scheme}' not allowed; use https (or http).")
    if parsed.scheme == "http" and not allow_http:
        return SSRFCheck(False, "HTTP URLs are disabled; use HTTPS.")

    host = (parsed.hostname or "").lower()
    if not host:
        return SSRFCheck(False, "URL has no host.")
    if host in _BLOCKED_HOSTS:
        return SSRFCheck(False, f"Host '{host}' is on the SSRF blocklist.")

    # Resolve and check each IP
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        return SSRFCheck(False, f"DNS resolution failed: {e}")

    seen: list[str] = []
    for info in infos:
        ip_str = info[4][0]
        seen.append(ip_str)
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return SSRFCheck(False, f"Unparseable IP '{ip_str}'.")
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return SSRFCheck(False, f"Host resolves to disallowed IP {ip}.", ip_str)

    return SSRFCheck(True, None, seen[0] if seen else None)
