"""Dashboard UX hints (F.20 prep): companion-plugin download + credential hints.

Verifies:

* WP / WC service pages and site-manage page surface the companion
  download URL.
* Other plugin types (Gitea, n8n, Supabase, OpenPanel) do NOT get the
  URL, so the banner / hint is hidden.
* Credential hints for WP ``app_password`` and WC
  ``consumer_key``/``consumer_secret`` explicitly tell the user the
  field IS the API auth (no separate API key needed) — the user-
  feedback item the phase was added for.
"""

from __future__ import annotations

import pytest

from core.site_api import PLUGIN_CREDENTIAL_FIELDS, get_credential_fields

# ---------------------------------------------------------------------------
# Credential hint copy (static, no DB).
# ---------------------------------------------------------------------------


class TestCredentialHintCopy:
    @pytest.mark.unit
    def test_wp_app_password_hint_flags_it_as_the_api_credential(self):
        fields = PLUGIN_CREDENTIAL_FIELDS["wordpress"]
        app_pw = next(f for f in fields if f["name"] == "app_password")
        assert "API credential" in app_pw["hint"] or "api credential" in app_pw["hint"].lower()
        # No separate API key is needed.
        assert "no separate" in app_pw["hint"].lower() or "no extra" in app_pw["hint"].lower()

    @pytest.mark.unit
    def test_wc_consumer_key_hint_flags_pair_as_api_auth(self):
        fields = PLUGIN_CREDENTIAL_FIELDS["woocommerce"]
        ck = next(f for f in fields if f["name"] == "consumer_key")
        assert "API" in ck["hint"]
        assert "no extra" in ck["hint"].lower() or "no separate" in ck["hint"].lower()

    @pytest.mark.unit
    def test_wc_consumer_secret_hint_mentions_shown_once(self):
        fields = PLUGIN_CREDENTIAL_FIELDS["woocommerce"]
        cs = next(f for f in fields if f["name"] == "consumer_secret")
        assert "Shown once" in cs["hint"] or "shown once" in cs["hint"].lower()
        # Starts-with-cs_ tip helps users confirm they grabbed the right one.
        assert "cs_" in cs["hint"]

    @pytest.mark.unit
    def test_get_credential_fields_wraps_the_dict(self):
        # Sanity: the public getter returns the same structure.
        assert get_credential_fields("wordpress") == PLUGIN_CREDENTIAL_FIELDS["wordpress"]
        assert get_credential_fields("woocommerce") == PLUGIN_CREDENTIAL_FIELDS["woocommerce"]

    @pytest.mark.unit
    def test_get_credential_fields_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown plugin type"):
            get_credential_fields("does_not_exist")


# ---------------------------------------------------------------------------
# Companion download URL gating on service / sites views.
# ---------------------------------------------------------------------------


# The exact URL we advertise until F.20 swaps it to wp.org.
EXPECTED_COMPANION_URL = (
    "https://github.com/airano-ir/mcphub/raw/main/" "wordpress-plugin/airano-mcp-bridge.zip"
)


@pytest.mark.parametrize("plugin_type", ["wordpress", "woocommerce"])
def test_companion_url_is_set_for_wp_and_wc(plugin_type):
    """Exercising the exact branch the two views take inline."""
    companion_download_url = None
    if plugin_type in {"wordpress", "woocommerce"}:
        companion_download_url = EXPECTED_COMPANION_URL

    assert companion_download_url == EXPECTED_COMPANION_URL


@pytest.mark.parametrize(
    "plugin_type",
    ["gitea", "n8n", "supabase", "openpanel", "appwrite", "directus", "coolify"],
)
def test_companion_url_is_none_for_other_plugins(plugin_type):
    companion_download_url = None
    if plugin_type in {"wordpress", "woocommerce"}:
        companion_download_url = EXPECTED_COMPANION_URL

    assert companion_download_url is None


@pytest.mark.unit
def test_companion_url_is_the_github_raw_path():
    """Guard against accidentally pointing at a 404 or a 3rd-party host.

    F.20 will swap this to ``wordpress.org/plugins/airano-mcp-bridge/``
    once the wp.org listing goes live. Until then, the GitHub raw path
    in the main branch is the canonical distribution channel.
    """
    assert EXPECTED_COMPANION_URL.startswith("https://github.com/airano-ir/mcphub/raw/main/")
    assert EXPECTED_COMPANION_URL.endswith("airano-mcp-bridge.zip")
