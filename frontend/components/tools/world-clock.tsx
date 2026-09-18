"use client";

// 세계 시계 + 회의 시간 맞추기.
//
// 브라우저가 들고 있는 시간대 정보(Intl)를 씁니다. 바깥에서 받아오는 것이 없습니다.
// 도시 목록은 백엔드 "도구 모음" 앱과 같은 곳을 씁니다.

import { useEffect, useMemo, useState } from "react";
import { Badge, Button, Field, Input, Muted, Row, Select } from "@/components/ui";

const CITY_ZONES: Record<string, string> = {
  서울: "Asia/Seoul",
  수원: "Asia/Seoul",
  도쿄: "Asia/Tokyo",
  베이징: "Asia/Shanghai",
  상하이: "Asia/Shanghai",
  시안: "Asia/Shanghai",
  호치민: "Asia/Ho_Chi_Minh",
  하노이: "Asia/Ho_Chi_Minh",
  델리: "Asia/Kolkata",
  벵갈루루: "Asia/Kolkata",
  두바이: "Asia/Dubai",
  런던: "Europe/London",
  파리: "Europe/Paris",
  프랑크푸르트: "Europe/Berlin",
  바르샤바: "Europe/Warsaw",
  모스크바: "Europe/Moscow",
  뉴욕: "America/New_York",
  오스틴: "America/Chicago",
  산호세: "America/Los_Angeles",
  샌프란시스코: "America/Los_Angeles",
  상파울루: "America/Sao_Paulo",
  시드니: "Australia/Sydney",
};

const DEFAULT_CITIES = ["서울", "프랑크푸르트", "오스틴", "샌프란시스코"];
const STORE_KEY = "wfa_tool_clock_cities";

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

export default function WorldClock() {
  const [now, setNow] = useState(() => new Date());
  const [cities, setCities] = useState<string[]>(DEFAULT_CITIES);
  const [adding, setAdding] = useState("");
  // 회의 시간 맞추기: 서울 기준 시각을 넣으면 다른 도시가 몇 시인지 봅니다.
  const [meetingAt, setMeetingAt] = useState("");

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

  const unused = Object.keys(CITY_ZONES).filter((city) => !cities.includes(city));

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
            <Muted>
              {row.offset === 0
                ? "서울과 같음"
                : `서울 ${row.offset > 0 ? "+" : ""}${row.offset}시간`}
            </Muted>
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

      <Row nowrap>
        <Select value={adding} onChange={(event) => setAdding(event.target.value)}>
          <option value="">도시 고르기</option>
          {unused.map((city) => (
            <option key={city}>{city}</option>
          ))}
        </Select>
        <Button
          small
          disabled={!adding}
          onClick={() => {
            if (adding) save([...cities, adding]);
            setAdding("");
          }}
        >
          추가
        </Button>
      </Row>

      <Muted>고른 도시는 이 브라우저에 기억해 둡니다.</Muted>
    </div>
  );
}
