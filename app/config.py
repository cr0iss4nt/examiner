import os
from dotenv import load_dotenv

load_dotenv()

QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-oss-20b:free")
DATA_FOLDER = os.getenv("DATA_FOLDER", "data")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "exam_documents")
