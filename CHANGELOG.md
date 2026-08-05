# Changelog

All notable changes to VoiceBridge AI will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-08-05

### Added
- **Developer Quality Gates**: Added `.pre-commit-config.yaml` for pre-commit hooks (Ruff, Black, private key detection) and GitHub Actions CI workflow (`ci.yml`) enforcing a 70%+ test coverage baseline.
- **Request Tracing & Contextual Logging**: Implemented `RequestTracingMiddleware` with `X-Request-ID` header generation and ContextVar support in structured logs.
- **Dedicated Health Checks**: Added `/api/health`, `/api/health/liveness`, and `/api/health/readiness` endpoints with CPU/memory telemetry.
- **Security & Input Boundaries**: Added Pydantic schema validation (`StartCallSchema`), in-memory rate limiting, and optional API key authentication support.
- **Comprehensive Documentation**: Updated `README.md` with environment prerequisites, detailed Mermaid API flow diagram, run commands, and troubleshooting guide.
- **Environment Configuration**: Added `.env.example` template covering server, model, security, and feature flag settings.

### Changed
- Standardized API global exception handling to return structured JSON payloads with request IDs.
- Updated `pyproject.toml` with Ruff, Black, and Pytest coverage configuration.

## [0.1.0] - 2026-08-01

### Added
- Initial release of VoiceBridge AI real-time speech translation and talking-head lip-sync pipeline.
- `faster-whisper` STT engine integration.
- `edge-tts` speech synthesis and fallback translation engines (Google / Argos).
- Interactive meeting UI with dual-participant WebSocket stream.
