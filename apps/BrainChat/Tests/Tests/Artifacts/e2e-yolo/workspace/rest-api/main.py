from app.routes import router
from fastapi import FastAPI

app = FastAPI(title="BrainChat YOLO API")
app.include_router(router)
