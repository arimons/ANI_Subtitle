import os
from openai import OpenAI
import google.generativeai as genai
from config import settings
import logging

logger = logging.getLogger(__name__)

# Initialize Clients
openai_client = None
if settings.OPENAI_API_KEY:
    openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)

import asyncio
import re
import time

async def transcribe_single_chunk(client, chunk_path: str, time_offset: float) -> str:
    """
    Transcribes a single chunk and returns the SRT content.
    """
    try:
        with open(chunk_path, "rb") as audio_file:
            # We use run_in_executor because the openai client is synchronous
            loop = asyncio.get_event_loop()
            transcript = await loop.run_in_executor(
                None, 
                lambda: client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="srt"
                )
            )
        return transcript
    except Exception as e:
        logger.error(f"Chunk transcription failed for {chunk_path}: {e}")
        return ""

def adjust_timestamps(srt_content: str, offset_seconds: float) -> str:
    """
    Parses SRT content and adds offset_seconds to all timestamps.
    SRT Timestamp format: 00:00:00,000
    """
    def replacer(match):
        # match.group(0) is the whole timestamp line: "00:00:01,000 --> 00:00:05,000"
        # We need to parse, add offset, and reformat.
        # This is a simple regex approach.
        
        def shift_time(t_str):
            h, m, s = t_str.replace(',', '.').split(':')
            total_seconds = int(h) * 3600 + int(m) * 60 + float(s)
            total_seconds += offset_seconds
            
            # Convert back
            h = int(total_seconds // 3600)
            m = int((total_seconds % 3600) // 60)
            s = total_seconds % 60
            return f"{h:02d}:{m:02d}:{s:06.3f}".replace('.', ',')

        start, end = match.group(1), match.group(2)
        return f"{shift_time(start)} --> {shift_time(end)}"

    # Regex for SRT timestamps: 00:00:00,000 --> 00:00:00,000
    pattern = r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})"
    return re.sub(pattern, replacer, srt_content)

async def transcribe_audio_parallel(audio_chunks: list[str], segment_time: int = 60) -> str:
    """
    Transcribes multiple audio chunks in parallel and merges them.
    """
    if not openai_client:
        raise ValueError("OpenAI API Key is missing.")

    logger.info(f"Starting parallel transcription for {len(audio_chunks)} chunks...")
    
    tasks = []
    for i, chunk_path in enumerate(audio_chunks):
        offset = i * segment_time
        tasks.append(transcribe_single_chunk(openai_client, chunk_path, offset))
    
    results = await asyncio.gather(*tasks)
    
    # Merge and adjust timestamps
    final_srt = ""
    sequence_counter = 1
    
    for i, srt_part in enumerate(results):
        if not srt_part: continue
        
        offset = i * segment_time
        adjusted_srt = adjust_timestamps(srt_part, offset)
        
        # Re-sequence the IDs (SRT requires sequential IDs)
        # This is a bit hacky, a proper SRT parser would be better, but for now:
        lines = adjusted_srt.strip().split('\n')
        for line in lines:
            if line.strip().isdigit():
                final_srt += f"{sequence_counter}\n"
                sequence_counter += 1
            else:
                final_srt += line + "\n"
        final_srt += "\n" # Separator between chunks

    return final_srt

def transcribe_audio(audio_path: str) -> str:
    """
    Transcribes audio using OpenAI Whisper API (Single file mode).
    """
    if not openai_client:
        raise ValueError("OpenAI API Key is missing.")

    logger.info(f"Transcribing audio: {audio_path}")
    try:
        with open(audio_path, "rb") as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="srt" # Get SRT directly from Whisper
            )
        return transcript
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise

async def translate_text_parallel(text: str, target_lang: str = "Korean", progress_callback=None) -> str:
    """
    Translates text using Google Gemini Flash with parallel chunking.
    Uses a semaphore to control concurrency and prevent rate limits.
    """
    if not settings.GEMINI_API_KEY:
        raise ValueError("Gemini API Key is missing.")

    model = genai.GenerativeModel('gemini-2.0-flash-lite')
    
    # Split SRT into blocks (separated by double newlines)
    srt_blocks = text.strip().split('\n\n')
    
    # Chunk size (number of subtitle blocks per request)
    # 50 blocks for faster individual responses
    CHUNK_SIZE = 50 
    chunks = [srt_blocks[i:i + CHUNK_SIZE] for i in range(0, len(srt_blocks), CHUNK_SIZE)]
    
    logger.info(f"Split subtitle into {len(chunks)} chunks for translation (Chunk size: {CHUNK_SIZE}).")
    
    # Semaphore to limit concurrent requests (e.g., 3 parallel requests)
    # Gemini Flash has high limits, but we want to be safe.
    sem = asyncio.Semaphore(3)

    async def translate_chunk(index, chunk):
        async with sem:
            chunk_text = "\n\n".join(chunk)
            logger.info(f"Translating chunk {index+1}/{len(chunks)}...")
            
            if progress_callback:
                await progress_callback(index + 1, len(chunks))

            prompt = f"""
            You are a professional anime subtitle translator.
            Translate the following subtitle text to {target_lang}.
            
            Rules:
            1. Maintain the original SRT/ASS format structure exactly. Do not change timestamps.
            2. Use natural, conversational Korean suitable for anime context.
            3. Handle Japanese names and slang appropriately.
            4. Output ONLY the translated content, no markdown code blocks.
            5. Do not omit any lines.
            
            Input:
            {chunk_text}
            """
            
            try:
                # Run the blocking synchronous API call in a thread
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, lambda: model.generate_content(prompt))
                
                # Add delay to respect rate limits (User requested)
                await asyncio.sleep(2)
                
                return index, response.text.strip()
            except Exception as e:
                logger.error(f"Translation failed for chunk {index}: {e}")
                return index, chunk_text # Fallback

    # Create tasks
    tasks = [translate_chunk(i, chunk) for i, chunk in enumerate(chunks)]
    
    # Run parallel
    results = await asyncio.gather(*tasks)
    
    # Sort results by index to ensure correct order
    results.sort(key=lambda x: x[0])
    
    # Join parts
    translated_parts = [part for _, part in results]
    return "\n\n".join(translated_parts)

# Wrapper for backward compatibility if needed, but we will update pipeline.py
def translate_text(text: str, target_lang: str = "Korean") -> str:
    return asyncio.run(translate_text_parallel(text, target_lang))

async def translate_text_openai(text: str, target_lang: str = "Korean", progress_callback=None) -> str:
    """
    Translates text using OpenAI GPT-4.1 Nano.
    """
    if not openai_client:
        raise ValueError("OpenAI API Key is missing.")

    # Split SRT into blocks (separated by double newlines)
    srt_blocks = text.strip().split('\n\n')
    
    # Chunk size (number of subtitle blocks per request)
    CHUNK_SIZE = 50 
    chunks = [srt_blocks[i:i + CHUNK_SIZE] for i in range(0, len(srt_blocks), CHUNK_SIZE)]
    
    logger.info(f"Split subtitle into {len(chunks)} chunks for OpenAI translation.")
    
    # Semaphore for OpenAI rate limits
    sem = asyncio.Semaphore(5) # Slightly higher concurrency for OpenAI

    async def translate_chunk(index, chunk):
        async with sem:
            chunk_text = "\n\n".join(chunk)
            
            if progress_callback:
                await progress_callback(index + 1, len(chunks))

            prompt = f"""
            You are a professional anime subtitle translator.
            Translate the following subtitle text to {target_lang}.
            
            Rules:
            1. Maintain the original SRT/ASS format structure exactly. Do not change timestamps.
            2. Use natural, conversational Korean suitable for anime context.
            3. Handle Japanese names and slang appropriately.
            4. Output ONLY the translated content, no markdown code blocks.
            5. Do not omit any lines.
            
            Input:
            {chunk_text}
            """
            
            try:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None, 
                    lambda: openai_client.chat.completions.create(
                        model="gpt-5-nano",
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant."},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.3
                    )
                )
                return index, response.choices[0].message.content.strip()
            except Exception as e:
                logger.error(f"OpenAI Translation failed for chunk {index}: {e}")
                return index, chunk_text # Fallback

    # Create tasks
    tasks = [translate_chunk(i, chunk) for i, chunk in enumerate(chunks)]
    
    # Run parallel
    results = await asyncio.gather(*tasks)
    
    # Sort results by index
    results.sort(key=lambda x: x[0])
    
    # Join parts
    translated_parts = [part for _, part in results]
    return "\n\n".join(translated_parts)
