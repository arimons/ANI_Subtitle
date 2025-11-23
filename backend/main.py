from fastapi import FastAPI, UploadFile, File, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import uvicorn
import os
import shutil
import uuid
from dotenv import load_dotenv
from config import settings
from task_store import get_task_status, update_task_status, update_task_metadata
import static_ffmpeg
from pydantic import BaseModel
import aiofiles
import time

load_dotenv()

# Initialize static_ffmpeg to ensure binaries are present
static_ffmpeg.add_paths()

app = FastAPI(title="ANI_Translate API", version="0.1.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class StartTaskRequest(BaseModel):
    mode: str  # 'extract' or 'transcribe'
    stream_index: int = None

@app.get("/")
def read_root():
    return {"status": "ANI_Translate Backend is running"}

@app.get("/tasks/{task_id}")
def get_status(task_id: str):
    return get_task_status(task_id)

@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = os.path.join(settings.OUTPUT_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, filename=filename)
    return {"error": "File not found"}

@app.post("/upload")
async def upload_video(file: UploadFile = File(...), background_tasks: BackgroundTasks = None):
    start_time = time.time()
    task_id = str(uuid.uuid4())
    file_path = os.path.join(settings.UPLOAD_DIR, f"{task_id}_{file.filename}")
    
    try:
        # Async write to avoid blocking event loop
        async with aiofiles.open(file_path, 'wb') as out_file:
            while content := await file.read(1024 * 1024):  # Read in 1MB chunks
                await out_file.write(content)
        
        duration = time.time() - start_time
        print(f"File saved to {file_path} in {duration:.2f} seconds")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save file: {e}")

    # Initialize status and metadata
    update_task_metadata(task_id, {
        "filename": file.filename,
        "file_path": file_path
    })
    update_task_status(task_id, "Uploading...", 0)

    # Trigger analysis in background
    from pipeline import analyze_file
    background_tasks.add_task(analyze_file, file_path, task_id)

    return {"task_id": task_id, "filename": file.filename, "status": "Analysis started"}

@app.post("/tasks/{task_id}/start")
async def start_task(task_id: str, request: StartTaskRequest, background_tasks: BackgroundTasks):
    # Trigger processing in background
    from pipeline import run_processing_task
    background_tasks.add_task(run_processing_task, task_id, request.mode, request.stream_index)
    return {"status": "Processing started"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
