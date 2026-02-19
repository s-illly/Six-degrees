import re
from urllib.parse import unquote, urlparse

from sqlalchemy import or_
from sqlalchemy.orm import Session

from models import Connection, GhostEdge, GhostProfile, User


def normalize_linkedin_slug(value: str) -> str:
    s = (value or "").strip()
    if not s:
        return ""

    s = s.lstrip("@").strip()
    s = re.sub(r"\s+", "", s)

    # If user pasted "linkedin.com/in/janedoe" without scheme, urlparse won't parse hostname.
    if "linkedin.com" in s.lower() and not s.lower().startswith(("http://", "https://")):
        s = "https://" + s

    slug = ""
    if s.lower().startswith(("http://", "https://")):
        parsed = urlparse(s)
        path = parsed.path or ""
        m = re.search(r"/(?:in|pub)/([^/?#]+)", path, flags=re.IGNORECASE)
        if m:
            slug = m.group(1)
        else:
            parts = [p for p in path.split("/") if p]
            slug = parts[-1] if parts else ""
    else:
        m = re.search(r"(?:^|/)(?:in|pub)/([^/?#]+)", s, flags=re.IGNORECASE)
        slug = m.group(1) if m else s

    slug = unquote(slug)
    slug = re.sub(r"[?#].*$", "", slug).strip().strip("/")
    slug = slug.lower()

    if "linkedin.com" in s.lower():
        # If it still looks like LinkedIn but no profile identifier was extracted, reject.
        if not slug:
            return ""
        if "linkedin.com" in slug:
            return ""
        if slug in {"in", "pub"}:
            return ""

    return slug


def find_ghost_profiles_for_slug(db: Session, slug: str) -> list[GhostProfile]:
    normalized = normalize_linkedin_slug(slug)
    if not normalized:
        return []

    # Exact match (newer data) + loose matches (legacy data where full URL was stored).
    candidates = (
        db.query(GhostProfile)
        .filter(
            or_(
                GhostProfile.linkedin_slug == normalized,
                GhostProfile.linkedin_slug.ilike(f"%/in/{normalized}%"),
                GhostProfile.linkedin_slug.ilike(f"%linkedin.com/in/{normalized}%"),
                GhostProfile.linkedin_slug.ilike(f"%{normalized}%"),
            )
        )
        .all()
    )

    out: dict[str, GhostProfile] = {}
    for g in candidates:
        if normalize_linkedin_slug(g.linkedin_slug) == normalized:
            out[g.id] = g
    return list(out.values())


def migrate_ghost_edges_to_user(db: Session, user: User, slug: str) -> int:
    normalized = normalize_linkedin_slug(slug)
    if not normalized:
        return 0

    ghosts = find_ghost_profiles_for_slug(db, normalized)
    if not ghosts:
        return 0

    migrated = 0
    for ghost in ghosts:
        pending_edges = db.query(GhostEdge).filter(GhostEdge.ghost_id == ghost.id).all()

        for pe in pending_edges:
            # Convert ghost edge to a real user-user connection.
            if pe.src_user_id == user.id:
                db.delete(pe)
                continue

            a = min(pe.src_user_id, user.id)
            b = max(pe.src_user_id, user.id)

            exists = db.query(Connection).filter(Connection.user_id_1 == a, Connection.user_id_2 == b).first()
            if not exists:
                db.add(Connection(user_id_1=a, user_id_2=b))
                migrated += 1

            db.delete(pe)

        db.delete(ghost)

    return migrated
