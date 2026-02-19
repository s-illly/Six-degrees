import re
from urllib.parse import unquote, urlparse

from typing import Dict, List, Optional

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

    out: Dict[str, GhostProfile] = {}
    for g in candidates:
        if normalize_linkedin_slug(g.linkedin_slug) == normalized:
            out[g.id] = g
    return list(out.values())


def find_user_for_slug(db: Session, slug: str) -> Optional[User]:
    normalized = normalize_linkedin_slug(slug)
    if not normalized:
        return None

    candidates = (
        db.query(User)
        .filter(
            or_(
                User.linkedin_slug == normalized,
                User.linkedin_slug.ilike(f"%/in/{normalized}%"),
                User.linkedin_slug.ilike(f"%linkedin.com/in/{normalized}%"),
                User.linkedin_slug.ilike(f"%{normalized}%"),
            )
        )
        .all()
    )

    matches: List[User] = []
    for u in candidates:
        if normalize_linkedin_slug(u.linkedin_slug) == normalized:
            matches.append(u)

    if not matches:
        return None

    # If multiple matches exist due to legacy bad data, prefer an exact normalized match.
    exact = next((u for u in matches if (u.linkedin_slug or "").strip().lower() == normalized), None)
    user = exact or matches[0]

    # Best-effort normalization of stored value (helps prevent future mismatches).
    if user.linkedin_slug and user.linkedin_slug != normalized:
        conflict = db.query(User).filter(User.linkedin_slug == normalized, User.id != user.id).first()
        if not conflict:
            user.linkedin_slug = normalized
            db.add(user)

    return user


def canonicalize_ghost_profiles_for_slug(db: Session, slug: str) -> Optional[GhostProfile]:
    normalized = normalize_linkedin_slug(slug)
    if not normalized:
        return None

    ghosts = find_ghost_profiles_for_slug(db, normalized)
    if not ghosts:
        return None

    canonical = next((g for g in ghosts if (g.linkedin_slug or "").strip().lower() == normalized), None) or ghosts[0]

    # Merge other ghosts into canonical.
    for g in ghosts:
        if g.id == canonical.id:
            continue
        edges = db.query(GhostEdge).filter(GhostEdge.ghost_id == g.id).all()
        for e in edges:
            exists = (
                db.query(GhostEdge)
                .filter(GhostEdge.src_user_id == e.src_user_id, GhostEdge.ghost_id == canonical.id)
                .first()
            )
            if exists:
                db.delete(e)
            else:
                e.ghost_id = canonical.id
                db.add(e)

        db.delete(g)

    # Normalize canonical stored slug if possible.
    if canonical.linkedin_slug != normalized:
        conflict = db.query(GhostProfile).filter(GhostProfile.linkedin_slug == normalized, GhostProfile.id != canonical.id).first()
        if not conflict:
            canonical.linkedin_slug = normalized
            db.add(canonical)

    return canonical


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
            if a == b:
                db.delete(pe)
                continue

            exists = db.query(Connection).filter(Connection.user_id_1 == a, Connection.user_id_2 == b).first()
            if not exists:
                db.add(Connection(user_id_1=a, user_id_2=b))
                migrated += 1

            db.delete(pe)

        db.delete(ghost)

    return migrated
