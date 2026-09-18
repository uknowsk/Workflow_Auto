"use client";

import { useEffect, useState } from "react";
import { api, App, Card, Form, Recipe, Run, getSession } from "@/lib/api";

const STATUS_LABEL: Record<Run["status"], string> = {
  queued: "대기 중",
  planning: "계획 세우는 중",
  awaiting_approval: "확인 필요",
  running: "처리 중",
  succeeded: "완료",
  failed: "실패",
  rejected: "취소함",
};

export default function Home() {
  const [cards, setCards] = useState<Card[]>([]);
  const [apps, setApps] = useState<App[]>([]);
  const [forms, setForms] = useState<Form[]>([]);
  const [text, setText] = useState("");
  const [cardId, setCardId] = useState("");
  const [formId, setFormId] = useState("");
  const [run, setRun] = useState<Run | null>(null);
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [error, setError] = useState("");

  const reload = () => {
    api.listCards().then(setCards).catch(() => undefined);
    api.listApps().then(setApps).catch(() => undefined);
    api.listForms().then(setForms).catch(() => undefined);
    api.listRecipes().then(setRecipes).catch(() => undefined);
  };

  useEffect(() => {
    if (!getSession()) {
      location.href = "/login";
      return;
    }
    reload();
  }, []);

  // 실행은 큐에 들어가므로, 끝나거나 확인이 필요할 때까지 2초마다 상태를 봅니다.
  useEffect(() => {
    if (!run) return;
    const done = ["succeeded", "failed", "rejected", "awaiting_approval"];
    if (done.includes(run.status)) return;
    const timer = setTimeout(
      () => api.getRun(run.id).then(setRun).catch(() => undefined),
      2000
    );
    return () => clearTimeout(timer);
  }, [run]);

  const submit = async () => {
    setError("");
    try {
      setRun(
        await api.createRun({
          request_text: text,
          card_id: cardId || null,
          form_id: formId || null,
        })
      );
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    }
  };

  // 한 번 잘 돌아간 흐름을 레시피로 굳혀 둡니다. 다음부터는 버튼 하나로 끝납니다.
  const saveAsRecipe = async () => {
    if (!run) return;
    const title = prompt(
      "이 흐름에 이름을 붙여 주세요. 예) 회의록 정리 후 담당자 메일"
    );
    if (!title) return;
    try {
      await api.createRecipeFromRun({ run_id: run.id, title });
      reload();
      alert("레시피로 저장했습니다. '레시피' 화면에서 언제든 다시 실행할 수 있어요.");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const addCard = async () => {
    const title = prompt("카드 이름을 적어 주세요. 예) 주간보고 자동작성");
    if (!title) return;
    const template = prompt("이 카드를 누르면 채워질 요청문을 적어 주세요.") || "";
    await api.createCard({
      title,
      prompt_template: template,
      app_ids: [],
      icon: "⭐",
      pinned: true,
    });
    reload();
  };

  return (
    <>
      <h3>자주 쓰는 에이전트</h3>
      <div className="grid">
        {cards.map((card) => (
          <div className="box" key={card.id} style={{ marginBottom: 0 }}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <b>
                {card.icon} {card.title}
              </b>
              <button className="ghost" onClick={() => api.deleteCard(card.id).then(reload)}>
                삭제
              </button>
            </div>
            <div className="muted">{card.prompt_template || "요청문 없음"}</div>
            <div style={{ marginTop: 8 }}>
              <button
                onClick={() => {
                  setText(card.prompt_template);
                  setCardId(card.id);
                }}
              >
                이 카드로 요청
              </button>
            </div>
          </div>
        ))}
        {recipes.slice(0, 4).map((recipe) => (
          <div className="box" key={recipe.id} style={{ marginBottom: 0 }}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <b>
                {recipe.icon} {recipe.title}
              </b>
              <span className="tag">레시피 {recipe.steps.length}단계</span>
            </div>
            <div className="muted">
              {recipe.description || "저장해 둔 앱 호출 흐름입니다."}
            </div>
            <div style={{ marginTop: 8 }}>
              <button className="ghost" onClick={() => (location.href = "/recipes")}>
                레시피 실행
              </button>
            </div>
          </div>
        ))}
        <div className="box" style={{ marginBottom: 0 }}>
          <div className="muted">새 카드를 만들어 자주 쓰는 요청을 저장하세요.</div>
          <div style={{ marginTop: 8 }}>
            <button className="ghost" onClick={addCard}>
              + 카드 추가
            </button>
          </div>
        </div>
      </div>

      <h3 style={{ marginTop: 28 }}>무엇을 도와드릴까요?</h3>
      <div className="box">
        <textarea
          rows={4}
          value={text}
          placeholder="예) 사번 E1001의 이번주 주간보고를 작성해줘"
          onChange={(e) => setText(e.target.value)}
        />
        <div className="row" style={{ marginTop: 8 }}>
          <select
            value={formId}
            onChange={(e) => setFormId(e.target.value)}
            style={{ width: 220 }}
          >
            <option value="">양식 없음 (자유 형식)</option>
            {forms.map((form) => (
              <option key={form.id} value={form.id}>
                {form.name}
              </option>
            ))}
          </select>
          <button onClick={submit} disabled={!text.trim()}>
            실행
          </button>
          {cardId && (
            <span className="tag">
              카드로 실행 중 ·{" "}
              <a onClick={() => setCardId("")} href="#">
                해제
              </a>
            </span>
          )}
          <span className="muted">사용 가능한 앱 {apps.length}개</span>
        </div>
      </div>

      {error && <div className="box" style={{ color: "#b91c1c" }}>{error}</div>}

      {run && (
        <div className="box">
          <div className="row">
            <b>상태</b>
            <span className="tag">{STATUS_LABEL[run.status]}</span>
          </div>

          {run.status === "awaiting_approval" && (
            <div style={{ marginTop: 10 }}>
              <p>
                되돌릴 수 없는 작업이 들어 있어 확인이 필요합니다. 아래 계획대로
                진행할까요?
              </p>
              <p className="muted">{run.plan_summary}</p>
              <ul>
                {run.plan.map((step, i) => (
                  <li key={i}>
                    {step.requires_confirmation ? "⚠️ " : ""}
                    <b>{step.app}</b> · {step.tool}
                    {step.why && <span className="muted"> — {step.why}</span>}
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

          {run.status === "succeeded" && (
            <div className="row">
              <button className="ghost" onClick={saveAsRecipe}>
                이 흐름을 레시피로 저장
              </button>
              <span className="muted">
                다음부터 같은 일을 버튼 하나로 하고, 예약도 걸 수 있습니다.
              </span>
            </div>
          )}
        </div>
      )}
    </>
  );
}
