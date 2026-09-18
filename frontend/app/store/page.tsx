"use client";

import { useEffect, useState } from "react";
import { api, App } from "@/lib/api";

const EMPTY = {
  slug: "",
  name: "",
  endpoint: "http://localhost:9001/mcp",
  description: "",
  usage_hint: "",
  category: "etc",
  capability_tag: "",
  owner: "",
  owner_dept: "",
  owner_contact: "",
  icon: "🧩",
};

const LABEL: Record<string, string> = {
  private: "개인용",
  pending: "승인 대기",
  approved: "공식",
};

export default function Store() {
  const [apps, setApps] = useState<App[]>([]);
  const [form, setForm] = useState({ ...EMPTY });
  const [message, setMessage] = useState("");

  const reload = () => api.listApps().then(setApps).catch((e) => setMessage(String(e)));
  useEffect(() => {
    reload();
  }, []);

  const register = async () => {
    setMessage("");
    try {
      const created = await api.registerApp(form);
      setMessage(
        created.status === "active"
          ? `등록 완료. 기능 ${created.tools.length}개를 자동으로 찾았습니다.`
          : `등록은 됐지만 앱에 접속하지 못했습니다: ${created.last_error}`
      );
      setForm({ ...EMPTY });
      reload();
    } catch (e) {
      setMessage(String(e));
    }
  };

  const field = (key: keyof typeof EMPTY, label: string, hint = "") => (
    <div>
      <label>
        {label} {hint && <span className="muted">· {hint}</span>}
      </label>
      <input
        value={form[key]}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
      />
    </div>
  );

  return (
    <>
      <h3>앱스토어</h3>
      <div className="grid">
        {apps.map((app) => (
          <div className="box" key={app.id} style={{ marginBottom: 0 }}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <b>
                {app.icon} {app.name}
              </b>
              <span className="tag">{LABEL[app.visibility]}</span>
            </div>
            <div className="muted">{app.description || app.usage_hint}</div>
            <div className="muted" style={{ marginTop: 6 }}>
              등록자: {app.owner || app.owner_user_id || "-"}
              {app.owner_contact && ` · ${app.owner_contact}`}
            </div>
            <div className="muted">
              기능 {app.tools.length}개
              {app.capability_tag && ` · 역할: ${app.capability_tag}`}
              {app.status !== "active" && ` · ⚠️ ${app.status}`}
            </div>
            <div className="row" style={{ marginTop: 8 }}>
              <button className="ghost" onClick={() => api.refreshApp(app.id).then(reload)}>
                새로고침
              </button>
              {app.visibility === "private" && (
                <button className="ghost" onClick={() => api.submitApp(app.id).then(reload)}>
                  공식 등록 신청
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      <h3 style={{ marginTop: 28 }}>내 앱 등록하기</h3>
      <div className="box">
        <p className="muted">
          내 앱을 고칠 필요는 없습니다. <code>templates/</code> 의 어댑터를 복사해
          실행한 뒤, 그 주소(<code>.../mcp</code>)를 여기에 넣으면 됩니다. 방법은{" "}
          <code>docs/WRAPPER_PROMPT.md</code> 참고.
        </p>
        {field("slug", "앱 ID", "영문 소문자와 - 만. 예) rag-policy")}
        {field("name", "앱 이름")}
        {field("endpoint", "어댑터 주소", "MCP 주소. 보통 /mcp 로 끝납니다")}
        {field("usage_hint", "언제 쓰는 앱인가요?", "오케스트레이터가 이 문장을 보고 고릅니다")}
        {field("capability_tag", "역할 태그", "같은 일을 하는 앱끼리 같은 값. 예) 사내규정검색")}
        {field("description", "설명")}
        {field("category", "분류")}
        {field("owner", "등록자 이름", "앱이 고장났을 때 연락할 사람")}
        {field("owner_dept", "등록자 소속")}
        {field("owner_contact", "연락처", "메일 또는 사내 메신저")}
        {field("icon", "아이콘")}
        <div style={{ marginTop: 12 }}>
          <button onClick={register} disabled={!form.slug || !form.name}>
            등록 (처음에는 개인용으로 저장됩니다)
          </button>
        </div>
        {message && <p className="muted">{message}</p>}
      </div>
    </>
  );
}
