"use client";

// 예약. "시간이 되면 알아서 해라" 를 등록하는 화면입니다.
import { useEffect, useState } from "react";
import { api, Recipe, Schedule, getSession } from "@/lib/api";

const WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"];

// 화면에서 고른 "언제"를 서버가 아는 값으로 바꿔 줍니다.
const LEAD_CHOICES = [
  { label: "정확히 그 시각에", minutes: 0 },
  { label: "1시간 전에", minutes: 60 },
  { label: "하루 전에", minutes: 1440 },
  { label: "3일 전에", minutes: 4320 },
];

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
      <h3>예약</h3>
      <p className="muted">
        회신기한 리마인드, 수명업무 기한 알림, 매주 월요일 주간보고 초안처럼 시간이 되면
        스스로 움직이는 일을 등록합니다.
      </p>

      {error && <div className="box" style={{ color: "#b91c1c" }}>{error}</div>}

      <div className="box">
        <b>새 예약</b>

        <label>이름</label>
        <input
          value={title}
          placeholder="예) 회신기한 하루 전 리마인드"
          onChange={(e) => setTitle(e.target.value)}
        />

        <label>언제</label>
        <div className="row">
          <select
            style={{ width: 160 }}
            value={trigger}
            onChange={(e) => setTrigger(e.target.value as Schedule["trigger"])}
          >
            <option value="daily">매일 정해진 시각</option>
            <option value="once">특정 시각에 한 번</option>
            <option value="interval">일정 간격마다</option>
          </select>

          {trigger === "daily" && (
            <input
              style={{ width: 120 }}
              type="time"
              value={atTime}
              onChange={(e) => setAtTime(e.target.value)}
            />
          )}
          {trigger === "once" && (
            <>
              <input
                style={{ width: 220 }}
                type="datetime-local"
                value={runAt}
                onChange={(e) => setRunAt(e.target.value)}
              />
              <select
                style={{ width: 180 }}
                value={lead}
                onChange={(e) => setLead(Number(e.target.value))}
              >
                {LEAD_CHOICES.map((choice) => (
                  <option key={choice.minutes} value={choice.minutes}>
                    {choice.label}
                  </option>
                ))}
              </select>
            </>
          )}
          {trigger === "interval" && (
            <>
              <input
                style={{ width: 90 }}
                type="number"
                min={5}
                value={intervalMinutes}
                onChange={(e) => setIntervalMinutes(Number(e.target.value))}
              />
              <span className="muted">분마다</span>
            </>
          )}
        </div>

        {trigger === "daily" && (
          <div className="row" style={{ marginTop: 8 }}>
            <span className="muted">요일(비워 두면 매일)</span>
            {WEEKDAYS.map((label, day) => (
              <button
                key={day}
                className={weekdays.includes(day) ? "" : "ghost"}
                onClick={() => toggleWeekday(day)}
              >
                {label}
              </button>
            ))}
          </div>
        )}

        <label>무엇을</label>
        <div className="row">
          <select
            style={{ width: 200 }}
            value={action}
            onChange={(e) => setAction(e.target.value as Schedule["action"])}
          >
            <option value="request">자연어로 요청하기</option>
            <option value="recipe">저장된 레시피 실행</option>
          </select>
          {action === "recipe" && (
            <select
              style={{ width: 260 }}
              value={recipeId}
              onChange={(e) => setRecipeId(e.target.value)}
            >
              <option value="">레시피를 고르세요</option>
              {recipes.map((recipe) => (
                <option key={recipe.id} value={recipe.id}>
                  {recipe.title}
                </option>
              ))}
            </select>
          )}
        </div>

        {action === "request" && (
          <textarea
            rows={3}
            style={{ marginTop: 8 }}
            value={requestText}
            placeholder="예) 회신기한이 지난 사람에게 리마인드 메일을 보내줘"
            onChange={(e) => setRequestText(e.target.value)}
          />
        )}

        <div className="row" style={{ marginTop: 10 }}>
          <input
            type="checkbox"
            style={{ width: 16 }}
            checked={preApproved}
            onChange={(e) => setPreApproved(e.target.checked)}
          />
          <span className="muted">
            메일 발송처럼 되돌릴 수 없는 작업도 확인 없이 자동 실행합니다. (예약이 도는
            순간에는 물어볼 사람이 없어, 그런 작업이 끼어 있으면 여기에 체크해야 저장됩니다)
          </span>
        </div>

        <div style={{ marginTop: 10 }}>
          <button onClick={create} disabled={!title.trim()}>
            예약 만들기
          </button>
        </div>
      </div>

      <div className="row" style={{ justifyContent: "space-between" }}>
        <h3>내 예약</h3>
        <label className="row" style={{ margin: 0 }}>
          <input
            type="checkbox"
            style={{ width: 16 }}
            checked={showDone}
            onChange={(e) => setShowDone(e.target.checked)}
          />
          <span className="muted">꺼진 예약도 보기</span>
        </label>
      </div>

      {rows.length === 0 && <div className="box muted">등록된 예약이 없습니다.</div>}

      {rows.map((row) => (
        <div className="box" key={row.id}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <b>
              {row.enabled ? "⏰" : "⏸️"} {row.title}
            </b>
            <span className="tag">{row.when_text}</span>
          </div>
          <div className="muted">
            다음 실행 {when(row.next_run_at)} · 지금까지 {row.run_count}번
            {row.last_status && ` · 최근 ${row.last_status}`}
          </div>
          {row.last_error && (
            <div className="muted" style={{ color: "#b91c1c" }}>
              {row.last_error}
            </div>
          )}
          <div className="row" style={{ marginTop: 8 }}>
            <button className="ghost" onClick={() => api.runScheduleNow(row.id).then(reload)}>
              지금 한 번 돌려보기
            </button>
            {row.enabled ? (
              <button className="ghost" onClick={() => api.cancelSchedule(row.id).then(reload)}>
                끄기
              </button>
            ) : (
              <button
                className="ghost"
                onClick={() =>
                  api
                    .resumeSchedule(row.id)
                    .then(reload)
                    .catch((e) => setError(e instanceof Error ? e.message : String(e)))
                }
              >
                다시 켜기
              </button>
            )}
            <button
              className="ghost"
              onClick={() => {
                if (confirm(`'${row.title}' 예약을 지울까요?`))
                  api.deleteSchedule(row.id).then(reload);
              }}
            >
              삭제
            </button>
          </div>
        </div>
      ))}
    </>
  );
}
