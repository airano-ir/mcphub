"""F.5a.2 / F.5a.8.1: Image optimization pipeline using Pillow.

Defaults for web publishing: JPEG quality 85, PNG→JPEG threshold via opacity check,
max long edge 2560 px, EXIF strip, animated GIF preserved untouched.

F.5a.8.1 adds an optional format conversion stage: when ``convert_to`` is
``"webp"`` or ``"avif"`` (or the env var ``WP_MEDIA_CONVERT_TO`` is set),
raster inputs are re-encoded in that modern format regardless of source
type. Transparency is preserved; animated GIFs are still left untouched.

Returns the (possibly reduced) bytes and the (possibly updated) MIME type.
Non-raster types (pdf, svg, video, audio) pass through unchanged.
"""

from __future__ import annotations

import io
import logging
import os

_logger = logging.getLogger("mcphub.wordpress.media.optimize")

try:
    from PIL import Image, ImageOps  # type: ignore
except Exception:  # pragma: no cover
    Image = None  # type: ignore
    ImageOps = None  # type: ignore

_DEFAULT_MAX_EDGE = int(os.environ.get("WP_MEDIA_MAX_EDGE", "2560"))
_DEFAULT_JPEG_QUALITY = int(os.environ.get("WP_MEDIA_JPEG_QUALITY", "85"))
# F.5a.8.1: optional output format override.
#   ""     → no conversion (current default, keeps source format)
#   "webp" → convert raster images to image/webp
#   "avif" → convert raster images to image/avif (requires Pillow≥9.2 with AVIF)
_DEFAULT_CONVERT_TO = os.environ.get("WP_MEDIA_CONVERT_TO", "").strip().lower()

_RASTER_MIMES = {"image/jpeg", "image/png", "image/webp", "image/bmp", "image/tiff"}

# Format map for the convert_to override. Values are (Pillow format, output MIME).
_CONVERT_TO_FORMATS: dict[str, tuple[str, str]] = {
    "webp": ("WEBP", "image/webp"),
    "avif": ("AVIF", "image/avif"),
}


def _avif_supported() -> bool:
    """Return True if the running Pillow actually decodes/encodes AVIF.

    We check at call time rather than import time so environments that
    upgrade Pillow without restarting still see support as it becomes
    available.
    """
    if Image is None:
        return False
    # Pillow registers the extension lazily; probing for a writer is more
    # reliable than checking the features module (which doesn't list AVIF
    # on every version).
    try:
        return "AVIF" in Image.registered_extensions().values()
    except Exception:  # pragma: no cover - defensive
        return False


def optimize(
    data: bytes,
    mime_hint: str | None,
    *,
    max_edge: int = _DEFAULT_MAX_EDGE,
    jpeg_quality: int = _DEFAULT_JPEG_QUALITY,
    strip_exif: bool = True,
    convert_to: str | None = None,
) -> tuple[bytes, str | None]:
    """Resize/recompress raster images.

    Args:
        data: raw image bytes.
        mime_hint: best-guess MIME from sniff/client; non-raster types are
            passed through unchanged.
        max_edge: long-edge pixel limit (default ``WP_MEDIA_MAX_EDGE`` or 2560).
        jpeg_quality: q parameter for JPEG / WebP / AVIF encoders.
        strip_exif: when True, apply ``ImageOps.exif_transpose`` to bake in
            rotation then drop the metadata.
        convert_to: force output format regardless of source. ``"webp"`` or
            ``"avif"``; ``None`` or ``""`` falls back to
            ``WP_MEDIA_CONVERT_TO`` then to source-format heuristics. When
            AVIF is requested but Pillow lacks AVIF support, falls back to
            WebP rather than silently writing the source bytes.

    Returns:
        ``(new_bytes, new_mime_or_original)``. If optimization produced
        larger output without resizing, the original bytes are returned.
    """
    if Image is None:
        return data, mime_hint

    if mime_hint and mime_hint not in _RASTER_MIMES:
        return data, mime_hint

    try:
        img = Image.open(io.BytesIO(data))
    except Exception:
        return data, mime_hint

    # Preserve animated GIFs untouched (single-frame re-encode would break them)
    if getattr(img, "is_animated", False):
        return data, mime_hint

    fmt = (img.format or "").upper()  # capture BEFORE exif_transpose strips .format

    try:
        img = ImageOps.exif_transpose(img) if strip_exif else img
    except Exception:
        pass

    w, h = img.size
    long_edge = max(w, h)

    resized = False
    if long_edge > max_edge:
        scale = max_edge / long_edge
        new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
        img = img.resize(new_size, Image.LANCZOS)
        resized = True

    # F.5a.8.1: explicit convert_to wins over the env default.
    requested_convert = (convert_to or _DEFAULT_CONVERT_TO or "").strip().lower()
    if requested_convert == "avif" and not _avif_supported():
        _logger.info("AVIF requested but Pillow lacks AVIF support; falling back to WebP.")
        requested_convert = "webp"

    has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)

    if requested_convert in _CONVERT_TO_FORMATS:
        out_fmt, out_mime = _CONVERT_TO_FORMATS[requested_convert]
        # Both WebP and AVIF support alpha; convert palette images to RGBA/RGB
        # so the encoder has a consistent colour model.
        if img.mode == "P":
            img = img.convert("RGBA" if has_alpha else "RGB")
        elif img.mode == "LA":
            img = img.convert("RGBA")
        elif img.mode == "L":
            img = img.convert("RGB")
    elif fmt == "PNG" and not has_alpha:
        # Opaque PNG → JPEG is typically smaller
        out_fmt = "JPEG"
        out_mime = "image/jpeg"
        if img.mode != "RGB":
            img = img.convert("RGB")
    elif fmt == "JPEG":
        out_fmt = "JPEG"
        out_mime = "image/jpeg"
        if img.mode != "RGB":
            img = img.convert("RGB")
    elif fmt == "WEBP":
        out_fmt = "WEBP"
        out_mime = "image/webp"
    elif fmt == "PNG":
        out_fmt = "PNG"
        out_mime = "image/png"
    else:
        # BMP/TIFF etc — convert to JPEG for web delivery
        out_fmt = "JPEG"
        out_mime = "image/jpeg"
        if img.mode != "RGB":
            img = img.convert("RGB")

    buf = io.BytesIO()
    save_kwargs: dict = {"optimize": True}
    if out_fmt == "JPEG":
        save_kwargs.update({"quality": jpeg_quality, "progressive": True})
    elif out_fmt == "WEBP":
        save_kwargs.update({"quality": jpeg_quality, "method": 6})
    elif out_fmt == "AVIF":
        save_kwargs.update({"quality": jpeg_quality})
    img.save(buf, format=out_fmt, **save_kwargs)
    new_bytes = buf.getvalue()

    # Explicit format conversion is honoured even if the converted bytes
    # are larger than the source (the caller asked for a format switch on
    # purpose — e.g. to serve WebP regardless). The size guard only applies
    # to the implicit recompression path.
    if not requested_convert and not resized and len(new_bytes) >= len(data):
        return data, mime_hint

    _logger.debug(
        "optimized %s %dx%d %dB -> %s %dB (resized=%s, convert=%s)",
        fmt,
        w,
        h,
        len(data),
        out_fmt,
        len(new_bytes),
        resized,
        requested_convert or "-",
    )
    return new_bytes, out_mime
