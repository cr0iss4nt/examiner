from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json

from app.config import COLLECTION_NAME
from app.services.user_db_service import UserDBService
import os

router = APIRouter()
db_service = UserDBService()


class FileAddRequest(BaseModel):
    user_id: str
    filename: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class FileSearchRequest(BaseModel):
    user_id: str
    query_text: Optional[str] = None
    query_vector: Optional[List[float]] = None
    filters: Optional[Dict[str, Any]] = None
    limit: int = 10


class FileUpdateRequest(BaseModel):
    user_id: str
    file_id: str
    metadata: Dict[str, Any]


class FileDeleteRequest(BaseModel):
    user_id: str
    file_id: str


@router.post("/init")
def init_db():
    try:
        db_service.init_collection()
        return {"success": True, "message": "Коллекция пользовательских файлов инициализирована"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add")
async def add_file(
        file: UploadFile = File(...),
        user_id: str = None,
        metadata: str = "{}"
):
    try:
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id обязателен")

        # Читаем файл
        content = await file.read()

        print(metadata)
        # Парсим метаданные
        try:
            metadata_dict = json.loads(metadata)
        except:
            metadata_dict = {}

        # Добавляем файл
        file_id = db_service.add_file(
            user_id=user_id,
            file_content=content,
            filename=file.filename,
            file_metadata=metadata_dict
        )

        return {
            "success": True,
            "message": f"Файл {file.filename} успешно добавлен",
            "file_id": file_id,
            "user_id": user_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
def search_files(req: FileSearchRequest):
    try:
        results = db_service.search_files(
            user_id=req.user_id,
            query_text=req.query_text,
            query_vector=req.query_vector,
            filters=req.filters,
            limit=req.limit
        )

        return {
            "success": True,
            "count": len(results),
            "results": results,
            "user_id": req.user_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/list")
def list_files(user_id: str, limit: int = 100):
    try:
        results = db_service.get_user_files(user_id=user_id, limit=limit)

        return {
            "success": True,
            "count": len(results),
            "results": results,
            "user_id": user_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update")
def update_file(req: FileUpdateRequest):
    try:
        success = db_service.update_file_metadata(
            user_id=req.user_id,
            file_id=req.file_id,
            new_metadata=req.metadata
        )

        if success:
            return {
                "success": True,
                "message": f"Файл {req.file_id} обновлен",
                "user_id": req.user_id,
                "file_id": req.file_id
            }
        else:
            raise HTTPException(status_code=404, detail="Файл не найден или нет доступа")

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/delete")
def delete_file(req: FileDeleteRequest):
    try:
        success = db_service.delete_file(
            user_id=req.user_id,
            file_id=req.file_id
        )

        if success:
            return {
                "success": True,
                "message": f"Файл {req.file_id} удален",
                "user_id": req.user_id,
                "file_id": req.file_id
            }
        else:
            raise HTTPException(status_code=404, detail="Файл не найден или нет доступа")

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/help")
def get_help():
    help_text = """
    Доступные методы:

    POST /db/init - Инициализировать коллекцию
    POST /db/add - Добавить файл (multipart/form-data)
      Параметры: file (файл), user_id, metadata (JSON строка)

    POST /db/search - Поиск файлов
      Тело запроса: {"user_id": "...", "query_text": "...", "limit": 10}

    POST /db/list - Список файлов пользователя
      Параметры: user_id, limit

    POST /db/update - Обновить метаданные
      Тело запроса: {"user_id": "...", "file_id": "...", "metadata": {...}}

    DELETE /db/delete - Удалить файл
      Тело запроса: {"user_id": "...", "file_id": "..."}
    """

    return {"help": help_text}


@router.get("/health")
def db_health():
    """Проверка состояния базы пользовательских файлов"""
    try:
        # Создаем простую проверку
        from qdrant_client import QdrantClient
        client = QdrantClient(host="localhost", port=6333)
        collections = client.get_collections()

        collection_exists = False
        points_count = 0
        collection_name = COLLECTION_NAME

        for col in collections.collections:
            if col.name == collection_name:
                collection_exists = True
                try:
                    collection_info = client.get_collection(collection_name)
                    points_count = collection_info.points_count
                except:
                    pass
                break

        return {
            "success": True,
            "collection_name": collection_name,
            "collection_exists": collection_exists,
            "points_count": points_count,
            "status": "healthy" if collection_exists else "warning"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "status": "error"
        }