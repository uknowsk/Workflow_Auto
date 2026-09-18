"use client";

import { useEffect, useState } from "react";
import { clearSession, getSession } from "@/lib/api";

export default function Nav() {
  const [session, setSession] = useState<{ user_id: string; is_admin: boolean } | null>(
    null
  );

  useEffect(() => {
    setSession(getSession());
  }, []);

  return (
    <nav>
      <b>⚙️ Workflow Auto</b>
      <a href="/dashboard">대시보드</a>
      <a href="/">내 에이전트</a>
      <a href="/recipes">레시피</a>
      <a href="/schedules">예약</a>
      <a href="/store">앱스토어</a>
      <a href="/forms">양식</a>
      <a href="/stats">이달의 앱</a>
      {session?.is_admin && <a href="/admin">관리자</a>}
      <span style={{ marginLeft: "auto" }} className="muted">
        {session ? (
          <>
            {session.user_id}
            {" · "}
            <a
              href="/login"
              onClick={() => clearSession()}
              style={{ cursor: "pointer" }}
            >
              로그아웃
            </a>
          </>
        ) : (
          <a href="/login">로그인</a>
        )}
      </span>
    </nav>
  );
}
