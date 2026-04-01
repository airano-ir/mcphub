"""Utility functions for OpenPanel handlers"""

from plugins.openpanel.client import OpenPanelClient


def get_project_id(client: OpenPanelClient, project_id: str | None) -> str:
    """
    Get effective project_id, using default if not provided.

    Args:
        client: OpenPanel client with potential default_project_id
        project_id: Explicitly provided project_id (may be None)

    Returns:
        Effective project_id to use

    Raises:
        ValueError: If no project_id available
    """
    if project_id:
        return project_id
    if client.default_project_id:
        return client.default_project_id
    raise ValueError(
        "project_id is required. Either provide it as a parameter or configure "
        "the project_id field when adding the site in the dashboard. "
        "You can find your Project ID in OpenPanel Dashboard → Project Settings."
    )
