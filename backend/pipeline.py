import os
import uuid
import asyncio
from media_utils import extract_audio, extract_subtitles, analyze_media, split_audio
from ai_services import transcribe_audio, transcribe_audio_parallel, translate_text_parallel
from config import settings
from task_store import update_task_status, update_task_metadata, get_task
import logging

logger = logging.getLogger(__name__)

async def analyze_file(file_path: str, task_id: str):
    """
    Step 1: Analyze the file and update task status.
    """
    logger.info(f"Analyzing file: {file_path}")
    update_task_status(task_id, "Analyzing...", 0)
    
    streams = analyze_media(file_path)
    
    # Store streams in task info
    update_task_metadata(task_id, {
        "streams": streams,
        "file_path": file_path,
        "needs_selection": True
    })
    
    # Update status to let UI know we are waiting
    update_task_status(task_id, "Waiting for Selection", 0)


async def run_processing_task(task_id: str, mode: str, stream_index: int = None):
    """
    Step 2: Execute the chosen task.
    mode: 'extract' or 'transcribe'
    """
    task = get_task(task_id)
    if not task:
        logger.error(f"Task {task_id} not found")
        return

    file_path = task.get("file_path")
    # Use original filename from task metadata to avoid UUID prefix
    original_filename = task.get("filename")
    if not original_filename:
        original_filename = os.path.basename(file_path)
        
    base_name = os.path.splitext(original_filename)[0]
    output_srt_path = os.path.join(settings.OUTPUT_DIR, f"{base_name}.ko.srt")

    try:
        raw_srt_content = ""

        if mode == 'extract':
            logger.info(f"Mode: Extract Subtitle (Stream {stream_index})")
            update_task_status(task_id, "Extracting Subtitles...", 10)
            
            temp_sub_path = os.path.join(settings.UPLOAD_DIR, f"{task_id}_raw.srt")
            # We need to update extract_subtitles to accept stream index, 
            # but for now let's assume media_utils handles it or we default.
            # TODO: Update media_utils to support stream selection.
            # For this MVP, we'll just extract the first one or the specific one if we update the util.
            
            # Re-using existing function for now, but ideally pass stream_index
            extracted_sub = extract_subtitles(file_path, temp_sub_path) 
            
            if extracted_sub and os.path.exists(extracted_sub):
                with open(extracted_sub, "r", encoding="utf-8") as f:
                    raw_srt_content = f.read()
            else:
                raise RuntimeError("Failed to extract subtitles")

        elif mode == 'transcribe':
            logger.info("Mode: Audio Transcription (Parallel)")
            update_task_status(task_id, "Extracting Audio...", 10)
            
            # 1. Extract Audio
            temp_audio_path = os.path.join(settings.UPLOAD_DIR, f"{task_id}.mp3")
            extract_audio(file_path, temp_audio_path)
            
            # 2. Split Audio
            update_task_status(task_id, "Splitting Audio...", 20)
            chunk_dir = os.path.join(settings.UPLOAD_DIR, f"{task_id}_chunks")
            os.makedirs(chunk_dir, exist_ok=True)
            
            chunks = split_audio(temp_audio_path, segment_time=60, output_dir=chunk_dir)
            
            # 3. Parallel Transcribe
            update_task_status(task_id, f"Transcribing {len(chunks)} chunks...", 30)
            raw_srt_content = await transcribe_audio_parallel(chunks, segment_time=60)
            
            # Cleanup
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
            # Cleanup chunks
            for chunk in chunks:
                os.remove(chunk)
            os.rmdir(chunk_dir)

        # Step 4: Translate
        logger.info("Translating subtitles...")
        
        async def translation_progress(current, total):
            percent = 80 + int((current / total) * 15) # 80% -> 95%
            update_task_status(task_id, f"번역 중 (Gemini) - {current}/{total} 청크", percent)

        translated_srt = await translate_text_parallel(raw_srt_content, progress_callback=translation_progress)

        # Step 5: Save Output
        with open(output_srt_path, "w", encoding="utf-8") as f:
            f.write(translated_srt)
        
        logger.info(f"Task {task_id} completed. Saved to {output_srt_path}")
        
        update_task_metadata(task_id, {
            "result": output_srt_path,
            "needs_selection": False
        })
            
        update_task_status(task_id, "Completed", 100)

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        update_task_status(task_id, f"Error: {str(e)}", 0)
        # raise e # Don't crash the worker
