"""API 입출력 형식(Pydantic). 화면과 백엔드가 주고받는 계약서입니다."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import AppStatus, AppVisibility, RunStatus


# ----------------------------- 앱스토어 -----------------------------
class AppRegisterIn(BaseModel):
    """개발자가 자기 앱을 앱스토어에 등록할 때 보내는 값."""

    slug: str = Field(..., pattern=r"^[a-z0-9][a-z0-9-]{1,63}$", description="앱 고유 ID")
    name: str
    endpoint: str = Field(..., description="MCP streamable-HTTP 주소. 예) http://my-app:9001/mcp")
    description: str = ""
    usage_hint: str = Field("", description="오케스트레이터가 언제 이 앱을 쓸지 판단하는 한 문장")
    category: str = "etc"
    capability_tag: str = Field(
        "", description="역할 태그. 같은 일을 하는 앱끼리 같은 값. 예) 사내규정검색"
    )
    owner: str = Field("", description="등록자 이름")
    owner_dept: str = Field("", description="등록자 소속")
    owner_contact: str = Field("", description="연락처(메일/사내메신저). 고장 시 연락용")
    icon: str = "🧩"
    auth_headers: dict[str, str] = Field(default_factory=dict)
    visibility: AppVisibility = Field(
        AppVisibility.private,
        description="private=나만 사용, pending=공식 등록 신청(관리자 승인 대기)",
    )


class AppUpdateIn(BaseModel):
    name: str | None = None
    endpoint: str | None = None
    description: str | None = None
    usage_hint: str | None = None
    category: str | None = None
    capability_tag: str | None = None
    owner: str | None = None
    owner_dept: str | None = None
    owner_contact: str | None = None
    icon: str | None = None
    auth_headers: dict[str, str] | None = None
    status: AppStatus | None = None


class AppToolOut(BaseModel):
    name: str
    description: str
    input_schema: dict

    model_config = ConfigDict(from_attributes=True)


class AppOut(BaseModel):
    id: str
    slug: str
    name: str
    description: str
    usage_hint: str
    category: str
    capability_tag: str
    owner: str
    owner_dept: str
    owner_contact: str
    icon: str
    endpoint: str
    status: AppStatus
    visibility: AppVisibility
    owner_user_id: str
    last_error: str
    tools: list[AppToolOut] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# --------------------------- 에이전트 카드 ---------------------------
class AgentCardIn(BaseModel):
    title: str
    description: str = ""
    icon: str = "⭐"
    prompt_template: str = ""
    app_ids: list[str] = Field(default_factory=list)
    position: int = 0
    pinned: bool = False


class AgentCardOut(AgentCardIn):
    id: str
    user_id: str

    model_config = ConfigDict(from_attributes=True)


# ------------------------------- 실행 -------------------------------
class RunCreateIn(BaseModel):
    request_text: str = Field(..., min_length=1, description="자연어 요청")
    card_id: str | None = None
    app_ids: list[str] = Field(
        default_factory=list, description="비우면 등록된 전체 앱을 후보로 사용"
    )


class RunOut(BaseModel):
    id: str
    user_id: str
    card_id: str | None
    request_text: str
    app_ids: list
    status: RunStatus
    steps: list
    result_text: str
    error: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = ConfigDict(from_attributes=True)
