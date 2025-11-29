from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.vector_service import VectorService
from app.config import DATA_FOLDER, COLLECTION_NAME

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
