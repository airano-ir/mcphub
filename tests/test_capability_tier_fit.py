"""F.7e — ``evaluate_tier_fit`` + ``TIER_REQUIREMENTS`` coverage."""

from __future__ import annotations

import pytest

from core.capability_probe import (
    TIER_REQUIREMENTS,
    _cap_matches,
    evaluate_tier_fit,
)

# ---------------------------------------------------------------------------
# TIER_REQUIREMENTS sanity
# ---------------------------------------------------------------------------


class TestTierRequirementsTable:
    @pytest.mark.unit
    def test_all_three_tiers_for_every_mapped_plugin(self):
        for plugin_type, tiers in TIER_REQUIREMENTS.items():
            assert {"read", "write", "admin"} <= set(tiers.keys()), f"{plugin_type} missing a tier"

    @pytest.mark.unit
    def test_requirements_are_non_empty_sets(self):
        for plugin_type, tiers in TIER_REQUIREMENTS.items():
            for tier, reqs in tiers.items():
                assert isinstance(reqs, set), f"{plugin_type}/{tier} is not a set"
                assert reqs, f"{plugin_type}/{tier} has no required caps"


# ---------------------------------------------------------------------------
# _cap_matches: canonical + alias resolution
# ---------------------------------------------------------------------------


class TestCapMatches:
    @pytest.mark.unit
    def test_exact_match(self):
        assert _cap_matches("read", {"read"})
        assert _cap_matches("manage_options", {"manage_options"})

    @pytest.mark.unit
    def test_role_satisfies_capability_alias(self):
        # WP role -> implied capability
        assert _cap_matches("manage_options", {"administrator"})
        assert _cap_matches("edit_posts", {"editor"})
        assert _cap_matches("read", {"subscriber"})

    @pytest.mark.unit
    def test_read_write_satisfies_read_and_write(self):
        # WC "read_write" permission satisfies both read_* and write_*.
        assert _cap_matches("read_products", {"read_write"})
        assert _cap_matches("write_products", {"read_write"})

    @pytest.mark.unit
    def test_missing_capability(self):
        assert not _cap_matches("manage_options", {"edit_posts"})
        assert not _cap_matches("write_products", {"read"})


# ---------------------------------------------------------------------------
# evaluate_tier_fit: probe-unavailable path
# ---------------------------------------------------------------------------


class TestEvaluateTierFit:
    @pytest.mark.unit
    def test_probe_unavailable_short_circuits(self):
        fit = evaluate_tier_fit(
            "wordpress",
            "admin",
            {"probe_available": False, "reason": "companion_not_installed"},
        )
        assert fit["status"] == "probe_unavailable"
        assert fit["reason"] == "companion_not_installed"
        assert fit["missing"] == []

    @pytest.mark.unit
    def test_custom_tier_is_always_ok(self):
        # "custom" means the caller cherry-picked tools — no tier-level
        # contract to validate.
        fit = evaluate_tier_fit(
            "wordpress",
            "custom",
            {"probe_available": True, "granted": ["read"]},
        )
        assert fit["status"] == "ok"
        assert fit["required"] == []
        assert fit["missing"] == []

    @pytest.mark.unit
    def test_none_tier_is_always_ok(self):
        fit = evaluate_tier_fit(
            "wordpress",
            None,
            {"probe_available": True, "granted": ["read"]},
        )
        assert fit["status"] == "ok"

    @pytest.mark.unit
    def test_unknown_tier_for_plugin_returns_unknown(self):
        fit = evaluate_tier_fit(
            "wordpress",
            "deploy",  # not in WP's table
            {"probe_available": True, "granted": ["read"]},
        )
        assert fit["status"] == "unknown_tier"

    @pytest.mark.unit
    def test_unknown_plugin_returns_unknown(self):
        fit = evaluate_tier_fit(
            "n8n",  # no tier table
            "read",
            {"probe_available": True, "granted": ["read"]},
        )
        assert fit["status"] == "unknown_tier"


class TestWordPressFit:
    @pytest.mark.unit
    def test_admin_tier_with_administrator_role_is_ok(self):
        fit = evaluate_tier_fit(
            "wordpress",
            "admin",
            {
                "probe_available": True,
                "granted": ["administrator", "manage_options", "upload_files"],
            },
        )
        assert fit["status"] == "ok"
        assert fit["missing"] == []

    @pytest.mark.unit
    def test_admin_tier_with_editor_role_warns_missing_manage_options(self):
        fit = evaluate_tier_fit(
            "wordpress",
            "admin",
            {"probe_available": True, "granted": ["editor", "edit_posts", "upload_files"]},
        )
        assert fit["status"] == "warning"
        assert "manage_options" in fit["missing"]

    @pytest.mark.unit
    def test_write_tier_with_editor_role_is_ok(self):
        fit = evaluate_tier_fit(
            "wordpress",
            "write",
            {"probe_available": True, "granted": ["editor"]},
        )
        # editor alias covers edit_posts + upload_files.
        assert fit["status"] == "ok"

    @pytest.mark.unit
    def test_read_tier_with_subscriber_is_ok(self):
        fit = evaluate_tier_fit(
            "wordpress",
            "read",
            {"probe_available": True, "granted": ["subscriber"]},
        )
        assert fit["status"] == "ok"


class TestWooCommerceFit:
    @pytest.mark.unit
    def test_read_key_satisfies_read_tier(self):
        fit = evaluate_tier_fit(
            "woocommerce",
            "read",
            {"probe_available": True, "granted": ["read_products", "read_orders"]},
        )
        assert fit["status"] == "ok"

    @pytest.mark.unit
    def test_read_key_fails_write_tier(self):
        fit = evaluate_tier_fit(
            "woocommerce",
            "write",
            {"probe_available": True, "granted": ["read_products", "read_orders"]},
        )
        assert fit["status"] == "warning"
        assert "write_products" in fit["missing"]

    @pytest.mark.unit
    def test_read_write_key_satisfies_both(self):
        # Using the raw permission alias "read_write" directly.
        fit_read = evaluate_tier_fit(
            "woocommerce",
            "read",
            {"probe_available": True, "granted": ["read_write"]},
        )
        fit_write = evaluate_tier_fit(
            "woocommerce",
            "write",
            {"probe_available": True, "granted": ["read_write"]},
        )
        assert fit_read["status"] == "ok"
        assert fit_write["status"] == "ok"


class TestGiteaFit:
    @pytest.mark.unit
    def test_admin_tier_needs_admin_repo_hook(self):
        fit = evaluate_tier_fit(
            "gitea",
            "admin",
            {
                "probe_available": True,
                "granted": ["read:repository", "write:repository"],
            },
        )
        assert fit["status"] == "warning"
        assert "admin:repo_hook" in fit["missing"]

    @pytest.mark.unit
    def test_write_tier_with_write_scope_ok(self):
        fit = evaluate_tier_fit(
            "gitea",
            "write",
            {"probe_available": True, "granted": ["write:repository"]},
        )
        assert fit["status"] == "ok"

    @pytest.mark.unit
    def test_read_tier_with_only_user_scope_warns(self):
        fit = evaluate_tier_fit(
            "gitea",
            "read",
            {"probe_available": True, "granted": ["read:user"]},
        )
        assert fit["status"] == "warning"
        assert "read:repository" in fit["missing"]
