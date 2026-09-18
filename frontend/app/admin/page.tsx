"use client";

import { useEffect, useState } from "react";
import { api, App, Notice, Usage } from "@/lib/api";

type Tab = "pending" | "usage" | "audit" | "notices";

export default function Admin() {
  const [tab, setTab] = useState<Tab>("pending");
  const [pending, setPending] = useState<App[]>([]);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [audit, setAudit] = useState<Record<string, unknown>[]>([]);
  const [notices, setNotices] = useState<Notice[]>([]);
  const [message, setMessage] = useState("");

  const reload = () => {
    setMessage("");
    api
      .listPending()
      .then(setPending)
      .catch(() =>
        setMessage(
          "관리자만 볼 수 있습니다. 백엔드 환경변수 ADMIN_USER_IDS 에 내 사번을 넣거나, 관리자 계정으로 로그인하세요."
        )
      );
    api.usage().then(setUsage).catch(() => undefined);
    api.audit().then(setAudit).catch(() => undefined);
    api.notifications().then(setNotices).catch(() => undefined);
  };

  useEffect(() => {
    reload();
  }, []);

  const tabs: [Tab, string][] = [
    ["pending", `승인 대기 ${pending.length}`],
    ["usage", "Gauss 사용량"],
    ["audit", "감사 기록"],
    ["notices", `알림 ${notices.filter((n) => !n.read).length}`],
  ];

  return (
    <>
      <div className="row" style={{ marginBottom: 16 }}>
        {tabs.map(([key, label]) => (
          <button
            key={key}
            className={tab === key ? "" : "ghost"}
            onClick={() => setTab(key)}
          >
            {label}
          </button>
        ))}
      </div>

      {message && <div className="box muted">{message}</div>}

      {tab === "pending" && (
        <>
          {pending.length === 0 && !message && (
            <div className="box muted">대기 중인 앱이 없습니다.</div>
          )}
          {pending.map((app) => (
            <div className="box" key={app.id}>
              <b>
                {app.icon} {app.name}
              </b>
              <div className="muted">
                올린 사람: {app.owner || app.owner_user_id || "-"}
                {app.owner_contact && ` · ${app.owner_contact}`} · 기능{" "}
                {app.tools.length}개
                {app.capability_tag && ` · 역할: ${app.capability_tag}`}
              </div>
              <div className="muted">{app.usage_hint || app.description}</div>
              {app.requires_confirmation && (
                <div className="muted">⚠️ 되돌릴 수 없는 작업을 하는 앱입니다</div>
              )}
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
      )}

      {tab === "usage" && usage && (
        <div className="box">
          <b>{usage.period} Gauss 사용량</b>
          <p className="muted">
            전체 {usage.all_users?.total_tokens.toLocaleString() ?? "-"} 토큰 ·
            호출 {usage.all_users?.calls ?? "-"}회
            <br />
            지금은 확인만 하고 한도로 막지는 않습니다.
          </p>
          <table style={{ width: "100%", fontSize: 13 }}>
            <thead>
              <tr>
                <th align="left">사번</th>
                <th align="right">토큰</th>
                <th align="right">호출</th>
              </tr>
            </thead>
            <tbody>
              {(usage.by_user || []).map((row) => (
                <tr key={row.user_id}>
                  <td>{row.user_id}</td>
                  <td align="right">{row.total_tokens.toLocaleString()}</td>
                  <td align="right">{row.calls}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === "audit" && (
        <div className="box">
          <b>감사 기록 (최근 100건)</b>
          <p className="muted">누가, 언제, 어떤 앱을 어떤 내용으로 불렀는지 남습니다.</p>
          <pre style={{ maxHeight: 460, overflow: "auto" }}>
            {audit
              .map(
                (row) =>
                  `${row.at}  ${row.actor}  ${row.action}  ${row.target ?? ""}\n    ${JSON.stringify(row.detail)}`
              )
              .join("\n")}
          </pre>
        </div>
      )}

      {tab === "notices" && (
        <>
          {notices.length === 0 && <div className="box muted">알림이 없습니다.</div>}
          {notices.map((notice) => (
            <div className="box" key={notice.id}>
              <b>{notice.read ? "" : "🔴 "}{notice.title}</b>
              <pre className="muted">{notice.body}</pre>
              <div className="muted">{notice.at}</div>
            </div>
          ))}
        </>
      )}
    </>
  );
}
