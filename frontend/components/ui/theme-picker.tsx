"use client";

// 화면 맨 위에서 테마를 고르는 곳.
// 고른 값은 브라우저에 바로 저장하고(다음에 열 때 안 번쩍이게), 로그인한 상태면
// 서버에도 보내서 다른 PC 에서 들어와도 같은 모양이 나오게 합니다.

import { useEffect, useRef, useState } from "react";
import { api, getSession } from "@/lib/api";
import {
  DEFAULT_THEME,
  THEMES,
  ThemeName,
  applyTheme,
  isTheme,
  readLocalTheme,
  themeLabel,
  writeLocalTheme,
} from "@/lib/theme";
import { cx } from "./primitives";

export function ThemePicker() {
  const [theme, setTheme] = useState<ThemeName>(DEFAULT_THEME);
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  // 처음 뜰 때: 브라우저에 저장된 값을 먼저 쓰고, 계정에 저장된 값이 오면 그걸로 맞춥니다.
  useEffect(() => {
    const local = readLocalTheme();
    setTheme(local);
    applyTheme(local);
    if (!getSession()) return;
    api
      .me()
      .then((me) => {
        if (isTheme(me.theme) && me.theme !== local) {
          setTheme(me.theme);
          applyTheme(me.theme);
          writeLocalTheme(me.theme);
        }
      })
      .catch(() => {
        /* 서버가 아직 안 떴어도 화면은 저장된 테마로 보입니다 */
      });
  }, []);

  // 바깥을 누르거나 Esc 를 누르면 닫습니다.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (!box.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // 고를 게 하나뿐이면 메뉴를 아예 내보내지 않습니다.
  if (THEMES.length < 2) return null;

  const pick = (name: ThemeName) => {
    setTheme(name);
    applyTheme(name);
    writeLocalTheme(name);
    setOpen(false);
    if (getSession()) {
      api.saveSettings({ theme: name }).catch(() => {
        /* 저장에 실패해도 이 브라우저에서는 계속 이 테마입니다 */
      });
    }
  };

  return (
    <div className="ui-theme" ref={box}>
      <button
        type="button"
        className="ui-theme__btn"
        aria-haspopup="true"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <Swatch name={theme} />
        <span className="ui-theme__now">{themeLabel(theme)}</span>
      </button>

      {open && (
        <div className="ui-theme__menu" role="menu" aria-label="화면 테마">
          <p className="ui-theme__head">화면 테마</p>
          {THEMES.map((item) => (
            <button
              key={item.name}
              type="button"
              role="menuitemradio"
              aria-checked={item.name === theme}
              className={cx(
                "ui-theme__item",
                item.name === theme && "ui-theme__item--on"
              )}
              onClick={() => pick(item.name)}
            >
              <Swatch name={item.name} />
              <span className="ui-theme__text">
                <b>{item.label}</b>
                <span>{item.note}</span>
              </span>
            </button>
          ))}
          <p className="ui-theme__foot">고른 테마는 내 계정에 저장됩니다.</p>
        </div>
      )}
    </div>
  );
}

/** 테마마다 색 세 칸을 보여 주는 작은 미리보기 */
function Swatch({ name }: { name: ThemeName }) {
  const item = THEMES.find((t) => t.name === name) ?? THEMES[0];
  return (
    <span className="ui-swatch" aria-hidden="true">
      {item.swatch.map((color, i) => (
        <i key={i} style={{ background: color }} />
      ))}
    </span>
  );
}
