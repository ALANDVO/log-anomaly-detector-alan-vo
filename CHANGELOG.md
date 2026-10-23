# Changelog

## 1.3.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

## 1.2.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

## [1.1.0] - 2026-10-07

All notable changes to `log-anomaly-detector-alan-vo` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2026-10-15

### Added
- Configurable service dependency topology persisted in SQLite database.
- REST API endpoints for dependency CRUD operations: `GET/POST/PATCH/DELETE /api/dependencies`.
- Correlator now reads live topology from database instead of hardcoded constants.
- Frontend DependencyView component for viewing and managing service dependencies (analyst/admin mutate, viewer read-only).
- Default topology seeded on first run for backward compatibility (db-proxy, cache-layer, auth-service, payment-service).
- Full audit trail for all dependency mutations.
- Backend tests (7) and frontend test (1) for new dependency topology feature.

## [1.1.0] - 2026-10-07
## [1.0.0] - 2026-10-07

### Added
- Modular FastAPI backend with persistent SQLite storage and transactional mutations.
- Deterministic log parsing engine implementing token-based template mining and parameter extraction.
- Statistical offline anomaly detector evaluating frequency z-scores, token entropy, and sliding-window bursts.
- Cross-service event correlation engine with temporal cascade clustering and root-cause candidate identification.
- Opt-in LLM advisory service supporting OpenAI-compatible, Anthropic, Gemini, and Ollama providers with server-side adapters.
- Role-based access control (viewer, analyst, admin) with secure Keycloak OIDC authorization code flow, PKCE, state/nonce verification, and HttpOnly SameSite cookies.
- Real-time audit log tracking mutations, status updates, and postmortem exports.
- Reproducible ML evaluation pipeline comparing template mining against baseline frequency thresholding on a labeled ground-truth benchmark dataset.
- React + TypeScript + Vite dashboard with responsive log stream viewer, incident timeline inspection, advisory panel, and evaluation metrics visualization.
- Production-ready Dockerfiles with non-root security contexts and compose.yaml Keycloak integration.
