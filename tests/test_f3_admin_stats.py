"""Tests for admin dashboard stats (Phase F.3)."""

from core.dashboard.routes import get_dashboard_stats


class TestAdminDashboardStats:
    """Test admin dashboard statistics include platform data."""

    async def test_stats_include_users_count(self):
        """Verify users_count is present in admin stats."""
        stats = await get_dashboard_stats()
        assert "users_count" in stats

    async def test_stats_include_user_sites_count(self):
        """Verify user_sites_count is present in admin stats."""
        stats = await get_dashboard_stats()
        assert "user_sites_count" in stats
