from fastapi import FastAPI

from app.health import router as health_router

app = FastAPI(title="Gastos OCR API", version="0.1.0")
app.include_router(health_router)
