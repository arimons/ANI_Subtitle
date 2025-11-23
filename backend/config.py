import os
from dotenv import load_dotenv

# Explicitly load .env from the same directory as this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH)

class Settings:
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
    OUTPUT_DIR = os.path.join(os.getcwd(), "outputs")

    def __init__(self):
        os.makedirs(self.UPLOAD_DIR, exist_ok=True)
        os.makedirs(self.OUTPUT_DIR, exist_ok=True)
        
        # Debug prints
        print(f"Loading .env from: {ENV_PATH}")
        print(f"OpenAI Key Loaded: {'Yes' if self.OPENAI_API_KEY else 'No'}")
        print(f"Gemini Key Loaded: {'Yes' if self.GEMINI_API_KEY else 'No'}")

settings = Settings()
