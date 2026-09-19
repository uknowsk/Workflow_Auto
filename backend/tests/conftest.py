"""테스트 공통 설정.

대부분의 테스트는 DB, Redis, LLM, 앱 서버 없이 도는 순수 계산만 확인합니다.
(날짜 계산과 변수 치환처럼 조용히 틀리기 쉬운 부분입니다)

다만 화면 권한 테스트(test_permissions.py)는 진짜 API 를 부르므로 DB 가 필요합니다.
그래서 설정은 **여기서** 정합니다. `app.config.get_settings()` 는 한 번 읽은 값을
계속 쓰고 `app.db` 는 import 되는 순간 엔진을 만들기 때문에, 테스트 파일 안에서
환경변수를 고쳐 봐야 먼저 import 된 쪽이 이미 정해 버린 뒤입니다.
(여기 말고 테스트 파일에서 정하면, 어느 파일이 먼저 import 되느냐에 따라
테스트가 됐다 안 됐다 합니다.)
"""
import os
import tempfile

# 메모리 DB(:memory:)는 연결할 때마다 빈 DB 가 새로 생겨서, 만들어 둔 표가
# 다음 연결에서 사라집니다. 그래서 임시 파일 하나를 씁니다(진짜 DB 는 안 건드림).
_DB_FILE = os.path.join(tempfile.mkdtemp(prefix="workflow-auto-tests-"), "test.db")
os.environ.setdefault("DATABASE_URL", f"sqlite+pysqlite:///{_DB_FILE}")
os.environ.setdefault("SCHEDULER_TZ_OFFSET_MINUTES", "540")  # 한국 시간
os.environ.setdefault("SCHEDULER_MIN_INTERVAL_MINUTES", "5")

# 아래 값들도 앱이 import 되기 전에 정해져 있어야 합니다.
os.environ.setdefault("ADMIN_USER_IDS", "E9999")
os.environ.setdefault("DEV_HEADER_AUTH", "true")
os.environ.setdefault("SCHEDULER_ENABLED", "false")
os.environ.setdefault("HEALTHCHECK_INTERVAL_SECONDS", "0")
os.environ.setdefault("SEED_FILE", "")
