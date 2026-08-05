# VoiceBridge AI — Operations & Troubleshooting Runbook

## Health Endpoints

VoiceBridge AI exposes REST endpoints for container orchestrators (Kubernetes, ECS, Docker Swarm):

- `GET /api/health`: Comprehensive system status, CPU/RAM usage, provider latencies, and circuit breaker states.
- `GET /api/health/liveness`: Returns `200 OK` (`{"status": "alive"}`) if application thread is responsive.
- `GET /api/health/readiness`: Returns `200 OK` (`{"status": "ready"}`) when models and pipeline workers are ready.

---

## Circuit Breaker Operations

If a provider trips into `OPEN` state due to consecutive failures:

1. **Auto-Recovery**: Circuit breakers automatically transition to `HALF_OPEN` after `resilience.circuit_breaker.recovery_timeout_sec` (default: 10 seconds).
2. **Manual Intervention**: Inspect `logs/voicebridge.log` for `[CircuitBreaker]` entries with `trace_id`.
3. **Environment Override**: Force-enable or disable circuit breakers using `VOICEBRIDGE_ENABLE_CIRCUIT_BREAKER=false`.

---

## Troubleshooting Common Issues

| Symptom | Root Cause | Solution |
|---|---|---|
| High STT Latency | CPU model size too large | Set `stt.cpu.model_size: "tiny"` or `routing.default_tier: "fast"` |
| 429 Too Many Requests | Rate limit threshold exceeded | Increase `resilience.rate_limiter.requests_per_second` in `config.yaml` |
| Fallback to Offline Argos | Google Translate rate limited | Verify outbound internet connection; Argos acts as offline backup |
