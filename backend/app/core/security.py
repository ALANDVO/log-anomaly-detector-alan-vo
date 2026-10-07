import secrets, hashlib, base64, uuid, jwt, httpx
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.config import settings
from app.core.database import transaction

security_bearer = HTTPBearer(auto_error=False)
ROLE_HIERARCHY = {"admin": 3, "analyst": 2, "viewer": 1}

def generate_pkce() -> Dict[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return {"code_verifier": verifier, "code_challenge": challenge, "code_challenge_method": "S256"}

def generate_state_and_nonce() -> Dict[str, str]:
    return {"state": secrets.token_urlsafe(32), "nonce": secrets.token_urlsafe(32)}

def create_user_session(user_id: str, username: str, email: str, role: str) -> Dict[str, str]:
    session_id = f"sess_{secrets.token_urlsafe(32)}"
    csrf_token = f"csrf_{secrets.token_urlsafe(32)}"
    now = datetime.now(timezone.utc)
    expires_at = (now + timedelta(hours=12)).isoformat()

    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO users (id, username, email, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, email, role, now.isoformat())
        )
        cursor.execute(
            """INSERT INTO sessions (session_id, user_id, username, email, role, csrf_token, created_at, expires_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, user_id, username, email, role, csrf_token, now.isoformat(), expires_at)
        )
    return {"session_id": session_id, "csrf_token": csrf_token, "expires_at": expires_at}

def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    with transaction() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        if not row: return None
        if datetime.now(timezone.utc) > datetime.fromisoformat(row["expires_at"]):
            cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            return None
        return dict(row)

def delete_session(session_id: str) -> None:
    with transaction() as conn:
        conn.cursor().execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))

async def validate_oidc_token(id_token: str, nonce: Optional[str] = None) -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            disc_resp = await client.get(settings.OIDC_DISCOVERY_URL)
            disc_resp.raise_for_status()
            config = disc_resp.json()
            jwks_resp = await client.get(config.get("jwks_uri"))
            jwks_resp.raise_for_status()
            jwks = jwks_resp.json()

        jwks_client = jwt.PyJWKClient.from_dict(jwks)
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)
        decoded = jwt.decode(
            id_token, signing_key.key, algorithms=["RS256", "ES256"],
            issuer=config.get("issuer"), audience=settings.OIDC_CLIENT_ID,
            options={"verify_exp": True, "verify_aud": True}
        )
        if nonce and decoded.get("nonce") != nonce:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="OIDC nonce validation failed")
        return decoded
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"OIDC validation failed: {type(e).__name__}")

async def get_current_user(
    request: Request,
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)
) -> Dict[str, Any]:
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if session_id:
        sess = get_session(session_id)
        if sess:
            return {"id": sess["user_id"], "username": sess["username"], "email": sess["email"], "role": sess["role"], "session_id": sess["session_id"], "csrf_token": sess["csrf_token"]}

    if bearer and bearer.credentials:
        try:
            payload = jwt.decode(bearer.credentials, settings.SECRET_KEY, algorithms=["HS256"], options={"verify_exp": True})
            return {"id": payload.get("sub", "token-user"), "username": payload.get("username", "api-user"), "email": payload.get("email", "api@alanvo.local"), "role": payload.get("role", "viewer"), "session_id": "bearer", "csrf_token": "bearer"}
        except Exception: pass

    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

def require_role(min_role: str):
    def role_checker(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        min_level = ROLE_HIERARCHY.get(min_role, 1)
        user_level = ROLE_HIERARCHY.get(user.get("role", "viewer"), 0)
        if user_level < min_level:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Access denied for role '{user.get('role')}'. Requires '{min_role}'.")
        return user
    return role_checker

def verify_csrf(request: Request, user: Dict[str, Any] = Depends(get_current_user)) -> None:
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        if user.get("session_id") == "bearer": return
        token_hdr = request.headers.get("X-CSRF-Token")
        expected = user.get("csrf_token")
        if not token_hdr or not expected or not secrets.compare_digest(token_hdr, expected):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed.")
