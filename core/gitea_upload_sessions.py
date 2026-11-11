"""Metadata helpers for Gitea HTTP binary upload sessions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from core.database import Database

GITEA_UPLOAD_SESSION_MIME = "application/vnd.mcphub.gitea-upload"


def is_gitea_upload_mime(mime: str | None) -> bool:
    """Return true for the Gitea upload session MIME and target variants."""
    return bool(mime) and (
        mime == GITEA_UPLOAD_SESSION_MIME or mime.startswith(f"{GITEA_UPLOAD_SESSION_MIME};")
    )


def make_gitea_upload_mime(kind: str, target: dict[str, Any]) -> str:
    """Build a MIME marker that makes upload_sessions ids target-specific."""
    payload = json.dumps({"kind": kind, "target": target}, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{GITEA_UPLOAD_SESSION_MIME};kind={kind};target={digest}"


@dataclass(frozen=True)
class GiteaUploadMetadata:
    session_id: str
    owner_user_id: str
    site_id: str
    alias: str
    plugin_type: str
    kind: str
    target: dict[str, Any]
    created_at: str

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> GiteaUploadMetadata:
        return cls(
            session_id=row["session_id"],
            owner_user_id=row["owner_user_id"],
            site_id=row["site_id"],
            alias=row["alias"],
            plugin_type=row["plugin_type"],
            kind=row["kind"],
            target=json.loads(row["target_json"]),
            created_at=row["created_at"],
        )

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "site_id": self.site_id,
            "alias": self.alias,
            "plugin_type": self.plugin_type,
            "target": dict(self.target),
        }


async def upsert_gitea_upload_metadata(
    db: Database,
    *,
    session_id: str,
    owner_user_id: str,
    site_id: str,
    alias: str,
    kind: str,
    target: dict[str, Any],
) -> GiteaUploadMetadata:
    target_json = json.dumps(target, sort_keys=True, separators=(",", ":"))
    created_at = datetime.now(UTC).isoformat()
    await db.execute(
        "INSERT OR REPLACE INTO gitea_upload_sessions "
        "(session_id, owner_user_id, site_id, alias, plugin_type, kind, target_json, created_at) "
        "VALUES (?, ?, ?, ?, 'gitea', ?, ?, ?)",
        (session_id, owner_user_id, site_id, alias, kind, target_json, created_at),
    )
    return GiteaUploadMetadata(
        session_id=session_id,
        owner_user_id=owner_user_id,
        site_id=site_id,
        alias=alias,
        plugin_type="gitea",
        kind=kind,
        target=dict(target),
        created_at=created_at,
    )


async def get_gitea_upload_metadata(
    db: Database,
    session_id: str,
) -> GiteaUploadMetadata | None:
    row = await db.fetchone(
        "SELECT * FROM gitea_upload_sessions WHERE session_id = ?",
        (session_id,),
    )
    return GiteaUploadMetadata.from_row(row) if row else None


async def delete_gitea_upload_metadata(db: Database, session_id: str) -> None:
    await db.execute("DELETE FROM gitea_upload_sessions WHERE session_id = ?", (session_id,))
