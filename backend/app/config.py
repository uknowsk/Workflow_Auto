"""환경변수 한 곳에서 읽기. .env 파일이나 컨테이너 환경변수로 주입됩니다."""
from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # populate_by_name: ADMIN_ID 처럼 별명을 붙인 값도 필드 이름으로 넣을 수 있게 합니다(테스트용).
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", populate_by_name=True
    )

    # 저장소
    database_url: str = "postgresql+psycopg://workflow:workflow@localhost:5432/workflow"
    redis_url: str = "redis://localhost:6379/0"

    # 오케스트레이터 LLM (OpenAI 호환이면 무엇이든 꽂힙니다: Gauss, vLLM, Ollama ...)
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "changeme"
    llm_model: str = "gauss"
    llm_tool_mode: str = "native"  # native | json
    llm_timeout: float = 120.0
    llm_max_steps: int = 8  # 한 번의 요청에서 앱을 최대 몇 번 호출할지

    # 등록된 앱(MCP 서버) 호출 타임아웃
    mcp_timeout: float = 60.0

    # --- 로그인 ---
    # 토큰 서명에 쓰는 비밀값. 회사에서는 반드시 긴 임의 문자열로 바꾸세요.
    secret_key: str = "change-me-in-production"
    token_ttl_seconds: int = 60 * 60 * 12  # 12시간
    auth_backend: str = "password"  # password | sso (sso 는 아직 자리만)
    # 개발 편의: X-User-Id 헤더만으로 로그인한 척할 수 있게 합니다.
    # 회사 배포에서는 반드시 false 로 두세요.
    dev_header_auth: bool = True
    # 서버가 처음 뜰 때 만들 관리자 계정. .env 의 ADMIN_ID / ADMIN_PASSWORD 로 정합니다.
    # (예전 이름 BOOTSTRAP_ADMIN_ID / BOOTSTRAP_ADMIN_PASSWORD 도 그대로 읽힙니다)
    admin_id: str = Field(
        "", validation_alias=AliasChoices("ADMIN_ID", "BOOTSTRAP_ADMIN_ID")
    )
    admin_password: str = Field(
        "", validation_alias=AliasChoices("ADMIN_PASSWORD", "BOOTSTRAP_ADMIN_PASSWORD")
    )
    admin_name: str = "관리자"
    # 계정이 이미 있으면 비밀번호를 건드리지 않습니다. true 로 두면 기동할 때마다
    # .env 의 비밀번호로 덮어씁니다(비밀번호를 잊었을 때만 잠깐 켜세요).
    admin_reset_password: bool = False

    # --- 파일 보관 위치 (앱 패키지, 양식) ---
    data_dir: str = "/srv/data"

    # --- 앱 생존 확인 ---
    healthcheck_interval_seconds: int = 300  # 5분마다. 0 이면 끔
    healthcheck_failure_threshold: int = 3   # 연속 3회 실패하면 등록자에게 알림

    # --- 예약(스케줄러) ---
    # 사내 표준시. 한국은 540분(UTC+9). "매일 09시"가 어느 나라 9시인지 정하는 값입니다.
    scheduler_tz_offset_minutes: int = 540
    # false 로 두면 예약을 아예 걸지 않습니다(예: 개발 PC).
    scheduler_enabled: bool = True
    # 예약은 이 간격보다 자주 돌 수 없습니다. 실수로 1분마다 도는 것을 막습니다.
    scheduler_min_interval_minutes: int = 5

    # --- 개인 대시보드 ---
    # 첫 화면에 어떤 칸을 띄울지 적은 파일. 비우면 기본값(config/dashboard.widgets.example.json
    # 과 같은 내용)을 씁니다. 사내 앱 이름이 다르면 이 파일만 바꿔 끼우세요.
    dashboard_widgets_file: str = ""
    # 대시보드가 앱 하나를 기다려 주는 시간. 느린 앱 때문에 첫 화면이 멈추면 안 됩니다.
    dashboard_timeout: float = 10.0

    # 서버가 뜰 때 자동 등록할 앱 목록 파일. 비우면 아무것도 등록하지 않습니다.
    # 예) SEED_FILE=config/apps.seed.json
    seed_file: str = ""

    # 관리자 사번 목록(쉼표 구분). 여기 있는 사람만 앱을 '공식 승인' 할 수 있습니다.
    # 예) ADMIN_USER_IDS=E1001,E2001
    admin_user_ids: str = ""

    # 사내 SSO 로 들어왔을 때 관리자로 볼 아이디 목록(쉼표 구분).
    # 예) ADMIN_SSO_IDS=sk1980.kim
    admin_sso_ids: str = ""

    # 개발 편의: 서버 시작 시 테이블 자동 생성
    auto_create_tables: bool = True

    @property
    def admins(self) -> set[str]:
        return {x.strip() for x in self.admin_user_ids.split(",") if x.strip()}

    @property
    def admin_sso(self) -> set[str]:
        """SSO 아이디는 대소문자를 가리지 않습니다(SK1980.Kim 도 같은 사람)."""
        return {x.strip().lower() for x in self.admin_sso_ids.split(",") if x.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
