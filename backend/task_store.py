import json
import os
import logging

logger = logging.getLogger(__name__)

TASKS_FILE = os.path.join(os.getcwd(), "tasks.json")

tasks = {}

def load_tasks():
    global tasks
    if os.path.exists(TASKS_FILE):
        try:
            with open(TASKS_FILE, "r", encoding="utf-8") as f:
                tasks = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load tasks: {e}")
            tasks = {}

def save_tasks():
    try:
        with open(TASKS_FILE, "w", encoding="utf-8") as f:
            json.dump(tasks, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save tasks: {e}")

# Load on import
load_tasks()

def update_task_status(task_id: str, status: str, progress: int = 0):
    if task_id not in tasks:
        tasks[task_id] = {}
    
    tasks[task_id]["status"] = status
    tasks[task_id]["progress"] = progress
    save_tasks()

def update_task_metadata(task_id: str, data: dict):
    if task_id not in tasks:
        tasks[task_id] = {}
    
    tasks[task_id].update(data)
    save_tasks()

def get_task(task_id: str):
    return tasks.get(task_id)

def get_task_status(task_id: str):
    return tasks.get(task_id, {"status": "unknown", "progress": 0})
