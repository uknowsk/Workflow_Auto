"use client";

import { useEffect, useState } from "react";
import {
  api,
  App,
  Card as CardType,
  Form,
  MyDept,
  Recipe,
  Run,
  getSession,
} from "@/lib/api";
import {
  Alert,
  Badge,
  Button,
  Card,
  Empty,
  Field,
  Grid,
  IconTile,
  Muted,
  Lines,
  PageTitle,
  Row,
  Section,
  SectionHead,
  Select,
  Textarea,
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
  canceled: "멈춤",
};

const STATUS_TONE: Record<Run["status"], Tone> = {
  queued: "neutral",
  planning: "accent",
  awaiting_approval: "warn",
  running: "accent",
  succeeded: "ok",
  failed: "crit",
  rejected: "neutral",
  canceled: "neutral",
};

// 처음 오신 분들을 위한 예시. 빈 화면에 커서만 깜빡이면 아무도 첫 줄을 못 씁니다.
// 넷 다 공식 앱만으로 실제로 되는 일이라, 눌러 보면 진짜 결과가 나옵니다.
const EXAMPLES = [
  "지난주 회의록을 정리해서 할 일을 담당자별로 뽑아 줘",
  "이번 주 내 기록을 모아 주간보고 초안을 써 줘",
  "아직 회신 안 한 사람들에게 리마인드 메일을 보내 줘",
  "이 문서를 한 장으로 요약해 줘",
];

// 아직 끝나지 않아 '멈추기'를 누를 수 있는 상태들.
const RUNNING: Run["status"][] = ["queued", "planning", "running"];

export default function Home() {
  const [cards, setCards] = useState<CardType[]>([]);
  const [apps, setApps] = useState<App[]>([]);
  const [forms, setForms] = useState<Form[]>([]);
  const [text, setText] = useState("");
  const [cardId, setCardId] = useState("");
  const [formId, setFormId] = useState("");
  const [run, setRun] = useState<Run | null>(null);
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [myDepts, setMyDepts] = useState<MyDept[]>([]);
  const [error, setError] = useState("");

  const reload = () => {
    api.listCards().then(setCards).catch(() => undefined);
    api.listApps().then(setApps).catch(() => undefined);
    api.listForms().then(setForms).catch(() => undefined);
    api.listRecipes().then(setRecipes).catch(() => undefined);
    api.myDepartments().then(setMyDepts).catch(() => undefined);
  };

  useEffect(() => {
    if (!getSession()) {
      location.href = "/login";
      return;
    }
    reload();
  }, []);

  // 실행은 큐에 들어가므로, 끝나거나 확인이 필요할 때까지 2초마다 상태를 봅니다.
  useEffect(() => {
    if (!run) return;
    const done = ["succeeded", "failed", "rejected", "canceled", "awaiting_approval"];
    if (done.includes(run.status)) return;
    const timer = setTimeout(
      () => api.getRun(run.id).then(setRun).catch(() => undefined),
      2000
    );
    return () => clearTimeout(timer);
  }, [run]);

  const submit = async () => {
    setError("");
    try {
      setRun(
        await api.createRun({
          request_text: text,
          card_id: cardId || null,
          form_id: formId || null,
        })
      );
    } catch (e) {
      setError(String(e instanceof Error ? e.message : e));
    }
  };

  // 방금 끝난 실행을 그대로 레시피로 굳혀 둡니다(다시 LLM 에게 묻지 않고 재실행).
  const saveAsRecipe = async () => {
    if (!run) return;
    const title = prompt(
      "이 흐름에 이름을 붙여 주세요. 예) 회의록 정리 후 담당자 메일"
    );
    if (!title) return;
    try {
      await api.createRecipeFromRun({ run_id: run.id, title });
      reload();
      alert("레시피로 저장했습니다. '레시피' 화면에서 언제든 다시 실행할 수 있어요.");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  // dept_code 를 주면 부서 공통 카드가 됩니다(부서 담당자만 만들 수 있습니다).
  const addCard = async (deptCode = "") => {
    const title = prompt(
      deptCode
        ? "부서원 모두에게 보일 카드 이름을 적어 주세요. 예) 주간보고 자동작성"
        : "카드 이름을 적어 주세요. 예) 주간보고 자동작성"
    );
    if (!title) return;
    const template = prompt("이 카드를 누르면 채워질 요청문을 적어 주세요.") || "";
    try {
      await api.createCard({
        title,
        prompt_template: template,
        app_ids: [],
        icon: deptCode ? "🏢" : "⭐",
        pinned: true,
        dept_code: deptCode,
      });
      reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const deptCards = cards.filter((card) => card.dept_code);
  const myCards = cards.filter((card) => !card.dept_code);
  const manageable = myDepts.filter((d) => d.can_manage);

  return (
    <>
      <PageTitle
        title="무엇을 맡길까요?"
        sub={`쓸 수 있는 앱 ${apps.length}개 · 저장한 카드 ${cards.length}개`}
      />

      <Card quiet className="ui-card--pad-lg">
        <Field
          label="편하게 한 문장으로 적어 주세요."
          htmlFor="ask"
          hint="누가, 무엇을, 어떤 형식으로 를 적어 주면 더 잘 알아듣습니다"
        >
          <Textarea
            id="ask"
            rows={4}
            value={text}
            placeholder="예) 사번 E1001의 이번주 주간보고를 작성해줘"
            onChange={(e) => setText(e.target.value)}
          />
        </Field>

        {!text.trim() && (
          <Row style={{ marginBottom: "var(--space-3)" }}>
            <Muted>이런 것도 됩니다</Muted>
            {EXAMPLES.map((example) => (
              <Button key={example} variant="ghost" small onClick={() => setText(example)}>
                {example}
              </Button>
            ))}
          </Row>
        )}

        <Row>
          <Select
            value={formId}
            onChange={(e) => setFormId(e.target.value)}
            style={{ width: 220 }}
            aria-label="결과를 채울 양식"
          >
            <option value="">양식 없음 (자유 형식)</option>
            {forms.map((form) => (
              <option key={form.id} value={form.id}>
                {form.name}
              </option>
            ))}
          </Select>
          {cardId && (
            <Badge tone="accent">
              카드로 실행 중{" "}
              <button
                type="button"
                onClick={() => setCardId("")}
                style={{
                  border: 0,
                  background: "none",
                  color: "inherit",
                  cursor: "pointer",
                  textDecoration: "underline",
                  padding: 0,
                  font: "inherit",
                }}
              >
                해제
              </button>
            </Badge>
          )}
          <span style={{ marginLeft: "auto" }}>
            <Button onClick={submit} disabled={!text.trim()}>
              계획 세우기
            </Button>
          </span>
        </Row>
      </Card>

      {error && (
        <Alert tone="crit" style={{ marginTop: "var(--space-4)" }}>
          {error}
        </Alert>
      )}

      {run && (
        <Section>
          <SectionHead
            label="실행"
            action={
              <Row>
                {RUNNING.includes(run.status) && (
                  <Button
                    variant="ghost"
                    small
                    onClick={() =>
                      api
                        .cancelRun(run.id)
                        .then(setRun)
                        .catch((e) => setError(e instanceof Error ? e.message : String(e)))
                    }
                  >
                    멈추기
                  </Button>
                )}
                <Badge tone={STATUS_TONE[run.status]}>{STATUS_LABEL[run.status]}</Badge>
              </Row>
            }
          />
          <Card>
            {run.status === "awaiting_approval" && (
              <>
                <p style={{ marginTop: 0 }}>
                  되돌릴 수 없는 작업이 들어 있어 확인이 필요합니다. 아래 계획대로
                  진행할까요?
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
                      {step.error && (
                        <span className="ui-list__meta">{String(step.error)}</span>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
            {run.status === "canceled" && (
              <Muted>멈췄습니다. 이미 끝난 단계까지의 결과만 위에 남아 있습니다.</Muted>
            )}
            {run.result_text && <Lines boxed>{run.result_text}</Lines>}
            {run.error && (
              <Alert tone="crit" style={{ marginTop: "var(--space-3)" }}>
                {run.error}
              </Alert>
            )}
            {run.status === "succeeded" && (
              <Row style={{ marginTop: "var(--space-3)" }}>
                <Button variant="ghost" small onClick={saveAsRecipe}>
                  이 흐름을 레시피로 저장
                </Button>
                <Muted>
                  다음부터 같은 일을 버튼 하나로 하고, 예약도 걸 수 있습니다.
                </Muted>
              </Row>
            )}
          </Card>
        </Section>
      )}

      {deptCards.length > 0 && (
        <Section>
          <SectionHead
            label="부서 공통 카드"
            action={<Muted>부서에 묶인 사람 모두에게 같이 보입니다</Muted>}
          />
          <Grid>
            {deptCards.map((card) => (
              <Card key={card.id} hoverable className="ui-card--stack">
                <Row between nowrap>
                  <Row nowrap>
                    <IconTile>{card.icon || "🏢"}</IconTile>
                    <b>{card.title}</b>
                  </Row>
                  <Badge tone="accent">{card.dept_name || card.dept_code}</Badge>
                </Row>
                <Muted>{card.prompt_template || "요청문 없음"}</Muted>
                <Row style={{ marginTop: "var(--space-2)" }}>
                  <Button
                    variant="ghost"
                    small
                    onClick={() => {
                      setText(card.prompt_template);
                      setCardId(card.id);
                      window.scrollTo({ top: 0, behavior: "smooth" });
                    }}
                  >
                    이 카드로 요청
                  </Button>
                  {card.editable && (
                    <Button
                      variant="ghost"
                      small
                      aria-label={`${card.title} 부서 공통 카드 삭제`}
                      onClick={() => api.deleteCard(card.id).then(reload)}
                    >
                      삭제
                    </Button>
                  )}
                </Row>
              </Card>
            ))}
          </Grid>
        </Section>
      )}

      <Section>
        <SectionHead
          label="내 에이전트 카드"
          action={
            <Row nowrap>
              {manageable.map((dept) => (
                <button
                  key={dept.code}
                  type="button"
                  className="ui-chip"
                  onClick={() => addCard(dept.code)}
                >
                  + {dept.name} 공통 카드
                </button>
              ))}
              <button type="button" className="ui-chip" onClick={() => addCard()}>
                + 카드 추가
              </button>
            </Row>
          }
        />
        {myCards.length === 0 ? (
          <Empty>
            자주 쓰는 요청을 카드로 저장해 두면 한 번에 불러옵니다. 오른쪽 위
            &ldquo;카드 추가&rdquo;를 눌러 보세요.
          </Empty>
        ) : (
          <Grid>
            {myCards.map((card) => (
              <Card key={card.id} hoverable className="ui-card--stack">
                <Row between nowrap>
                  <Row nowrap>
                    <IconTile>{card.icon || "⭐"}</IconTile>
                    <b>{card.title}</b>
                  </Row>
                  <Button
                    variant="ghost"
                    small
                    aria-label={`${card.title} 카드 삭제`}
                    onClick={() => api.deleteCard(card.id).then(reload)}
                  >
                    삭제
                  </Button>
                </Row>
                {/* 앱스토어에서 설치한 카드는 요청문이 없습니다(무엇을 시킬지는
                    그때그때 다르므로). 대신 앱 설명을 보여 주고, 눌렀을 때
                    입력칸으로 바로 커서를 옮깁니다. */}
                <Muted>
                  {card.prompt_template || card.description || "요청문 없음"}
                </Muted>
                <div style={{ marginTop: "var(--space-2)" }}>
                  <Button
                    variant="ghost"
                    small
                    onClick={() => {
                      setText(card.prompt_template);
                      setCardId(card.id);
                      window.scrollTo({ top: 0, behavior: "smooth" });
                      if (!card.prompt_template) {
                        document.getElementById("ask")?.focus();
                      }
                    }}
                  >
                    {card.prompt_template ? "이 카드로 요청" : "이 앱에게 시키기"}
                  </Button>
                </div>
              </Card>
            ))}
          </Grid>
        )}
      </Section>

      {recipes.length > 0 && (
        <Section>
          <SectionHead
            label="저장해 둔 레시피"
            action={
              <button
                type="button"
                className="ui-chip"
                onClick={() => (location.href = "/recipes")}
              >
                전체 보기
              </button>
            }
          />
          <Grid>
            {recipes.slice(0, 4).map((recipe) => (
              <Card key={recipe.id} hoverable className="ui-card--stack">
                <Row between nowrap>
                  <Row nowrap>
                    <IconTile>{recipe.icon || "🧾"}</IconTile>
                    <b>{recipe.title}</b>
                  </Row>
                  <Badge tone="neutral">{recipe.steps.length}단계</Badge>
                </Row>
                <Muted>
                  {recipe.description || "저장해 둔 앱 호출 흐름입니다."}
                </Muted>
                <div style={{ marginTop: "var(--space-2)" }}>
                  <Button
                    variant="ghost"
                    small
                    onClick={() => (location.href = "/recipes")}
                  >
                    레시피 실행
                  </Button>
                </div>
              </Card>
            ))}
          </Grid>
        </Section>
      )}
    </>
  );
}
