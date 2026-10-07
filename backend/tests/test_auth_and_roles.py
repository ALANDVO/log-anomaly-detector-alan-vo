import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.config import settings
from app.core.security import generate_pkce, generate_state_and_nonce

@pytest.mark.asyncio
async def test_unauthenticated_request_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get("/api/logs")
        assert resp.status_code == 401
        assert "Authentication required" in resp.json()["detail"]

@pytest.mark.asyncio
async def test_demo_login_and_role_denial():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Enable demo mode for test
        settings.DEMO_MODE = True

        # Login as viewer
        viewer_resp = await client.post("/api/auth/demo-login", json={"role": "viewer"})
        assert viewer_resp.status_code == 200
        viewer_data = viewer_resp.json()
        assert viewer_data["user"]["role"] == "viewer"
        csrf = viewer_data["csrf_token"]

        # Viewer can read logs
        read_resp = await client.get("/api/logs")
        assert read_resp.status_code == 200

        # Viewer CANNOT ingest logs (requires analyst) -> 403 Forbidden
        ingest_resp = await client.post(
            "/api/logs/ingest",
            json={"logs": [{"message": "test", "service": "api-gateway"}], "trigger_correlation": False},
            headers={"X-CSRF-Token": csrf}
        )
        assert ingest_resp.status_code == 403
        assert "Access denied" in ingest_resp.json()["detail"]

@pytest.mark.asyncio
async def test_csrf_protection_on_mutations():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        settings.DEMO_MODE = True
        # Login as analyst
        login_resp = await client.post("/api/auth/demo-login", json={"role": "analyst"})
        assert login_resp.status_code == 200

        # Ingest without CSRF token header -> 403 Forbidden
        bad_resp = await client.post(
            "/api/logs/ingest",
            json={"logs": [{"message": "test without csrf", "service": "api-gateway"}]}
        )
        assert bad_resp.status_code == 403
        assert "CSRF validation failed" in bad_resp.json()["detail"]

def test_pkce_and_state_nonce_generation():
    pkce = generate_pkce()
    assert "code_verifier" in pkce
    assert "code_challenge" in pkce
    assert pkce["code_challenge_method"] == "S256"
    assert len(pkce["code_verifier"]) > 40

    meta = generate_state_and_nonce()
    assert "state" in meta
    assert "nonce" in meta
    assert len(meta["state"]) > 20
