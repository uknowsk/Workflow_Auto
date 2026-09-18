"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { clearSession, getSession } from "@/lib/api";
import {
  Avatar,
  NavTabs,
  ThemePicker,
  TopBar,
  type NavTabItem,
} from "@/components/ui";

// 메뉴는 묶음으로 나눠 둡니다. 위아래 탭 테마에서는 한 줄로 이어 붙고,
// 세로 메뉴 테마에서는 묶음 이름이 작은 라벨로 보입니다.
const GROUPS: { label: string; items: NavTabItem[] }[] = [
  {
    label: "작업",
    items: [
      { href: "/dashboard", label: "대시보드" },
      { href: "/", label: "내 에이전트" },
      { href: "/recipes", label: "레시피" },
      { href: "/schedules", label: "예약" },
    ],
  },
  {
    label: "자원",
    items: [
      { href: "/store", label: "앱스토어" },
      { href: "/forms", label: "양식" },
    ],
  },
  {
    label: "내 것",
    items: [
      { href: "/tasks", label: "할 일" },
      { href: "/mail", label: "메일함" },
    ],
  },
];

// 관리자만 보는 메뉴. "이달의 앱"은 앱 순위·사용량이라 일반 사용자에게는 감춥니다.
const ADMIN_GROUP: { label: string; items: NavTabItem[] } = {
  label: "관리",
  items: [
    { href: "/stats", label: "이달의 앱" },
    { href: "/admin", label: "관리자" },
  ],
};

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

  const groups = session?.is_admin ? [...GROUPS, ADMIN_GROUP] : GROUPS;

  return (
    <header className="ui-nav">
      <TopBar
        right={
          onLogin ? null : session ? (
            <>
              <ThemePicker />
              <span className="ui-topbar__id">{session.user_id}</span>
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
        <div className="ui-nav__menu ui-wrap">
          <NavTabs groups={groups} current={pathname} />
        </div>
      )}
    </header>
  );
}
