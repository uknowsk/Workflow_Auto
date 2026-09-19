"use client";

// 도구 목록. 여기에 한 줄 더하면 왼쪽 인덱스와 /도구 화면에 같이 나옵니다.

import type { ComponentType } from "react";
import Calculator from "./calculator";
import DateCalc from "./date-calc";
import DrawTool from "./draw";
import NotesTool from "./notes";
import TextTools from "./text-tools";
import TimerTool from "./timer";
import UnitConverter from "./unit-converter";
import WorldClock from "./world-clock";

export type ToolDef = {
  key: string;
  /** 인덱스에 보이는 짧은 이름. 두 글자가 가장 보기 좋습니다. */
  short: string;
  name: string;
  icon: string;
  hint: string;
  /** 넓게 펼쳐야 쓸 만한 도구(그리기)는 처음부터 넓게 엽니다. */
  wide?: boolean;
  Component: ComponentType;
};

export const TOOLS: ToolDef[] = [
  {
    key: "draw",
    short: "그리기",
    name: "그리기",
    icon: "🖌",
    hint: "화면에 그림을 그려 설명하고 PNG 로 저장합니다.",
    wide: true,
    Component: DrawTool,
  },
  {
    key: "calc",
    short: "계산기",
    name: "계산기",
    icon: "🧮",
    hint: "괄호와 거듭제곱까지 되는 계산기입니다.",
    Component: Calculator,
  },
  {
    key: "unit",
    short: "단위",
    name: "단위 변환",
    icon: "📏",
    hint: "길이·무게·넓이·부피·시간·데이터·온도를 바꿉니다.",
    Component: UnitConverter,
  },
  {
    key: "clock",
    short: "시계",
    name: "세계 시계",
    icon: "🕒",
    hint: "해외 지사 시각과 회의 시간을 맞춥니다.",
    Component: WorldClock,
  },
  {
    key: "date",
    short: "날짜",
    name: "날짜 계산",
    icon: "📅",
    hint: "D-day, 두 날짜 사이, 영업일 더하기.",
    Component: DateCalc,
  },
  {
    key: "timer",
    short: "타이머",
    name: "타이머",
    icon: "⏱",
    hint: "타이머와 스톱워치. 시간이 되면 소리로 알려 줍니다.",
    Component: TimerTool,
  },
  {
    key: "note",
    short: "메모",
    name: "메모",
    icon: "📝",
    hint: "계정에 저장되는 간단 메모. 멈추면 알아서 저장됩니다.",
    Component: NotesTool,
  },
  {
    key: "text",
    short: "텍스트",
    name: "텍스트 정리",
    icon: "🔤",
    hint: "글자 수·바이트 수 세기, 공백 정리, JSON 보기.",
    Component: TextTools,
  },
];

export function findTool(key: string | null): ToolDef | undefined {
  return TOOLS.find((tool) => tool.key === key);
}
