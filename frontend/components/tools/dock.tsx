"use client";

// 도구 서랍.
//
// 화면 왼쪽 구석에 도구 인덱스가 세로로 붙어 있고, 하나를 누르면 오른쪽으로
// 패널이 펼쳐집니다. 어느 화면에서 일하다가도 그 자리에서 열어 쓰라는 뜻이라
// 화면을 옮기지 않습니다(레이아웃에 한 번만 붙입니다).
//
// 한 번 연 도구는 닫아도 메모리에 남겨 두고 화면에서만 숨깁니다.
// 타이머를 켜 둔 채 계산기를 봐도 타이머가 계속 돌아야 하고, 그리다 만 그림이
// 도구를 바꿨다고 사라지면 안 되기 때문입니다.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import { TOOLS, findTool } from "./registry";

const OPEN_KEY = "wfa_tool_open";
const SIZE_KEY = "wfa_tool_size";

type Size = "normal" | "wide" | "full";

const NEXT_SIZE: Record<Size, Size> = { normal: "wide", wide: "full", full: "normal" };
const SIZE_LABEL: Record<Size, string> = {
  normal: "넓게",
  wide: "전체 화면",
  full: "원래대로",
};

export default function ToolDock() {
  const pathname = usePathname() || "/";
  const [openKey, setOpenKey] = useState<string | null>(null);
  const [size, setSize] = useState<Size>("normal");
  // 한 번이라도 연 도구. 닫아도 목록에 남겨 상태를 지킵니다.
  const [mounted, setMounted] = useState<string[]>([]);
  const [ready, setReady] = useState(false);
  const panelRef = useRef<HTMLDivElement | null>(null);

  // 지난번에 열어 둔 도구를 그대로 다시 엽니다.
  useEffect(() => {
    try {
      const savedKey = window.localStorage.getItem(OPEN_KEY);
      const savedSize = window.localStorage.getItem(SIZE_KEY) as Size | null;
      if (savedSize === "normal" || savedSize === "wide" || savedSize === "full") {
        setSize(savedSize);
      }
      if (savedKey && findTool(savedKey)) {
        setOpenKey(savedKey);
        setMounted([savedKey]);
      }
    } catch {
      /* 브라우저가 저장을 막아 두었으면 그냥 닫힌 채로 시작합니다 */
    }
    setReady(true);
  }, []);

  const remember = useCallback((key: string | null, next: Size) => {
    try {
      window.localStorage.setItem(OPEN_KEY, key ?? "");
      window.localStorage.setItem(SIZE_KEY, next);
    } catch {
      /* 저장이 막혀 있어도 이번 화면에서는 그대로 씁니다 */
    }
  }, []);

  const toggle = (key: string) => {
    const tool = findTool(key);
    if (!tool) return;
    const closing = openKey === key;
    const nextKey = closing ? null : key;
    // 넓게 써야 하는 도구는 처음 열 때 한 번 넓혀 줍니다.
    const nextSize = !closing && tool.wide && size === "normal" ? "wide" : size;
    setOpenKey(nextKey);
    setSize(nextSize);
    if (!closing) {
      setMounted((prev) => (prev.includes(key) ? prev : [...prev, key]));
    }
    remember(nextKey, nextSize);
  };

  const close = useCallback(() => {
    setOpenKey(null);
    remember(null, size);
  }, [remember, size]);

  const resize = () => {
    const next = NEXT_SIZE[size];
    setSize(next);
    remember(openKey, next);
  };

  // Esc 로 닫기. 글자를 입력하는 중에는 가로채지 않습니다.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || !openKey) return;
      const tag = (event.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      close();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [openKey, close]);

  const open = useMemo(() => findTool(openKey), [openKey]);

  // 로그인 화면에는 아예 없고, 도구 화면에서는 접어 둡니다.
  // 도구 화면에는 같은 도구가 이미 넓게 펼쳐져 있어서, 서랍까지 열려 있으면
  // 같은 것이 두 번 나오고 화면을 반쯤 가립니다.
  const hideAll = pathname.startsWith("/login");
  const tucked = pathname.startsWith("/tools");

  // 서랍이 없는 화면에서는 왼쪽 여백도 비워 두지 않습니다.
  useEffect(() => {
    const body = document.body;
    body.classList.toggle("no-dock", hideAll || tucked);
    return () => body.classList.remove("no-dock");
  }, [hideAll, tucked]);

  // 서랍이 위쪽 메뉴줄을 덮으면, 도구를 열어 둔 채로는 다른 화면으로 갈 수가
  // 없습니다. 메뉴줄 높이를 재서 그 아래부터 펼치게 합니다(글씨 크기나 화면
  // 폭에 따라 달라질 수 있어 숫자로 박아 두지 않습니다).
  useEffect(() => {
    const menu = document.querySelector(".ui-tabs");
    if (!menu) return;
    const apply = () => {
      // 문서 맨 위에서 메뉴줄 끝까지의 거리. 화면을 내려도 값이 변하지 않게
      // 스크롤한 만큼을 더해 둡니다.
      const bottom = menu.getBoundingClientRect().bottom + window.scrollY;
      document.documentElement.style.setProperty("--drawer-top", `${Math.round(bottom)}px`);
    };
    apply();
    const watch = new ResizeObserver(apply);
    watch.observe(menu);
    return () => watch.disconnect();
  }, [pathname]);

  if (hideAll) return null;

  // 접을 때 지우지 않고 숨기기만 하는 이유: 그리다 만 그림과 돌아가는 타이머를
  // 그대로 두기 위해서입니다. 도구 화면에서 나오면 있던 그대로 다시 나타납니다.
  return (
    <div hidden={tucked}>
      <nav className="tdock" aria-label="도구">
        <span className="tdock__cap" aria-hidden="true">
          도구
        </span>
        {TOOLS.map((tool) => (
          <button
            key={tool.key}
            type="button"
            className={`tdock__btn${openKey === tool.key ? " is-on" : ""}`}
            aria-pressed={openKey === tool.key}
            aria-label={tool.name}
            title={`${tool.name} — ${tool.hint}`}
            onClick={() => toggle(tool.key)}
          >
            <span className="tdock__icon" aria-hidden="true">
              {tool.icon}
            </span>
            <span className="tdock__label">{tool.short}</span>
          </button>
        ))}
      </nav>

      {/* 넓게 펼쳤을 때 뒤쪽을 눌러도 닫히게 합니다. */}
      {open && size === "full" && (
        <div className="tdrawer__scrim" onClick={close} aria-hidden="true" />
      )}

      <section
        ref={panelRef}
        className={`tdrawer tdrawer--${size}${open ? " is-open" : ""}`}
        aria-hidden={open ? undefined : true}
        aria-label={open ? `${open.name} 도구` : undefined}
      >
        <header className="tdrawer__head">
          <span className="tdrawer__title">
            <span aria-hidden="true">{open?.icon}</span> {open?.name}
          </span>
          <span className="tdrawer__hint">{open?.hint}</span>
          <button type="button" className="tdrawer__act" onClick={resize}>
            {SIZE_LABEL[size]}
          </button>
          <button type="button" className="tdrawer__act" onClick={close} aria-label="도구 닫기">
            닫기 ✕
          </button>
        </header>
        <div className="tdrawer__body">
          {/* 연 적이 있는 도구는 모두 여기 남아 있고, 지금 것만 보입니다. */}
          {ready &&
            mounted.map((key) => {
              const tool = findTool(key);
              if (!tool) return null;
              const { Component } = tool;
              return (
                <div key={key} hidden={key !== openKey}>
                  <Component />
                </div>
              );
            })}
        </div>
      </section>
    </div>
  );
}
