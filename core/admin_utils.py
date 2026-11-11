"""Admin utility functions for role determination.

Centralizes admin email checking so it can be used in OAuth callback,
dashboard auth, and future admin/user panel unification (F.5+).
"""

import os


def is_admin_email(email: str | None) -> bool:
    """Check if an email is in the ADMIN_EMAILS env var list.

    Args:
        email: Email address to check.

    Returns:
        True if email matches an admin email (case-insensitive).
    """
    if not email:
        return False

    admin_emails_raw = os.environ.get("ADMIN_EMAILS", "")
    if not admin_emails_raw.strip():
        return False

    admin_emails = {e.strip().lower() for e in admin_emails_raw.split(",") if e.strip()}
    return email.strip().lower() in admin_emails


def is_admin_user_record(user: dict | None) -> bool:
    """Check whether a DB user record belongs to an admin.

    An admin is a user whose DB role is ``admin`` or whose email is listed in
    ``ADMIN_EMAILS``. This is the single trust boundary for admin exemptions
    (site limit, rate limit, plugin visibility, private site destinations).

    Args:
        user: User row as returned by ``Database.get_user_by_id`` (or None).

    Returns:
        True if the user is an admin.
    """
    if not isinstance(user, dict):
        return False
    return user.get("role") == "admin" or is_admin_email(user.get("email"))


async def user_id_is_admin(user_id: str | None) -> bool:
    """Look a user up by id and report whether they are an admin.

    Fails closed: any lookup error (no database, unknown user) returns False.

    Args:
        user_id: User UUID.

    Returns:
        True if the user exists and is an admin.
    """
    if not user_id:
        return False
    try:
        from core.database import get_database

        user = await get_database().get_user_by_id(user_id)
    except Exception:
        return False
    return is_admin_user_record(user)
