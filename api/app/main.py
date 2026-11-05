from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import categories, expenses, stats, users
from app.config import get_settings
from app.health import router as health_router

app = FastAPI(title="Gastos OCR API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(health_router)

api = APIRouter(prefix="/api/v1")
api.include_router(users.router)
api.include_router(categories.router)
api.include_router(expenses.router)
api.include_router(stats.router)
app.include_router(api)
