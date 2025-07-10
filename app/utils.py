import os, hashlib

from openai_client import ask_chatgpt_single_prompt

CACHE_DIR = "./data/cache"

def _get_cache_path(key: str) -> str:
    return os.path.join(CACHE_DIR, f"{key}.txt")

def load_cached_reduction(key: str) -> str | None:
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = _get_cache_path(key)
    if os.path.exists(path):
        print("🔄 Verwende gecachte Reduktion.")
        return open(path, "r", encoding="utf-8").read()
    return None

def save_cached_reduction(key: str, text: str):
    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(_get_cache_path(key), "w", encoding="utf-8") as f:
        f.write(text)
