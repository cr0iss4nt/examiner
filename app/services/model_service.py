import os
import json
import requests
from app.config import OPENROUTER_API_KEY, OPENROUTER_MODEL

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

def model_request(prompt: str, temperature: float = 0.3, max_tokens: int = 2000):
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not set")

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    resp = requests.post(OPENROUTER_URL, headers=headers, data=json.dumps(payload), timeout=60)
    resp.raise_for_status()
    return resp
