# Changelog

All notable changes to `log-anomaly-detector-alan-vo` will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Incident root-cause selection follows the service dependency graph. A downstream symptom logged before the upstream failure is no longer stored as the origin. The incident window stays chronological, and cascade edges are ordered by UTC instant rather than raw timestamp text. Correlation looks back from the newest unassigned anomaly, so an already closed incident does not hide an older cascade.
- Log level parsing only accepts a prefix token (`ERROR`, `[ERROR]`, or `auth-service ERROR`). Words such as "error" or "info" inside the message body no longer override the structured level.

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
