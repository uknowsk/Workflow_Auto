"""테스트는 진짜 저장소 대신 임시 폴더를 씁니다.

DATA_DIR 은 앱을 불러올 때 한 번 읽히므로, 앱보다 먼저 정해 두어야 합니다.
그래서 이 파일(conftest)에서 맨 먼저 설정합니다.
"""
import os
import tempfile

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="workflow-auto-test-"))
