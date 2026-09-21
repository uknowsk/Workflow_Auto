"use client";

// 세계 시계 + 회의 시간 맞추기.
//
// 브라우저가 들고 있는 시간대 정보(Intl)를 씁니다. 바깥에서 받아오는 것이 없습니다.
// 도시 목록은 백엔드 "도구 모음" 앱과 같은 곳을 씁니다. (city-zones.ts 참고)

import { useEffect, useMemo, useRef, useState } from "react";
import { Badge, Button, Field, Input, Muted, Row } from "@/components/ui";
import { CITY_ZONES, City, searchCities } from "./city-zones";

const DEFAULT_CITIES = ["서울", "프랑크푸르트", "오스틴", "샌프란시스코"];
const STORE_KEY = "wfa_tool_clock_cities";
const SUGGEST_LIMIT = 8;

/** 그 도시의 '지금'(또는 주어진 시각)을 부분별로 읽습니다. */
function partsIn(zone: string, at: Date) {
  const formatter = new Intl.DateTimeFormat("ko-KR", {
    timeZone: zone,
    hour12: false,
    weekday: "short",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
  const map: Record<string, string> = {};
  formatter.formatToParts(at).forEach((part) => {
    map[part.type] = part.value;
  });
  const hour = Number(map.hour === "24" ? "0" : map.hour);
  const weekday = map.weekday || "";
  return {
    label: `${map.month}/${map.day} (${weekday}) ${String(hour).padStart(2, "0")}:${map.minute}`,
    hour,
    weekend: weekday.includes("토") || weekday.includes("일"),
  };
}

/** 서울 기준 시차(시간). 같은 순간을 두 시간대에서 읽어 차이를 봅니다. */
function offsetFromSeoul(zone: string, at: Date): number {
  const read = (tz: string) =>
    new Date(at.toLocaleString("en-US", { timeZone: tz })).getTime();
  return Math.round(((read(zone) - read("Asia/Seoul")) / 3600000) * 10) / 10;
}

/** "서울 +8시간" 처럼 읽기 쉽게. */
function gapLabel(offset: number): string {
  if (offset === 0) return "서울과 같음";
  return `서울 ${offset > 0 ? "+" : ""}${offset}시간`;
}

/** Asia/Seoul 같은 표준 이름을 직접 쳤을 때도 받아 줍니다. */
function asRawZone(text: string): City | null {
  const zone = text.trim();
  if (!zone.includes("/")) return null;
  try {
    new Intl.DateTimeFormat("ko-KR", { timeZone: zone }).format(new Date());
  } catch {
    return null;
  }
  return { name: zone, en: zone, country: "표준 시간대", zone };
}

export default function WorldClock() {
  const [now, setNow] = useState(() => new Date());
  const [cities, setCities] = useState<string[]>(DEFAULT_CITIES);
  // 도시 고르기: 친 글자와 맞는 후보를 아래에 펼쳐 보여 줍니다.
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(0);
  // 회의 시간 맞추기: 서울 기준 시각을 넣으면 다른 도시가 몇 시인지 봅니다.
  const [meetingAt, setMeetingAt] = useState("");
  const pickerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORE_KEY);
      if (saved) setCities(JSON.parse(saved));
    } catch {
      /* 저장된 값이 깨져 있으면 기본 도시로 갑니다 */
    }
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  // 후보 목록 밖을 누르면 닫습니다.
  useEffect(() => {
    if (!open) return;
    const close = (event: MouseEvent) => {
      if (!pickerRef.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);

  const save = (next: string[]) => {
    setCities(next);
    try {
      window.localStorage.setItem(STORE_KEY, JSON.stringify(next));
    } catch {
      /* 브라우저가 저장을 막아도 이번 화면에서는 그대로 씁니다 */
    }
  };

  const at = useMemo(() => {
    if (!meetingAt) return now;
    // 입력값은 "서울 시각"입니다. 서울과 내 컴퓨터의 시차만큼 되돌려 놓습니다.
    const naive = new Date(meetingAt);
    if (Number.isNaN(naive.getTime())) return now;
    const shift = offsetFromSeoul(
      Intl.DateTimeFormat().resolvedOptions().timeZone,
      naive
    );
    return new Date(naive.getTime() - shift * 3600000);
  }, [meetingAt, now]);

  const rows = cities.map((city) => {
    const zone = CITY_ZONES[city] || city;
    let info;
    try {
      info = partsIn(zone, at);
    } catch {
      info = { label: "모르는 도시", hour: -1, weekend: false };
    }
    return {
      city,
      ...info,
      offset: offsetFromSeoul(zone, at),
      business: info.hour >= 9 && info.hour < 18 && !info.weekend,
    };
  });

  // 후보는 목록에 없는 도시만. 못 찾으면 표준 시간대 이름으로도 받아 봅니다.
  const matches = useMemo(() => {
    const found = searchCities(query, cities).slice(0, SUGGEST_LIMIT);
    if (found.length) return found;
    const raw = asRawZone(query);
    return raw && !cities.includes(raw.name) ? [raw] : [];
  }, [query, cities]);

  const add = (city: City) => {
    if (!cities.includes(city.name)) save([...cities, city.name]);
    setQuery("");
    setCursor(0);
    setOpen(false);
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Escape") {
      setOpen(false);
      return;
    }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      setOpen(true);
      if (!matches.length) return;
      const step = event.key === "ArrowDown" ? 1 : matches.length - 1;
      setCursor((at_) => (at_ + step) % matches.length);
      return;
    }
    if (event.key === "Enter" && open && matches[cursor]) {
      event.preventDefault();
      add(matches[cursor]);
    }
  };

  return (
    <div className="tool-clock">
      <Field label="회의 시간 맞추기" hint="서울 기준 시각을 넣으면 각 도시가 몇 시인지 봅니다">
        <Row nowrap>
          <Input
            type="datetime-local"
            value={meetingAt}
            onChange={(event) => setMeetingAt(event.target.value)}
          />
          {meetingAt && (
            <Button variant="ghost" small onClick={() => setMeetingAt("")}>
              지금으로
            </Button>
          )}
        </Row>
      </Field>

      <div className="ui-rows">
        {rows.map((row) => (
          <div key={row.city} className="tool-clock__row">
            <span className="tool-clock__city">{row.city}</span>
            <span className="tool-clock__time">{row.label}</span>
            <Badge tone={row.business ? "ok" : row.weekend ? "neutral" : "warn"}>
              {row.business ? "근무 중" : row.weekend ? "주말" : "근무 시간 아님"}
            </Badge>
            <Muted>{gapLabel(row.offset)}</Muted>
            <Button
              variant="ghost"
              small
              onClick={() => save(cities.filter((city) => city !== row.city))}
            >
              빼기
            </Button>
          </div>
        ))}
      </div>

      <div className="tool-clock__pick" ref={pickerRef}>
        <Input
          value={query}
          placeholder="도시 고르기 (도시·나라·영문 이름을 쳐 보세요)"
          role="combobox"
          aria-expanded={open && matches.length > 0}
          aria-controls="tool-clock-suggest"
          aria-autocomplete="list"
          aria-activedescendant={
            open && matches[cursor] ? `tool-clock-city-${cursor}` : undefined
          }
          onFocus={() => setOpen(true)}
          onChange={(event) => {
            setQuery(event.target.value);
            setCursor(0);
            setOpen(true);
          }}
          onKeyDown={onKeyDown}
        />

        {open && matches.length > 0 && (
          <ul className="tool-clock__suggest" id="tool-clock-suggest" role="listbox">
            {matches.map((city, index) => (
              <li
                key={city.name}
                id={`tool-clock-city-${index}`}
                role="option"
                aria-selected={index === cursor}
                className={
                  index === cursor
                    ? "tool-clock__option tool-clock__option--on"
                    : "tool-clock__option"
                }
                onMouseEnter={() => setCursor(index)}
                onMouseDown={(event) => {
                  event.preventDefault();
                  add(city);
                }}
              >
                <span className="tool-clock__option-name">{city.name}</span>
                <span className="tool-clock__option-sub">
                  {city.en} · {city.country}
                </span>
                <span className="tool-clock__option-gap">
                  {gapLabel(offsetFromSeoul(city.zone, now))}
                </span>
              </li>
            ))}
          </ul>
        )}

        {open && query.trim() && matches.length === 0 && (
          <div className="tool-clock__suggest tool-clock__suggest--empty">
            <Muted>맞는 도시가 없습니다. Asia/Seoul 같은 표준 이름도 됩니다.</Muted>
          </div>
        )}
      </div>

      <Muted>고른 도시는 이 브라우저에 기억해 둡니다.</Muted>
    </div>
  );
}
