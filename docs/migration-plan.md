# VoiceBridge AI — Architectural Migration Plan

## Objectives

Iteratively modernize VoiceBridge AI into a low-latency, modular, streaming architecture across 3 zero-downtime phases.

---

## Phase Breakdown

### Phase 1: Architectural Modernization & Contracts (Current)

- [x] Architecture Review & Documentation (`docs/`)
- [x] Typed Pipeline Contracts (`voicebridge.pipeline.contracts`)
- [x] Provider Interfaces (`BaseSTT`, `BaseLLM`, `BaseTTS`, `BaseVAD`, `BasePlayback`)
- [x] Dependency Isolation Adapters (`voicebridge.adapters`)
- [x] Telemetry with `trace_id` correlation (`voicebridge.telemetry`)
- [x] Centralized Configuration & Feature Flags (`ENABLE_PIPELINE_CONTRACTS`, `ENABLE_NEW_INTERFACES`, `ENABLE_TRACING`)
- [x] 100% Backward Compatibility & Unit Test Coverage

### Phase 2: Asynchronous & Streaming Architecture (Next Phase)

- [ ] End-to-End Streaming (Partial STT, LLM tokens, chunked TTS synthesis)
- [ ] Worker Queue Architecture (VAD Queue → STT Queue → LLM Queue → TTS Queue → Playback Queue)
- [ ] Backpressure & Queue Compaction
- [ ] Model Warm-Up & Session Reuse

### Phase 3: Advanced Optimization & Production Deployment (Future)

- [ ] Fallback Chains & Model Routing
- [ ] Hardware Acceleration & Model Quantization Tuning
- [ ] WebRTC / Real-Time Streaming Integration
