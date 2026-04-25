"""F.X.fix #5 — tier-fit for the WP ``read`` tier recognises role names.

Regression: every admin probe showed ``status=warning, missing=['read']``
because the companion capability payload places WP role strings under
``roles`` (e.g. ``administrator``) while the bare ``read`` capability
is only implied by the role and never written out as a standalone cap.
The ``_cap_matches`` alias resolver understood the mapping but was
only fed ``granted`` — not ``granted ∪ roles``.
"""

from __future__ import annotations

import pytest

from core.capability_probe import evaluate_tier_fit

# Realistic admin probe payload captured from Phase A of F.X.test on
# blog.example.com. Only the fields that ``evaluate_tier_fit``
# actually reads are kept.
ADMIN_PROBE_PAYLOAD = {
    "probe_available": True,
    "granted": [
        "delete_others_pages",
        "delete_others_posts",
        "delete_pages",
        "delete_posts",
        "delete_private_pages",
        "delete_private_posts",
        "delete_published_pages",
        "delete_published_posts",
        "edit_others_pages",
        "edit_others_posts",
        "edit_pages",
        "edit_posts",
        "manage_options",
        "moderate_comments",
        "upload_files",
    ],
    "roles": ["administrator"],
    "plugin_version": "2.9.0",
}


@pytest.mark.unit
class TestReadTierForAdminRoles:
    def test_read_tier_ok_when_only_role_is_administrator(self):
        # Admin user: ``read`` is implied by the role, not present in
        # granted. Before the fix this returned status=warning.
        fit = evaluate_tier_fit(
            plugin_type="wordpress",
            tier="read",
            probe_payload=ADMIN_PROBE_PAYLOAD,
        )
        assert fit["status"] == "ok"
        assert fit["missing"] == []

    def test_read_tier_ok_for_subscriber_role_only(self):
        # Subscriber: no caps in granted, but ``subscriber`` role
        # implies ``read``. This was also broken before the fix.
        payload = {
            "probe_available": True,
            "granted": [],
            "roles": ["subscriber"],
        }
        fit = evaluate_tier_fit(
            plugin_type="wordpress",
            tier="read",
            probe_payload=payload,
        )
        assert fit["status"] == "ok"

    def test_write_tier_ok_when_editor_role_present(self):
        # ``edit_posts`` aliases cover ``editor`` and ``administrator``
        # roles — this was the alias resolver's job all along; with
        # the fix it now also works when the cap only arrives via
        # ``roles`` (edge case but possible for leaner probes).
        payload = {
            "probe_available": True,
            "granted": ["upload_files"],  # one required cap missing from granted
            "roles": ["editor"],
        }
        fit = evaluate_tier_fit(
            plugin_type="wordpress",
            tier="write",
            probe_payload=payload,
        )
        assert fit["status"] == "ok"
        assert fit["missing"] == []


@pytest.mark.unit
class TestWarningStillFiresForUnderPrivileged:
    def test_read_tier_warning_when_no_role_and_no_cap(self):
        # Sanity: the union doesn't silence ALL missing-cap warnings,
        # only the "role implies cap" bucket.
        payload = {
            "probe_available": True,
            "granted": [],
            "roles": [],
        }
        fit = evaluate_tier_fit(
            plugin_type="wordpress",
            tier="read",
            probe_payload=payload,
        )
        assert fit["status"] == "warning"
        assert fit["missing"] == ["read"]

    def test_admin_tier_still_requires_manage_options(self):
        # An editor cannot satisfy the admin tier — roles are in the
        # union but manage_options still isn't granted.
        payload = {
            "probe_available": True,
            "granted": ["edit_posts", "upload_files"],
            "roles": ["editor"],
        }
        fit = evaluate_tier_fit(
            plugin_type="wordpress",
            tier="admin",
            probe_payload=payload,
        )
        assert fit["status"] == "warning"
        assert fit["missing"] == ["manage_options"]
