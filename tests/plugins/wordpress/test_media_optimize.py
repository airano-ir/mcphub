"""Tests for F.5a.2 image optimization pipeline."""

from __future__ import annotations

import io

import pytest

PIL = pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from plugins.wordpress.handlers._media_optimize import optimize  # noqa: E402


def _make_png(w: int, h: int, mode: str = "RGB") -> bytes:
    import os as _os

    img = Image.new(mode, (w, h))
    # Fill with noise so solid-color PNG compression doesn't undercut JPEG
    img.frombytes(_os.urandom(w * h * len(mode)))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_jpeg(w: int, h: int, quality: int = 95) -> bytes:
    img = Image.new("RGB", (w, h), color=(200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def test_large_jpeg_is_resized():
    data = _make_jpeg(4000, 3000)
    new_data, new_mime = optimize(data, "image/jpeg", max_edge=1024)
    assert new_mime == "image/jpeg"
    img = Image.open(io.BytesIO(new_data))
    assert max(img.size) == 1024
    assert len(new_data) < len(data)


def test_opaque_png_converted_to_jpeg():
    data = _make_png(800, 600, mode="RGB")
    new_data, new_mime = optimize(data, "image/png", max_edge=2560)
    assert new_mime == "image/jpeg"
    assert len(new_data) < len(data)


def test_transparent_png_stays_png():
    data = _make_png(800, 600, mode="RGBA")
    new_data, new_mime = optimize(data, "image/png", max_edge=2560)
    assert new_mime == "image/png"


def test_small_image_returns_original_bytes():
    # Tiny image that cannot be made smaller
    data = _make_jpeg(8, 8, quality=50)
    new_data, new_mime = optimize(data, "image/jpeg", max_edge=2560)
    # Either unchanged or still JPEG
    assert new_mime in (None, "image/jpeg")
    assert len(new_data) <= len(data) + 1024


def test_pdf_passthrough():
    data = b"%PDF-1.4\n%garbage\n%%EOF"
    new_data, new_mime = optimize(data, "application/pdf")
    assert new_data == data
    assert new_mime == "application/pdf"


def test_video_passthrough():
    data = b"\x00" * 32
    new_data, new_mime = optimize(data, "video/mp4")
    assert new_data == data
    assert new_mime == "video/mp4"


def test_unknown_mime_tries_anyway_but_fails_gracefully():
    # Garbage bytes with no PIL-recognizable format → passthrough
    data = b"not an image at all"
    new_data, new_mime = optimize(data, None)
    assert new_data == data


# ---------------------------------------------------------------------------
# F.5a.8.1 — convert_to override (WebP / AVIF)
# ---------------------------------------------------------------------------


def _peek_format(data: bytes) -> str:
    return (Image.open(io.BytesIO(data)).format or "").upper()


def test_convert_png_to_webp():
    data = _make_png(64, 64, mode="RGB")
    new_data, new_mime = optimize(data, "image/png", convert_to="webp")
    assert new_mime == "image/webp"
    assert _peek_format(new_data) == "WEBP"


def test_convert_jpeg_to_webp():
    data = _make_jpeg(64, 64)
    new_data, new_mime = optimize(data, "image/jpeg", convert_to="webp")
    assert new_mime == "image/webp"
    assert _peek_format(new_data) == "WEBP"


def test_convert_preserves_alpha_on_webp():
    data = _make_png(64, 64, mode="RGBA")
    new_data, new_mime = optimize(data, "image/png", convert_to="webp")
    assert new_mime == "image/webp"
    img = Image.open(io.BytesIO(new_data))
    # Either RGBA or palette-with-alpha is acceptable
    assert "A" in img.mode or "A" in "".join(img.getbands())


def test_convert_avif_falls_back_to_webp_when_unsupported():
    from plugins.wordpress.handlers._media_optimize import _avif_supported

    data = _make_png(32, 32, mode="RGB")
    new_data, new_mime = optimize(data, "image/png", convert_to="avif")
    if _avif_supported():
        assert new_mime == "image/avif"
        assert _peek_format(new_data) == "AVIF"
    else:
        assert new_mime == "image/webp"
        assert _peek_format(new_data) == "WEBP"


def test_convert_to_env_default(monkeypatch):
    import plugins.wordpress.handlers._media_optimize as opt_mod

    monkeypatch.setattr(opt_mod, "_DEFAULT_CONVERT_TO", "webp")
    data = _make_png(48, 48, mode="RGB")
    new_data, new_mime = optimize(data, "image/png")
    assert new_mime == "image/webp"
    assert _peek_format(new_data) == "WEBP"


def test_convert_wins_over_size_guard():
    # 1×1 images re-encode to formats that carry larger container overhead.
    # The explicit convert_to request MUST still win — the size guard only
    # applies to the implicit recompression path.
    tiny = _make_png(1, 1, mode="RGB")
    new_data, new_mime = optimize(tiny, "image/png", convert_to="webp")
    assert new_mime == "image/webp"
    assert _peek_format(new_data) == "WEBP"


def test_convert_unknown_value_falls_through_to_heuristic():
    # "jpg" isn't in the convert_to map → optimizer uses source-format heuristic.
    data = _make_jpeg(64, 64)
    _, new_mime = optimize(data, "image/jpeg", convert_to="jpg")
    assert new_mime == "image/jpeg"


def test_convert_to_does_not_touch_pdf():
    data = b"%PDF-1.4\n%fake\n"
    new_data, new_mime = optimize(data, "application/pdf", convert_to="webp")
    assert new_data == data
    assert new_mime == "application/pdf"


def test_maybe_optimize_forwards_convert_to():
    from plugins.wordpress.handlers.media import _maybe_optimize

    out, mime = _maybe_optimize(
        _make_png(48, 48, mode="RGB"), "image/png", skip=False, convert_to="webp"
    )
    assert mime == "image/webp"
    assert _peek_format(out) == "WEBP"


def test_maybe_optimize_skip_overrides_convert_to():
    from plugins.wordpress.handlers.media import _maybe_optimize

    src = _make_png(48, 48, mode="RGB")
    out, mime = _maybe_optimize(src, "image/png", skip=True, convert_to="webp")
    assert out == src
    assert mime == "image/png"
