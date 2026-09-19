"""회의록 정리 앱 실행 파일.

  /mcp   - 오케스트레이터가 부르는 MCP 주소
  /api/* - 화면이 부르는 주소

실행:  python server.py   ->  http://localhost:9102/mcp
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import store
from mcp_adapter import mcp


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.init()
    async with mcp.session_manager.run():
        yield


api = FastAPI(title="회의록 정리 앱", lifespan=lifespan)
api.add_middleware(
    CORSMiddleware,
    allow_origins=(os.getenv("ALLOW_ORIGINS", "*").split(",")),
    allow_methods=["*"],
    allow_headers=["*"],
)


@api.get("/api/meetings", summary="정리된 회의록 목록")
def list_meetings(limit: int = 20) -> dict:
    items = store.recent(limit)
    return {"count": len(items), "meetings": items}


@api.get("/api/meetings/{meeting_id}", summary="회의록 한 건")
def get_meeting(meeting_id: str) -> dict:
    meeting = store.get(meeting_id)
    return {"found": meeting is not None, "meeting": meeting}


@api.get("/api/health", summary="살아있나 확인")
def health() -> dict:
    return {"status": "ok", "app": "meeting-notes"}


api.mount("/mcp", mcp.streamable_http_app())


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(api, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "9102")))
