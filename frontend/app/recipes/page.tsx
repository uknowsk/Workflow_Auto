"use client";

// 워크플로우 레시피. 앱 여러 개를 엮은 흐름을 이름 붙여 저장해 두고 버튼 하나로 재실행합니다.
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Recipe, Run, getSession } from "@/lib/api";
import {
  Alert,
  Badge,
  Button,
  Card,
  Empty,
  Field,
  IconTile,
  Muted,
  Lines,
  PageTitle,
  Row,
  Section,
  SectionHead,
  Tag,
  Textarea,
  type Tone,
} from "@/components/ui";

const RUN_LABEL: Record<Run["status"], string> = {
  queued: "대기 중",
  planning: "계획 세우는 중",
  awaiting_approval: "확인 필요",
  running: "처리 중",
  succeeded: "완료",
  failed: "실패",
  rejected: "취소함",
};

const RUN_TONE: Record<Run["status"], Tone> = {
  queued: "neutral",
  planning: "accent",
  awaiting_approval: "warn",
  running: "accent",
  succeeded: "ok",
  failed: "crit",
  rejected: "neutral",
};

export default function Recipes() {
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [open, setOpen] = useState<string>("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [run, setRun] = useState<Run | null>(null);
  const [error, setError] = useState("");

  const reload = () => api.listRecipes().then(setRecipes).catch(() => undefined);

  useEffect(() => {
    if (!getSession()) {
      location.href = "/login";
      return;
    }
    reload();
  }, []);

  // 실행은 큐에 들어가므로 끝날 때까지 2초마다 확인합니다.
  useEffect(() => {
    if (!run) return;
    if (["succeeded", "failed", "rejected", "awaiting_approval"].includes(run.status)) return;
    const timer = setTimeout(
      () => api.getRun(run.id).then(setRun).catch(() => undefined),
      2000
    );
    return () => clearTimeout(timer);
  }, [run]);

  const start = async (recipe: Recipe) => {
    setError("");
    try {
      setRun(await api.runRecipe(recipe.id, values));
      setOpen("");
      setValues({});
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <>
      <PageTitle
        title="워크플로우 레시피"
        sub={`저장한 레시피 ${recipes.length}개 · 앱 여러 개를 엮은 흐름을 버튼 하나로 다시 돌립니다`}
      />

      <Muted style={{ marginBottom: "var(--space-5)" }}>
        카드가 앱 하나라면, 레시피는 <b>앱 여러 개를 엮은 카드</b>입니다. 요청을 한 번
        실행해서 잘 나왔으면 <Link href="/">내 에이전트</Link> 화면에서 그 흐름을 레시피로
        저장해 두세요.
      </Muted>

      {error && (
        <Alert tone="crit" style={{ marginBottom: "var(--space-4)" }}>
          {error}
        </Alert>
      )}

      {recipes.length === 0 ? (
        <Empty>
          아직 저장된 레시피가 없습니다. 요청을 한 번 실행해 결과가 마음에 들면
          &ldquo;이 흐름을 레시피로 저장&rdquo;을 눌러 보세요.
        </Empty>
      ) : (
        recipes.map((recipe) => (
          <Card key={recipe.id} style={{ marginBottom: "var(--space-3)" }}>
            <Row between nowrap>
              <Row nowrap>
                <IconTile>{recipe.icon || "🔁"}</IconTile>
                <b>{recipe.title}</b>
              </Row>
              <Row nowrap>
                <Tag>{recipe.steps.length}단계</Tag>
                <Tag>{recipe.run_count}번 실행</Tag>
                <Button
                  variant="danger"
                  small
                  aria-label={`${recipe.title} 레시피 삭제`}
                  onClick={() => {
                    if (confirm(`'${recipe.title}' 레시피를 지울까요?`))
                      api.deleteRecipe(recipe.id).then(reload);
                  }}
                >
                  삭제
                </Button>
              </Row>
            </Row>

            {recipe.description && (
              <Muted style={{ marginTop: "var(--space-2)" }}>{recipe.description}</Muted>
            )}

            {/* 어떤 앱을 어떤 순서로 부르는지 한 줄로 보여 줍니다. */}
            <Row style={{ marginTop: "var(--space-3)" }}>
              {recipe.steps.map((step, i) => (
                <span key={i} className="ui-row" style={{ gap: "var(--space-1)" }}>
                  {i > 0 && <span className="ui-muted">→</span>}
                  <Tag>
                    {step.app_name} · {step.tool}
                  </Tag>
                </span>
              ))}
            </Row>

            {open === recipe.id ? (
              <div style={{ marginTop: "var(--space-4)" }}>
                {recipe.variables.map((name) => (
                  <Field key={name} label={name} htmlFor={`var-${recipe.id}-${name}`}>
                    <Textarea
                      id={`var-${recipe.id}-${name}`}
                      rows={2}
                      value={values[name] || ""}
                      onChange={(e) => setValues({ ...values, [name]: e.target.value })}
                    />
                  </Field>
                ))}
                <Row>
                  <Button onClick={() => start(recipe)}>실행</Button>
                  <Button variant="ghost" onClick={() => setOpen("")}>
                    취소
                  </Button>
                </Row>
              </div>
            ) : (
              <Row style={{ marginTop: "var(--space-3)" }}>
                <Button
                  onClick={() => {
                    setValues({});
                    if (recipe.variables.length === 0) start(recipe);
                    else setOpen(recipe.id);
                  }}
                >
                  {recipe.variables.length === 0 ? "실행" : "값 넣고 실행"}
                </Button>
              </Row>
            )}
          </Card>
        ))
      )}

      {run && (
        <Section>
          <SectionHead
            label="실행 결과"
            action={<Badge tone={RUN_TONE[run.status]}>{RUN_LABEL[run.status]}</Badge>}
          />
          <Card>
            {run.status === "awaiting_approval" && (
              <>
                <p style={{ marginTop: 0 }}>
                  되돌릴 수 없는 작업이 들어 있어 확인이 필요합니다. 이대로 진행할까요?
                </p>
                <ul style={{ paddingLeft: 18 }}>
                  {run.plan.map((step, i) => (
                    <li key={i}>
                      {step.requires_confirmation ? "⚠️ " : ""}
                      <b>{step.app}</b> · {step.tool}
                    </li>
                  ))}
                </ul>
                <Row>
                  <Button onClick={() => api.approveRun(run.id).then(setRun)}>
                    이대로 진행
                  </Button>
                  <Button variant="ghost" onClick={() => api.rejectRun(run.id).then(setRun)}>
                    취소
                  </Button>
                </Row>
              </>
            )}

            {run.steps?.length > 0 && (
              <ul className="ui-list">
                {run.steps.map((step, i) => (
                  <li key={i}>
                    <span className={step.error ? "ui-dot ui-dot--crit" : "ui-dot ui-dot--ok"} />
                    <div className="ui-list__main">
                      <span className="ui-list__title">
                        {step.app} · {step.tool}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
            {run.result_text && <Lines boxed>{run.result_text}</Lines>}
            {run.error && (
              <Alert tone="crit" style={{ marginTop: "var(--space-3)" }}>
                {run.error}
              </Alert>
            )}
          </Card>
        </Section>
      )}
    </>
  );
}
