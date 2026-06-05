"""
Speech-to-Text Transcriber using faster-whisper.
Optimized for Traditional Chinese (繁體中文) financial podcast content.
Uses CUDA acceleration with RTX 3060 GPU.
"""

import logging
import os

logger = logging.getLogger(__name__)


def transcribe(audio_path, model_name="medium", device="cuda", language="zh"):
    """
    Transcribe audio to text using faster-whisper.
    
    Args:
        audio_path: Path to audio file
        model_name: Whisper model size (tiny/base/small/medium/large-v3)
        device: 'cuda' for GPU or 'cpu'
        language: Language code ('zh' for Chinese)
    
    Returns:
        str: Transcribed text
    """
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    file_size = os.path.getsize(audio_path) / (1024 * 1024)
    logger.info("Transcribing: %s (%.1f MB) with model=%s device=%s",
                audio_path, file_size, model_name, device)

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        logger.error("faster-whisper not installed. Run: pip install faster-whisper")
        raise

    # Determine compute type based on device
    if device == "cuda":
        compute_type = "float16"  # Best for NVIDIA GPUs
    else:
        compute_type = "int8"     # Best for CPU

    try:
        logger.info("Loading Whisper model '%s' on %s (compute_type=%s)...",
                     model_name, device, compute_type)
        model = WhisperModel(model_name, device=device, compute_type=compute_type)
        logger.info("Model loaded successfully.")
    except Exception as e:
        if device == "cuda":
            logger.warning("CUDA failed (%s), falling back to CPU...", e)
            device = "cpu"
            compute_type = "int8"
            model = WhisperModel(model_name, device=device, compute_type=compute_type)
        else:
            raise

    # Initial prompt helps guide the model for Traditional Chinese financial content
    initial_prompt = (
        "以下是繁體中文的財經節目「股癌」的內容。"
        "節目討論台灣與美國股市、個股分析、產業趨勢。"
        "常見用語包括：台積電、大盤、本益比、殖利率、ETF、"
        "半導體、AI、費城半導體指數、聯準會、Fed、CPI。"
    )

    logger.info("Starting transcription (language=%s)...", language)

    try:
        segments, info = model.transcribe(
            audio_path,
            language=language,
            initial_prompt=initial_prompt,
            vad_filter=True,           # Voice Activity Detection to skip silence
            vad_parameters=dict(
                min_silence_duration_ms=500,
            ),
            beam_size=5,
            best_of=5,
        )

        # Collect all segments
        text_parts = []
        total_duration = 0

        for segment in segments:
            text_parts.append(segment.text.strip())
            total_duration = max(total_duration, segment.end)

        full_text = ' '.join(text_parts)

        # Clean up the text
        full_text = _clean_transcript(full_text)

        logger.info(
            "Transcription complete: %d characters, %.1f min audio, "
            "detected language: %s (prob: %.2f)",
            len(full_text), total_duration / 60,
            info.language, info.language_probability
        )

        return full_text

    except Exception as e:
        logger.error("Transcription failed: %s", e)
        raise


def _clean_transcript(text):
    """Clean up transcribed text - remove duplicates and artifacts."""
    import re

    # Remove common Whisper artifacts
    text = re.sub(r'(\.{3,})', '...', text)
    text = re.sub(r'\s+', ' ', text)

    # Remove repeated phrases (Whisper sometimes loops)
    words = text.split()
    if len(words) > 20:
        cleaned = []
        i = 0
        while i < len(words):
            # Check for repeated sequences
            repeat_found = False
            for seq_len in range(3, min(20, len(words) - i)):
                seq = words[i:i + seq_len]
                next_seq = words[i + seq_len:i + 2 * seq_len]
                if seq == next_seq:
                    cleaned.extend(seq)
                    i += 2 * seq_len
                    repeat_found = True
                    break
            if not repeat_found:
                cleaned.append(words[i])
                i += 1
        text = ' '.join(cleaned)

    return text.strip()
