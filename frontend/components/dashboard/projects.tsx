"use client";

// 대시보드의 "등록된 프로젝트" 칸.
// 한 줄에는 모델명·현재 단계·RTS(개발완료) 날짜만 두고, 누르면 그 아래로
// 시간축이 펼쳐집니다. 시간축에는 오늘이 어디쯤인지와 주요 마일스톤이 찍히고,
// 마일스톤을 누르면 그 마일스톤에서 내야 하는 산출물과 완료 여부가 보입니다.

import { useState } from "react";
import { Milestone, Project } from "@/lib/api";
import { Badge, Button, Dot, Empty, Muted, Row, type Tone } from "@/components/ui";

/** D-30 / D+3 처럼 남은 날을 짧게 적습니다. */
function dday(days: number | null): string {
  if (days === null || Number.isNaN(days)) return "";
  if (days === 0) return "D-Day";
  return days > 0 ? `D-${days}` : `D+${-days}`;
}

function ddayTone(days: number | null): Tone {
  if (days === null) return "neutral";
  if (days < 0) return "crit";
  if (days <= 14) return "warn";
  return "neutral";
}

function short(date: string): string {
  return date ? date.replaceAll("-", ".").slice(2) : "";
}

function MilestoneRow({ milestone }: { milestone: Milestone }) {
  const [open, setOpen] = useState(false);
  const items = milestone.deliverables || [];
  const label = items.length
    ? `산출물 ${milestone.done_count}/${items.length}`
    : "산출물 없음";

  return (
    <div className="ptl__ms">
      <button
        type="button"
        className="ptl__msbtn"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <Dot tone={milestone.done ? "ok" : milestone.passed ? "crit" : "neutral"} />
        <span className="ptl__msname">{milestone.name}</span>
        <span className="ptl__msdate">{short(milestone.date)}</span>
        <Badge tone={milestone.done ? "ok" : "neutral"}>{label}</Badge>
        <span className="ptl__caret" aria-hidden="true">
          {open ? "▾" : "▸"}
        </span>
      </button>
      {open && (
        <div className="ptl__items">
          {items.length === 0 ? (
            <Muted>
              이 마일스톤에 걸린 산출물이 아직 없습니다. 마일스톤 이름에 단계(설계,
              구현 같은)를 넣거나, 대괄호로 직접 적어 주면 여기에 뜹니다.
            </Muted>
          ) : (
            <ul className="ptl__list">
              {items.map((item) => (
                <li key={item.name} className={item.done ? "is-done" : ""}>
                  <span aria-hidden="true">{item.done ? "✓" : "○"}</span>
                  <span>{item.name}</span>
                  <Muted>{item.done ? "완료" : "미완료"}</Muted>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function Timeline({ project }: { project: Project }) {
  const line = project.timeline;
  return (
    <div className="ptl__body">
      <div className="ptl__axis" aria-hidden="true">
        <div className="ptl__track">
          <div className="ptl__fill" style={{ width: `${line.percent}%` }} />
          {project.milestones.map((m) => (
            <span
              key={`${m.name}-${m.date}`}
              className={`ptl__pin${m.done ? " is-done" : ""}${m.passed && !m.done ? " is-late" : ""}`}
              style={{ left: `${m.percent}%` }}
              title={`${m.name} ${short(m.date)}`}
            />
          ))}
          <span className="ptl__today" style={{ left: `${line.percent}%` }}>
            <b>오늘</b>
          </span>
        </div>
        <Row between nowrap>
          <Muted>시작 {short(line.start)}</Muted>
          <Muted>RTS {short(line.end)}</Muted>
        </Row>
      </div>

      {project.milestones.length === 0 ? (
        <Muted>
          아직 마일스톤이 없습니다. &ldquo;설계완료 2026-03-31, PP 2026-05-20&rdquo;
          처럼 적어 두면 시간축에 찍힙니다.
        </Muted>
      ) : (
        <div className="ptl__mslist">
          {project.milestones.map((m) => (
            <MilestoneRow key={`${m.name}-${m.date}`} milestone={m} />
          ))}
        </div>
      )}
    </div>
  );
}

export function ProjectList({
  projects,
  onAdd,
}: {
  projects: Project[];
  onAdd?: () => void;
}) {
  const [openId, setOpenId] = useState("");

  if (projects.length === 0) {
    return (
      <Empty>
        등록된 프로젝트가 없습니다. {onAdd ? "오른쪽 위 " : ""}
        &ldquo;프로젝트 추가&rdquo;를 누르거나, 위 입력창에 &ldquo;SM-X100 프로젝트
        등록해줘&rdquo;라고 적어 보세요.
      </Empty>
    );
  }

  return (
    <div className="ptl">
      {projects.map((project) => {
        const open = openId === project.id;
        return (
          <div key={project.id} className={`ptl__row${open ? " is-open" : ""}`}>
            <button
              type="button"
              className="ptl__head"
              aria-expanded={open}
              onClick={() => setOpenId(open ? "" : project.id)}
            >
              <span className="ptl__model">{project.model || project.name}</span>
              {project.model && <span className="ptl__name">{project.name}</span>}
              <Badge tone="accent">{project.stage}</Badge>
              <span className="ptl__rts">
                RTS {short(project.rts_date) || "미정"}
              </span>
              <Badge tone={ddayTone(project.days_left)}>{dday(project.days_left)}</Badge>
              <span className="ptl__caret" aria-hidden="true">
                {open ? "▾" : "▸"}
              </span>
            </button>
            {open && <Timeline project={project} />}
          </div>
        );
      })}
      {onAdd && (
        <Row style={{ marginTop: "var(--space-3)" }}>
          <Button variant="ghost" small onClick={onAdd}>
            + 프로젝트 추가
          </Button>
        </Row>
      )}
    </div>
  );
}
