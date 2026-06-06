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

    # Add NVIDIA CUDA/cuDNN DLLs to path if installed in python packages
    try:
        import sys
        site_packages = [p for p in sys.path if p.endswith('site-packages')]
        if site_packages:
            sp = site_packages[0]
            cublas_bin = os.path.join(sp, 'nvidia', 'cublas', 'bin')
            cudnn_bin = os.path.join(sp, 'nvidia', 'cudnn', 'bin')
            if os.path.exists(cublas_bin) and cublas_bin not in os.environ['PATH']:
                os.environ['PATH'] = cublas_bin + os.pathsep + os.environ['PATH']
                logger.info("Added to PATH: %s", cublas_bin)
            if os.path.exists(cudnn_bin) and cudnn_bin not in os.environ['PATH']:
                os.environ['PATH'] = cudnn_bin + os.pathsep + os.environ['PATH']
                logger.info("Added to PATH: %s", cudnn_bin)
    except Exception as e:
        logger.warning("Failed to add NVIDIA library paths: %s", e)

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        logger.error("faster-whisper not installed. Run: pip install faster-whisper")
        raise

    # Initial prompt helps guide the model for Traditional Chinese financial content
    initial_prompt = (
        "以下是繁體中文的財經節目「股癌」的內容。"
        "節目討論台灣與美國股市、個股分析、產業趨勢。"
        "常見用語包括：台積電、大盤、本益比、殖利率、ETF、"
        "半導體、AI、費城半導體指數、聯準會、Fed、CPI。"
    )

    def run_transcription(dev, comp_type):
        logger.info("Loading Whisper model '%s' on %s (compute_type=%s)...",
                     model_name, dev, comp_type)
        model = WhisperModel(model_name, device=dev, compute_type=comp_type)
        logger.info("Model loaded successfully. Starting transcription (language=%s)...", language)
        
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
        last_reported_pct = -5

        for segment in segments:
            text_parts.append(segment.text.strip())
            total_duration = max(total_duration, segment.end)
            
            # Print progress every 5%
            if info.duration > 0:
                pct = (segment.end / info.duration) * 100
                if pct - last_reported_pct >= 5:
                    logger.info("Transcription progress: %.1f%%", pct)
                    last_reported_pct = pct

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

    if device == "cuda":
        try:
            return run_transcription("cuda", "float16")
        except Exception as e:
            logger.warning("CUDA transcription failed (%s). Falling back to CPU...", e)
            return run_transcription("cpu", "int8")
    else:
        return run_transcription("cpu", "int8")


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
