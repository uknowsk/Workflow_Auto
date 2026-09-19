"use client";

// 타이머와 스톱워치.
//
// 시간이 다 되면 소리를 냅니다. 소리 파일을 받아오지 않고 브라우저가 직접
// "삐" 소리를 만들어 냅니다(사내 폐쇄망이라 바깥 파일을 못 씁니다).
// 흐른 시간은 셈으로 더하지 않고 시작한 시각과 지금을 빼서 구합니다.
// 탭을 잠깐 가려 두어도 시간이 밀리지 않게 하려는 것입니다.

import { useCallback, useEffect, useRef, useState } from "react";
import { Alert, Button, Chip, Field, Input, Muted, Row, Tabs, type TabItem } from "@/components/ui";

function clock(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 100)) / 10;
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = Math.floor(total % 60);
  const tenth = Math.floor((total * 10) % 10);
  const head = hours ? `${hours}:${String(minutes).padStart(2, "0")}` : String(minutes);
  return `${head}:${String(seconds).padStart(2, "0")}.${tenth}`;
}

/** 브라우저가 직접 만들어 내는 알림음. */
function beep() {
  try {
    const Ctor =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext?: typeof AudioContext })
        .webkitAudioContext;
    if (!Ctor) return;
    const ctx = new Ctor();
    [0, 0.25, 0.5].forEach((delay) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.frequency.value = 880;
      gain.gain.setValueAtTime(0.0001, ctx.currentTime + delay);
      gain.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + delay + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + delay + 0.18);
      osc.connect(gain).connect(ctx.destination);
      osc.start(ctx.currentTime + delay);
      osc.stop(ctx.currentTime + delay + 0.2);
    });
    window.setTimeout(() => ctx.close(), 1200);
  } catch {
    /* 소리를 못 내도 화면 알림은 그대로 뜹니다 */
  }
}

const MODES: TabItem<"timer" | "stopwatch">[] = [
  { key: "timer", label: "타이머" },
  { key: "stopwatch", label: "스톱워치" },
];

const PRESETS = [1, 3, 5, 10, 15, 25, 30, 60];

export default function TimerTool() {
  const [mode, setMode] = useState<"timer" | "stopwatch">("timer");

  // ── 타이머 ─────────────────────────────────────────────────────
  const [minutes, setMinutes] = useState("5");
  const [endAt, setEndAt] = useState<number | null>(null);
  const [left, setLeft] = useState(0);
  const [rang, setRang] = useState(false);

  // ── 스톱워치 ───────────────────────────────────────────────────
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [laps, setLaps] = useState<number[]>([]);
  const elapsedRef = useRef(0);
  elapsedRef.current = elapsed;

  useEffect(() => {
    const tick = window.setInterval(() => {
      if (endAt !== null) setLeft(endAt - Date.now());
      if (startedAt !== null) setElapsed(Date.now() - startedAt);
    }, 100);
    return () => window.clearInterval(tick);
  }, [endAt, startedAt]);

  useEffect(() => {
    if (endAt !== null && left <= 0 && !rang) {
      setRang(true);
      setEndAt(null);
      beep();
    }
  }, [endAt, left, rang]);

  const startTimer = useCallback(
    (mins: number) => {
      if (!(mins > 0)) return;
      setRang(false);
      setLeft(mins * 60000);
      setEndAt(Date.now() + mins * 60000);
    },
    []
  );

  return (
    <div className="tool-timer">
      <Tabs items={MODES} value={mode} onChange={setMode} />

      {mode === "timer" ? (
        <>
          <div className="tool-timer__face">{clock(Math.max(0, left))}</div>
          {rang && <Alert tone="warn">시간이 다 됐습니다.</Alert>}

          <Row>
            {PRESETS.map((value) => (
              <Chip key={value} onClick={() => { setMinutes(String(value)); startTimer(value); }}>
                {value}분
              </Chip>
            ))}
          </Row>

          <Row nowrap>
            <Field label="분">
              <Input
                type="number"
                min={0}
                value={minutes}
                onChange={(event) => setMinutes(event.target.value)}
              />
            </Field>
            {endAt === null ? (
              <Button onClick={() => startTimer(Number(minutes))}>시작</Button>
            ) : (
              <Button variant="ghost" onClick={() => setEndAt(null)}>
                멈춤
              </Button>
            )}
            <Button
              variant="ghost"
              onClick={() => {
                setEndAt(null);
                setLeft(0);
                setRang(false);
              }}
            >
              되돌리기
            </Button>
          </Row>
          <Muted>
            다른 화면으로 가 있어도 시간은 그대로 흐릅니다. 시간이 되면 소리로 알려 줍니다.
          </Muted>
        </>
      ) : (
        <>
          <div className="tool-timer__face">{clock(elapsed)}</div>
          <Row>
            {startedAt === null ? (
              <Button onClick={() => setStartedAt(Date.now() - elapsedRef.current)}>
                {elapsed ? "이어서" : "시작"}
              </Button>
            ) : (
              <Button variant="ghost" onClick={() => setStartedAt(null)}>
                멈춤
              </Button>
            )}
            <Button
              variant="ghost"
              disabled={startedAt === null}
              onClick={() => setLaps((prev) => [elapsed, ...prev])}
            >
              구간 기록
            </Button>
            <Button
              variant="ghost"
              onClick={() => {
                setStartedAt(null);
                setElapsed(0);
                setLaps([]);
              }}
            >
              ０으로
            </Button>
          </Row>
          {laps.length > 0 && (
            <div className="ui-rows">
              {laps.map((lap, index) => (
                <Row key={`${lap}-${index}`} between>
                  <span>{laps.length - index}번째</span>
                  <strong>{clock(lap)}</strong>
                  <Muted>
                    구간 {clock(lap - (laps[index + 1] ?? 0))}
                  </Muted>
                </Row>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
