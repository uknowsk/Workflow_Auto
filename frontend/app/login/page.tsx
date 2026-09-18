"use client";

import { useState } from "react";
import { api, saveSession } from "@/lib/api";
import { Alert, Button, Card, Field, Input, Muted } from "@/components/ui";

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
    <Card className="ui-card--pad-lg" style={{ maxWidth: 380, margin: "72px auto" }}>
      <h1 className="ui-page-title" style={{ marginTop: 0, fontSize: "var(--text-lg)" }}>
        로그인
      </h1>
      <p className="ui-page-sub">사번과 비밀번호를 넣어 주세요.</p>

      <form onSubmit={submit}>
        <Field label="사번" htmlFor="login-user">
          <Input
            id="login-user"
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            autoFocus
            autoComplete="username"
          />
        </Field>
        <Field label="비밀번호" htmlFor="login-pw">
          <Input
            id="login-pw"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </Field>
        <Button type="submit" block disabled={busy || !userId || !password}>
          {busy ? "확인 중…" : "로그인"}
        </Button>
      </form>

      {error && (
        <Alert tone="crit" style={{ marginTop: "var(--space-3)" }}>
          {error}
        </Alert>
      )}

      <Muted style={{ marginTop: "var(--space-5)" }}>
        나중에 사내 SSO(사번 로그인)로 바뀝니다. 지금은 관리자에게 계정을 받아
        사용하세요.
      </Muted>
    </Card>
  );
}
