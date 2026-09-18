// 탭 두 가지.
// - NavTabs: 주소가 바뀌는 탭 (화면 이동). 링크라서 새 창으로도 열립니다.
// - Tabs: 같은 화면 안에서 내용만 바꾸는 탭 (관리자 화면처럼).

import type { ReactNode } from "react";
import { cx } from "./primitives";

export type NavTabItem = { href: string; label: ReactNode };
export type NavTabGroup = { label: string; items: NavTabItem[] };

/**
 * 화면 이동 메뉴. 묶음별로 넘기면 테마가 알아서 가로 탭 줄이나
 * 세로 메뉴로 그려 줍니다. 묶음 이름은 세로 메뉴 테마에서만 보입니다.
 */
export function NavTabs({
  groups,
  current,
}: {
  groups: NavTabGroup[];
  /** 지금 열려 있는 주소. 예) usePathname() 값 */
  current: string;
}) {
  return (
    <nav className="ui-tabs">
      {groups.map((group) => (
        <div className="ui-tabs__group" key={group.label}>
          <span className="ui-tabs__label" aria-hidden="true">
            {group.label}
          </span>
          {group.items.map((item) => {
            const active =
              item.href === "/" ? current === "/" : current.startsWith(item.href);
            return (
              <a
                key={item.href}
                href={item.href}
                className={cx("ui-tab")}
                aria-current={active ? "page" : undefined}
              >
                {item.label}
              </a>
            );
          })}
        </div>
      ))}
    </nav>
  );
}

export type TabItem<T extends string> = { key: T; label: ReactNode };

export function Tabs<T extends string>({
  items,
  value,
  onChange,
}: {
  items: TabItem<T>[];
  value: T;
  onChange: (key: T) => void;
}) {
  return (
    <div className="ui-tabs" role="tablist">
      {items.map((item) => (
        <button
          key={item.key}
          type="button"
          role="tab"
          aria-selected={value === item.key}
          className="ui-tab"
          onClick={() => onChange(item.key)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
