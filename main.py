from fastapi import FastAPI
from app.routers import tests_router, db_router

app = FastAPI(title="Exam Test Generator API")

app.include_router(db_router.router, prefix="/db", tags=["database"])
app.include_router(tests_router.router, prefix="", tags=["tests"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8500, reload=True)
