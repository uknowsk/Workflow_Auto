"""워크플로우 레시피 API.

카드가 앱 하나라면, 레시피는 '앱 여러 개를 엮은 카드'입니다.
한 번 잘 돌아간 흐름(회의록 정리 -> 할 일 추출 -> 담당자 메일)을 이름 붙여
저장해 두고, 다음부터는 버튼 하나로 똑같이 재실행합니다.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.audit import record, summarize
from app.db import get_db
from app.deps import current_user
from app.models import App, Recipe, Run, RunStatus
from app.orchestrator import recipe as recipe_engine
from app.schemas import (
    RecipeFromRunIn,
    RecipeIn,
    RecipeOut,
    RecipeRunIn,
    RunOut,
)
from app.worker.queue import get_queue
from app.worker.tasks import process_recipe_run

router = APIRouter(prefix="/api/recipes", tags=["워크플로우 레시피"])


def _owned(db: Session, recipe_id: str, user_id: str) -> Recipe:
    target = db.get(Recipe, recipe_id)
    if target is None or target.user_id != user_id:
        raise HTTPException(404, "레시피를 찾을 수 없습니다.")
    return target


def _out(target: Recipe) -> RecipeOut:
    """응답에 '채워 넣어야 할 변수 목록'을 얹어 줍니다."""
    data = RecipeOut.model_validate(target)
    data.variables = recipe_engine.find_variables(
        target.steps or [], target.final_instruction or ""
    )
    return data


@router.get("", response_model=list[RecipeOut], summary="내 레시피 목록")
def list_recipes(
    db: Session = Depends(get_db), user_id: str = Depends(current_user)
) -> list[RecipeOut]:
    rows = (
        db.query(Recipe)
        .filter(Recipe.user_id == user_id)
        .order_by(Recipe.last_run_at.desc().nullslast(), Recipe.created_at.desc())
        .all()
    )
    return [_out(row) for row in rows]


@router.post("", response_model=RecipeOut, status_code=201, summary="레시피 만들기")
def create_recipe(
    payload: RecipeIn,
    request: Request,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> RecipeOut:
    data = payload.model_dump()
    data["steps"] = [_fill_app_names(db, step) for step in data["steps"]]

    target = Recipe(user_id=user_id, **data)
    db.add(target)
    db.commit()
    db.refresh(target)
    record(db, user_id, "recipe_created", "recipe", target.id, {"title": target.title}, request)
    return _out(target)


def _fill_app_names(db: Session, step: dict) -> dict:
    """단계에 앱 이름을 같이 적어 둡니다. 앱이 지워져도 뭘 하려던 건지 남게요."""
    app = db.get(App, step.get("app_id", ""))
    if app is not None:
        step["app_slug"] = app.slug
        step["app_name"] = app.name
    return step


@router.post(
    "/from-run", response_model=RecipeOut, status_code=201, summary="방금 실행을 레시피로 저장"
)
def create_from_run(
    payload: RecipeFromRunIn,
    request: Request,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> RecipeOut:
    """가장 많이 쓰게 될 입구입니다.

    한 번 요청해서 잘 나왔으면, 그 실행 기록의 앱 호출 순서를 그대로 떠서
    레시피로 굳힙니다. 다음부터는 LLM 이 매번 계획을 새로 세우지 않아 빠릅니다.
    """
    run = db.get(Run, payload.run_id)
    if run is None or run.user_id != user_id:
        raise HTTPException(404, "실행 기록을 찾을 수 없습니다.")
    if run.status != RunStatus.succeeded:
        raise HTTPException(409, "성공한 실행만 레시피로 저장할 수 있습니다.")

    steps: list[dict] = []
    # 실행 기록에는 앱 '이름'만 남아 있으므로 이름으로 앱을 다시 찾아 id 를 붙입니다.
    by_name = {a.name: a for a in db.query(App).all()}
    for index, step in enumerate(run.steps or [], start=1):
        if step.get("error"):
            continue  # 실패한 호출은 레시피에 넣지 않습니다
        app = by_name.get(step.get("app", ""))
        steps.append(
            {
                "app_id": app.id if app else "",
                "app_slug": app.slug if app else "",
                "app_name": step.get("app", ""),
                "tool": step.get("tool", ""),
                "arguments": step.get("arguments") or {},
                "title": f"{index}단계 {step.get('app', '')}",
            }
        )

    if not steps:
        raise HTTPException(409, "이 실행에는 저장할 앱 호출이 없습니다.")

    target = Recipe(
        user_id=user_id,
        title=payload.title,
        description=payload.description,
        icon=payload.icon,
        steps=steps,
        final_instruction=run.request_text if payload.keep_final_instruction else "",
        form_id=run.form_id or "",
        source_run_id=run.id,
    )
    db.add(target)
    db.commit()
    db.refresh(target)
    record(db, user_id, "recipe_created", "recipe", target.id,
           {"title": target.title, "from_run": run.id}, request)
    return _out(target)


@router.get("/{recipe_id}", response_model=RecipeOut, summary="레시피 상세")
def get_recipe(
    recipe_id: str, db: Session = Depends(get_db), user_id: str = Depends(current_user)
) -> RecipeOut:
    return _out(_owned(db, recipe_id, user_id))


@router.put("/{recipe_id}", response_model=RecipeOut, summary="레시피 수정")
def update_recipe(
    recipe_id: str,
    payload: RecipeIn,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> RecipeOut:
    target = _owned(db, recipe_id, user_id)
    data = payload.model_dump()
    data["steps"] = [_fill_app_names(db, step) for step in data["steps"]]
    for key, value in data.items():
        setattr(target, key, value)
    db.commit()
    db.refresh(target)
    return _out(target)


@router.delete("/{recipe_id}", status_code=204, response_model=None,
               summary="레시피 삭제")
def delete_recipe(
    recipe_id: str, db: Session = Depends(get_db), user_id: str = Depends(current_user)
) -> None:
    db.delete(_owned(db, recipe_id, user_id))
    db.commit()


@router.post("/{recipe_id}/run", response_model=RunOut, status_code=202, summary="레시피 실행")
def run_recipe(
    recipe_id: str,
    payload: RecipeRunIn,
    request: Request,
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user),
) -> Run:
    """레시피를 큐에 넣습니다. 결과는 보통 실행과 똑같이 /api/runs/{id} 로 봅니다."""
    target = _owned(db, recipe_id, user_id)

    missing = [
        name
        for name in recipe_engine.find_variables(
            target.steps or [], target.final_instruction or ""
        )
        if not (payload.variables or {}).get(name)
    ]
    if missing:
        raise HTTPException(400, f"채워 넣어야 할 값이 있습니다: {', '.join(missing)}")

    run = Run(
        user_id=user_id,
        recipe_id=target.id,
        request_text=f"레시피 '{target.title}' 실행",
        variables=dict(payload.variables or {}),
        form_id=payload.form_id or target.form_id or "",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    record(db, user_id, "recipe_run", "recipe", target.id,
           {"run": run.id, "title": summarize(target.title)}, request)

    get_queue().enqueue(process_recipe_run, run.id)
    return run
