"""[템플릿] PC에 설치해서 쓰는 앱(실행파일/스크립트)을 MCP 로 감싸는 얇은 어댑터.

내 앱은 한 줄도 고치지 않습니다. 이 어댑터가 명령어로 내 앱을 실행하고
화면에 찍히는 결과를 그대로 돌려줍니다.

쓰는 법
  1) 아래 TODO 부분만 내 앱에 맞게 고칩니다 (함수 1개 = 기능 1개).
  2) pip install -r requirements.txt
  3) python server.py        ->  http://localhost:9002/mcp
  4) 이 주소를 Workflow Auto 앱스토어에 등록합니다.

※ 이 어댑터는 그 앱이 깔려 있는 PC(또는 서버)에서 돌아가야 합니다.

주의: 파일 맨 위에 `from __future__ import annotations` 를 넣지 마세요.
      MCP 가 함수의 인자 타입을 읽지 못하게 됩니다.
"""
import os
import shlex
import subprocess

from mcp.server.fastmcp import FastMCP

# ── 내 앱 실행파일 경로. 환경변수로 빼 두면 PC마다 값만 바꾸면 됩니다. ──
APP_COMMAND = os.getenv("APP_COMMAND", r"C:\Program Files\MyApp\myapp.exe")
APP_WORKDIR = os.getenv("APP_WORKDIR", ".")
TIMEOUT = float(os.getenv("APP_TIMEOUT", "120"))

mcp = FastMCP(
    # TODO: 내 앱 이름과 한 줄 설명으로 바꾸세요.
    "내 앱 이름",
    instructions="이 앱이 무엇을 해 주는지 한 문장으로 적으세요.",
    host=os.getenv("HOST", "0.0.0.0"),
    port=int(os.getenv("PORT", "9002")),
)


def _run(args: list[str]) -> dict:
    """앱을 실행하고 결과를 돌려줍니다.

    보안상 shell=True 는 쓰지 않습니다. 사용자가 넣은 값이 그대로
    명령어로 실행되는 사고를 막기 위해서입니다.
    """
    try:
        completed = subprocess.run(
            [APP_COMMAND, *args],
            cwd=APP_WORKDIR,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            shell=False,
        )
    except FileNotFoundError:
        return {"ok": False, "error": f"실행파일을 찾을 수 없습니다: {APP_COMMAND}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"{TIMEOUT}초 안에 끝나지 않아 중단했습니다."}

    return {
        "ok": completed.returncode == 0,
        "exit_code": completed.returncode,
        "output": (completed.stdout or "").strip(),
        "error": (completed.stderr or "").strip(),
    }


# ──────────────────────────────────────────────────────────────────────
# TODO: 여기부터 내 앱의 기능을 하나씩 함수로 만듭니다.
#
# 규칙 3가지만 지키면 됩니다.
#   1) 함수 위에 @mcp.tool() 을 붙인다
#   2) 인자마다 타입을 적는다 (str, int, list[str] ...)
#   3) docstring 첫 줄에 "이 기능이 뭘 하는지"를 한국어로 적는다
#      -> 오케스트레이터는 이 설명만 보고 언제 이 기능을 쓸지 판단합니다.
#
# 사용자가 넣은 값은 옵션 "값"으로만 넘기세요. 옵션 이름까지 사용자가
# 정하게 두면 위험합니다.
# ──────────────────────────────────────────────────────────────────────


@mcp.tool()
def example_convert(input_path: str, output_path: str) -> dict:
    """(예시) 파일을 변환합니다. 설명을 실제 기능에 맞게 바꾸세요.

    Args:
        input_path: 입력 파일 경로
        output_path: 결과를 저장할 파일 경로
    """
    return _run(["--convert", input_path, "--out", output_path])


@mcp.tool()
def example_query(keyword: str) -> dict:
    """(예시) 키워드로 조회합니다. 설명을 실제 기능에 맞게 바꾸세요.

    Args:
        keyword: 찾을 키워드
    """
    return _run(["--query", keyword])


@mcp.tool()
def show_command() -> str:
    """이 어댑터가 실제로 실행하는 명령어를 알려줍니다(설정 확인용)."""
    return shlex.join([APP_COMMAND]) + f"  (작업 폴더: {APP_WORKDIR})"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
