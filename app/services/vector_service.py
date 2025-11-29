import os
import uuid
from typing import List, Dict, Any, Tuple
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer
import PyPDF2
import docx

from app.config import QDRANT_URL, COLLECTION_NAME

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

class VectorService:
    def __init__(self, collection_name: str = COLLECTION_NAME):
        self.collection_name = collection_name
        self.client = QdrantClient(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", 6333))
        )

        self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        self._initialize_collection()

    def _initialize_collection(self):
        try:
            self.client.get_collection(self.collection_name)
        except Exception:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=384, distance=Distance.COSINE)
            )

    # --- file readers ---
    def _read_text(self, path: str) -> str:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()

    def _read_pdf(self, path: str) -> str:
        text = ""
        with open(path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                txt = page.extract_text()
                if txt:
                    text += txt + "\n"
        return text

    def _read_docx(self, path: str) -> str:
        doc = docx.Document(path)
        return "\n".join([p.text for p in doc.paragraphs])

    def _chunk_text(self, text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
        words = text.split()
        chunks = []
        step = chunk_size - overlap
        for i in range(0, len(words), step):
            chunk = ' '.join(words[i:i+chunk_size])
            if chunk:
                chunks.append(chunk)
            if i + chunk_size >= len(words):
                break
        return chunks

    def add_documents_from_folder(self, folder_path: str) -> int:
        """Process files in folder and upsert into Qdrant. Returns number of points added."""
        if not os.path.exists(folder_path):
            return 0

        points = []
        for filename in os.listdir(folder_path):
            path = os.path.join(folder_path, filename)
            if os.path.isdir(path):
                continue

            ext = filename.lower().rsplit('.', 1)[-1]
            try:
                if ext == 'txt':
                    content = self._read_text(path)
                elif ext == 'pdf':
                    content = self._read_pdf(path)
                elif ext in ('docx', 'doc'):
                    content = self._read_docx(path)
                else:
                    continue
            except Exception:
                continue

            chunks = self._chunk_text(content)
            for idx, chunk in enumerate(chunks):
                vector = self.model.encode(chunk).tolist()
                points.append(PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload={"filename": filename, "content": chunk, "chunk_id": idx}
                ))

        if points:
            self.client.upsert(collection_name=self.collection_name, points=points)
        return len(points)

    def recreate_collection(self):
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
        self._initialize_collection()

    def get_collection_info(self):
        try:
            return self.client.get_collection(self.collection_name)
        except Exception:
            return None

    def scroll_all(self, limit: int = 100000) -> Tuple[List[Any], int]:
        try:
            points, _ = self.client.scroll(collection_name=self.collection_name, limit=limit, with_payload=True, with_vectors=False)
            return points, len(points)
        except Exception:
            return [], 0

    def get_context(self, max_chars: int = 100000) -> Dict[str, Any]:
        points, _ = self.scroll_all(limit=100000)
        files = {}
        for p in points:
            filename = p.payload.get('filename', 'unknown')
            content = p.payload.get('content', '')
            files.setdefault(filename, []).append(content)

        parts = []
        total = 0
        for fname, chunks in files.items():
            header = f"=== {fname} ===\n"
            section = header + "\n".join(chunks) + "\n"
            if total + len(section) <= max_chars:
                parts.append(section)
                total += len(section)
            else:
                remaining = max_chars - total
                if remaining > 10:
                    parts.append(section[:remaining] + "\n...")
                break

        return {"context": "\n\n".join(parts), "total_chars": total, "files": list(files.keys())}
