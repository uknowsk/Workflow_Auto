# 예시: 기존 앱을 고치지 않고 붙이기

이 폴더는 "내 앱을 어떻게 Workflow Auto 에 붙이나"의 완성된 예시입니다.

```
legacy_app/     ← 원래 있던 앱. MCP 를 전혀 모릅니다. 한 줄도 안 고쳤습니다.
mcp_adapter/    ← 옆에 새로 붙인 얇은 통역사. 이것만 새로 만들었습니다.
```

`mcp_adapter/server.py` 는 `templates/mcp_adapter_http/server.py` 를 복사해서
TODO 부분만 채운 것입니다. 한번 비교해 보면 무엇을 채워야 하는지 바로 보입니다.

## 직접 돌려보기

```bash
# 터미널 1 - 기존 앱
cd legacy_app && pip install -r requirements.txt && uvicorn app:app --port 8100

# 터미널 2 - 어댑터
cd mcp_adapter && pip install -r requirements.txt && \
  APP_BASE_URL=http://localhost:8100 python server.py
```

그다음 Workflow Auto 앱스토어에 `http://localhost:9001/mcp` 를 등록하면
기능 3개(`find_employee`, `search_employees_by_team`, `fill_weekly_report`)가
자동으로 잡힙니다.

`docker compose up` 을 쓰면 이 둘도 같이 떠서 자동 등록됩니다.

## 흐름

```
오케스트레이터 ──MCP──> mcp_adapter ──평범한 HTTP──> legacy_app
                        (새로 만듦)                 (안 고침)
```

내 앱을 붙이는 방법은 [../docs/WRAPPER_PROMPT.md](../docs/WRAPPER_PROMPT.md) 를 보세요.
