// 디자인 시스템의 기본 조각들.
// 화면에서는 색·여백을 직접 쓰지 말고 여기 있는 컴포넌트를 쓰세요.
// 모양을 바꾸고 싶으면 app/globals.css 의 토큰이나 .ui-* 규칙을 고칩니다.
// 사용 예시는 docs/DESIGN.md.

import type {
  AnchorHTMLAttributes,
  ButtonHTMLAttributes,
  HTMLAttributes,
  InputHTMLAttributes,
  ReactNode,
  SelectHTMLAttributes,
  TextareaHTMLAttributes,
} from "react";

/** 클래스 이름을 이어 붙입니다. 빈 값은 버립니다. */
export function cx(...names: (string | false | null | undefined)[]) {
  return names.filter(Boolean).join(" ");
}

/* ------------------------------------------------------------------ 버튼 */

type ButtonVariant = "primary" | "ghost" | "danger";

export function Button({
  variant = "primary",
  small,
  block,
  className,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  small?: boolean;
  block?: boolean;
}) {
  return (
    <button
      type="button"
      {...rest}
      className={cx(
        "ui-btn",
        variant === "ghost" && "ui-btn--ghost",
        variant === "danger" && "ui-btn--danger",
        small && "ui-btn--sm",
        block && "ui-btn--block",
        className
      )}
    />
  );
}

/** 링크인데 버튼처럼 보여야 할 때. 예) 파일 내려받기 */
export function LinkButton({
  variant = "ghost",
  small,
  className,
  ...rest
}: AnchorHTMLAttributes<HTMLAnchorElement> & {
  variant?: ButtonVariant;
  small?: boolean;
}) {
  return (
    <a
      {...rest}
      className={cx(
        "ui-btn",
        variant === "ghost" && "ui-btn--ghost",
        variant === "danger" && "ui-btn--danger",
        small && "ui-btn--sm",
        className
      )}
    />
  );
}

/** 알약 모양 작은 버튼. 추천 문구나 목록 필터에 씁니다. */
export function Chip({
  active,
  className,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { active?: boolean }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      {...rest}
      className={cx("ui-chip", active && "ui-chip--on", className)}
    />
  );
}

/* ---------------------------------------------------------------- 담는 것 */

export function Card({
  quiet,
  hoverable,
  className,
  ...rest
}: HTMLAttributes<HTMLDivElement> & { quiet?: boolean; hoverable?: boolean }) {
  return (
    <div
      {...rest}
      className={cx(
        "ui-card",
        quiet && "ui-card--quiet",
        hoverable && "ui-card--hoverable",
        className
      )}
    />
  );
}

/** 제목 + 개수가 붙는, 목록을 담는 상자 */
export function Panel({
  title,
  count,
  children,
  className,
  ...rest
}: HTMLAttributes<HTMLDivElement> & { title: ReactNode; count?: ReactNode }) {
  return (
    <div {...rest} className={cx("ui-panel", className)}>
      <div className="ui-panel__head">
        <h2 className="ui-section__title">{title}</h2>
        {count !== undefined && <span className="ui-count">{count}</span>}
      </div>
      {children}
    </div>
  );
}

export function Row({
  between,
  nowrap,
  className,
  ...rest
}: HTMLAttributes<HTMLDivElement> & { between?: boolean; nowrap?: boolean }) {
  return (
    <div
      {...rest}
      className={cx(
        "ui-row",
        between && "ui-row--between",
        nowrap && "ui-row--nowrap",
        className
      )}
    />
  );
}

/** cols: 2 나 3 이면 그만큼 나누고, 없으면 폭에 맞춰 자동으로 채웁니다. */
export function Grid({
  cols,
  className,
  ...rest
}: HTMLAttributes<HTMLDivElement> & { cols?: 2 | 3 }) {
  return (
    <div
      {...rest}
      className={cx(
        "ui-grid",
        cols === 2 && "ui-grid--2",
        cols === 3 && "ui-grid--3",
        !cols && "ui-grid--auto",
        className
      )}
    />
  );
}

/* ------------------------------------------------------------------ 제목 */

export function PageTitle({
  title,
  sub,
}: {
  title: ReactNode;
  sub?: ReactNode;
}) {
  return (
    <>
      <h1 className="ui-page-title">{title}</h1>
      {sub ? <p className="ui-page-sub">{sub}</p> : null}
    </>
  );
}

/** 섹션 머리: 작은 대문자 라벨 + 오른쪽 링크 */
export function SectionHead({
  label,
  note,
  action,
}: {
  label: ReactNode;
  note?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="ui-section__head">
      <span className="ui-eyebrow">{label}</span>
      {note ? <span className="ui-list__meta">{note}</span> : null}
      {action ? <span className="ui-section__more">{action}</span> : null}
    </div>
  );
}

export function Section({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div {...rest} className={cx("ui-section", className)} />;
}

/* ------------------------------------------------------------------ 입력 */

export function Field({
  label,
  hint,
  error,
  htmlFor,
  children,
}: {
  label: ReactNode;
  hint?: ReactNode;
  error?: ReactNode;
  htmlFor?: string;
  children: ReactNode;
}) {
  return (
    <div className="ui-field">
      <label className="ui-field__label" htmlFor={htmlFor}>
        {label}
        {hint ? <span className="ui-field__hint"> · {hint}</span> : null}
      </label>
      {children}
      {error ? <div className="ui-field__error">{error}</div> : null}
    </div>
  );
}

export function Input({
  className,
  ...rest
}: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...rest} className={cx("ui-input", className)} />;
}

export function Textarea({
  className,
  ...rest
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...rest} className={cx("ui-textarea", className)} />;
}

export function Select({
  className,
  ...rest
}: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...rest} className={cx("ui-select", className)} />;
}

export function Checkbox({
  label,
  className,
  ...rest
}: InputHTMLAttributes<HTMLInputElement> & { label: ReactNode }) {
  return (
    <label className={cx("ui-checkbox", className)}>
      <input type="checkbox" {...rest} />
      <span>{label}</span>
    </label>
  );
}

/* ------------------------------------------------------- 상태 표시용 조각 */

export type Tone = "neutral" | "accent" | "ok" | "warn" | "crit";

const TONE_CLASS: Record<Tone, string> = {
  neutral: "",
  accent: "ui-badge--accent",
  ok: "ui-badge--ok",
  warn: "ui-badge--warn",
  crit: "ui-badge--crit",
};

/** 지금 어떤 상태인지 (완료, 진행 중, 실패…) */
export function Badge({
  tone = "neutral",
  className,
  ...rest
}: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span {...rest} className={cx("ui-badge", TONE_CLASS[tone], className)} />
  );
}

/** 무엇인지 분류 (메일, 문서, 등록자…) */
export function Tag({ className, ...rest }: HTMLAttributes<HTMLSpanElement>) {
  return <span {...rest} className={cx("ui-tag", className)} />;
}

export function Dot({ tone = "neutral" }: { tone?: Tone }) {
  const cls =
    tone === "ok"
      ? "ui-dot--ok"
      : tone === "warn"
        ? "ui-dot--warn"
        : tone === "crit"
          ? "ui-dot--crit"
          : "";
  return <span className={cx("ui-dot", cls)} aria-hidden="true" />;
}

/** 앱·카드 앞에 붙는 네모 아이콘. 이모지나 두 글자를 넣습니다. */
export function IconTile({
  children,
  large,
}: {
  children: ReactNode;
  large?: boolean;
}) {
  return (
    <span
      className={cx("ui-icon-tile", large && "ui-icon-tile--lg")}
      aria-hidden="true"
    >
      {children}
    </span>
  );
}

/** 날짜·시간처럼 폭이 고른 글씨로 보여야 하는 값 */
export function When({ children }: { children: ReactNode }) {
  return <span className="ui-when">{children}</span>;
}

export function Muted({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div {...rest} className={cx("ui-muted", className)} />;
}

/** 0~100 사이 값을 막대로 */
export function Bar({ percent }: { percent: number }) {
  const width = Math.max(0, Math.min(100, percent));
  return (
    <span className="ui-bar">
      <i style={{ width: `${width}%` }} />
    </span>
  );
}

/* ------------------------------------------------------------ 알림·빈 화면 */

export function Alert({
  tone = "neutral",
  className,
  ...rest
}: HTMLAttributes<HTMLDivElement> & { tone?: Tone }) {
  return (
    <div
      {...rest}
      className={cx(
        "ui-alert",
        tone === "crit" && "ui-alert--crit",
        tone === "warn" && "ui-alert--warn",
        tone === "ok" && "ui-alert--ok",
        className
      )}
    />
  );
}

/** 목록이 비었을 때. 사용자가 다음에 뭘 하면 되는지 한 줄로 적어 주세요. */
export function Empty({ children }: { children: ReactNode }) {
  return <div className="ui-empty">{children}</div>;
}

/** 원문·로그처럼 그대로 보여 줄 때 */
export function Pre({ className, ...rest }: HTMLAttributes<HTMLPreElement>) {
  return <pre {...rest} className={cx("ui-pre", className)} />;
}

/* -------------------------------------------------------------- 목록 / 표 */

export function List({ className, ...rest }: HTMLAttributes<HTMLUListElement>) {
  return <ul {...rest} className={cx("ui-list", className)} />;
}

/** 목록 한 줄: 점 + 제목/설명 + 오른쪽 시각 */
export function ListItem({
  tone,
  title,
  meta,
  when,
  right,
}: {
  tone?: Tone;
  title: ReactNode;
  meta?: ReactNode;
  when?: ReactNode;
  right?: ReactNode;
}) {
  return (
    <li>
      {tone !== undefined && <Dot tone={tone} />}
      <div className="ui-list__main">
        <span className="ui-list__title">{title}</span>
        {meta ? <span className="ui-list__meta">{meta}</span> : null}
      </div>
      {when ? <When>{when}</When> : null}
      {right}
    </li>
  );
}

/** 테두리로 감싼 줄 목록. 자식 하나가 한 줄입니다. */
export function Rows({ className, ...rest }: HTMLAttributes<HTMLDivElement>) {
  return <div {...rest} className={cx("ui-rows", className)} />;
}

export function Table({
  className,
  ...rest
}: HTMLAttributes<HTMLTableElement>) {
  return <table {...rest} className={cx("ui-table", className)} />;
}
