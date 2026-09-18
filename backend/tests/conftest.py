"""테스트 공통 설정.

여기 있는 테스트는 DB, Redis, LLM, 앱 서버 없이 도는 순수 계산만 확인합니다.
(날짜 계산과 변수 치환처럼 조용히 틀리기 쉬운 부분입니다)
"""
import os

# import 만으로 진짜 DB 에 붙지 않도록 메모리 DB 를 가리켜 둡니다.
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("SCHEDULER_TZ_OFFSET_MINUTES", "540")  # 한국 시간
os.environ.setdefault("SCHEDULER_MIN_INTERVAL_MINUTES", "5")
