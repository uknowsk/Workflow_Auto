"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { clearSession, getSession } from "@/lib/api";
import { Avatar, NavTabs, TopBar, type NavTabItem } from "@/components/ui";

// 자주 쓰는 순서대로 둡니다. 좁은 화면에서는 옆으로 밀어 볼 수 있습니다.
const BASE_TABS: NavTabItem[] = [
  { href: "/dashboard", label: "대시보드" },
  { href: "/", label: "내 에이전트" },
  { href: "/tasks", label: "할 일" },
  { href: "/mail", label: "메일함" },
  { href: "/store", label: "앱스토어" },
  { href: "/recipes", label: "레시피" },
  { href: "/schedules", label: "예약" },
  { href: "/forms", label: "양식" },
  { href: "/stats", label: "이달의 앱" },
];

export default function Nav() {
  const pathname = usePathname() || "/";
  const [session, setSession] = useState<{ user_id: string; is_admin: boolean } | null>(
    null
  );

  useEffect(() => {
    setSession(getSession());
  }, []);

  // 로그인 화면에서는 이동할 곳이 없으므로 로고만 보여 줍니다.
  const onLogin = pathname.startsWith("/login");

  const tabs = session?.is_admin
    ? [...BASE_TABS, { href: "/admin", label: "관리자" }]
    : BASE_TABS;

  return (
    <>
      <TopBar
        right={
          onLogin ? null : session ? (
            <>
              <span>{session.user_id}</span>
              <a href="/login" onClick={() => clearSession()}>
                로그아웃
              </a>
              <Avatar name={session.user_id} />
            </>
          ) : (
            <a href="/login">로그인</a>
          )
        }
      />
      {!onLogin && (
        <div className="ui-wrap" style={{ paddingBottom: 0 }}>
          <NavTabs items={tabs} current={pathname} />
        </div>
      )}
    </>
  );
}
