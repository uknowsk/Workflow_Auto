"use client";

// 화면 위에 겹쳐 뜨는 상자. 앱 등록처럼 "필요할 때만" 쓰는 것을 담습니다.
// 평소에는 목록이 화면을 다 쓰고, 버튼을 눌렀을 때만 이게 열립니다.

import { useEffect, type ReactNode } from "react";
import { Button } from "./primitives";

export function Modal({
  open,
  title,
  sub,
  onClose,
  children,
  footer,
}: {
  open: boolean;
  title: ReactNode;
  sub?: ReactNode;
  onClose: () => void;
  children: ReactNode;
  /** 아래에 고정으로 붙는 버튼 줄 */
  footer?: ReactNode;
}) {
  // Esc 로 닫고, 열려 있는 동안에는 뒤 화면이 따라 스크롤되지 않게 합니다.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const before = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = before;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="ui-modal" role="dialog" aria-modal="true" aria-label={String(title)}>
      <div className="ui-modal__back" onClick={onClose} />
      <div className="ui-modal__box">
        <div className="ui-modal__head">
          <div>
            <h2 className="ui-modal__title">{title}</h2>
            {sub ? <p className="ui-modal__sub">{sub}</p> : null}
          </div>
          <Button variant="ghost" small onClick={onClose} aria-label="닫기">
            닫기
          </Button>
        </div>
        <div className="ui-modal__body">{children}</div>
        {footer ? <div className="ui-modal__foot">{footer}</div> : null}
      </div>
    </div>
  );
}
