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
