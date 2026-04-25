"""F.5a.6.2 — Error-code taxonomy stability test.

Walks every raise-site in the media stack, extracts the literal error
code, and asserts each one is in the documented
:data:`core.media_error_codes.MEDIA_ERROR_CODES` set (or matches the
dynamic ``WP_<status>`` pattern).

If this test fails, you're either:
  - Introducing a new code — add it to ``MEDIA_ERROR_CODES`` *and*
    ``docs/media-error-codes.md``, or
  - Removing a documented code — make sure it's actually unused and drop
    it from both the set and the docs.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from core.media_error_codes import MEDIA_ERROR_CODES, is_valid_code

REPO_ROOT = Path(__file__).resolve().parents[3]

# Files to scan for error-code literals.
SCANNED_FILES = [
    "plugins/wordpress/handlers/_media_security.py",
    "plugins/wordpress/handlers/_media_core.py",
    "plugins/wordpress/handlers/media.py",
    "plugins/wordpress/handlers/media_attach.py",
    "plugins/wordpress/handlers/media_chunked.py",
    "plugins/wordpress/handlers/ai_media.py",
    "core/upload_sessions.py",
    "core/tool_rate_limiter.py",
    "plugins/ai_image/providers/base.py",
    "plugins/ai_image/providers/openai.py",
    "plugins/ai_image/providers/stability.py",
    "plugins/ai_image/providers/replicate.py",
    "plugins/ai_image/registry.py",
]

# Literal raise-site patterns. Multiline to span wrapped calls.
_RAISE_RE = re.compile(
    r'raise\s+(?:UploadError|UploadSessionError|ProviderError)\s*\(\s*"([A-Z][A-Z0-9_]+)"',
    re.MULTILINE,
)
# Formatted (f-string) codes like f"WP_{response.status}" — we assert the
# pattern prefix is a valid dynamic code.
_FSTRING_RE = re.compile(
    r"raise\s+(?:UploadError|UploadSessionError|ProviderError)\s*\(\s*" r'f"([A-Z_]+)\{',
    re.MULTILINE,
)
# Hard-coded error_code dict literals like {"error_code": "INTERNAL", ...}
_ERROR_CODE_RE = re.compile(r'"error_code"\s*:\s*"([A-Z][A-Z0-9_]+)"')


def _collect_codes() -> tuple[set[str], set[str]]:
    literal_codes: set[str] = set()
    fstring_prefixes: set[str] = set()
    for rel in SCANNED_FILES:
        path = REPO_ROOT / rel
        text = path.read_text(encoding="utf-8")
        literal_codes.update(_RAISE_RE.findall(text))
        literal_codes.update(_ERROR_CODE_RE.findall(text))
        fstring_prefixes.update(_FSTRING_RE.findall(text))
    return literal_codes, fstring_prefixes


def test_every_raise_site_uses_documented_code():
    literal_codes, fstring_prefixes = _collect_codes()
    assert literal_codes, "taxonomy test found no raise sites — scanner broken?"

    undocumented = {c for c in literal_codes if not is_valid_code(c)}
    assert not undocumented, (
        f"Undocumented error codes in raise sites: {sorted(undocumented)}. "
        f"Add them to core.media_error_codes.MEDIA_ERROR_CODES and "
        f"docs/media-error-codes.md, or remove the raise site."
    )

    # f-string codes must have a documented prefix (e.g. "WP_" for WP_{status}
    # or "COMPANION_" for COMPANION_{status} from the F.5a.7 upload-chunk route).
    allowed_prefixes = {"WP_", "COMPANION_"}
    for prefix in fstring_prefixes:
        assert prefix in allowed_prefixes, (
            f"Unknown dynamic error-code prefix '{prefix}'. "
            f"Allowed prefixes: {sorted(allowed_prefixes)} (see is_valid_code)."
        )


def test_documented_codes_are_all_used():
    """Stability guard: every documented code has at least one raise/use site.

    Prevents the documented set from drifting with dead entries. A small
    allow-list exists for codes that are reserved for upcoming work.
    """
    literal_codes, _ = _collect_codes()
    reserved: set[str] = set()  # None currently reserved.
    unused = MEDIA_ERROR_CODES - literal_codes - reserved
    # WP_<status> is dynamic; its fixed siblings (WP_413, WP_AUTH, WP_BAD_RESPONSE)
    # must be explicitly raised.
    assert not unused, (
        f"Documented codes with no raise site: {sorted(unused)}. "
        "Either wire them up, move to the 'reserved' set, or remove them."
    )


@pytest.mark.parametrize("code", sorted(MEDIA_ERROR_CODES))
def test_is_valid_code_accepts_documented(code):
    assert is_valid_code(code)


@pytest.mark.parametrize("code", ["WP_400", "WP_500", "WP_418"])
def test_is_valid_code_accepts_dynamic_wp_status(code):
    assert is_valid_code(code)


@pytest.mark.parametrize("code", ["UNKNOWN", "wp_413", "WP_", "WP_X", "WP_41"])
def test_is_valid_code_rejects_others(code):
    assert not is_valid_code(code)
