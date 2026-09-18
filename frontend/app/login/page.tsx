"use client";

import { useState } from "react";
import { api, saveSession } from "@/lib/api";

export default function Login() {
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      const result = await api.login(userId, password);
      saveSession(result.token, result.user_id, result.is_admin);
      location.href = "/";
    } catch (err) {
      setError(String(err instanceof Error ? err.message : err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="box" style={{ maxWidth: 380, margin: "48px auto" }}>
      <h3 style={{ marginTop: 0 }}>로그인</h3>
      <form onSubmit={submit}>
        <label>사번</label>
        <input value={userId} onChange={(e) => setUserId(e.target.value)} autoFocus />
        <label>비밀번호</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <div style={{ marginTop: 14 }}>
          <button type="submit" disabled={busy || !userId || !password}>
            {busy ? "확인 중…" : "로그인"}
          </button>
        </div>
      </form>
      {error && <p style={{ color: "#b91c1c", fontSize: 13 }}>{error}</p>}
      <p className="muted" style={{ marginTop: 16 }}>
        나중에 사내 SSO(사번 로그인)로 바뀝니다. 지금은 관리자에게 계정을 받아
        사용하세요.
      </p>
    </div>
  );
}
