"use client";

// 단위 변환.
//
// 환산표는 백엔드 "도구 모음" 앱(official_apps/toolbox/server.py)과 같은 값을
// 씁니다. 화면에서 바로 계산하므로 서버를 부르지 않습니다.
// 값은 "기준 단위 몇 개인가"로 적어 두고 나눗셈 한 번으로 바꿉니다.

import { useState } from "react";
import { Field, Input, Muted, Row, Select } from "@/components/ui";

const UNITS: Record<string, Record<string, number>> = {
  길이: {
    mm: 0.001, cm: 0.01, m: 1, km: 1000,
    inch: 0.0254, ft: 0.3048, yard: 0.9144, mile: 1609.344, 자: 0.303,
  },
  무게: {
    mg: 0.000001, g: 0.001, kg: 1, t: 1000,
    oz: 0.0283495, lb: 0.453592, 근: 0.6, 돈: 0.00375,
  },
  넓이: { m2: 1, cm2: 0.0001, km2: 1000000, 평: 3.305785, ha: 10000, 에이커: 4046.86 },
  부피: { ml: 0.001, l: 1, m3: 1000, 컵: 0.2, 말: 18, 갤런: 3.78541 },
  시간: { 초: 1, 분: 60, 시간: 3600, 일: 86400, 주: 604800 },
  데이터: { B: 1, KB: 1024, MB: 1048576, GB: 1073741824, TB: 1099511627776 },
  온도: { "섭씨 °C": 0, "화씨 °F": 0, 켈빈K: 0 },
};

function toCelsius(value: number, unit: string): number {
  if (unit.includes("화씨")) return ((value - 32) * 5) / 9;
  if (unit.includes("켈빈")) return value - 273.15;
  return value;
}

function fromCelsius(value: number, unit: string): number {
  if (unit.includes("화씨")) return (value * 9) / 5 + 32;
  if (unit.includes("켈빈")) return value + 273.15;
  return value;
}

function convert(value: number, category: string, from: string, to: string): number {
  if (category === "온도") return fromCelsius(toCelsius(value, from), to);
  const table = UNITS[category];
  return (value * table[from]) / table[to];
}

function pretty(value: number): string {
  if (!Number.isFinite(value)) return "-";
  const rounded = Math.round(value * 1e6) / 1e6;
  return rounded.toLocaleString("ko-KR", { maximumFractionDigits: 6 });
}

// 자주 쓰는 조합을 한 번에 불러올 수 있게 해 둡니다.
const PRESETS = [
  { label: "인치 → cm", category: "길이", from: "inch", to: "cm", value: "3.5" },
  { label: "평 → m²", category: "넓이", from: "평", to: "m2", value: "25" },
  { label: "lb → kg", category: "무게", from: "lb", to: "kg", value: "150" },
  { label: "℉ → ℃", category: "온도", from: "화씨 °F", to: "섭씨 °C", value: "72" },
  { label: "GB → MB", category: "데이터", from: "GB", to: "MB", value: "1" },
];

export default function UnitConverter() {
  const [category, setCategory] = useState("길이");
  const [from, setFrom] = useState("inch");
  const [to, setTo] = useState("cm");
  const [value, setValue] = useState("1");

  const units = Object.keys(UNITS[category]);
  const number = Number(value.replace(/,/g, ""));
  const ok = value.trim() !== "" && !Number.isNaN(number);
  const result = ok ? convert(number, category, from, to) : NaN;

  const pickCategory = (next: string) => {
    const list = Object.keys(UNITS[next]);
    setCategory(next);
    setFrom(list[0]);
    setTo(list[1] ?? list[0]);
  };

  return (
    <div className="tool-unit">
      <Row className="tool-unit__presets">
        {PRESETS.map((preset) => (
          <button
            key={preset.label}
            type="button"
            className="ui-chip"
            onClick={() => {
              setCategory(preset.category);
              setFrom(preset.from);
              setTo(preset.to);
              setValue(preset.value);
            }}
          >
            {preset.label}
          </button>
        ))}
      </Row>

      <Field label="종류">
        <Select value={category} onChange={(event) => pickCategory(event.target.value)}>
          {Object.keys(UNITS).map((name) => (
            <option key={name}>{name}</option>
          ))}
        </Select>
      </Field>

      <div className="tool-unit__pair">
        <Field label="바꿀 값">
          <Input
            value={value}
            inputMode="decimal"
            onChange={(event) => setValue(event.target.value)}
          />
        </Field>
        <Field label="지금 단위">
          <Select value={from} onChange={(event) => setFrom(event.target.value)}>
            {units.map((unit) => (
              <option key={unit}>{unit}</option>
            ))}
          </Select>
        </Field>
        <button
          type="button"
          className="tool-unit__swap"
          title="위아래 바꾸기"
          onClick={() => {
            setFrom(to);
            setTo(from);
          }}
        >
          ⇅
        </button>
        <Field label="바꿀 단위">
          <Select value={to} onChange={(event) => setTo(event.target.value)}>
            {units.map((unit) => (
              <option key={unit}>{unit}</option>
            ))}
          </Select>
        </Field>
      </div>

      <div className="tool-unit__result">
        {ok ? (
          <>
            <span>
              {number.toLocaleString("ko-KR")} {from}
            </span>
            <strong>
              = {pretty(result)} {to}
            </strong>
          </>
        ) : (
          <span>숫자를 적어 주세요.</span>
        )}
      </div>

      <Muted>
        길이·무게·넓이·부피·시간·데이터·온도를 다룹니다. 평, 근, 돈, 자처럼 우리가 쓰는
        단위도 들어 있습니다.
      </Muted>
    </div>
  );
}
