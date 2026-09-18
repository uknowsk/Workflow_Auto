"use client";

import { useEffect, useState } from "react";
import { api, Ranking, Usage } from "@/lib/api";

export default function Stats() {
  const [data, setData] = useState<Ranking | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.appRanking().then(setData).catch((e) => setError(String(e)));
    api.usage().then(setUsage).catch(() => undefined);
  }, []);

  return (
    <>
      <h3>이달의 앱 {data && <span className="tag">{data.period}</span>}</h3>
      <p className="muted">
        순위는 단순 호출 수가 아니라 <b>성공한 호출 수</b> 기준입니다. 많이 불렸어도
        계속 실패한 앱은 위로 올라오지 않습니다.
      </p>
      {usage && (
        <div className="box muted">
          내 Gauss 사용량 ({usage.period}): {usage.mine.total_tokens.toLocaleString()} 토큰
          · 호출 {usage.mine.calls}회
        </div>
      )}
      {error && <div className="box" style={{ color: "#b91c1c" }}>{error}</div>}
      {data?.ranking.length === 0 && (
        <div className="box muted">이번 달 호출 기록이 아직 없습니다.</div>
      )}
      {data?.ranking.map((row) => (
        <div className="box" key={row.rank}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <b>
              {row.rank === 1 ? "🏆" : `${row.rank}위`} {row.name}
            </b>
            <span className="tag">성공률 {row.success_rate}%</span>
          </div>
          <div className="muted">
            성공 {row.success_calls}회 / 전체 {row.total_calls}회 · 사용자{" "}
            {row.user_count}명
          </div>
          <div className="muted">
            등록자: {row.owner.name || row.owner.user_id || "-"}
            {row.owner.dept && ` · ${row.owner.dept}`}
            {row.owner.contact && ` · ${row.owner.contact}`}
          </div>
        </div>
      ))}
    </>
  );
}
