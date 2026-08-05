# VoiceBridge AI — Observability & Telemetry Guide

## Overview

Observability in VoiceBridge AI tracks every utterance end-to-end through a unique `trace_id`. Structured logs and metrics collectors provide detailed visibility into stage latencies, model execution times, queue waiting times, audio durations, throughput, and error rates.

---

## Key Metrics Tracked

| Metric Name | Type | Unit | Description |
|---|---|---|---|
| `trace_id` | Context Tag | UUID String | Unique identifier per request/utterance flow |
| `total_latency_ms` | Gauge | ms | End-to-end processing latency |
| `stage_latencies_ms` | Histogram | ms | Latency per pipeline stage (VAD, STT, LLM, TTS, LipSync, Playback) |
| `queue_wait_time_ms` | Gauge | ms | Wait time in inter-worker queues |
| `model_inference_time_ms` | Gauge | ms | Provider model computation duration |
| `tokens_per_sec` | Rate | tokens/s | Generation throughput for LLM translation |
| `audio_duration_sec` | Gauge | seconds | Synthesized or captured audio length |
| `errors` | Counter | count | Count of stage failures grouped by error type |

---

## Structured Log Format

Structured logs are written in JSON Lines format to `logs/performance.jsonl`:

```json
{
  "timestamp": "2026-08-05T14:35:00Z",
  "trace_id": "c1f72a49-980b-4654-8c8b-59d0ef7b819f",
  "session_id": "session-1",
  "direction": "EN->AR",
  "sentence_id": 1,
  "source_lang": "en",
  "target_lang": "ar",
  "text": "Hello, how are you?",
  "translated_text": "مرحبا، كيف حالك؟",
  "stage_latencies_ms": {
    "Audio Capture": 20.0,
    "STT": 350.0,
    "Translation": 80.0,
    "TTS": 280.0,
    "Lip Sync": 450.0
  },
  "total_latency_ms": 1180.0,
  "audio_duration_sec": 2.5
}
```

---

## Prometheus & OpenTelemetry Compatibility

The `TraceContext` and `StructuredMetricsLogger` modules format telemetry fields matching OpenTelemetry trace conventions (`trace_id`, `span_id`, `service.name`), allowing easy export to Prometheus, Jaeger, Grafana Tempo, or Datadog.
