import asyncio
import os
import queue
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

# Helps avoid some Windows OpenMP runtime conflicts with AI packages.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import edge_tts
import numpy as np
import sounddevice as sd
from deep_translator import GoogleTranslator
from faster_whisper import WhisperModel
from playsound import playsound
from scipy.io.wavfile import write


# VoiceBridge AI - Two Way Video Call Translator backend prototype.
# Future Chrome extension plan:
# - Pipeline A receives microphone audio.
# - Pipeline B receives Google Meet / Zoom tab audio.

CHUNK_SECONDS = 4
SAMPLE_RATE = 16000

# The sentence buffer sends text to translation only when one of these happens:
# 1. A sentence-ending punctuation mark appears.
# 2. The buffer reaches enough words.
# 3. The speaker pauses long enough for a timeout.
BUFFER_WORD_LIMIT = 10
BUFFER_TIMEOUT_SECONDS = 4
SENTENCE_ENDINGS = (".", "?", "!", "\u061f", "\u06d4", "\u0964")

BASE_DIR = Path(__file__).resolve().parent
TEMP_CHUNK_DIR = BASE_DIR / "temp_chunks"
TTS_OUTPUT_DIR = BASE_DIR / "generated_speech"

STOP_SENTINEL = object()
stop_event = threading.Event()
whisper_lock = threading.Lock()

LANGUAGES = {
    "1": {
        "display_name": "English",
        "translation_code": "en",
        "edge_voice": "en-US-JennyNeural",
    },
    "2": {
        "display_name": "Arabic",
        "translation_code": "ar",
        "edge_voice": "ar-SA-ZariyahNeural",
    },
    "3": {
        "display_name": "Urdu",
        "translation_code": "ur",
        "edge_voice": "ur-PK-UzmaNeural",
    },
    "4": {
        "display_name": "Hindi",
        "translation_code": "hi",
        "edge_voice": "hi-IN-SwaraNeural",
    },
    "5": {
        "display_name": "French",
        "translation_code": "fr",
        "edge_voice": "fr-FR-DeniseNeural",
    },
    "6": {
        "display_name": "Spanish",
        "translation_code": "es",
        "edge_voice": "es-ES-ElviraNeural",
    },
}

NOISE_PHRASES = {
    "thanks for watching",
    "thank you for watching",
    "please subscribe",
    "subscribe",
}


@dataclass
class PipelineContext:
    """All queues and settings for one translation direction."""

    direction: str
    source_language: dict
    target_language: dict
    audio_queue: queue.Queue = field(default_factory=queue.Queue)
    text_queue: queue.Queue = field(default_factory=queue.Queue)
    sentence_queue: queue.Queue = field(default_factory=queue.Queue)
    translated_queue: queue.Queue = field(default_factory=queue.Queue)


def log(message):
    print(message, flush=True)


def clean_text(text):
    """Normalize whitespace while keeping multilingual text unchanged."""
    text = text.replace("\n", " ").replace("\r", " ")
    return re.sub(r"\s+", " ", text).strip()


def count_words(text):
    """Count words in a simple way that works for English, Arabic, Urdu, etc."""
    text = re.sub(r"[^\w\s'-]", " ", text, flags=re.UNICODE)
    words = [word for word in text.split() if any(char.isalnum() for char in word)]
    return len(words)


def ends_with_sentence_punctuation(text):
    return clean_text(text).endswith(SENTENCE_ENDINGS)


def looks_like_noise(text):
    """Reject empty/noisy Whisper outputs before they enter the buffer."""
    text = clean_text(text)
    lower_text = text.casefold()

    if not text:
        return True

    if lower_text in NOISE_PHRASES:
        return True

    if re.fullmatch(r"[\W_]+", text):
        return True

    if re.fullmatch(r"[\[(]?(music|noise|silence|applause)[\])]?", lower_text):
        return True

    words = lower_text.split()
    if len(words) >= 4 and len(set(words)) == 1:
        return True

    letters = [char for char in lower_text if char.isalpha()]
    if len(letters) > 8 and len(set(letters)) <= 2:
        return True

    return False


def split_complete_sentences(text):
    """Return complete punctuated sentences and the unfinished tail."""
    complete_sentences = []
    start_index = 0

    for index, char in enumerate(text):
        if char in SENTENCE_ENDINGS:
            sentence = clean_text(text[start_index : index + 1])
            if sentence:
                complete_sentences.append(sentence)
            start_index = index + 1

    remainder = clean_text(text[start_index:])
    return complete_sentences, remainder


def select_language(title):
    """Ask the user to select one supported language."""
    log(f"\n{title}")
    for key, language in LANGUAGES.items():
        log(
            f"{key}. {language['display_name']} "
            f"({language['translation_code']}, {language['edge_voice']})"
        )

    choice = input("Enter choice number: ").strip()

    if choice not in LANGUAGES:
        log("[LANGUAGE] Invalid choice. Defaulting to English.")
        choice = "1"

    selected = LANGUAGES[choice]
    log(f"[LANGUAGE] Selected: {selected['display_name']}")
    return selected


def ask_for_other_person_wav():
    """Optional Pipeline B test using a WAV file until tab audio is available."""
    answer = input(
        "\nTest OTHER -> ME using a WAV file for now? (y/n): "
    ).strip().casefold()

    if answer not in {"y", "yes"}:
        return None

    default_wav = BASE_DIR / "test.wav"
    prompt = "Enter WAV file path"
    if default_wav.exists():
        prompt += " (press Enter for test.wav)"
    prompt += ": "

    raw_path = input(prompt).strip().strip('"')

    if not raw_path and default_wav.exists():
        wav_path = default_wav
    else:
        wav_path = Path(raw_path).expanduser()

    if not wav_path.is_absolute():
        wav_path = BASE_DIR / wav_path

    if not wav_path.exists() or wav_path.suffix.casefold() != ".wav":
        log(f"[OTHER -> ME] WAV file not found or not a .wav file: {wav_path}")
        log("[OTHER -> ME] Skipping Pipeline B for now.")
        return None

    return wav_path


def print_project_flow(my_language, other_language, other_wav_path):
    """Show the two-way purpose clearly at startup."""
    log("\nVoiceBridge AI - Two Way Video Call Translator")
    log("------------------------------------------------")
    log(
        "Direction 1: My "
        f"{my_language['display_name']} speech -> "
        f"{other_language['display_name']} translated text + voice"
    )
    log(
        "Direction 2: Other "
        f"{other_language['display_name']} speech -> "
        f"{my_language['display_name']} translated text (voice disabled, commented out)"
    )
    log("Pipeline A input: microphone")

    if other_wav_path:
        log(f"Pipeline B input: WAV file ({other_wav_path.name})")
    else:
        log("Pipeline B input: skipped for now; Chrome extension will provide tab audio")

    log("------------------------------------------------\n")


def load_whisper_model():
    """Load faster-whisper once. Try CUDA first, then fall back to CPU."""
    log("[MODEL] Loading faster-whisper model...")

    try:
        model = WhisperModel("tiny", device="cuda", compute_type="float16")
        log("[MODEL] Using GPU: tiny model on CUDA with float16")
        return model
    except Exception as cuda_error:
        log("[MODEL] CUDA failed. Falling back to CPU.")
        log(f"[MODEL] CUDA reason: {cuda_error}")

    model = WhisperModel("base", device="cpu", compute_type="int8")
    log("[MODEL] Using CPU: base model with int8")
    return model


def save_microphone_chunk(recording, context, chunk_id):
    """Save one microphone chunk as a temporary WAV file for faster-whisper."""
    TEMP_CHUNK_DIR.mkdir(exist_ok=True)

    safe_direction = context.direction.lower().replace(" ", "_").replace("->", "to")
    audio_file = TEMP_CHUNK_DIR / f"{safe_direction}_{chunk_id}_{uuid.uuid4().hex}.wav"

    # sounddevice returns float audio. PCM int16 WAV is widely compatible.
    pcm_audio = np.clip(recording, -1.0, 1.0)
    pcm_audio = (pcm_audio * 32767).astype(np.int16)

    write(str(audio_file), SAMPLE_RATE, pcm_audio)
    return audio_file


def microphone_recorder_worker(context):
    """Pipeline A producer: continuously records microphone chunks."""
    chunk_id = 1

    while not stop_event.is_set():
        try:
            log(f"\n[{context.direction}] Recording chunk {chunk_id}")

            recording = sd.rec(
                int(CHUNK_SECONDS * SAMPLE_RATE),
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="float32",
            )
            sd.wait()

            if stop_event.is_set():
                break

            audio_file = save_microphone_chunk(recording, context, chunk_id)
            context.audio_queue.put(
                {"chunk_id": chunk_id, "audio_file": audio_file, "delete_after": True}
            )
            log(f"[{context.direction}] Queued microphone chunk {chunk_id}")

            chunk_id += 1

        except Exception as error:
            if not stop_event.is_set():
                log(f"[{context.direction}] Recorder error: {error}")
                time.sleep(0.5)

    log(f"[{context.direction}] Recorder stopped.")


def wav_file_producer_worker(context, wav_path):
    """Pipeline B producer: sends one WAV file through the same backend stages."""
    try:
        log(f"[{context.direction}] Processing {wav_path.name}")
        context.audio_queue.put(
            {"chunk_id": 1, "audio_file": wav_path, "delete_after": False}
        )
    except Exception as error:
        log(f"[{context.direction}] WAV producer error: {error}")
    finally:
        context.audio_queue.put(STOP_SENTINEL)


def transcribe_audio(model, audio_file):
    """Run Whisper with requested real-time/noise settings."""
    try:
        return model.transcribe(
            str(audio_file),
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 500},
            beam_size=5,
            temperature=0.0,
            condition_on_previous_text=False,
            no_speech_threshold=0.6,
            log_prob_threshold=-1.0,
            compression_ratio_threshold=2.4,
        )
    except TypeError:
        # Older faster-whisper versions may not support every keyword above.
        return model.transcribe(
            str(audio_file),
            vad_filter=True,
            beam_size=5,
            condition_on_previous_text=False,
        )


def segment_is_reliable(segment):
    """Use Whisper confidence fields to reduce silence hallucinations."""
    no_speech_prob = getattr(segment, "no_speech_prob", 0.0) or 0.0
    avg_logprob = getattr(segment, "avg_logprob", 0.0) or 0.0
    compression_ratio = getattr(segment, "compression_ratio", 0.0) or 0.0

    if no_speech_prob > 0.85:
        return False
    if avg_logprob < -1.5:
        return False
    if compression_ratio > 2.8:
        return False

    return True


def stt_worker(context, model):
    """Convert audio chunks/files to text and send useful text to the buffer."""
    while True:
        item = context.audio_queue.get()

        if item is STOP_SENTINEL:
            context.audio_queue.task_done()
            context.text_queue.put(STOP_SENTINEL)
            log(f"[{context.direction}] STT worker stopped.")
            break

        chunk_id = item["chunk_id"]
        audio_file = item["audio_file"]
        delete_after = item["delete_after"]

        try:
            log(f"[{context.direction}] STT processing chunk {chunk_id}")

            # One Whisper model is shared by both directions.
            # The lock keeps shared model access stable on Windows.
            with whisper_lock:
                segments, info = transcribe_audio(model, audio_file)
                segment_list = list(segments)

            accepted_parts = []
            for segment in segment_list:
                segment_text = clean_text(segment.text)
                if segment_text and segment_is_reliable(segment):
                    accepted_parts.append(segment_text)

            original_text = clean_text(" ".join(accepted_parts))
            detected_language = getattr(info, "language", "unknown")

            if not original_text or looks_like_noise(original_text):
                log(f"[{context.direction}] STT: no clear speech in chunk {chunk_id}")
                continue

            log(f"[{context.direction}] STT: {original_text}")
            context.text_queue.put((chunk_id, original_text, detected_language))

        except Exception as error:
            log(f"[{context.direction}] STT error in chunk {chunk_id}: {error}")

        finally:
            if delete_after:
                try:
                    Path(audio_file).unlink(missing_ok=True)
                except Exception as cleanup_error:
                    log(f"[{context.direction}] Could not delete temp chunk: {cleanup_error}")

            context.audio_queue.task_done()


def should_accept_fragment(text, buffer_has_text):
    """Ignore one-word unclear fragments unless they complete a sentence."""
    if looks_like_noise(text):
        return False

    if count_words(text) <= 1 and not ends_with_sentence_punctuation(text):
        return buffer_has_text

    return True


def should_translate_sentence(sentence):
    """Final guard before translation."""
    sentence = clean_text(sentence)

    if looks_like_noise(sentence):
        return False

    if count_words(sentence) <= 1 and not ends_with_sentence_punctuation(sentence):
        return False

    return True


def sentence_buffer_worker(context):
    """Build complete sentences from STT fragments before translation."""
    buffer_text = ""
    last_detected_language = context.source_language["translation_code"]
    last_update_time = None
    sentence_id = 1

    def emit_sentence(sentence, reason):
        nonlocal sentence_id

        sentence = clean_text(sentence)
        if not should_translate_sentence(sentence):
            log(f"[{context.direction}] Buffer ignored unclear sentence: {sentence}")
            return

        log(f"[{context.direction}] Sentence buffer ({reason}): {sentence}")
        context.sentence_queue.put(
            (sentence_id, sentence, last_detected_language, reason)
        )
        sentence_id += 1

    def flush_if_timed_out():
        nonlocal buffer_text, last_update_time

        if not buffer_text or last_update_time is None:
            return

        elapsed = time.time() - last_update_time
        if elapsed < BUFFER_TIMEOUT_SECONDS:
            return

        if count_words(buffer_text) <= 1 and not ends_with_sentence_punctuation(buffer_text):
            log(f"[{context.direction}] Buffer dropped short unclear text: {buffer_text}")
        else:
            emit_sentence(buffer_text, "timeout")

        buffer_text = ""
        last_update_time = None

    while True:
        try:
            item = context.text_queue.get(timeout=0.5)
        except queue.Empty:
            flush_if_timed_out()
            continue

        if item is STOP_SENTINEL:
            context.text_queue.task_done()

            if buffer_text:
                emit_sentence(buffer_text, "shutdown")

            context.sentence_queue.put(STOP_SENTINEL)
            log(f"[{context.direction}] Sentence buffer stopped.")
            break

        chunk_id, text, detected_language = item

        try:
            text = clean_text(text)
            buffer_has_text = bool(buffer_text)

            if not should_accept_fragment(text, buffer_has_text):
                log(f"[{context.direction}] Buffer ignored short/noisy chunk {chunk_id}: {text}")
                continue

            last_detected_language = detected_language
            last_update_time = time.time()
            buffer_text = clean_text(f"{buffer_text} {text}")
            log(f"[{context.direction}] Buffer: {buffer_text}")

            complete_sentences, remainder = split_complete_sentences(buffer_text)
            for sentence in complete_sentences:
                emit_sentence(sentence, "punctuation")

            buffer_text = remainder

            if buffer_text and count_words(buffer_text) >= BUFFER_WORD_LIMIT:
                emit_sentence(buffer_text, "word limit")
                buffer_text = ""
                last_update_time = None

        except Exception as error:
            log(f"[{context.direction}] Buffer error in chunk {chunk_id}: {error}")

        finally:
            context.text_queue.task_done()


def translation_worker(context):
    """Translate complete sentences using deep-translator."""
    target_code = context.target_language["translation_code"]
    target_name = context.target_language["display_name"]
    translator = GoogleTranslator(source="auto", target=target_code)

    while True:
        item = context.sentence_queue.get()

        if item is STOP_SENTINEL:
            context.sentence_queue.task_done()
            context.translated_queue.put(STOP_SENTINEL)
            log(f"[{context.direction}] Translation worker stopped.")
            break

        sentence_id, original_sentence, detected_language, reason = item

        try:
            log(f"[{context.direction}] Translating sentence {sentence_id}")
            translated_text = clean_text(translator.translate(original_sentence))

            if not translated_text:
                log(f"[{context.direction}] Empty translation for sentence {sentence_id}")
                continue

            log(f"[{context.direction}] Original ({detected_language}): {original_sentence}")
            log(f"[{context.direction}] Translated {target_name}: {translated_text}")

            context.translated_queue.put((sentence_id, translated_text))

        except Exception as error:
            log(f"[{context.direction}] Translation error in sentence {sentence_id}: {error}")

        finally:
            context.sentence_queue.task_done()


async def generate_voice(text, context, sentence_id):
    """Generate a unique MP3 file with Edge TTS."""
    safe_direction = context.direction.lower().replace(" ", "_").replace("->", "to")
    output_dir = TTS_OUTPUT_DIR / safe_direction
    output_dir.mkdir(parents=True, exist_ok=True)

    output_audio = output_dir / f"translated_{sentence_id}_{uuid.uuid4().hex}.mp3"
    voice = context.target_language["edge_voice"]

    communicate = edge_tts.Communicate(text, voice=voice)
    await communicate.save(str(output_audio))

    return output_audio


def tts_worker(context):
    """Convert translated sentences to speech and play them in order."""
    while True:
        item = context.translated_queue.get()

        if item is STOP_SENTINEL:
            context.translated_queue.task_done()
            log(f"[{context.direction}] TTS worker stopped.")
            break

        # ONE-WAY VOICE MODE: Only translate MY voice into speech audio.
        # For second person (OTHER -> ME), translation is text-only (voice generation/playback disabled).
        if context.direction == "OTHER -> ME":
            log(f"[{context.direction}] Text-only translation (voice disabled): {translated_text}")
            # --- UNCOMMENT BELOW CODE IF YOU WANT SECOND PERSON VOICE TRANSLATION LATER ---
            # try:
            #     log(f"[{context.direction}] Voice generation for sentence {sentence_id}")
            #     output_audio = asyncio.run(generate_voice(translated_text, context, sentence_id))
            #     log(f"[{context.direction}] Playing voice: {output_audio.name}")
            #     playsound(str(output_audio))
            # except Exception as error:
            #     log(f"[{context.direction}] TTS/playback error in sentence {sentence_id}: {error}")
            # ---------------------------------------------------------------------------------
            context.translated_queue.task_done()
            continue

        try:
            log(f"[{context.direction}] Voice generation for sentence {sentence_id}")
            output_audio = asyncio.run(generate_voice(translated_text, context, sentence_id))

            log(f"[{context.direction}] Playing voice: {output_audio.name}")
            playsound(str(output_audio))

        except Exception as error:
            log(f"[{context.direction}] TTS/playback error in sentence {sentence_id}: {error}")

        finally:
            context.translated_queue.task_done()


def start_pipeline_workers(context, model, producer_thread):
    """Start one complete direction: input -> STT -> buffer -> translation -> TTS."""
    threads = [
        producer_thread,
        threading.Thread(
            target=stt_worker,
            args=(context, model),
            name=f"{context.direction} STT",
            daemon=True,
        ),
        threading.Thread(
            target=sentence_buffer_worker,
            args=(context,),
            name=f"{context.direction} Buffer",
            daemon=True,
        ),
        threading.Thread(
            target=translation_worker,
            args=(context,),
            name=f"{context.direction} Translator",
            daemon=True,
        ),
        threading.Thread(
            target=tts_worker,
            args=(context,),
            name=f"{context.direction} TTS",
            daemon=True,
        ),
    ]

    for thread in threads:
        thread.start()

    return threads


def stop_pipelines(contexts):
    """Ask all active pipelines to stop and wake up their STT workers."""
    log("\n[STOP] Stopping VoiceBridge AI pipelines...")
    stop_event.set()

    try:
        sd.stop()
    except Exception:
        pass

    for context in contexts:
        context.audio_queue.put(STOP_SENTINEL)


def main():
    log("\nVoiceBridge AI - Two Way Video Call Translator")

    my_language = select_language("Select My Language:")
    other_language = select_language("Select Other Person Language:")
    other_wav_path = ask_for_other_person_wav()

    print_project_flow(my_language, other_language, other_wav_path)

    model = load_whisper_model()

    me_to_other = PipelineContext(
        direction="ME -> OTHER",
        source_language=my_language,
        target_language=other_language,
    )
    other_to_me = PipelineContext(
        direction="OTHER -> ME",
        source_language=other_language,
        target_language=my_language,
    )

    active_contexts = [me_to_other]
    all_threads = []

    mic_thread = threading.Thread(
        target=microphone_recorder_worker,
        args=(me_to_other,),
        name="ME -> OTHER Recorder",
        daemon=True,
    )
    all_threads.extend(start_pipeline_workers(me_to_other, model, mic_thread))

    if other_wav_path:
        active_contexts.append(other_to_me)
        wav_thread = threading.Thread(
            target=wav_file_producer_worker,
            args=(other_to_me, other_wav_path),
            name="OTHER -> ME WAV Producer",
            daemon=True,
        )
        all_threads.extend(start_pipeline_workers(other_to_me, model, wav_thread))
    else:
        log("[OTHER -> ME] Pipeline B skipped for now.")

    log("\n[START] Two-way backend pipeline is running.")
    log("[START] Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        stop_pipelines(active_contexts)

        for thread in all_threads:
            thread.join(timeout=5)

        log("[STOP] VoiceBridge AI stopped cleanly.")


if __name__ == "__main__":
    main()
