"""FastAPI 앱 진입점"""
import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import score, facilities, geocode, admin_weights, admin_refresh

load_dotenv()

app = FastAPI(title="동네 진단 API")

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(score.router)
app.include_router(facilities.router)
app.include_router(geocode.router)
app.include_router(admin_weights.router)
app.include_router(admin_refresh.router)


@app.get("/")
def root():
    return {"message": "동네 진단 API 서버가 정상 동작 중입니다.", "docs": "/docs"}
