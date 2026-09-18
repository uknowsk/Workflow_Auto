"""FastAPI 진입점.  API 문서는 브라우저에서 http://localhost:8000/docs"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import apps, cards, health, runs, stats
from app.config import get_settings
from app.db import create_all
from app.seed import seed_from_file

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.auto_create_tables:
        create_all()
    if settings.seed_file:
        await seed_from_file(settings.seed_file)
    yield


app = FastAPI(
    title="Workflow Auto",
    version="0.1.0",
    description=(
        "자연어 요청을 오케스트레이터가 분석해, 앱스토어에 등록된 "
        "개발자 앱(MCP 서버)들을 호출하고 결과를 합쳐 최종 산출물을 만듭니다."
    ),
    lifespan=lifespan,
)

# 사내 배포 시에는 allow_origins 를 실제 프론트 주소로 좁히세요.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(apps.router)
app.include_router(cards.router)
app.include_router(runs.router)
app.include_router(stats.router)
