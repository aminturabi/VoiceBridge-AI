# VoiceBridge AI — System Architecture (Phase 1 Modernization)

## Overview

VoiceBridge AI provides real-time, bi-directional speech translation and lip-synced avatar animation. Phase 1 modernizes the codebase architecture by introducing:

1. **Typed Pipeline Contracts**: Request, response, and error schemas for every stage with mandatory `trace_id` correlation.
2. **Provider Interfaces**: Abstract provider contracts (`BaseSTT`, `BaseLLM`, `BaseTTS`, `BaseVAD`, `BasePlayback`).
3. **Dependency Isolation**: Adapter layer insulating core business logic from specific vendor implementations (Whisper, Google, Argos, NLLB, Edge-TTS, Silero).
4. **Structured Telemetry**: Contextual tracing and metrics export (OpenTelemetry & Prometheus ready).
5. **Centralized Configuration & Feature Flags**: Standardized configuration loader with feature flag toggles (`ENABLE_PIPELINE_CONTRACTS`, `ENABLE_NEW_INTERFACES`, `ENABLE_TRACING`).

---

## Component Architecture

```mermaid
flowchart TD
    subgraph UI ["User Interface Layer"]
        WEBUI[Meeting Web UI]
        WS[WebSocket Stream]
    end

    subgraph API ["API & Routing Layer"]
        APP[FastAPI App /api]
        BROKER[Event Broker]
    end

    subgraph PIPELINE ["Pipeline Core (DirectionWorker)"]
        ORCH[Orchestrator]
        BUFFER[Sentence Buffer]
        CONTRACTS[Pipeline Contracts & TraceContext]
    end

    subgraph ADAPTERS ["Provider Adapter Layer"]
        STT_ADAPTER[STT Adapter]
        LLM_ADAPTER[LLM / Translation Adapter]
        TTS_ADAPTER[TTS Adapter]
        VAD_ADAPTER[VAD & Capture Adapter]
    end

    subgraph PROVIDERS ["External / Concrete Providers"]
        WHISPER[faster-whisper / Vosk]
        GOOGLE[Google Translate / Argos / NLLB]
        EDGE[Edge-TTS / Coqui]
        SILERO[Silero VAD]
    end

    subgraph TELEMETRY ["Observability & Metrics"]
        TRACE[TraceContext & Logger]
        COLLECTOR[MetricsCollector]
    end

    WEBUI --> APP
    WEBUI <--> WS
    APP --> ORCH
    ORCH --> CONTRACTS
    CONTRACTS --> VAD_ADAPTER
    CONTRACTS --> STT_ADAPTER
    CONTRACTS --> LLM_ADAPTER
    CONTRACTS --> TTS_ADAPTER

    VAD_ADAPTER --> SILERO
    STT_ADAPTER --> WHISPER
    LLM_ADAPTER --> GOOGLE
    TTS_ADAPTER --> EDGE

    CONTRACTS -.-> TRACE
    TRACE --> COLLECTOR
    BROKER --> WS
```

---

## Phase 2 Asynchronous Worker Queue Architecture

```mermaid
flowchart LR
    MIC[Input Capture] --> |Audio Frames| VAD_W[VadWorker]
    VAD_W --> |stt_queue| STT_W[SttWorker]
    STT_W --> |llm_queue| LLM_W[LlmWorker]
    LLM_W --> |tts_queue| TTS_W[TtsWorker]
    TTS_W --> |playback_queue| PLAY_W[PlaybackWorker]
    PLAY_W --> SPK[Audio Playback]

    subgraph BACKPRESSURE ["Backpressure & Bounded Queues"]
        stt_q[(stt_queue)]
        llm_q[(llm_queue)]
        tts_q[(tts_queue)]
        pb_q[(playback_queue)]
    end
```

Phase 2 connects independent stage workers (`VadWorker`, `SttWorker`, `LlmWorker`, `TtsWorker`, `PlaybackWorker`) using bounded async queues (`BoundedAsyncQueue`). When queues reach capacity under heavy load, backpressure logic compacts partial STT transcripts or evicts oldest items to prevent unbounded memory growth while logging overload events correlated with `trace_id`.

---

## Dependency Graph

```mermaid
graph LR
    subgraph Core
        Config[voicebridge.config]
        Telemetry[voicebridge.telemetry]
        Contracts[voicebridge.pipeline.contracts]
    end

    subgraph Interfaces
        BaseSTT[voicebridge.models.stt.BaseSTT]
        BaseLLM[voicebridge.models.llm.BaseLLM]
        BaseTTS[voicebridge.models.tts.BaseTTS]
        BaseVAD[voicebridge.models.vad.BaseVAD]
        BasePlayback[voicebridge.models.playback.BasePlayback]
    end

    subgraph Adapters
        SttAdapter[voicebridge.adapters.stt_adapter]
        LlmAdapter[voicebridge.adapters.llm_adapter]
        TtsAdapter[voicebridge.adapters.tts_adapter]
        VadAdapter[voicebridge.adapters.vad_adapter]
    end

    subgraph BusinessLogic
        Buffer[voicebridge.pipeline.buffer]
        Worker[voicebridge.pipeline.worker]
        Orchestrator[voicebridge.pipeline.orchestrator]
    end

    Adapters --> Interfaces
    BusinessLogic --> Contracts
    BusinessLogic --> Interfaces
    Contracts --> Telemetry
    Interfaces --> Config
```

---

## SOLID Principles & Clean Architecture

- **Single Responsibility Principle (SRP)**: Each provider interface and adapter has a single concern.
- **Open/Closed Principle (OCP)**: New STT/LLM/TTS backends can be registered via adapters without modifying pipeline orchestration logic.
- **Liskov Substitution Principle (LSP)**: All STT, LLM, and TTS providers conform strictly to `BaseSTT`, `BaseLLM`, `BaseTTS` contracts.
- **Interface Segregation Principle (ISP)**: Interfaces are strictly focused per modality.
- **Dependency Inversion Principle (DIP)**: Pipeline orchestration depends on abstract interfaces (`BaseSTT`, `BaseLLM`, `BaseTTS`), not concrete libraries.
