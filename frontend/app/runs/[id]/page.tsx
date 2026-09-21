"use client";

// 요청 하나의 결과를 넓게 보는 화면.
// 대시보드에는 상태와 요약만 두고, 결과가 길어지면 여기로 넘어옵니다.
// (대시보드 안에서 결과가 길어지면 아래 칸들이 통째로 밀려나기 때문입니다.)

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api, getSession, Run } from "@/lib/api";
import {
  Alert,
  Badge,
  Button,
  Card,
  Lines,
  Muted,
  PageTitle,
  Row,
  Section,
  SectionHead,
  type Tone,
} from "@/components/ui";

const STATUS_LABEL: Record<Run["status"], string> = {
  queued: "대기 중",
  planning: "계획 세우는 중",
  awaiting_approval: "확인 필요",
  running: "처리 중",
  succeeded: "완료",
  failed: "실패",
  rejected: "취소함",
};

const STATUS_TONE: Record<Run["status"], Tone> = {
  queued: "neutral",
  planning: "accent",
  awaiting_approval: "warn",
  running: "accent",
  succeeded: "ok",
  failed: "crit",
  rejected: "neutral",
};

export default function RunPage() {
  const params = useParams<{ id: string }>();
  const runId = String(params?.id || "");
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    api
      .getRun(runId)
      .then(setRun)
      .catch((e) => setError(e instanceof Error ? e.message : String(e)));
  }, [runId]);

  useEffect(() => {
    if (!getSession()) {
      location.href = "/login";
      return;
    }
    load();
  }, [load]);

  // 아직 도는 중이면 2초마다 다시 물어봅니다.
  useEffect(() => {
    if (!run) return;
    if (["succeeded", "failed", "rejected", "awaiting_approval"].includes(run.status)) return;
    const timer = setTimeout(load, 2000);
    return () => clearTimeout(timer);
  }, [run, load]);

  const saveAsRecipe = async () => {
    if (!run) return;
    const title = prompt("이 흐름에 이름을 붙여 주세요. 예) 회의록 정리 후 담당자 메일");
    if (!title) return;
    try {
      await api.createRecipeFromRun({ run_id: run.id, title });
      alert("레시피로 저장했습니다. '레시피' 화면에서 언제든 다시 실행할 수 있어요.");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  if (error) return <Alert tone="crit">{error}</Alert>;
  if (!run) return <Muted>불러오는 중…</Muted>;

  return (
    <>
      <PageTitle title="요청 결과" sub={run.request_text} />
      <Row style={{ marginBottom: "var(--space-4)" }}>
        <Badge tone={STATUS_TONE[run.status]}>{STATUS_LABEL[run.status]}</Badge>
        <Link href="/dashboard">← 대시보드로</Link>
      </Row>

      {run.status === "awaiting_approval" && (
        <Card>
          <p style={{ marginTop: 0 }}>
            되돌릴 수 없는 작업이 들어 있어 확인이 필요합니다. 아래 계획대로 진행할까요?
          </p>
          <Muted>{run.plan_summary}</Muted>
          <ul style={{ paddingLeft: 18 }}>
            {run.plan.map((step, i) => (
              <li key={i}>
                {step.requires_confirmation ? "⚠️ " : ""}
                <b>{step.app}</b> · {step.tool}
                {step.why && <span className="ui-muted"> — {step.why}</span>}
              </li>
            ))}
          </ul>
          <Row>
            <Button onClick={() => api.approveRun(run.id).then(setRun)}>이대로 진행</Button>
            <Button variant="ghost" onClick={() => api.rejectRun(run.id).then(setRun)}>
              취소
            </Button>
          </Row>
        </Card>
      )}

      {run.steps?.length > 0 && (
        <Section>
          <SectionHead label="처리 과정" />
          <ul className="ui-list">
            {run.steps.map((step, i) => (
              <li key={i}>
                <span className={step.error ? "ui-dot ui-dot--crit" : "ui-dot ui-dot--ok"} />
                <div className="ui-list__main">
                  <span className="ui-list__title">
                    {step.app} · {step.tool}
                  </span>
                  {step.error && <span className="ui-list__meta">{String(step.error)}</span>}
                </div>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {run.result_text && (
        <Section>
          <SectionHead label="결과" />
          <Lines boxed>{run.result_text}</Lines>
        </Section>
      )}

      {run.error && <Alert tone="crit">{run.error}</Alert>}

      {run.status === "succeeded" && (
        <Row style={{ marginTop: "var(--space-4)" }}>
          <Button variant="ghost" small onClick={saveAsRecipe}>
            이 흐름을 레시피로 저장
          </Button>
          <Muted>다음부터 같은 일을 버튼 하나로 하고, 예약도 걸 수 있습니다.</Muted>
        </Row>
      )}
    </>
  );
}
