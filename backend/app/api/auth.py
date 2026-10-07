import secrets, urllib.parse, httpx
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Response, HTTPException, status, Depends
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.core.security import (
    generate_pkce, generate_state_and_nonce, create_user_session, delete_session, validate_oidc_token, get_current_user
)
from app.models.schemas import UserSession, DemoLoginRequest, UserBase
from app.services.audit import AuditService

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@router.get("/me", response_model=UserSession)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserSession(
        user=UserBase(id=current_user["id"], username=current_user["username"], email=current_user["email"], role=current_user["role"]),
        csrf_token=current_user["csrf_token"], expires_at=datetime.now(timezone.utc).isoformat(), demo_mode=settings.DEMO_MODE
    )

@router.get("/login")
async def oidc_login(request: Request, response: Response):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            disc_resp = await client.get(settings.OIDC_DISCOVERY_URL)
            disc_resp.raise_for_status()
            auth_endpoint = disc_resp.json().get("authorization_endpoint")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"OIDC discovery error: {type(e).__name__}")

    pkce = generate_pkce()
    meta = generate_state_and_nonce()
    params = {
        "client_id": settings.OIDC_CLIENT_ID, "response_type": "code", "scope": "openid email profile roles",
        "redirect_uri": settings.OIDC_REDIRECT_URI, "state": meta["state"], "nonce": meta["nonce"],
        "code_challenge": pkce["code_challenge"], "code_challenge_method": pkce["code_challenge_method"]
    }
    res = RedirectResponse(url=f"{auth_endpoint}?{urllib.parse.urlencode(params)}", status_code=status.HTTP_302_FOUND)
    res.set_cookie("oidc_state", meta["state"], httponly=True, samesite="lax", max_age=300)
    res.set_cookie("oidc_nonce", meta["nonce"], httponly=True, samesite="lax", max_age=300)
    res.set_cookie("oidc_verifier", pkce["code_verifier"], httponly=True, samesite="lax", max_age=300)
    return res

@router.get("/callback")
async def oidc_callback(request: Request, response: Response, code: str, state: str):
    stored_state = request.cookies.get("oidc_state")
    stored_nonce = request.cookies.get("oidc_nonce")
    code_verifier = request.cookies.get("oidc_verifier")
    if not stored_state or not secrets.compare_digest(state, stored_state):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid state")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            disc = (await client.get(settings.OIDC_DISCOVERY_URL)).json()
            token_resp = await client.post(disc.get("token_endpoint"), data={
                "grant_type": "authorization_code", "client_id": settings.OIDC_CLIENT_ID,
                "client_secret": settings.OIDC_CLIENT_SECRET, "code": code,
                "redirect_uri": settings.OIDC_REDIRECT_URI, "code_verifier": code_verifier
            })
            token_resp.raise_for_status()
            tokens = token_resp.json()

        claims = await validate_oidc_token(tokens["id_token"], nonce=stored_nonce)
        user_id = claims.get("sub", f"usr_{secrets.token_hex(4)}")
        username = claims.get("preferred_username") or claims.get("email") or "keycloak-user"
        email = claims.get("email") or f"{username}@alanvo.local"
        roles = claims.get("realm_access", {}).get("roles", [])
        role = "admin" if "admin" in roles else ("analyst" if "analyst" in roles else "viewer")

        session = create_user_session(user_id=user_id, username=username, email=email, role=role)
        res = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
        res.set_cookie(key=settings.SESSION_COOKIE_NAME, value=session["session_id"], httponly=True, samesite="lax")
        res.delete_cookie("oidc_state"); res.delete_cookie("oidc_nonce"); res.delete_cookie("oidc_verifier")

        AuditService.record(user_id, username, "oidc_login", "session", session["session_id"], request.client.host if request.client else "127.0.0.1")
        return res
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"OIDC failed: {type(e).__name__}")

@router.post("/demo-login", response_model=UserSession)
async def demo_login(payload: DemoLoginRequest, request: Request, response: Response):
    if not settings.DEMO_MODE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Demo mode disabled.")
    if settings.ENVIRONMENT.lower() == "production":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Demo mode refused in production.")

    client_host = request.client.host if request.client else "127.0.0.1"
    if client_host not in ("127.0.0.1", "localhost", "testclient"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Local demo only.")

    role = payload.role
    username = payload.username or f"demo-{role}"
    user_id = f"usr-demo-{role}"
    email = f"{username}@alanvo.local"

    session = create_user_session(user_id=user_id, username=username, email=email, role=role)
    response.set_cookie(key=settings.SESSION_COOKIE_NAME, value=session["session_id"], httponly=True, samesite="lax")

    AuditService.record(user_id, username, "demo_login", "session", session["session_id"], client_host, f"Role {role}")
    return UserSession(
        user=UserBase(id=user_id, username=username, email=email, role=role),
        csrf_token=session["csrf_token"], expires_at=session["expires_at"], demo_mode=True
    )

@router.post("/logout")
async def logout(request: Request, response: Response, current_user: dict = Depends(get_current_user)):
    if current_user.get("session_id") and current_user["session_id"] != "bearer":
        delete_session(current_user["session_id"])
    response.delete_cookie(settings.SESSION_COOKIE_NAME)
    AuditService.record(current_user["id"], current_user["username"], "logout", "session", current_user.get("session_id") or "bearer", request.client.host if request.client else "127.0.0.1")
    return {"status": "success", "message": "Logged out successfully"}
