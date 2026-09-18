"""API 입출력 형식(Pydantic). 화면과 백엔드가 주고받는 계약서입니다."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    AppStatus,
    AppVisibility,
    RunStatus,
    RuntimeLocation,
    ScheduleAction,
    ScheduleTrigger,
    SourceType,
)


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
    requires_confirmation: bool = Field(
        False,
        description="메일 발송·결재 상신처럼 되돌릴 수 없는 일을 하면 True. "
        "실행 전에 사용자 확인을 받습니다.",
    )
    runtime_location: RuntimeLocation = Field(
        RuntimeLocation.server, description="server=중앙 서버 구동, pc=개인 PC(Launcher)"
    )


class AppUpdateIn(BaseModel):
    name: str | None = None
    endpoint: str | None = None
    description: str | None = None
    usage_hint: str | None = None
    category: str | None = None
    capability_tag: str | None = None
    requires_confirmation: bool | None = None
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
    requires_confirmation: bool
    runtime_location: RuntimeLocation
    source_type: SourceType
    source_url: str
    package_version: str
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
    recipe_id: str | None = Field(
        None, description="값이 있으면 이 카드는 저장된 레시피를 재실행합니다"
    )
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
    form_id: str | None = Field(
        None, description="결과를 채워 넣을 양식. 비우면 자유 형식"
    )


class RunOut(BaseModel):
    id: str
    user_id: str
    card_id: str | None
    recipe_id: str | None
    schedule_id: str | None
    request_text: str
    app_ids: list
    form_id: str
    status: RunStatus
    plan: list
    plan_summary: str
    needs_approval: bool
    approved_by: str
    steps: list
    result_text: str
    error: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


# --------------------------- 워크플로우 레시피 ---------------------------
class RecipeStepIn(BaseModel):
    """레시피의 한 단계 = 앱 하나의 기능 하나."""

    app_id: str = Field(..., description="호출할 앱(App.id)")
    tool: str = Field(..., description="그 앱의 기능 이름")
    arguments: dict = Field(
        default_factory=dict,
        description="기능에 넘길 값. {{회의록}} {{step1}} {{today}} 같은 변수를 쓸 수 있습니다",
    )
    title: str = Field("", description="이 단계를 사람이 알아볼 이름. 예) 회의록 요약")
    app_slug: str = ""
    app_name: str = ""


class RecipeIn(BaseModel):
    title: str = Field(..., min_length=1, description="레시피 이름. 예) 회의록 정리 후 메일")
    description: str = ""
    icon: str = "🧾"
    steps: list[RecipeStepIn] = Field(default_factory=list)
    final_instruction: str = Field(
        "", description="단계 결과를 모아 최종 결과물을 쓰는 지시문. 비우면 결과를 이어 붙입니다"
    )
    form_id: str = ""


class RecipeFromRunIn(BaseModel):
    """방금 잘 돌아간 실행을 그대로 레시피로 저장할 때."""

    run_id: str = Field(..., description="저장할 실행 기록")
    title: str = Field(..., min_length=1)
    description: str = ""
    icon: str = "🧾"
    keep_final_instruction: bool = Field(
        True, description="원래 요청문을 '마무리 지시문'으로 같이 저장할지"
    )


class RecipeOut(BaseModel):
    id: str
    user_id: str
    title: str
    description: str
    icon: str
    steps: list
    final_instruction: str
    form_id: str
    source_run_id: str
    run_count: int
    last_run_at: datetime | None
    created_at: datetime
    # 실행할 때 사용자가 채워 넣어야 하는 변수 이름들. 서버가 계산해 줍니다.
    variables: list[str] = []

    model_config = ConfigDict(from_attributes=True)


class RecipeRunIn(BaseModel):
    variables: dict[str, str] = Field(
        default_factory=dict, description="{{변수}} 에 채워 넣을 값"
    )
    form_id: str | None = None


# ------------------------------- 예약 -------------------------------
class ScheduleIn(BaseModel):
    title: str = Field(..., min_length=1, description="예약 이름. 예) 회신기한 리마인드")
    description: str = ""
    enabled: bool = True

    # 언제
    trigger: ScheduleTrigger = ScheduleTrigger.once
    run_at: datetime | None = Field(
        None, description="once 용 기준 시각. 기한을 넣고 lead_minutes 로 당겨 쓰세요"
    )
    at_time: str = Field("", pattern=r"^$|^([01]\d|2[0-3]):[0-5]\d$", description="daily 용. 09:00")
    weekdays: list[int] = Field(
        default_factory=list, description="daily 용. 0=월 ... 6=일. 비우면 매일"
    )
    interval_minutes: int = Field(0, ge=0, description="interval 용")
    lead_minutes: int = Field(
        0, ge=0, description="run_at 보다 이만큼 미리 실행. 1440 이면 기한 하루 전"
    )

    # 무엇을
    action: ScheduleAction = ScheduleAction.request
    request_text: str = ""
    app_ids: list[str] = Field(default_factory=list)
    recipe_id: str | None = None
    variables: dict[str, str] = Field(default_factory=dict)
    app_id: str = ""
    tool_name: str = ""
    arguments: dict = Field(default_factory=dict)

    pre_approved: bool = Field(
        False,
        description=(
            "되돌릴 수 없는 앱(메일 발송 등)이 들어 있으면 true 여야 저장됩니다. "
            "예약이 도는 순간에는 사람이 화면 앞에 없어 확인을 받을 수 없기 때문입니다"
        ),
    )


class ScheduleOut(BaseModel):
    id: str
    user_id: str
    title: str
    description: str
    enabled: bool
    trigger: ScheduleTrigger
    run_at: datetime | None
    at_time: str
    weekdays: list
    interval_minutes: int
    lead_minutes: int
    action: ScheduleAction
    request_text: str
    app_ids: list
    recipe_id: str | None
    variables: dict
    app_id: str
    tool_name: str
    arguments: dict
    pre_approved: bool
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_run_id: str
    last_status: str
    last_error: str
    run_count: int
    created_at: datetime
    # 사람이 읽는 한 줄 설명. 예) "매일 09:00", "2026-09-20 18:00 기준 1일 전에 한 번"
    when_text: str = ""

    model_config = ConfigDict(from_attributes=True)


# ----------------------------- 도구 서랍 -----------------------------
class NoteIn(BaseModel):
    title: str = Field("", max_length=200)
    body: str = ""
    pinned: bool = False


class NoteOut(NoteIn):
    id: str
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DrawingIn(BaseModel):
    title: str = Field("", max_length=200)
    image: str = Field(..., description="data:image/png;base64,... 모양의 PNG")
    width: int = 0
    height: int = 0


class DrawingOut(BaseModel):
    """목록에서는 그림 자체를 빼고 제목만 보냅니다(목록이 무거워지지 않게)."""

    id: str
    title: str
    width: int
    height: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DrawingFull(DrawingOut):
    image: str
