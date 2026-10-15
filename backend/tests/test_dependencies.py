import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.config import settings
from app.core.database import init_db, transaction

@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    # Clear service_dependencies table before each test to ensure isolation
    with transaction() as conn:
        conn.execute("DELETE FROM service_dependencies")
        # Re-seed defaults
        import uuid
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        defaults = [
            ("db-proxy", "auth-service", "depends_on"),
            ("db-proxy", "payment-service", "depends_on"),
            ("db-proxy", "order-service", "depends_on"),
            ("cache-layer", "api-gateway", "depends_on"),
            ("cache-layer", "auth-service", "depends_on"),
            ("auth-service", "api-gateway", "depends_on"),
            ("payment-service", "api-gateway", "depends_on"),
            ("payment-service", "order-service", "depends_on"),
        ]
        conn.executemany(
            "INSERT INTO service_dependencies (id, upstream, downstream, relationship, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            [(f"dep_{uuid.uuid4().hex[:10]}", u, d, r, now, now) for u, d, r in defaults]
        )
@pytest.mark.asyncio
async def test_dependencies_crud_workflow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        settings.DEMO_MODE = True

        # Login as analyst
        login_res = await client.post("/api/auth/demo-login", json={"role": "analyst"})
        assert login_res.status_code == 200
        csrf = login_res.json()["csrf_token"]
        headers = {"X-CSRF-Token": csrf}

        # 1. List dependencies (should have defaults)
        list_res = await client.get("/api/dependencies")
        assert list_res.status_code == 200
        deps = list_res.json()
        assert len(deps) >= 8  # default seeded dependencies

        # 2. Create a new dependency
        create_res = await client.post(
            "/api/dependencies",
            json={"upstream": "crud-new-svc", "downstream": "crud-consumer", "relationship": "calls"},
            headers=headers
        )
        assert create_res.status_code == 201
        new_dep = create_res.json()
        assert new_dep["upstream"] == "crud-new-svc"
        assert new_dep["downstream"] == "crud-consumer"
        assert new_dep["relationship"] == "calls"
        dep_id = new_dep["id"]

        # 3. List again, verify new dependency appears
        list_res2 = await client.get("/api/dependencies")
        assert list_res2.status_code == 200
        deps2 = list_res2.json()
        assert len(deps2) == len(deps) + 1
        assert any(d["id"] == dep_id for d in deps2)

        # 4. Filter by upstream
        filter_res = await client.get("/api/dependencies?upstream=crud-new-svc")
        assert filter_res.status_code == 200
        filtered = filter_res.json()
        assert len(filtered) == 1
        assert filtered[0]["id"] == dep_id

        # 5. Update the dependency
        patch_res = await client.patch(
            f"/api/dependencies/{dep_id}",
            json={"relationship": "replicates", "downstream": "updated-consumer"},
            headers=headers
        )
        assert patch_res.status_code == 200
        updated = patch_res.json()
        assert updated["relationship"] == "replicates"
        assert updated["downstream"] == "updated-consumer"
        assert updated["upstream"] == "crud-new-svc"  # unchanged

        # 6. Delete the dependency
        delete_res = await client.delete(f"/api/dependencies/{dep_id}", headers=headers)
        assert delete_res.status_code == 204

        # 7. Verify deleted
        list_res3 = await client.get("/api/dependencies")
        assert list_res3.status_code == 200
        deps3 = list_res3.json()
        assert len(deps3) == len(deps)
        assert not any(d["id"] == dep_id for d in deps3)


@pytest.mark.asyncio
async def test_dependencies_viewer_read_only():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        settings.DEMO_MODE = True

        # Login as viewer
        login_res = await client.post("/api/auth/demo-login", json={"role": "viewer"})
        assert login_res.status_code == 200
        csrf = login_res.json()["csrf_token"]
        headers = {"X-CSRF-Token": csrf}

        # Viewer can read
        list_res = await client.get("/api/dependencies")
        assert list_res.status_code == 200

        # Viewer CANNOT create
        create_res = await client.post(
            "/api/dependencies",
            json={"upstream": "a", "downstream": "b"},
            headers=headers
        )
        assert create_res.status_code == 403
        assert "Access denied" in create_res.json()["detail"]


@pytest.mark.asyncio
async def test_dependencies_duplicate_conflict():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        settings.DEMO_MODE = True

        login_res = await client.post("/api/auth/demo-login", json={"role": "analyst"})
        assert login_res.status_code == 200
        csrf = login_res.json()["csrf_token"]
        headers = {"X-CSRF-Token": csrf}

        # Create once
        create1 = await client.post("/api/dependencies", json={"upstream": "dup-test-svc-a", "downstream": "dup-test-svc-b"}, headers=headers)
        assert create1.status_code == 201

        # Create duplicate -> 409 Conflict
        create2 = await client.post("/api/dependencies", json={"upstream": "dup-test-svc-a", "downstream": "dup-test-svc-b"}, headers=headers)
        assert create2.status_code == 409
        assert "already exists" in create2.json()["detail"]


@pytest.mark.asyncio
async def test_dependencies_update_duplicate_conflict():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        settings.DEMO_MODE = True

        login_res = await client.post("/api/auth/demo-login", json={"role": "analyst"})
        assert login_res.status_code == 200
        csrf = login_res.json()["csrf_token"]
        headers = {"X-CSRF-Token": csrf}

        # Create two distinct dependencies
        c1 = await client.post("/api/dependencies", json={"upstream": "update-test-a", "downstream": "update-test-b"}, headers=headers)
        c2 = await client.post("/api/dependencies", json={"upstream": "update-test-c", "downstream": "update-test-d"}, headers=headers)
        assert c1.status_code == 201
        assert c2.status_code == 201
        id1, id2 = c1.json()["id"], c2.json()["id"]

        # Try to update second to match first -> 409
        patch_res = await client.patch(f"/api/dependencies/{id2}", json={"upstream": "update-test-a", "downstream": "update-test-b"}, headers=headers)
        assert patch_res.status_code == 409
        assert "already exists" in patch_res.json()["detail"]


def test_correlator_uses_database_dependencies():
    from app.services.correlator import EventCorrelator

    deps = EventCorrelator._get_dependencies()
    # Should contain default seeded dependencies
    assert "db-proxy" in deps
    assert "auth-service" in deps["db-proxy"]
    assert "payment-service" in deps["db-proxy"]
    assert "order-service" in deps["db-proxy"]
    assert "cache-layer" in deps
    assert "api-gateway" in deps["cache-layer"]
    assert "auth-service" in deps["cache-layer"]
    assert "auth-service" in deps
    assert "api-gateway" in deps["auth-service"]
    assert "payment-service" in deps
    assert "api-gateway" in deps["payment-service"]
    assert "order-service" in deps["payment-service"]


def test_correlator_downstream_calculation():
    from app.services.correlator import EventCorrelator

    # db-proxy upstream of auth-service, payment-service, order-service
    downstream = EventCorrelator._downstream("db-proxy")
    assert "auth-service" in downstream
    assert "payment-service" in downstream
    assert "order-service" in downstream

    # auth-service upstream of api-gateway
    downstream_auth = EventCorrelator._downstream("auth-service")
    assert "api-gateway" in downstream_auth

    # Unknown service returns empty
    assert EventCorrelator._downstream("unknown-service") == set()

@pytest.mark.asyncio
async def test_dependency_audit_trail():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        settings.DEMO_MODE = True

        login_res = await client.post("/api/auth/demo-login", json={"role": "analyst"})
        assert login_res.status_code == 200
        csrf = login_res.json()["csrf_token"]
        headers = {"X-CSRF-Token": csrf}

        # Create
        create_res = await client.post("/api/dependencies", json={"upstream": "audit-trail-svc", "downstream": "audit-target"}, headers=headers)
        assert create_res.status_code == 201
        dep_id = create_res.json()["id"]

        # Check audit log
        admin_login = await client.post("/api/auth/demo-login", json={"role": "admin"})
        admin_csrf = admin_login.json()["csrf_token"]
        admin_headers = {"X-CSRF-Token": admin_csrf}

        audit_res = await client.get("/api/audit", headers=admin_headers)
        assert audit_res.status_code == 200
        audits = audit_res.json()
        create_audit = next((a for a in audits if a["action"] == "create_dependency" and a["entity_id"] == dep_id), None)
        assert create_audit is not None
        assert "audit-trail-svc -> audit-target" in create_audit["details"]