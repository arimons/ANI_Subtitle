import ffmpeg
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def extract_audio(video_path: str, output_path: str) -> str:
    """
    Extracts audio from a video file and saves it as an MP3.
    Returns the path to the extracted audio file.
    """
    try:
        logger.info(f"Extracting audio from {video_path} to {output_path}")
        (
            ffmpeg
            .input(video_path)
            .output(output_path, acodec='mp3', audio_bitrate='64k')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        return output_path
    except ffmpeg.Error as e:
        logger.error(f"FFmpeg error: {e.stderr.decode('utf8')}")
        raise RuntimeError(f"Failed to extract audio: {e.stderr.decode('utf8')}")

def extract_subtitles(video_path: str, output_path: str) -> str:
    """
    Extracts the first subtitle stream from a video file.
    Returns the path to the extracted subtitle file.
    """
    try:
        # Probe to find subtitle streams
        probe = ffmpeg.probe(video_path)
        subtitle_streams = [stream for stream in probe['streams'] if stream['codec_type'] == 'subtitle']
        
        if not subtitle_streams:
            logger.warning("No subtitle streams found.")
            return None

        # Extract the first subtitle stream (map 0:s:0)
        logger.info(f"Extracting subtitles from {video_path} to {output_path}")
        (
            ffmpeg
            .input(video_path)
            .output(output_path, map='0:s:0')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        return output_path
    except ffmpeg.Error as e:
        logger.error(f"FFmpeg error: {e.stderr.decode('utf8')}")
        raise RuntimeError(f"Failed to extract subtitles: {e.stderr.decode('utf8')}")

def get_media_info(video_path: str):
    """
    Returns metadata about the video file.
    """
    try:
        return ffmpeg.probe(video_path)
    except ffmpeg.Error as e:
        logger.error(f"FFmpeg error: {e.stderr.decode('utf8')}")
        raise

def analyze_media(video_path: str):
    """
    Analyzes the media file and returns a list of streams.
    """
    try:
        probe = ffmpeg.probe(video_path)
        return probe.get('streams', [])
    except ffmpeg.Error as e:
        logger.error(f"FFmpeg error: {e.stderr.decode('utf8')}")
        return []

def split_audio(audio_path: str, segment_time: int = 60, output_dir: str = None) -> list[str]:
    """
    Splits audio into chunks of `segment_time` seconds.
    Returns a list of paths to the chunks.
    """
    if output_dir is None:
        output_dir = os.path.dirname(audio_path)
    
    base_name = os.path.splitext(os.path.basename(audio_path))[0]
    output_pattern = os.path.join(output_dir, f"{base_name}_%03d.mp3")
    
    try:
        logger.info(f"Splitting audio {audio_path} into {segment_time}s chunks...")
        (
            ffmpeg
            .input(audio_path)
            .output(output_pattern, f='segment', segment_time=segment_time, c='copy')
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        
        # Find all generated chunks
        chunks = sorted([
            os.path.join(output_dir, f) 
            for f in os.listdir(output_dir) 
            if f.startswith(base_name) and f.endswith('.mp3') and f != os.path.basename(audio_path)
        ])
        return chunks
    except ffmpeg.Error as e:
        logger.error(f"FFmpeg split error: {e.stderr.decode('utf8')}")
        raise RuntimeError(f"Failed to split audio: {e.stderr.decode('utf8')}")
