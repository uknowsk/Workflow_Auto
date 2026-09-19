"use client";

// 도구 화면. 왼쪽 서랍과 같은 도구들을 넓게 펼쳐 놓고 씁니다.
// 그리기처럼 화면이 넓어야 편한 작업은 여기서 하시면 됩니다.

import { useState } from "react";
import { PageTitle } from "@/components/ui";
import { TOOLS } from "@/components/tools/registry";

export default function ToolsPage() {
  const [current, setCurrent] = useState(TOOLS[0].key);
  const tool = TOOLS.find((item) => item.key === current) ?? TOOLS[0];
  const { Component } = tool;

  return (
    <>
      <PageTitle
        title="도구"
        sub="자주 쓰는 잔도구들입니다. 왼쪽 구석의 세로 인덱스를 누르면 어느 화면에서든 같은 도구가 열립니다."
      />

      <div className="tpage">
        <nav className="tpage__index" aria-label="도구 목록">
          {TOOLS.map((item) => (
            <button
              key={item.key}
              type="button"
              className={`tpage__item${item.key === current ? " is-on" : ""}`}
              aria-current={item.key === current ? "page" : undefined}
              onClick={() => setCurrent(item.key)}
            >
              <span className="tpage__icon" aria-hidden="true">
                {item.icon}
              </span>
              <span>
                <strong>{item.name}</strong>
                <em>{item.hint}</em>
              </span>
            </button>
          ))}
        </nav>

        <div className="tpage__stage">
          <Component />
        </div>
      </div>
    </>
  );
}
