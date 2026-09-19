"use client";

// 예약. "시간이 되면 알아서 해라" 를 등록하는 화면입니다.
import { useEffect, useState } from "react";
import { api, Recipe, Schedule, getSession } from "@/lib/api";
import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Chip,
  Empty,
  Field,
  Input,
  Muted,
  PageTitle,
  Row,
  Section,
  SectionHead,
  Select,
  Tag,
  Textarea,
  When,
} from "@/components/ui";

const WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"];

// 화면에서 고른 "언제"를 서버가 아는 값으로 바꿔 줍니다.
const LEAD_CHOICES = [
  { label: "정확히 그 시각에", minutes: 0 },
  { label: "1시간 전에", minutes: 60 },
  { label: "하루 전에", minutes: 1440 },
  { label: "3일 전에", minutes: 4320 },
];

// 서버가 주는 영문 상태를 사람 말로 바꿔 줍니다.
const LAST_STATUS: Record<string, string> = {
  succeeded: "성공",
  failed: "실패",
  running: "처리 중",
  queued: "대기 중",
  rejected: "취소됨",
  awaiting_approval: "확인 필요",
};

function when(iso: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("ko-KR", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function Schedules() {
  const [rows, setRows] = useState<Schedule[]>([]);
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [showDone, setShowDone] = useState(false);
  const [error, setError] = useState("");

  // 새 예약 입력값
  const [title, setTitle] = useState("");
  const [trigger, setTrigger] = useState<Schedule["trigger"]>("daily");
  const [atTime, setAtTime] = useState("09:00");
  const [weekdays, setWeekdays] = useState<number[]>([]);
  const [runAt, setRunAt] = useState("");
  const [lead, setLead] = useState(0);
  const [intervalMinutes, setIntervalMinutes] = useState(60);
  const [action, setAction] = useState<Schedule["action"]>("request");
  const [requestText, setRequestText] = useState("");
  const [recipeId, setRecipeId] = useState("");
  const [preApproved, setPreApproved] = useState(false);

  const reload = () =>
    api.listSchedules(showDone).then(setRows).catch(() => undefined);

  useEffect(() => {
    if (!getSession()) {
      location.href = "/login";
      return;
    }
    api.listRecipes().then(setRecipes).catch(() => undefined);
  }, []);

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showDone]);

  const create = async () => {
    setError("");
    try {
      await api.createSchedule({
        title,
        trigger,
        at_time: trigger === "daily" ? atTime : "",
        weekdays: trigger === "daily" ? weekdays : [],
        // datetime-local 값은 브라우저 시간대 기준이라 ISO 로 바꿔 보냅니다.
        run_at: trigger === "once" && runAt ? new Date(runAt).toISOString() : null,
        lead_minutes: trigger === "once" ? lead : 0,
        interval_minutes: trigger === "interval" ? intervalMinutes : 0,
        action,
        request_text: action === "request" ? requestText : "",
        recipe_id: action === "recipe" ? recipeId || null : null,
        pre_approved: preApproved,
      });
      setTitle("");
      setRequestText("");
      setPreApproved(false);
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const toggleWeekday = (day: number) =>
    setWeekdays(
      weekdays.includes(day) ? weekdays.filter((d) => d !== day) : [...weekdays, day]
    );

  return (
    <>
      <PageTitle
        title="예약"
        sub="회신기한 리마인드, 수명업무 기한 알림, 매주 월요일 주간보고 초안처럼 시간이 되면 스스로 움직이는 일을 등록합니다."
      />

      {error && (
        <Alert tone="crit" style={{ marginBottom: "var(--space-4)" }}>
          {error}
        </Alert>
      )}

      <Card quiet className="ui-card--pad-lg">
        <Field label="이름" htmlFor="sch-title">
          <Input
            id="sch-title"
            value={title}
            placeholder="예) 회신기한 하루 전 리마인드"
            onChange={(e) => setTitle(e.target.value)}
          />
        </Field>

        <Field label="언제">
          <Row>
            <Select
              style={{ width: 170 }}
              value={trigger}
              aria-label="예약 방식"
              onChange={(e) => setTrigger(e.target.value as Schedule["trigger"])}
            >
              <option value="daily">매일 정해진 시각</option>
              <option value="once">특정 시각에 한 번</option>
              <option value="interval">일정 간격마다</option>
            </Select>

            {trigger === "daily" && (
              <Input
                style={{ width: 130 }}
                type="time"
                aria-label="시각"
                value={atTime}
                onChange={(e) => setAtTime(e.target.value)}
              />
            )}
            {trigger === "once" && (
              <>
                <Input
                  style={{ width: 230 }}
                  type="datetime-local"
                  aria-label="날짜와 시각"
                  value={runAt}
                  onChange={(e) => setRunAt(e.target.value)}
                />
                <Select
                  style={{ width: 180 }}
                  value={lead}
                  aria-label="얼마나 미리"
                  onChange={(e) => setLead(Number(e.target.value))}
                >
                  {LEAD_CHOICES.map((choice) => (
                    <option key={choice.minutes} value={choice.minutes}>
                      {choice.label}
                    </option>
                  ))}
                </Select>
              </>
            )}
            {trigger === "interval" && (
              <>
                <Input
                  style={{ width: 100 }}
                  type="number"
                  min={5}
                  aria-label="간격(분)"
                  value={intervalMinutes}
                  onChange={(e) => setIntervalMinutes(Number(e.target.value))}
                />
                <Muted>분마다</Muted>
              </>
            )}
          </Row>
        </Field>

        {trigger === "daily" && (
          <Field label="요일" hint="비워 두면 매일">
            <Row>
              {WEEKDAYS.map((label, day) => (
                <Chip
                  key={day}
                  active={weekdays.includes(day)}
                  onClick={() => toggleWeekday(day)}
                >
                  {label}
                </Chip>
              ))}
            </Row>
          </Field>
        )}

        <Field label="무엇을">
          <Row>
            <Select
              style={{ width: 210 }}
              value={action}
              aria-label="할 일 종류"
              onChange={(e) => setAction(e.target.value as Schedule["action"])}
            >
              <option value="request">자연어로 요청하기</option>
              <option value="recipe">저장된 레시피 실행</option>
            </Select>
            {action === "recipe" && (
              <Select
                style={{ width: 270 }}
                value={recipeId}
                aria-label="레시피"
                onChange={(e) => setRecipeId(e.target.value)}
              >
                <option value="">레시피를 고르세요</option>
                {recipes.map((recipe) => (
                  <option key={recipe.id} value={recipe.id}>
                    {recipe.title}
                  </option>
                ))}
              </Select>
            )}
          </Row>
        </Field>

        {action === "request" && (
          <Textarea
            rows={3}
            style={{ marginBottom: "var(--space-3)" }}
            value={requestText}
            aria-label="요청문"
            placeholder="예) 회신기한이 지난 사람에게 리마인드 메일을 보내줘"
            onChange={(e) => setRequestText(e.target.value)}
          />
        )}

        <Checkbox
          checked={preApproved}
          onChange={(e) => setPreApproved(e.target.checked)}
          label="메일 발송처럼 되돌릴 수 없는 작업도 확인 없이 자동 실행합니다. (예약이 도는 순간에는 물어볼 사람이 없어, 그런 작업이 끼어 있으면 여기에 체크해야 저장됩니다)"
        />

        <Button onClick={create} disabled={!title.trim()}>
          예약 만들기
        </Button>
      </Card>

      <Section>
        <SectionHead
          label="내 예약"
          action={
            <Chip active={showDone} onClick={() => setShowDone(!showDone)}>
              꺼진 예약도 보기
            </Chip>
          }
        />

        {rows.length === 0 ? (
          <Empty>등록된 예약이 없습니다. 위에서 하나 만들어 보세요.</Empty>
        ) : (
          rows.map((row) => (
            <Card key={row.id} style={{ marginBottom: "var(--space-3)" }}>
              <Row between nowrap>
                <b>
                  {row.enabled ? "⏰" : "⏸️"} {row.title}
                </b>
                <Badge tone={row.enabled ? "accent" : "neutral"}>{row.when_text}</Badge>
              </Row>
              <Row style={{ marginTop: "var(--space-2)" }}>
                <Tag>
                  다음 실행 <When>{when(row.next_run_at)}</When>
                </Tag>
                <Tag>지금까지 {row.run_count}번</Tag>
                {row.last_status && (
                  <Badge tone={row.last_status === "failed" ? "crit" : "neutral"}>
                    최근 {LAST_STATUS[row.last_status] || row.last_status}
                  </Badge>
                )}
              </Row>
              {row.last_error && (
                <Alert tone="crit" style={{ marginTop: "var(--space-2)" }}>
                  {row.last_error}
                </Alert>
              )}
              <Row style={{ marginTop: "var(--space-3)" }}>
                <Button
                  variant="ghost"
                  small
                  onClick={() => api.runScheduleNow(row.id).then(reload)}
                >
                  지금 한 번 돌려보기
                </Button>
                {row.enabled ? (
                  <Button
                    variant="ghost"
                    small
                    onClick={() => api.cancelSchedule(row.id).then(reload)}
                  >
                    끄기
                  </Button>
                ) : (
                  <Button
                    variant="ghost"
                    small
                    onClick={() =>
                      api
                        .resumeSchedule(row.id)
                        .then(reload)
                        .catch((e) => setError(e instanceof Error ? e.message : String(e)))
                    }
                  >
                    다시 켜기
                  </Button>
                )}
                <Button
                  variant="danger"
                  small
                  onClick={() => {
                    if (confirm(`'${row.title}' 예약을 지울까요?`))
                      api.deleteSchedule(row.id).then(reload);
                  }}
                >
                  삭제
                </Button>
              </Row>
            </Card>
          ))
        )}
      </Section>
    </>
  );
}
