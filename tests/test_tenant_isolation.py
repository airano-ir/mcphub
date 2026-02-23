"""Tests for tenant isolation in Dashboard routes."""

import pytest
from core.dashboard.routes import get_all_projects
from core.site_manager import SiteManager, SiteConfig

@pytest.mark.asyncio
async def test_get_all_projects_tenant_isolation(monkeypatch):
    """Normal user should only see their own sites, ignoring global ones."""
    
    # Mock SiteManager with some global and user sites
    mgr = SiteManager()
    
    # Global site (no user_id)
    mgr.register_site(SiteConfig(site_id="global1", plugin_type="wordpress"))
    
    # User 123's site
    mgr.register_site(SiteConfig(
        site_id="user1site", 
        plugin_type="wordpress", 
        user_id="user-123"
    ))
    
    monkeypatch.setattr("core.site_manager.get_site_manager", lambda: mgr)
    
    # Normal user 456 (has no sites)
    session_456 = {"user_id": "user-456", "type": "user"}
    res = await get_all_projects(user_session=session_456)
    assert len(res["projects"]) == 0
    
    # Normal user 123 (has 1 site)
    session_123 = {"user_id": "user-123", "type": "user"}
    res = await get_all_projects(user_session=session_123)
    assert len(res["projects"]) == 1
    assert res["projects"][0]["site_id"] == "user1site"
    
    # Master user (sees all)
    class DummyMaster:
        user_type = "master"
    
    res = await get_all_projects(user_session=DummyMaster())
    assert len(res["projects"]) == 2
