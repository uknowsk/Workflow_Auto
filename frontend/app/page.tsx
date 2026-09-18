"use client";

import { useEffect, useState } from "react";
import { api, App, Card, Run, getUserId, setUserId } from "@/lib/api";

export default function Home() {
  const [userId, setUser] = useState("demo");
  const [cards, setCards] = useState<Card[]>([]);
  const [apps, setApps] = useState<App[]>([]);
  const [text, setText] = useState("");
  const [cardId, setCardId] = useState<string>("");
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState("");

  const reload = () => {
    api.listCards().then(setCards).catch((e) => setError(String(e)));
    api.listApps().then(setApps).catch((e) => setError(String(e)));
  };

  useEffect(() => {
    setUser(getUserId());
    reload();
  }, []);

  // 실행은 큐에 들어가므로, 끝날 때까지 상태를 2초마다 확인합니다.
  useEffect(() => {
    if (!run || run.status === "succeeded" || run.status === "failed") return;
    const timer = setTimeout(
      () => api.getRun(run.id).then(setRun).catch(() => undefined),
      2000
    );
    return () => clearTimeout(timer);
  }, [run]);

  const submit = async () => {
    setError("");
    try {
      setRun(await api.createRun({ request_text: text, card_id: cardId || null }));
    } catch (e) {
      setError(String(e));
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
      <div className="box">
        <div className="row">
          <label style={{ margin: 0 }}>사용 중인 사번</label>
          <input
            style={{ width: 160 }}
            value={userId}
            onChange={(e) => setUser(e.target.value)}
            onBlur={() => {
              setUserId(userId);
              reload();
            }}
          />
          <span className="muted">
            뼈대 단계의 임시 로그인입니다. 사내에서는 SSO 로 바뀝니다.
          </span>
        </div>
      </div>

      <h3>자주 쓰는 에이전트</h3>
      <div className="grid">
        {cards.map((card) => (
          <div className="box" key={card.id} style={{ marginBottom: 0 }}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <b>
                {card.icon} {card.title}
              </b>
              <button
                className="ghost"
                onClick={() => api.deleteCard(card.id).then(reload)}
              >
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
          <button onClick={submit} disabled={!text.trim()}>
            실행
          </button>
          {cardId && (
            <span className="tag">
              카드로 실행 중 · <a onClick={() => setCardId("")} href="#">해제</a>
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
            <span className="tag">{run.status}</span>
          </div>
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
