"""환경변수 한 곳에서 읽기. .env 파일이나 컨테이너 환경변수로 주입됩니다."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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
    # 서버가 처음 뜰 때 만들 최초 관리자 계정(이미 있으면 건너뜁니다)
    bootstrap_admin_id: str = ""
    bootstrap_admin_password: str = ""

    # --- 파일 보관 위치 (앱 패키지, 양식) ---
    data_dir: str = "/srv/data"

    # --- 앱 생존 확인 ---
    healthcheck_interval_seconds: int = 300  # 5분마다. 0 이면 끔
    healthcheck_failure_threshold: int = 3   # 연속 3회 실패하면 등록자에게 알림

    # 서버가 뜰 때 자동 등록할 앱 목록 파일. 비우면 아무것도 등록하지 않습니다.
    # 예) SEED_FILE=config/apps.seed.json
    seed_file: str = ""

    # 관리자 사번 목록(쉼표 구분). 여기 있는 사람만 앱을 '공식 승인' 할 수 있습니다.
    # 예) ADMIN_USER_IDS=E1001,E2001
    admin_user_ids: str = ""

    # 개발 편의: 서버 시작 시 테이블 자동 생성
    auto_create_tables: bool = True

    @property
    def admins(self) -> set[str]:
        return {x.strip() for x in self.admin_user_ids.split(",") if x.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
