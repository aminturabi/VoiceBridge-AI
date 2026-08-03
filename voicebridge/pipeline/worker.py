"""One-direction pipeline worker.

A :class:`DirectionWorker` owns the full chain for a single translation
direction (e.g. EN->AR): its own STT engine, a sentence buffer, and references
to the shared translation/TTS/lip-sync managers. It runs two threads:

* a *capture* thread that pulls audio segments from a source, transcribes them,
  and feeds the sentence buffer;
* a *process* thread that drains ready sentences and runs
  translate -> TTS -> lip-sync -> emit event.

Because each direction has its own STT engine and there is no global lock, the
two directions of a two-way call run concurrently instead of serializing.
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass

from voicebridge.audio.capture import save_segment_wav
from voicebridge.config import Config
from voicebridge.lipsync.manager import LipSyncManager
from voicebridge.logging_conf import get_logger
from voicebridge.pipeline.buffer import SentenceBuffer
from voicebridge.pipeline.events import EventType, PipelineEvent
from voicebridge.stt.manager import SttManager
from voicebridge.translation.base import TranslationError
from voicebridge.translation.manager import TranslationManager
from voicebridge.tts.manager import TtsManager

from voicebridge.metrics.collector import MetricsCollector, StageTimer, UtteranceMetric
from voicebridge.metrics.logger import StructuredMetricsLogger

logger = get_logger(__name__)


@dataclass
class DirectionSpec:
    """Configuration for one direction of translation."""

    source_lang: str   # "en"
    target_lang: str   # "ar"
    speaker: str        # participant id this direction listens to

    @property
    def label(self) -> str:
        return f"{self.source_lang.upper()}->{self.target_lang.upper()}"


class DirectionWorker:
    """Runs the full pipeline for a single direction."""

    def __init__(
        self,
        config: Config,
        spec: DirectionSpec,
        source,
        translation: TranslationManager,
        tts: TtsEngine,
        lipsync: LipSyncManager,
        emit,
        stop_event: threading.Event,
    ):
        self._config = config
        self._spec = spec
        self._source = source
        self._translation = translation
        self._tts = tts
        self._lipsync = lipsync
        self._emit = emit
        self._stop_event = stop_event

        self._sample_rate = int(config.get("audio.sample_rate", 16000))
        self._temp_dir = config.path("app.temp_chunk_dir")
        self._voice = config.language(spec.target_lang)["edge_voice"]

        # Per-direction STT engine (no shared model, no global lock).
        self._stt = SttManager(config, label=spec.label, source_lang=spec.source_lang)
        self._buffer = SentenceBuffer(config)

        self._sentence_queue: "queue.Queue[str]" = queue.Queue()
        self._sentence_counter = 0
        self._threads: list[threading.Thread] = []

        # Metrics collectors
        self._metrics_collector = MetricsCollector.get_instance()
        self._metrics_logger = StructuredMetricsLogger(config)
        self._recent_stage_latencies: dict[str, float] = {}

    # -- lifecycle ----------------------------------------------------------

    def start(self) -> None:
        self._emit(self._status_event(f"{self._spec.label} pipeline starting"))
        capture = threading.Thread(
            target=self._capture_loop, name=f"capture-{self._spec.label}", daemon=True
        )
        process = threading.Thread(
            target=self._process_loop, name=f"process-{self._spec.label}", daemon=True
        )
        timeout = threading.Thread(
            target=self._timeout_loop, name=f"timeout-{self._spec.label}", daemon=True
        )
        self._threads = [capture, process, timeout]
        for thread in self._threads:
            thread.start()

    def join(self) -> None:
        for thread in self._threads:
            thread.join(timeout=5)

    # -- capture: audio -> STT -> buffer -----------------------------------

    def _capture_loop(self) -> None:
        try:
            for segment in self._source.segments():
                if self._stop_event.is_set():
                    break
                self._handle_segment(segment)
        except Exception as error:  # noqa: BLE001
            logger.exception("[%s] capture loop crashed", self._spec.label)
            self._emit(self._error_event(f"capture failed: {error}"))
        finally:
            # Release any trailing buffered text at end of stream.
            for sentence in self._buffer.force_flush():
                self._sentence_queue.put(sentence)

    def _handle_segment(self, segment) -> None:
        t_capture = time.perf_counter()
        audio_file = save_segment_wav(
            segment, self._sample_rate, self._temp_dir, self._spec.label.replace("->", "to")
        )
        cap_lat = (time.perf_counter() - t_capture) * 1000.0

        try:
            t_stt = time.perf_counter()
            result = self._stt.transcribe(audio_file)
            stt_lat = (time.perf_counter() - t_stt) * 1000.0
        finally:
            audio_file.unlink(missing_ok=True)

        if not result.text:
            return

        self._recent_stage_latencies["Audio Capture"] = cap_lat
        self._recent_stage_latencies["VAD"] = 24.0  # Silero VAD segmenting estimate
        self._recent_stage_latencies["STT"] = stt_lat

        logger.debug("[%s] STT: %s", self._spec.label, result.text)

        t_buf = time.perf_counter()
        added_sentences = list(self._buffer.add(result.text))
        buf_lat = (time.perf_counter() - t_buf) * 1000.0
        self._recent_stage_latencies["Sentence Buffer"] = buf_lat

        for sentence in added_sentences:
            self._enqueue_sentence(sentence)

    def _enqueue_sentence(self, sentence: str) -> None:
        self._emit(
            PipelineEvent(
                type=EventType.TRANSCRIPT,
                direction=self._spec.label,
                speaker=self._spec.speaker,
                text=sentence,
                source_lang=self._spec.source_lang,
                target_lang=self._spec.target_lang,
            )
        )
        self._sentence_queue.put(sentence)

    # -- timeout: flush buffer on pause ------------------------------------

    def _timeout_loop(self) -> None:
        while not self._stop_event.is_set():
            time.sleep(0.5)
            for sentence in self._buffer.flush_on_timeout():
                self._enqueue_sentence(sentence)

    # -- process: sentence -> translate -> TTS -> lipsync -> emit ----------

    def _process_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                sentence = self._sentence_queue.get(timeout=0.3)
            except queue.Empty:
                continue
            try:
                self._process_sentence(sentence)
            except Exception as error:  # noqa: BLE001
                logger.exception("[%s] processing failed", self._spec.label)
                self._emit(self._error_event(f"processing failed: {error}"))

    def _process_sentence(self, sentence: str) -> None:
        self._sentence_counter += 1
        sentence_id = self._sentence_counter
        start = time.perf_counter()
        stage_latencies: dict[str, float] = dict(self._recent_stage_latencies)

        try:
            t_tr = time.perf_counter()
            translated = self._translation.translate(
                sentence, self._spec.source_lang, self._spec.target_lang
            )
            tr_lat = (time.perf_counter() - t_tr) * 1000.0
            stage_latencies["Translation"] = tr_lat
        except TranslationError as error:
            self._emit(self._error_event(f"translation failed: {error}"))
            return

        self._emit(
            PipelineEvent(
                type=EventType.TRANSLATION,
                direction=self._spec.label,
                speaker=self._spec.speaker,
                text=sentence,
                translated_text=translated,
                source_lang=self._spec.source_lang,
                target_lang=self._spec.target_lang,
                sentence_id=sentence_id,
            )
        )

        # ONE-WAY VOICE MODE: For speaker "other" (second person), translation is text-only.
        # Voice generation (TTS) and audio/video playback code for second person is commented out below:
        if self._spec.speaker == "other":
            logger.info("[%s] Text-only translation for speaker 'other' (voice disabled)", self._spec.label)
            # --- UNCOMMENT BELOW CODE IF YOU WANT SECOND PERSON VOICE TRANSLATION LATER ---
            # t_tts = time.perf_counter()
            # audio_path = self._tts.synthesize(
            #     translated, self._voice, self._spec.label, sentence_id
            # )
            # tts_lat = (time.perf_counter() - t_tts) * 1000.0
            # stage_latencies["TTS"] = tts_lat
            #
            # t_lip = time.perf_counter()
            # lip_result = self._lipsync.sync(audio_path, self._spec.label, sentence_id)
            # lip_lat = (time.perf_counter() - t_lip) * 1000.0
            # stage_latencies["Lip Sync"] = lip_lat
            # stage_latencies["Playback"] = 15.0  # Playback dispatch baseline
            #
            # latency_ms = (time.perf_counter() - start) * 1000
            # fps_val = 25.0 if lip_result.is_synced else 0.0
            # metric = UtteranceMetric(
            #     session_id=f"session_{self._spec.label}",
            #     direction=self._spec.label,
            #     sentence_id=sentence_id,
            #     text=sentence,
            #     translated_text=translated,
            #     source_lang=self._spec.source_lang,
            #     target_lang=self._spec.target_lang,
            #     stage_latencies_ms=stage_latencies,
            #     total_latency_ms=latency_ms,
            #     audio_duration_sec=3.0,
            #     lip_sync_backend=lip_result.backend,
            #     is_synced=lip_result.is_synced,
            #     fps=fps_val,
            # )
            # self._metrics_collector.record_utterance(metric)
            # self._metrics_logger.log_utterance(metric)
            # self._emit(
            #     PipelineEvent(
            #         type=EventType.SPEECH_READY,
            #         direction=self._spec.label,
            #         speaker=self._spec.speaker,
            #         text=sentence,
            #         translated_text=translated,
            #         source_lang=self._spec.source_lang,
            #         target_lang=self._spec.target_lang,
            #         audio_url=str(lip_result.audio_path),
            #         video_url=str(lip_result.video_path) if lip_result.video_path else "",
            #         is_synced=lip_result.is_synced,
            #         latency_ms=latency_ms,
            #         note=lip_result.note,
            #         sentence_id=sentence_id,
            #     )
            # )
            # ---------------------------------------------------------------------------------
            return

        t_tts = time.perf_counter()
        audio_path = self._tts.synthesize(
            translated, self._voice, self._spec.label, sentence_id
        )
        tts_lat = (time.perf_counter() - t_tts) * 1000.0
        stage_latencies["TTS"] = tts_lat

        t_lip = time.perf_counter()
        lip_result = self._lipsync.sync(audio_path, self._spec.label, sentence_id)
        lip_lat = (time.perf_counter() - t_lip) * 1000.0
        stage_latencies["Lip Sync"] = lip_lat
        stage_latencies["Playback"] = 15.0  # Playback dispatch baseline

        latency_ms = (time.perf_counter() - start) * 1000

        # Record utterance metrics
        fps_val = 25.0 if lip_result.is_synced else 0.0
        metric = UtteranceMetric(
            session_id=f"session_{self._spec.label}",
            direction=self._spec.label,
            sentence_id=sentence_id,
            text=sentence,
            translated_text=translated,
            source_lang=self._spec.source_lang,
            target_lang=self._spec.target_lang,
            stage_latencies_ms=stage_latencies,
            total_latency_ms=latency_ms,
            audio_duration_sec=3.0,  # estimated segment audio length
            lip_sync_backend=lip_result.backend,
            is_synced=lip_result.is_synced,
            fps=fps_val,
        )
        self._metrics_collector.record_utterance(metric)
        self._metrics_logger.log_utterance(metric)

        self._emit(
            PipelineEvent(
                type=EventType.SPEECH_READY,
                direction=self._spec.label,
                speaker=self._spec.speaker,
                text=sentence,
                translated_text=translated,
                source_lang=self._spec.source_lang,
                target_lang=self._spec.target_lang,
                audio_url=str(lip_result.audio_path),
                video_url=str(lip_result.video_path) if lip_result.video_path else "",
                is_synced=lip_result.is_synced,
                latency_ms=latency_ms,
                note=lip_result.note,
                sentence_id=sentence_id,
            )
        )

    # -- event helpers ------------------------------------------------------

    def _status_event(self, message: str) -> PipelineEvent:
        return PipelineEvent(
            type=EventType.STATUS, direction=self._spec.label,
            speaker=self._spec.speaker, note=message,
        )

    def _error_event(self, message: str) -> PipelineEvent:
        return PipelineEvent(
            type=EventType.ERROR, direction=self._spec.label,
            speaker=self._spec.speaker, note=message,
        )

