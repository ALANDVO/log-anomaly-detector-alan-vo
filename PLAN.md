# Product development plan

Each round completes one feature or repair. Future items are planned, not implemented claims.

## Current round

detector-threshold-configuration

## Roadmap

### configurable-service-dependencies — Configurable Service Dependency Topology with Persistence

Status: done

Acceptance:
- Service dependencies stored in SQLite database instead of hardcoded constants
- REST API endpoints for CRUD operations on service dependencies (GET, POST, PATCH, DELETE)
- Correlator uses database-backed dependencies for cascade graph construction
- Frontend UI for viewing and managing dependencies (analyst/admin roles)
- Default dependencies seeded on first run for backward compatibility
- Role-based access: viewers can read, analysts/admins can mutate
- Audit trail records all dependency mutations

Implementation: `backend/app/models/schemas.py: add ServiceDependency schemas`, `backend/app/core/database.py: add service_dependencies table to init_db`, `backend/app/services/correlator.py: replace SERVICE_DEPENDENCIES constant with DB lookup`, `backend/app/api/dependencies.py: new API router with CRUD endpoints`, `backend/app/main.py: register dependencies router`, `backend/app/api/logs.py: import EventCorrelator after DB init (no change needed)`, `frontend/src/types/index.ts: add ServiceDependency type`, `frontend/src/api/client.ts: add dependency API methods`, `frontend/src/components/DependencyView.tsx: new component for dependency management`, `frontend/src/App.tsx: register DependencyView route`, `frontend/src/components/Navbar.tsx: add Dependencies nav item`

Tests: `backend/tests/test_dependencies.py: new test file for dependency CRUD and correlator integration`, `frontend/src/__tests__/DependencyView.test.tsx: new frontend test`

### detector-threshold-configuration — Configurable Anomaly Detection Thresholds with Persistence

Status: done

Acceptance:
- Anomaly detection thresholds (anomaly threshold, severity bands) stored in SQLite database
- REST API endpoints for GET/PUT threshold configuration (analyst/admin roles)
- Detector uses database-backed thresholds at evaluation time
- Default thresholds seeded on first run for backward compatibility
- Frontend UI for viewing and adjusting thresholds (analyst/admin roles)
- Role-based access: viewers can read, analysts/admins can mutate
- Audit trail records all threshold mutations

Implementation: `backend/app/core/database.py: add threshold_config table to init_db with default seeding`, `backend/app/services/detector.py: AnomalyDetector uses database-backed thresholds with caching`, `backend/app/api/thresholds.py: new API router with GET/PUT endpoints`, `backend/app/main.py: register thresholds router`, `backend/app/models/schemas.py: add ThresholdConfig schemas`, `frontend/src/types/index.ts: add ThresholdConfig type`, `frontend/src/api/client.ts: add threshold API methods`, `frontend/src/components/ThresholdView.tsx: new component for threshold management`, `frontend/src/App.tsx: register ThresholdView route`, `frontend/src/components/Navbar.tsx: add Thresholds nav item`

Tests: `backend/tests/test_thresholds.py: new test file for threshold CRUD and detector integration`, `frontend/src/__tests__/ThresholdView.test.tsx: new frontend test`

---

Alan Vo · [alanvo.net](https://alanvo.net) · [X: @alanvoasi](https://x.com/alanvoasi)
