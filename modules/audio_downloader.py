"""
Audio Downloader using yt-dlp.
Downloads audio-only from YouTube videos and attempts to fetch auto-generated subtitles.
"""

import os
import logging
import glob

logger = logging.getLogger(__name__)

AUDIO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'audio')

def ensure_audio_dir():
    """Ensure the audio directory exists."""
    os.makedirs(AUDIO_DIR, exist_ok=True)
    return AUDIO_DIR

# Auto-detect FFmpeg path (winget installs to a non-PATH location)
FFMPEG_PATH = None

def _find_ffmpeg():
    """Find FFmpeg binary, checking common install locations."""
    global FFMPEG_PATH
    if FFMPEG_PATH:
        return FFMPEG_PATH

    import shutil

    # Check if already on PATH
    if shutil.which('ffmpeg'):
        FFMPEG_PATH = os.path.dirname(shutil.which('ffmpeg'))
        return FFMPEG_PATH

    # Check WinGet install location
    local_appdata = os.environ.get('LOCALAPPDATA', '')
    if local_appdata:
        winget_dir = os.path.join(local_appdata, 'Microsoft', 'WinGet', 'Packages')
        if os.path.isdir(winget_dir):
            for root, dirs, files in os.walk(winget_dir):
                if 'ffmpeg.exe' in files:
                    FFMPEG_PATH = root
                    logger.info("Found FFmpeg at: %s", root)
                    # Add to PATH for this process
                    os.environ['PATH'] = root + os.pathsep + os.environ.get('PATH', '')
                    return FFMPEG_PATH

    # Check common locations
    for path in [
        r'C:\ffmpeg\bin',
        r'C:\Program Files\ffmpeg\bin',
        os.path.expanduser(r'~\ffmpeg\bin'),
    ]:
        if os.path.isfile(os.path.join(path, 'ffmpeg.exe')):
            FFMPEG_PATH = path
            os.environ['PATH'] = path + os.pathsep + os.environ.get('PATH', '')
            return FFMPEG_PATH

    logger.warning("FFmpeg not found. Audio conversion may fail.")
    return None


def download_subtitles(video_url, video_id):
    """
    Try to download auto-generated subtitles from YouTube.
    
    Returns:
        str or None: Subtitle text if available, None otherwise.
    """
    import yt_dlp

    ensure_audio_dir()
    sub_path = os.path.join(AUDIO_DIR, f"{video_id}_sub")

    ydl_opts = {
        'writeautomaticsub': True,
        'writesubtitles': True,
        'subtitleslangs': ['zh-Hant', 'zh-TW', 'zh', 'zh-Hans'],
        'subtitlesformat': 'vtt',
        'skip_download': True,
        'outtmpl': sub_path + '.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        # Look for downloaded subtitle files
        for ext in ['*.vtt', '*.srt', '*.ass']:
            pattern = os.path.join(AUDIO_DIR, f"{video_id}_sub*{ext}")
            files = glob.glob(pattern)
            if files:
                sub_file = files[0]
                logger.info("Found subtitle file: %s", sub_file)
                text = _parse_subtitle_file(sub_file)
                # Clean up subtitle file
                for f in files:
                    try:
                        os.remove(f)
                    except OSError:
                        pass
                if text and len(text.strip()) > 100:
                    return text

        logger.info("No usable subtitles found for video %s", video_id)
        return None

    except Exception as e:
        logger.warning("Failed to download subtitles: %s", e)
        return None


def _parse_subtitle_file(filepath):
    """Parse a VTT/SRT subtitle file and extract plain text."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        lines = content.split('\n')
        text_lines = []
        seen = set()

        for line in lines:
            line = line.strip()
            # Skip VTT headers, timestamps, and empty lines
            if not line:
                continue
            if line.startswith('WEBVTT'):
                continue
            if line.startswith('Kind:') or line.startswith('Language:'):
                continue
            if '-->' in line:
                continue
            if line.isdigit():
                continue
            # Remove HTML tags
            import re
            clean = re.sub(r'<[^>]+>', '', line)
            clean = clean.strip()
            if clean and clean not in seen:
                seen.add(clean)
                text_lines.append(clean)

        return ' '.join(text_lines)

    except Exception as e:
        logger.error("Failed to parse subtitle file %s: %s", filepath, e)
        return None


def download_audio(video_url, video_id):
    """
    Download audio from a YouTube video.
    
    Returns:
        str: Path to downloaded audio file.
    """
    import yt_dlp

    ensure_audio_dir()
    output_path = os.path.join(AUDIO_DIR, f"{video_id}.mp3")

    # If already downloaded, skip
    if os.path.exists(output_path):
        logger.info("Audio already exists: %s", output_path)
        return output_path

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(AUDIO_DIR, f"{video_id}.%(ext)s"),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '128',
        }],
        'quiet': False,
        'no_warnings': False,
    }

    ffmpeg_dir = _find_ffmpeg()
    if ffmpeg_dir:
        ydl_opts['ffmpeg_location'] = ffmpeg_dir

    try:
        logger.info("Downloading audio from: %s", video_url)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path) / (1024 * 1024)
            logger.info("Audio downloaded: %s (%.1f MB)", output_path, file_size)
            return output_path
        else:
            # yt-dlp might save with different extension, find the file
            for f in glob.glob(os.path.join(AUDIO_DIR, f"{video_id}.*")):
                if f.endswith(('.mp3', '.m4a', '.wav', '.ogg', '.opus')):
                    logger.info("Audio downloaded: %s", f)
                    return f

            raise FileNotFoundError(f"Downloaded audio file not found for {video_id}")

    except Exception as e:
        logger.error("Failed to download audio: %s", e)
        raise


def cleanup_audio(video_id):
    """Remove downloaded audio files for a video."""
    for f in glob.glob(os.path.join(AUDIO_DIR, f"{video_id}.*")):
        try:
            os.remove(f)
            logger.debug("Cleaned up: %s", f)
        except OSError:
            pass
