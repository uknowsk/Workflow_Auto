"use client";

import { useEffect, useState } from "react";
import { api, App } from "@/lib/api";

export default function Admin() {
  const [pending, setPending] = useState<App[]>([]);
  const [message, setMessage] = useState("");

  const reload = () =>
    api
      .listPending()
      .then(setPending)
      .catch(() =>
        setMessage(
          "관리자만 볼 수 있습니다. 백엔드 환경변수 ADMIN_USER_IDS 에 내 사번을 넣고, 첫 화면에서 같은 사번으로 바꿔 주세요."
        )
      );

  useEffect(() => {
    reload();
  }, []);

  return (
    <>
      <h3>승인 대기 중인 앱</h3>
      {message && <div className="box muted">{message}</div>}
      {pending.length === 0 && !message && (
        <div className="box muted">대기 중인 앱이 없습니다.</div>
      )}
      {pending.map((app) => (
        <div className="box" key={app.id}>
          <b>
            {app.icon} {app.name}
          </b>
          <div className="muted">
            올린 사람: {app.owner_user_id || "-"} · 기능 {app.tools.length}개
            {app.capability_tag && ` · 역할: ${app.capability_tag}`}
          </div>
          <div className="muted">{app.usage_hint || app.description}</div>
          <div className="row" style={{ marginTop: 8 }}>
            <button onClick={() => api.approveApp(app.id).then(reload)}>
              공식 승인
            </button>
            <button className="ghost" onClick={() => api.rejectApp(app.id).then(reload)}>
              반려 (개인용으로 되돌림)
            </button>
          </div>
        </div>
      ))}
    </>
  );
}
