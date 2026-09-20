"use client";

// 로그인하고 처음 보는 화면. 오늘 챙겨야 할 것만 한눈에 모아 둡니다.
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Dashboard, DashboardWidget, getSession } from "@/lib/api";
import {
  Alert,
  Badge,
  Bar,
  Empty,
  Grid,
  Lines,
  Muted,
  PageTitle,
  Panel,
  Row,
  Rows,
  Section,
  SectionHead,
  Tag,
  When,
  type Tone,
} from "@/components/ui";

const RUN_LABEL: Record<string, string> = {
  queued: "대기 중",
  planning: "계획 세우는 중",
  awaiting_approval: "확인 필요",
  running: "처리 중",
  succeeded: "완료",
  failed: "실패",
  rejected: "취소함",
};

const RUN_TONE: Record<string, Tone> = {
  queued: "neutral",
  planning: "accent",
  awaiting_approval: "warn",
  running: "accent",
  succeeded: "ok",
  failed: "crit",
  rejected: "neutral",
};

function when(iso: string) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("ko-KR", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function Widget({ widget }: { widget: DashboardWidget }) {
  return (
    <Panel
      title={
        <>
          {widget.icon} {widget.title}
        </>
      }
      count={widget.app ? <Tag>{widget.app}</Tag> : undefined}
    >
      {widget.status === "ok" && <Lines>{widget.text}</Lines>}
      {widget.status === "empty" && (
        <Muted style={{ paddingBottom: "var(--space-3)" }}>지금은 없습니다. 👍</Muted>
      )}
      {widget.status === "missing" && (
        <Muted style={{ paddingBottom: "var(--space-3)" }}>
          {widget.hint || "이 칸을 채워 줄 앱이 아직 등록되지 않았습니다."}
        </Muted>
      )}
      {widget.status === "error" && (
        <Alert tone="crit" style={{ margin: "var(--space-2) 0 var(--space-3)" }}>
          앱을 부르지 못했습니다. 앱스토어에서 상태를 확인해 주세요.
        </Alert>
      )}
    </Panel>
  );
}

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!getSession()) {
      location.href = "/login";
      return;
    }
    api
      .dashboard()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  if (error)
    return (
      <Alert tone="crit" style={{ marginTop: "var(--space-8)" }}>
        {error}
      </Alert>
    );
  if (!data)
    return <Muted style={{ marginTop: "var(--space-8)" }}>불러오는 중…</Muted>;

  const today = new Date().toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  });
  const topCalls = data.ranking[0]?.success_calls || 1;

  return (
    <>
      <PageTitle title="오늘 챙길 것" sub={today} />

      <Grid cols={3}>
        {data.widgets.map((widget) => (
          <Widget key={widget.key} widget={widget} />
        ))}
      </Grid>

      <Section>
        <SectionHead
          label="예약된 작업"
          action={<Link href="/schedules">예약 만들기</Link>}
        />
        {data.schedules.length === 0 ? (
          <Empty>
            정해진 시각에 저절로 돌게 하고 싶은 일이 있으면 예약을 걸어 두세요.
          </Empty>
        ) : (
          <Rows>
            {data.schedules.map((row) => (
              <div key={row.id}>
                <span className="ui-list__main">⏰ {row.title}</span>
                <Muted>{row.when_text}</Muted>
                {row.next_run_at && <When>다음 {when(row.next_run_at)}</When>}
              </div>
            ))}
          </Rows>
        )}
      </Section>

      <Section>
        <SectionHead label="내 레시피" action={<Link href="/recipes">전체 보기</Link>} />
        {data.recipes.length === 0 ? (
          <Empty>
            요청을 한 번 실행해서 잘 나오면, 그 흐름을 레시피로 저장해 보세요.
            다음부터는 버튼 하나로 끝납니다.
          </Empty>
        ) : (
          <Rows>
            {data.recipes.map((row) => (
              <div key={row.id}>
                <Link className="ui-list__main" href="/recipes">
                  {row.icon} {row.title}
                </Link>
                <When>{row.run_count}번 실행</When>
              </div>
            ))}
          </Rows>
        )}
      </Section>

      <Section>
        <SectionHead label="최근 실행" />
        {data.runs.length === 0 ? (
          <Empty>아직 실행한 것이 없습니다. 내 에이전트에서 한 문장 적어 보세요.</Empty>
        ) : (
          <Rows>
            {data.runs.map((row) => (
              <div key={row.id}>
                <span className="ui-list__main">{row.request_text}</span>
                <Badge tone={RUN_TONE[row.status] ?? "neutral"}>
                  {RUN_LABEL[row.status] || row.status}
                </Badge>
              </div>
            ))}
          </Rows>
        )}
      </Section>

      {data.ranking.length > 0 && (
        <Section>
          <SectionHead
            label="이달의 앱"
            note="성공 호출 수 기준"
            action={<Link href="/stats">전체 순위</Link>}
          />
          <div style={{ display: "grid", gap: "var(--space-3)" }}>
            {data.ranking.map((row) => (
              <Row key={row.rank} nowrap>
                <span className="ui-count" style={{ width: 18 }}>
                  {row.rank === 1 ? "🏆" : row.rank}
                </span>
                <span style={{ flex: 1, minWidth: 0 }}>{row.name}</span>
                <span style={{ width: 120 }}>
                  <Bar percent={(row.success_calls / topCalls) * 100} />
                </span>
                <When>{row.success_calls}회</When>
              </Row>
            ))}
          </div>
        </Section>
      )}
    </>
  );
}
