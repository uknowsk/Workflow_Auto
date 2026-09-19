"use client";

// 날짜 계산기: D-day, 두 날짜 사이, 영업일 더하기.
//
// 주말만 빼고 셉니다. 공휴일은 해마다 달라 사내 달력이 붙기 전에는 넣지 않습니다.

import { useState } from "react";
import { Field, Input, Muted, Row, Tabs, type TabItem } from "@/components/ui";

const DAY = 86400000;
const WEEKDAY = "일월화수목금토";

function today(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${now.getFullYear()}-${month}-${day}`;
}

/** 시각은 빼고 날짜만 다룹니다. 하루 차이가 시간대 때문에 어긋나지 않게요. */
function toDate(text: string): Date | null {
  if (!text) return null;
  const [y, m, d] = text.split("-").map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

function label(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(
    date.getDate()
  ).padStart(2, "0")} (${WEEKDAY[date.getDay()]})`;
}

/** 시작일 다음 날부터 끝일까지 주말을 뺀 날 수 */
function workdaysBetween(start: Date, end: Date): number {
  const step = end >= start ? 1 : -1;
  let count = 0;
  const cursor = new Date(start);
  while (cursor.getTime() !== end.getTime()) {
    cursor.setDate(cursor.getDate() + step);
    const day = cursor.getDay();
    if (day !== 0 && day !== 6) count += step;
  }
  return count;
}

function addWorkdays(start: Date, days: number): Date {
  const step = days >= 0 ? 1 : -1;
  let left = Math.abs(days);
  const cursor = new Date(start);
  while (left > 0) {
    cursor.setDate(cursor.getDate() + step);
    const day = cursor.getDay();
    if (day !== 0 && day !== 6) left -= 1;
  }
  return cursor;
}

type Mode = "dday" | "between" | "add";

const MODES: TabItem<Mode>[] = [
  { key: "dday", label: "D-day" },
  { key: "between", label: "두 날짜 사이" },
  { key: "add", label: "영업일 더하기" },
];

export default function DateCalc() {
  const [mode, setMode] = useState<Mode>("dday");
  const [target, setTarget] = useState("");
  const [start, setStart] = useState(today());
  const [end, setEnd] = useState(today());
  const [base, setBase] = useState(today());
  const [days, setDays] = useState("3");

  const now = toDate(today())!;

  return (
    <div className="tool-date">
      <Tabs items={MODES} value={mode} onChange={setMode} />

      {mode === "dday" && (
        <>
          <Field label="그 날짜" hint="기념일, 마감일, 출시일">
            <Input
              type="date"
              value={target}
              onChange={(event) => setTarget(event.target.value)}
            />
          </Field>
          {(() => {
            const date = toDate(target);
            if (!date) return <Muted>날짜를 고르면 며칠 남았는지 알려 드립니다.</Muted>;
            const diff = Math.round((date.getTime() - now.getTime()) / DAY);
            const work = workdaysBetween(now, date);
            return (
              <div className="tool-date__result">
                <strong>
                  {diff === 0 ? "오늘입니다" : diff > 0 ? `D-${diff}` : `D+${-diff}`}
                </strong>
                <span>{label(date)}</span>
                <Muted>
                  {diff > 0
                    ? `${diff}일 남았습니다 (영업일 ${work}일)`
                    : diff < 0
                      ? `${-diff}일 지났습니다 (영업일 ${-work}일)`
                      : "오늘이 바로 그 날입니다"}
                </Muted>
              </div>
            );
          })()}
        </>
      )}

      {mode === "between" && (
        <>
          <Row nowrap>
            <Field label="시작일">
              <Input
                type="date"
                value={start}
                onChange={(event) => setStart(event.target.value)}
              />
            </Field>
            <Field label="종료일">
              <Input
                type="date"
                value={end}
                onChange={(event) => setEnd(event.target.value)}
              />
            </Field>
          </Row>
          {(() => {
            const from = toDate(start);
            const to = toDate(end);
            if (!from || !to) return <Muted>두 날짜를 모두 골라 주세요.</Muted>;
            const diff = Math.round((to.getTime() - from.getTime()) / DAY);
            return (
              <div className="tool-date__result">
                <strong>{Math.abs(diff)}일</strong>
                <span>영업일 {Math.abs(workdaysBetween(from, to))}일</span>
                <Muted>
                  약 {Math.abs(Math.round((diff / 7) * 10) / 10)}주 · 시작일은 세지 않습니다
                </Muted>
              </div>
            );
          })()}
        </>
      )}

      {mode === "add" && (
        <>
          <Row nowrap>
            <Field label="기준일">
              <Input
                type="date"
                value={base}
                onChange={(event) => setBase(event.target.value)}
              />
            </Field>
            <Field label="영업일" hint="음수면 거꾸로">
              <Input
                type="number"
                value={days}
                onChange={(event) => setDays(event.target.value)}
              />
            </Field>
          </Row>
          {(() => {
            const from = toDate(base);
            const count = Number(days);
            if (!from || Number.isNaN(count)) return <Muted>기준일과 일수를 넣어 주세요.</Muted>;
            const result = addWorkdays(from, count);
            return (
              <div className="tool-date__result">
                <strong>{label(result)}</strong>
                <Muted>
                  주말은 빼고 셌습니다. 공휴일은 반영하지 않습니다.
                </Muted>
              </div>
            );
          })()}
        </>
      )}
    </div>
  );
}
