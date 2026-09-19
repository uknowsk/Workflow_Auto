"use client";

import { useEffect, useState } from "react";
import { api, App, Notice, Usage } from "@/lib/api";
import {
  Alert,
  Badge,
  Button,
  Card,
  Empty,
  IconTile,
  Muted,
  Lines,
  PageTitle,
  Pre,
  Row,
  Section,
  Table,
  Tabs,
  Tag,
  type TabItem,
} from "@/components/ui";

type Tab = "pending" | "usage" | "audit" | "notices";

export default function Admin() {
  const [tab, setTab] = useState<Tab>("pending");
  const [pending, setPending] = useState<App[]>([]);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [audit, setAudit] = useState<Record<string, unknown>[]>([]);
  const [notices, setNotices] = useState<Notice[]>([]);
  const [message, setMessage] = useState("");

  const reload = () => {
    setMessage("");
    api
      .listPending()
      .then(setPending)
      .catch(() =>
        setMessage(
          "관리자만 볼 수 있습니다. 백엔드 환경변수 ADMIN_USER_IDS 에 내 사번을 넣거나, 관리자 계정으로 로그인하세요."
        )
      );
    api.usage().then(setUsage).catch(() => undefined);
    api.audit().then(setAudit).catch(() => undefined);
    api.notifications().then(setNotices).catch(() => undefined);
  };

  useEffect(() => {
    reload();
  }, []);

  const unread = notices.filter((n) => !n.read).length;
  const tabs: TabItem<Tab>[] = [
    { key: "pending", label: `승인 대기 ${pending.length}` },
    { key: "usage", label: "Gauss 사용량" },
    { key: "audit", label: "감사 기록" },
    { key: "notices", label: `알림 ${unread}` },
  ];

  return (
    <>
      <PageTitle title="관리자" sub="앱 승인, 사용량, 감사 기록을 여기서 봅니다." />

      <Tabs items={tabs} value={tab} onChange={setTab} />

      {message && (
        <Alert tone="warn" style={{ marginTop: "var(--space-5)" }}>
          {message}
        </Alert>
      )}

      {tab === "pending" && (
        <Section>
          {pending.length === 0 && !message ? (
            <Empty>대기 중인 앱이 없습니다.</Empty>
          ) : (
            pending.map((app) => (
              <Card key={app.id} style={{ marginBottom: "var(--space-3)" }}>
                <Row>
                  <IconTile>{app.icon || "🧩"}</IconTile>
                  <b>{app.name}</b>
                  {app.requires_confirmation && (
                    <Badge tone="warn">되돌릴 수 없는 작업</Badge>
                  )}
                </Row>
                <Muted style={{ margin: "var(--space-2) 0" }}>
                  {app.usage_hint || app.description}
                </Muted>
                <Row style={{ marginBottom: "var(--space-3)" }}>
                  <Tag>
                    올린 사람 {app.owner || app.owner_user_id || "-"}
                    {app.owner_contact && ` · ${app.owner_contact}`}
                  </Tag>
                  <Tag>기능 {app.tools.length}개</Tag>
                  {app.capability_tag && <Tag>역할 {app.capability_tag}</Tag>}
                </Row>
                <Row>
                  <Button onClick={() => api.approveApp(app.id).then(reload)}>
                    공식 승인
                  </Button>
                  <Button variant="ghost" onClick={() => api.rejectApp(app.id).then(reload)}>
                    반려 (개인용으로 되돌림)
                  </Button>
                </Row>
              </Card>
            ))
          )}
        </Section>
      )}

      {tab === "usage" && usage && (
        <Section>
          <Card>
            <b>{usage.period} Gauss 사용량</b>
            <Muted style={{ margin: "var(--space-2) 0 var(--space-4)" }}>
              전체 {usage.all_users?.total_tokens.toLocaleString() ?? "-"} 토큰 · 호출{" "}
              {usage.all_users?.calls ?? "-"}회. 지금은 확인만 하고 한도로 막지는
              않습니다.
            </Muted>
            <Table>
              <thead>
                <tr>
                  <th>사번</th>
                  <th className="num">토큰</th>
                  <th className="num">호출</th>
                </tr>
              </thead>
              <tbody>
                {(usage.by_user || []).map((row) => (
                  <tr key={row.user_id}>
                    <td>{row.user_id}</td>
                    <td className="num">{row.total_tokens.toLocaleString()}</td>
                    <td className="num">{row.calls}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </Card>
        </Section>
      )}

      {tab === "audit" && (
        <Section>
          <Card>
            <b>감사 기록 (최근 100건)</b>
            <Muted style={{ margin: "var(--space-2) 0 var(--space-3)" }}>
              누가, 언제, 어떤 앱을 어떤 내용으로 불렀는지 남습니다.
            </Muted>
            <Pre style={{ maxHeight: 460, overflow: "auto" }}>
              {audit
                .map(
                  (row) =>
                    `${row.at}  ${row.actor}  ${row.action}  ${row.target ?? ""}\n    ${JSON.stringify(row.detail)}`
                )
                .join("\n")}
            </Pre>
          </Card>
        </Section>
      )}

      {tab === "notices" && (
        <Section>
          {notices.length === 0 ? (
            <Empty>알림이 없습니다.</Empty>
          ) : (
            notices.map((notice) => (
              <Card key={notice.id} style={{ marginBottom: "var(--space-3)" }}>
                <Row between>
                  <b>{notice.title}</b>
                  {!notice.read && <Badge tone="accent">읽지 않음</Badge>}
                </Row>
                <Lines boxed style={{ marginTop: "var(--space-2)" }}>
                  {notice.body}
                </Lines>
                <Muted style={{ marginTop: "var(--space-2)" }}>{notice.at}</Muted>
              </Card>
            ))
          )}
        </Section>
      )}
    </>
  );
}
