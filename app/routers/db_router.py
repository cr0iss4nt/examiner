from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from app.services.vector_service import VectorService
from app.config import DATA_FOLDER, COLLECTION_NAME
import os
from typing import List
import asyncio

router = APIRouter()
vector_service = VectorService(collection_name=COLLECTION_NAME)

class InitRequest(BaseModel):
    force_recreate: bool = False

@router.post("/init")
def init_db(req: InitRequest):
    try:
        if req.force_recreate:
            vector_service.recreate_collection()
        num = vector_service.add_documents_from_folder(DATA_FOLDER)
        return {"ok": True, "points_added": num}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
def db_health():
    info = vector_service.get_collection_info()
    if not info:
        return {"ok": False, "message": "collection not found"}
    return {
        "ok": True,
        "collection_name": vector_service.collection_name,
        "points_count": info.points_count,
        "vectors_size": info.config.params.vectors.size
    }

@router.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    try:
        for file in files:
            file_path = os.path.join(DATA_FOLDER, file.filename)
            with open(file_path, "wb") as f:
                f.write(await file.read())
        # Асинхронно пересоздаем коллекцию
        await asyncio.to_thread(vector_service.recreate_collection)
        await asyncio.to_thread(vector_service.add_documents_from_folder, DATA_FOLDER)
        return {"ok": True, "message": f"{len(files)} files uploaded and DB rebuilt"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class DeleteRequest(BaseModel):
    filenames: List[str]

@router.delete("/delete")
async def delete_files(req: DeleteRequest):
    try:
        deleted_count = 0
        for filename in req.filenames:
            file_path = os.path.join(DATA_FOLDER, filename)
            if os.path.exists(file_path):
                os.remove(file_path)
                deleted_count += 1
        if deleted_count > 0:
            # Асинхронно пересоздаем коллекцию
            await asyncio.to_thread(vector_service.recreate_collection)
            await asyncio.to_thread(vector_service.add_documents_from_folder, DATA_FOLDER)
        return {"ok": True, "deleted_files": deleted_count, "message": "DB rebuilt after deletion"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))