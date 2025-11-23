# ANI_Translate (Anime Subtitle Generator)

## Project Structure
This project is divided into two parts:
1.  **Backend (`/backend`)**: Python (FastAPI). Handles video processing, AI translation, and file management.
2.  **Frontend (`/frontend`)**: TypeScript (React). The user interface you see in the browser.

## How to Run (Development Mode)

You need **two separate terminals** open to run this app.

### 1. Start the Backend (Terminal 1)
This starts the API server on `http://127.0.0.1:8000`.

```powershell
cd backend
uv run main.py
```
*(If you are not using `uv`, use your python interpreter: `python main.py`)*

### 2. Start the Frontend (Terminal 2)
This starts the UI server on `http://localhost:5173`.

```powershell
cd frontend
npm run dev
```

### 3. Open in Browser
Open your browser and go to: **http://localhost:5173**

## Configuration
Make sure you have a `.env` file in the `backend` folder with your API keys:
```
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
```
