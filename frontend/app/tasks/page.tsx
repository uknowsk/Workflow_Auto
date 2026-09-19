"use client";

import { useEffect, useState } from "react";
import { Task, tasksApi } from "@/lib/apps";
import {
  Alert,
  Badge,
  Button,
  Card,
  Empty,
  Field,
  Grid,
  Input,
  Muted,
  PageTitle,
  Row,
  Section,
  SectionHead,
  Select,
  Tag,
} from "@/components/ui";

function dueLabel(task: Task) {
  if (!task.due) return "기한 없음";
  if (task.days_left === null) return task.due;
  if (task.days_left < 0) return `${task.due} (${-task.days_left}일 지남)`;
  if (task.days_left === 0) return `${task.due} (오늘)`;
  return `${task.due} (${task.days_left}일 남음)`;
}

// 기한이 지났으면 빨강, 오늘·내일이면 주황, 나머지는 회색.
function dueTone(task: Task) {
  if (task.overdue) return "crit" as const;
  if (task.days_left !== null && task.days_left <= 1) return "warn" as const;
  return "neutral" as const;
}

export default function Tasks() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [status, setStatus] = useState("open");
  const [kind, setKind] = useState("all");
  const [title, setTitle] = useState("");
  const [owner, setOwner] = useState("");
  const [due, setDue] = useState("");
  const [orderer, setOrderer] = useState("");
  const [message, setMessage] = useState("");

  const reload = () =>
    tasksApi
      .list(status, kind)
      .then((data) => setTasks(data.tasks))
      .catch((e) => setMessage(String(e)));

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, kind]);

  const add = async () => {
    if (!title) return;
    setMessage("");
    try {
      await tasksApi.add({
        title,
        owner,
        due,
        orderer,
        kind: orderer ? "order" : "task",
      });
      setTitle("");
      setOwner("");
      setDue("");
      setOrderer("");
      reload();
    } catch (e) {
      setMessage(String(e));
    }
  };

  return (
    <>
      <PageTitle
        title="할 일 / 수명업무"
        sub={`${tasks.length}건 · 회의록에서 자동으로 등록된 할 일과 상급자에게 지시받은 수명업무를 한 곳에서 봅니다`}
      />

      <Row style={{ marginBottom: "var(--space-4)" }}>
        <Select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          style={{ width: 150 }}
          aria-label="상태로 거르기"
        >
          <option value="open">아직 안 한 일</option>
          <option value="done">끝낸 일</option>
          <option value="all">전부</option>
        </Select>
        <Select
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          style={{ width: 170 }}
          aria-label="종류로 거르기"
        >
          <option value="all">할 일 + 수명업무</option>
          <option value="task">할 일만</option>
          <option value="order">수명업무만</option>
        </Select>
      </Row>

      {message && (
        <Alert tone="crit" style={{ marginBottom: "var(--space-4)" }}>
          {message}
        </Alert>
      )}

      {tasks.length === 0 ? (
        <Empty>해당하는 일이 없습니다. 아래에서 직접 추가할 수 있어요.</Empty>
      ) : (
        <div>
          {tasks.map((task) => (
            <Card key={task.id} style={{ marginBottom: "var(--space-3)" }}>
              <Row between nowrap>
                <b>
                  {task.kind === "order" ? "📌 " : "✅ "}
                  {task.title}
                </b>
                <Badge tone={dueTone(task)}>{dueLabel(task)}</Badge>
              </Row>
              <Row style={{ marginTop: "var(--space-2)" }}>
                <Tag>담당 {task.owner || "미정"}</Tag>
                {task.orderer && <Tag>지시 {task.orderer}</Tag>}
                {task.source && <Tag>출처 {task.source}</Tag>}
                {task.status === "done" && <Badge tone="ok">완료</Badge>}
              </Row>
              {task.status === "open" && (
                <Row style={{ marginTop: "var(--space-3)" }}>
                  <Button
                    variant="ghost"
                    small
                    onClick={() => tasksApi.complete(task.id).then(reload)}
                  >
                    완료 처리
                  </Button>
                </Row>
              )}
            </Card>
          ))}
        </div>
      )}

      <Section>
        <SectionHead label="직접 추가" />
        <Card className="ui-card--pad-lg">
          <Field label="할 일" htmlFor="task-title">
            <Input
              id="task-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </Field>
          <Grid cols={3}>
            <Field label="담당자" htmlFor="task-owner">
              <Input
                id="task-owner"
                value={owner}
                onChange={(e) => setOwner(e.target.value)}
              />
            </Field>
            <Field label="기한" hint="2026-09-25, 내일, 3일 뒤 …" htmlFor="task-due">
              <Input id="task-due" value={due} onChange={(e) => setDue(e.target.value)} />
            </Field>
            <Field
              label="지시한 상급자"
              hint="적으면 수명업무가 됩니다"
              htmlFor="task-orderer"
            >
              <Input
                id="task-orderer"
                value={orderer}
                onChange={(e) => setOrderer(e.target.value)}
              />
            </Field>
          </Grid>
          <Button onClick={add} disabled={!title}>
            추가
          </Button>
        </Card>
      </Section>
    </>
  );
}
