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
