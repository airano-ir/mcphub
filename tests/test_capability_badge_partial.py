"""F.X.fix #9 — capability badge HTMX partial endpoint + template.

Regression: the Re-check button called ``window.location.reload()``,
which is jarring on slow networks and discards unrelated unsaved
state on the page. Fix: swap the badge in place via HTMX. The button
now carries ``hx-get="/api/sites/{id}/capabilities/badge"`` and the
target element has a matching id.

These tests don't spin up Starlette — they verify the two contracts
the front end depends on:

  1. The partial template contains the right HTMX attrs (hx-get,
     hx-target, hx-swap outerHTML) so the button actually triggers a
     swap of just the badge element.
  2. The new Starlette handler name is importable from
     ``core.capability_probe`` and wired under
     /api/sites/{id}/capabilities/badge in server.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest

BADGE_PARTIAL = (
    Path(__file__).resolve().parent.parent / "core/templates/dashboard/sites/_capability_badge.html"
)
MANAGE_PAGE = Path(__file__).resolve().parent.parent / "core/templates/dashboard/sites/manage.html"
SERVER_PY = Path(__file__).resolve().parent.parent / "server.py"


class TestBadgePartialTemplate:
    @pytest.mark.unit
    def test_partial_exists(self):
        assert BADGE_PARTIAL.is_file(), "_capability_badge.html partial must exist"

    @pytest.mark.unit
    def test_partial_has_stable_target_id(self):
        text = BADGE_PARTIAL.read_text()
        # The target id MUST match the hx-target value and the manage.html
        # container id the old JS used.
        assert 'id="capability-badge"' in text

    @pytest.mark.unit
    def test_partial_has_htmx_attrs(self):
        text = BADGE_PARTIAL.read_text()
        assert 'hx-get="/api/sites/{{ site.id }}/capabilities/badge?force=1"' in text
        assert 'hx-target="#capability-badge"' in text
        assert 'hx-swap="outerHTML"' in text

    @pytest.mark.unit
    def test_partial_renders_all_four_fit_states(self):
        text = BADGE_PARTIAL.read_text()
        # One branch per fit.status value produced by evaluate_tier_fit.
        for state in ("ok", "warning", "probe_unavailable", "unknown_tier"):
            assert state in text, f"partial missing branch for status={state!r}"


class TestManagePageUsesPartial:
    @pytest.mark.unit
    def test_manage_page_includes_partial(self):
        text = MANAGE_PAGE.read_text()
        assert '"dashboard/sites/_capability_badge.html"' in text

    @pytest.mark.unit
    def test_legacy_reload_shim_is_gone(self):
        text = MANAGE_PAGE.read_text()
        # The old window.location.reload()-based recheck must not be
        # the mechanism any more.
        assert "__capabilityProbe.recheck()" not in text
        assert "window.__capabilityProbe" not in text


class TestHandlerIsWired:
    @pytest.mark.unit
    def test_handler_importable(self):
        from core.capability_probe import api_site_capabilities_badge

        assert callable(api_site_capabilities_badge)

    @pytest.mark.unit
    def test_route_registered_in_server_py(self):
        text = SERVER_PY.read_text()
        assert "/api/sites/{id}/capabilities/badge" in text
        assert "api_site_capabilities_badge" in text
