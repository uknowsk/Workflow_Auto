"use client";

// 로그인하고 처음 보는 화면. 오늘 챙겨야 할 것만 한눈에 모아 둡니다.
import { useEffect, useState } from "react";
import { api, Dashboard, DashboardWidget, getSession } from "@/lib/api";

const RUN_LABEL: Record<string, string> = {
  queued: "대기 중",
  planning: "계획 세우는 중",
  awaiting_approval: "확인 필요",
  running: "처리 중",
  succeeded: "완료",
  failed: "실패",
  rejected: "취소함",
};

function when(iso: string) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("ko-KR", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function Widget({ widget }: { widget: DashboardWidget }) {
  return (
    <div className="box" style={{ marginBottom: 0 }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <b>
          {widget.icon} {widget.title}
        </b>
        {widget.app && <span className="tag">{widget.app}</span>}
      </div>

      {widget.status === "ok" && <pre>{widget.text}</pre>}
      {widget.status === "empty" && <div className="muted">지금은 없습니다. 👍</div>}
      {widget.status === "missing" && (
        <div className="muted">
          {widget.hint || "이 칸을 채워 줄 앱이 아직 등록되지 않았습니다."}
        </div>
      )}
      {widget.status === "error" && (
        <div className="muted" style={{ color: "#b91c1c" }}>
          앱을 부르지 못했습니다. 앱스토어에서 상태를 확인해 주세요.
        </div>
      )}
    </div>
  );
}

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getSession()) {
      location.href = "/login";
      return;
    }
    api
      .dashboard()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  if (error) return <div className="box" style={{ color: "#b91c1c" }}>{error}</div>;
  if (!data) return <div className="box muted">불러오는 중...</div>;

  return (
    <>
      <h3>오늘 챙길 것</h3>
      <div className="grid">
        {data.widgets.map((widget) => (
          <Widget key={widget.key} widget={widget} />
        ))}
      </div>

      <h3 style={{ marginTop: 28 }}>예약된 작업</h3>
      <div className="box">
        {data.schedules.length === 0 ? (
          <div className="muted">
            예약이 없습니다. <a href="/schedules">예약 만들기</a>
          </div>
        ) : (
          data.schedules.map((row) => (
            <div key={row.id} className="row" style={{ justifyContent: "space-between" }}>
              <span>⏰ {row.title}</span>
              <span className="muted">
                {row.when_text}
                {row.next_run_at && ` · 다음 ${when(row.next_run_at)}`}
              </span>
            </div>
          ))
        )}
      </div>

      <h3 style={{ marginTop: 28 }}>내 레시피</h3>
      <div className="box">
        {data.recipes.length === 0 ? (
          <div className="muted">
            아직 없습니다. 요청을 한 번 실행해서 잘 나오면 그 흐름을 레시피로 저장해 보세요.
          </div>
        ) : (
          data.recipes.map((row) => (
            <div key={row.id} className="row" style={{ justifyContent: "space-between" }}>
              <a href="/recipes">
                {row.icon} {row.title}
              </a>
              <span className="muted">{row.run_count}번 실행</span>
            </div>
          ))
        )}
      </div>

      <h3 style={{ marginTop: 28 }}>최근 실행</h3>
      <div className="box">
        {data.runs.length === 0 ? (
          <div className="muted">아직 실행한 것이 없습니다.</div>
        ) : (
          data.runs.map((row) => (
            <div key={row.id} className="row" style={{ justifyContent: "space-between" }}>
              <span>{row.request_text}</span>
              <span className="tag">{RUN_LABEL[row.status] || row.status}</span>
            </div>
          ))
        )}
      </div>

      {data.ranking.length > 0 && (
        <>
          <h3 style={{ marginTop: 28 }}>이달의 앱</h3>
          <div className="box">
            {data.ranking.map((row) => (
              <div key={row.rank} className="row" style={{ justifyContent: "space-between" }}>
                <span>
                  {row.rank === 1 ? "🏆" : `${row.rank}위`} {row.name}
                </span>
                <span className="muted">성공 {row.success_calls}회</span>
              </div>
            ))}
            <div style={{ marginTop: 8 }}>
              <a href="/stats" className="muted">
                전체 순위 보기
              </a>
            </div>
          </div>
        </>
      )}
    </>
  );
}
