"use client";

// 로그인하고 처음 보는 화면. 전체 업무 흐름을 한눈에 봅니다.
//   1) 맨 위에서 한 문장으로 일을 맡기고
//   2) 등록된 프로젝트가 지금 어디쯤인지 보고
//   3) 오늘 챙길 것(할 일·메일·예약·최근 실행)을 훑습니다.
//
// 요청 결과는 여기에 길게 펼치지 않고 한 줄 요약만 둡니다. 결과가 길어지면
// 아래 칸들이 통째로 밀려나기 때문에, 전체 내용은 /runs/[id] 화면에서 봅니다.
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Dashboard, DashboardWidget, Project, Run, getSession } from "@/lib/api";
import { ProjectList } from "@/components/dashboard/projects";
import {
  Alert,
  Badge,
  Bar,
  Button,
  Card,
  Empty,
  Field,
  Grid,
  Input,
  Lines,
  Modal,
  Muted,
  PageTitle,
  Panel,
  Row,
  Rows,
  Section,
  SectionHead,
  Tag,
  Textarea,
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
  canceled: "멈춤",
};

const RUN_TONE: Record<string, Tone> = {
  queued: "neutral",
  planning: "accent",
  awaiting_approval: "warn",
  running: "accent",
  succeeded: "ok",
  failed: "crit",
  rejected: "neutral",
  canceled: "neutral",
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

/** 방금 맡긴 일의 한 줄 요약. 길어지지 않게 항상 한 줄만 씁니다. */
function RunLine({ run, onChange }: { run: Run; onChange: (run: Run) => void }) {
  // 끝날 때까지 2초마다 상태만 다시 물어봅니다.
  useEffect(() => {
    if (["succeeded", "failed", "rejected", "canceled", "awaiting_approval"].includes(run.status))
      return;
    const timer = setTimeout(
      () => api.getRun(run.id).then(onChange).catch(() => undefined),
      2000
    );
    return () => clearTimeout(timer);
  }, [run, onChange]);

  return (
    <Card quiet style={{ marginTop: "var(--space-3)" }}>
      <Row between nowrap>
        <Row nowrap style={{ minWidth: 0 }}>
          <Badge tone={RUN_TONE[run.status] ?? "neutral"}>
            {RUN_LABEL[run.status] || run.status}
          </Badge>
          <span className="ui-ellipsis">{run.request_text}</span>
        </Row>
        <Row nowrap>
          {run.status === "awaiting_approval" && (
            <>
              <Button small onClick={() => api.approveRun(run.id).then(onChange)}>
                이대로 진행
              </Button>
              <Button variant="ghost" small onClick={() => api.rejectRun(run.id).then(onChange)}>
                취소
              </Button>
            </>
          )}
          <Link href={`/runs/${run.id}`}>전체 보기</Link>
        </Row>
      </Row>
    </Card>
  );
}

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");
  const [text, setText] = useState("");
  const [run, setRun] = useState<Run | null>(null);
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({
    name: "",
    model: "",
    stage: "기획",
    start_date: "",
    rts_date: "",
    milestones: "",
  });

  const reload = () =>
    api
      .dashboard()
      .then(setData)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));

  useEffect(() => {
    if (!getSession()) {
      location.href = "/login";
      return;
    }
    reload();
  }, []);

  const submit = async () => {
    setError("");
    setBusy(true);
    try {
      setRun(await api.createRun({ request_text: text }));
      setText("");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const addProject = async () => {
    setError("");
    try {
      await api.addProject(form);
      setAdding(false);
      setForm({ name: "", model: "", stage: "기획", start_date: "", rts_date: "", milestones: "" });
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  if (error && !data)
    return (
      <Alert tone="crit" style={{ marginTop: "var(--space-8)" }}>
        {error}
      </Alert>
    );
  if (!data) return <Muted style={{ marginTop: "var(--space-8)" }}>불러오는 중…</Muted>;

  const today = new Date().toLocaleDateString("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  });
  const topCalls = data.ranking[0]?.success_calls || 1;

  // 프로젝트 칸은 글이 아니라 시간축으로 그리므로 따로 꺼냅니다.
  const projectWidget = data.widgets.find((w) => w.render === "projects");
  const otherWidgets = data.widgets.filter((w) => w.render !== "projects");
  const projects: Project[] = projectWidget?.data?.projects || [];

  return (
    <>
      <PageTitle title="오늘 챙길 것" sub={today} />

      <Card quiet className="ui-card--pad-lg">
        <Field
          label="무엇을 맡길까요?"
          htmlFor="ask"
          hint="누가, 무엇을, 어떤 형식으로 를 적어 주면 더 잘 알아듣습니다"
        >
          <Textarea
            id="ask"
            rows={3}
            value={text}
            placeholder="예) 사번 E1001의 이번주 주간보고를 작성해줘"
            onChange={(e) => setText(e.target.value)}
          />
        </Field>
        <Row between>
          <Muted>
            자주 쓰는 요청은 <Link href="/">내 에이전트</Link> 화면에서 카드로 저장해 둘 수
            있습니다.
          </Muted>
          <Button onClick={submit} disabled={busy || !text.trim()}>
            {busy ? "보내는 중…" : "계획 세우기"}
          </Button>
        </Row>
        {run && <RunLine run={run} onChange={setRun} />}
      </Card>

      {error && (
        <Alert tone="crit" style={{ marginTop: "var(--space-4)" }}>
          {error}
        </Alert>
      )}

      <Section>
        <SectionHead
          label="등록된 프로젝트"
          note="누르면 시간축과 마일스톤이 펼쳐집니다"
          action={
            projectWidget?.status === "missing" ? undefined : (
              <button type="button" className="ui-chip" onClick={() => setAdding(true)}>
                + 프로젝트 추가
              </button>
            )
          }
        />
        {projectWidget?.status === "missing" ? (
          <Empty>
            {projectWidget.hint ||
              "개발 프로젝트 앱을 앱스토어에 등록하면 여기에 채워집니다."}
          </Empty>
        ) : projectWidget?.status === "error" ? (
          <Alert tone="crit">
            프로젝트 앱을 부르지 못했습니다. 앱스토어에서 상태를 확인해 주세요.
          </Alert>
        ) : (
          <ProjectList projects={projects} onAdd={projects.length ? undefined : () => setAdding(true)} />
        )}
      </Section>

      <Section>
        <SectionHead label="할 일과 메일" note="등록된 앱이 채워 줍니다" />
        <Grid cols={3}>
          {otherWidgets.map((widget) => (
            <Widget key={widget.key} widget={widget} />
          ))}
        </Grid>
      </Section>

      <Section>
        <SectionHead label="예약된 작업" action={<Link href="/schedules">예약 만들기</Link>} />
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
            요청을 한 번 실행해서 잘 나오면, 그 흐름을 레시피로 저장해 보세요. 다음부터는
            버튼 하나로 끝납니다.
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
          <Empty>아직 실행한 것이 없습니다. 맨 위에 한 문장 적어 보세요.</Empty>
        ) : (
          <Rows>
            {data.runs.map((row) => (
              <div key={row.id}>
                <Link className="ui-list__main" href={`/runs/${row.id}`}>
                  {row.request_text}
                </Link>
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

      <Modal
        open={adding}
        title="프로젝트 추가"
        sub="모델명과 RTS(개발완료) 날짜를 넣어 두면 시간축에 바로 그려집니다."
        onClose={() => setAdding(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setAdding(false)}>
              닫기
            </Button>
            <Button onClick={addProject} disabled={!form.name.trim()}>
              등록
            </Button>
          </>
        }
      >
        <Field label="프로젝트 이름" htmlFor="p-name">
          <Input
            id="p-name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
        </Field>
        <Field label="모델명" htmlFor="p-model" hint="예) SM-X100">
          <Input
            id="p-model"
            value={form.model}
            onChange={(e) => setForm({ ...form, model: e.target.value })}
          />
        </Field>
        <Row>
          <Field label="시작일" htmlFor="p-start">
            <Input
              id="p-start"
              type="date"
              value={form.start_date}
              onChange={(e) => setForm({ ...form, start_date: e.target.value })}
            />
          </Field>
          <Field label="RTS (개발완료)" htmlFor="p-rts">
            <Input
              id="p-rts"
              type="date"
              value={form.rts_date}
              onChange={(e) => setForm({ ...form, rts_date: e.target.value })}
            />
          </Field>
        </Row>
        <Field
          label="주요 마일스톤"
          htmlFor="p-ms"
          hint="이름과 날짜를 쉼표로 이어 적습니다. 산출물은 대괄호로."
        >
          <Textarea
            id="p-ms"
            rows={3}
            value={form.milestones}
            placeholder="예) 설계완료 2026-03-31 [시스템설계서, 화면설계서], PP 2026-05-20"
            onChange={(e) => setForm({ ...form, milestones: e.target.value })}
          />
        </Field>
      </Modal>
    </>
  );
}
