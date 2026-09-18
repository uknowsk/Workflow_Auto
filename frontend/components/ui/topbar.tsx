// 화면 맨 위 고정 바. 왼쪽에 로고, 오른쪽에 로그인한 사람.

import type { ReactNode } from "react";

export function TopBar({ right }: { right?: ReactNode }) {
  return (
    <div className="ui-topbar">
      <div className="ui-topbar__in">
        <a className="ui-brand" href="/">
          <span className="ui-brand__mark">W</span> Workflow Auto
        </a>
        {right ? <div className="ui-topbar__who">{right}</div> : null}
      </div>
    </div>
  );
}

/** 사번 첫 글자를 넣는 동그란 표시 */
export function Avatar({ name }: { name: string }) {
  return <span className="ui-avatar">{name.slice(0, 1) || "?"}</span>;
}
