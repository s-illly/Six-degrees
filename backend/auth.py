from jwt import ExpiredSignatureError, InvalidTokenError
import jwt 
import datetime
import os, secrets, urllib.parse
import httpx 
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse 
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db
from models import User
from linkedin_utils import find_user_for_slug, normalize_linkedin_slug, migrate_ghost_edges_to_user

router = APIRouter(prefix="/auth", tags=["auth"])
load_dotenv()
bearer_scheme = HTTPBearer()

@router.get("/linkedin/start")
def register():
    state = secrets.token_urlsafe(24)
    params = {
        "response_type": "code",
        "client_id": os.getenv("LINKEDIN_CLIENT_ID"),
        "redirect_uri": os.getenv("LINKEDIN_REDIRECT_URI"),
        "state": state,
        "scope": "openid profile email",
    }
    url = "https://www.linkedin.com/oauth/v2/authorization?" + urllib.parse.urlencode(params)
    resp = RedirectResponse(url=url, status_code = 302)
    resp.set_cookie("li_state", state, httponly=True, samesite="lax")
    return resp 


@router.get("/linkedin/callback")
async def login(code: str, state: str, request: Request, db: Session = Depends(get_db)):
    cookie_state = request.cookies.get("li_state")
    if (not cookie_state) or (cookie_state != state):
        raise HTTPException(status_code = 400, detail="Invalid state")
    
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": os.getenv("LINKEDIN_REDIRECT_URI"),
        "client_id": os.getenv("LINKEDIN_CLIENT_ID"),
        "client_secret": os.getenv("LINKEDIN_CLIENT_SECRET"),
    }
    async with httpx.AsyncClient(timeout=10) as client:
        token_res = await client.post(token_url, data=data)
    if token_res.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_res.text}")
    access_token = token_res.json().get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="No access token returned")
    
    userinfo_url = "https://api.linkedin.com/v2/userinfo"
    headers ={"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient(timeout=10) as client:
        ui_res = await client.get(userinfo_url, headers=headers)
    
    if ui_res.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Userinfo failed: {ui_res.text}")
    
    ui = ui_res.json()
    linkedin_sub = ui.get("sub")
    name = ui.get("name") or ui.get("given_name")

    # Best-effort: LinkedIn OIDC userinfo sometimes includes a usable public identifier.
    # We accept either a raw slug or a full URL and normalize it.
    slug_candidate = (
        ui.get("preferred_username")
        or ui.get("vanityName")
        or ui.get("publicProfileUrl")
        or ui.get("profile")
        or ui.get("profile_url")
    )
    inferred_slug = normalize_linkedin_slug(slug_candidate) if slug_candidate else ""

    if not linkedin_sub:
        raise HTTPException(status_code=400, detail="No linkedin subject returned")
    
    user = db.query(User).filter(User.linkedin_sub == linkedin_sub).first()
    if not user:
        user = User(full_name=name or "New User", linkedin_sub=linkedin_sub)
        db.add(user)
        db.commit()
        db.refresh(user)

    # If we can infer a slug on login, attach it. Then (or if the user already has a slug),
    # migrate any matching ghost nodes into real connections.
    changed = False
    if inferred_slug and not user.linkedin_slug:
        existing_owner = find_user_for_slug(db, inferred_slug)
        if (not existing_owner) or (existing_owner.id == user.id):
            user.linkedin_slug = inferred_slug
            changed = True

    migrated = 0
    if user.linkedin_slug:
        migrated = migrate_ghost_edges_to_user(db, user, user.linkedin_slug)
        if migrated:
            changed = True

    if changed:
        db.add(user)
        db.commit()
        db.refresh(user)

    app_token = create_access_token({"id": user.id})
    frontend = os.getenv("FRONTEND_REDIRECT_URI", "http://localhost:5173/auth/callback")
    redirect_url = f"{frontend}?token={urllib.parse.quote(app_token)}"

    resp = RedirectResponse(url=redirect_url, status_code=302)

    resp.delete_cookie("li_state")
    return resp


def create_access_token(data: dict):
    payload = {
        "sub": data['id'],
        "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")))
    }

    token = jwt.encode(
        payload = payload,
        key = os.getenv("SECRET_KEY"),
        algorithm = os.getenv("ALGORITHM")
    )

    return token


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer_scheme), db: Session = Depends(get_db)):
    try:
        token = creds.credentials
        payload = jwt.decode(token, key = os.getenv("SECRET_KEY"), algorithms = os.getenv("ALGORITHM"))
        id = payload.get("sub")
        if id is None:
            raise HTTPException(status_code = 401, detail = "Invalid token")
        user = db.query(User).filter(User.id == id).first()
        if user is None:
            raise HTTPException(status_code = 401, detail = "User not found")
        return user
    except ExpiredSignatureError:
        raise HTTPException(status_code = 401, detail = "Token expired")
    except InvalidTokenError:
        raise HTTPException(status_code = 401, detail = "Invalid token")
    