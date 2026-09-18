"use client";

// 워크플로우 레시피. 앱 여러 개를 엮은 흐름을 이름 붙여 저장해 두고 버튼 하나로 재실행합니다.
import { useEffect, useState } from "react";
import { api, Recipe, Run, getSession } from "@/lib/api";

const RUN_LABEL: Record<Run["status"], string> = {
  queued: "대기 중",
  planning: "계획 세우는 중",
  awaiting_approval: "확인 필요",
  running: "처리 중",
  succeeded: "완료",
  failed: "실패",
  rejected: "취소함",
};

export default function Recipes() {
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [open, setOpen] = useState<string>("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState("");

  const reload = () => api.listRecipes().then(setRecipes).catch(() => undefined);

  useEffect(() => {
    if (!getSession()) {
      location.href = "/login";
      return;
    }
    reload();
  }, []);

  // 실행은 큐에 들어가므로 끝날 때까지 2초마다 확인합니다.
  useEffect(() => {
    if (!run) return;
    if (["succeeded", "failed", "rejected", "awaiting_approval"].includes(run.status)) return;
    const timer = setTimeout(
      () => api.getRun(run.id).then(setRun).catch(() => undefined),
      2000
    );
    return () => clearTimeout(timer);
  }, [run]);

  const start = async (recipe: Recipe) => {
    setError("");
    try {
      setRun(await api.runRecipe(recipe.id, values));
      setOpen("");
      setValues({});
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <>
      <h3>워크플로우 레시피</h3>
      <p className="muted">
        카드가 앱 하나라면, 레시피는 <b>앱 여러 개를 엮은 카드</b>입니다. 요청을 한 번
        실행해서 잘 나왔으면 <a href="/">내 에이전트</a> 화면에서 그 흐름을 레시피로
        저장해 두세요. 다음부터는 여기서 버튼 하나로 똑같이 돌아갑니다.
      </p>

      {error && <div className="box" style={{ color: "#b91c1c" }}>{error}</div>}

      {recipes.length === 0 && (
        <div className="box muted">아직 저장된 레시피가 없습니다.</div>
      )}

      {recipes.map((recipe) => (
        <div className="box" key={recipe.id}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <b>
              {recipe.icon} {recipe.title}
            </b>
            <span className="row">
              <span className="tag">{recipe.steps.length}단계</span>
              <span className="tag">{recipe.run_count}번 실행</span>
              <button
                className="ghost"
                onClick={() => {
                  if (confirm(`'${recipe.title}' 레시피를 지울까요?`))
                    api.deleteRecipe(recipe.id).then(reload);
                }}
              >
                삭제
              </button>
            </span>
          </div>

          {recipe.description && <div className="muted">{recipe.description}</div>}

          <ol className="muted" style={{ marginTop: 8 }}>
            {recipe.steps.map((step, i) => (
              <li key={i}>
                <b>{step.app_name}</b> · {step.tool}
              </li>
            ))}
          </ol>

          {open === recipe.id ? (
            <div style={{ marginTop: 8 }}>
              {recipe.variables.map((name) => (
                <div key={name}>
                  <label>{name}</label>
                  <textarea
                    rows={2}
                    value={values[name] || ""}
                    onChange={(e) => setValues({ ...values, [name]: e.target.value })}
                  />
                </div>
              ))}
              <div className="row" style={{ marginTop: 8 }}>
                <button onClick={() => start(recipe)}>실행</button>
                <button className="ghost" onClick={() => setOpen("")}>
                  취소
                </button>
              </div>
            </div>
          ) : (
            <div style={{ marginTop: 8 }}>
              <button
                onClick={() => {
                  setValues({});
                  if (recipe.variables.length === 0) start(recipe);
                  else setOpen(recipe.id);
                }}
              >
                {recipe.variables.length === 0 ? "실행" : "값 넣고 실행"}
              </button>
            </div>
          )}
        </div>
      ))}

      {run && (
        <div className="box">
          <div className="row">
            <b>실행 결과</b>
            <span className="tag">{RUN_LABEL[run.status]}</span>
          </div>

          {run.status === "awaiting_approval" && (
            <div style={{ marginTop: 10 }}>
              <p>
                되돌릴 수 없는 작업이 들어 있어 확인이 필요합니다. 이대로 진행할까요?
              </p>
              <ul>
                {run.plan.map((step, i) => (
                  <li key={i}>
                    {step.requires_confirmation ? "⚠️ " : ""}
                    <b>{step.app}</b> · {step.tool}
                  </li>
                ))}
              </ul>
              <div className="row">
                <button onClick={() => api.approveRun(run.id).then(setRun)}>
                  이대로 진행
                </button>
                <button className="ghost" onClick={() => api.rejectRun(run.id).then(setRun)}>
                  취소
                </button>
              </div>
            </div>
          )}

          {run.steps?.length > 0 && (
            <ul className="muted">
              {run.steps.map((step, i) => (
                <li key={i}>
                  {step.error ? "⚠️" : "✅"} {step.app} · {step.tool}
                </li>
              ))}
            </ul>
          )}
          {run.result_text && <pre>{run.result_text}</pre>}
          {run.error && <pre style={{ color: "#b91c1c" }}>{run.error}</pre>}
        </div>
      )}
    </>
  );
}
