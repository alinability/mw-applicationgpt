import os
from dotenv import load_dotenv

load_dotenv()

print("Projekt läuft. OpenAI Key:", os.getenv("OPENAI_API_KEY"))