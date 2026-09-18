"use client";

import { useEffect, useState } from "react";
import { Mail, MailSummary, mailApi } from "@/lib/apps";
import {
  Alert,
  Badge,
  Button,
  Card,
  Empty,
  Muted,
  PageTitle,
  Pre,
  Row,
  Tag,
} from "@/components/ui";

function dueLabel(mail: Mail) {
  if (mail.replied) return "";
  if (!mail.reply_due) return "회신 기한 없음";
  if (mail.days_left === null) return "";
  if (mail.days_left < 0) return `회신 기한 ${-mail.days_left}일 지남`;
  if (mail.days_left === 0) return "회신 기한 오늘";
  return `회신 기한 ${mail.days_left}일 남음`;
}

export default function MailBox() {
  const [mails, setMails] = useState<Mail[]>([]);
  const [summary, setSummary] = useState<MailSummary | null>(null);
  const [connection, setConnection] = useState<{ adapter: string; sends_real_mail: boolean } | null>(
    null
  );
  const [openId, setOpenId] = useState("");
  const [body, setBody] = useState("");
  const [message, setMessage] = useState("");

  const reload = () =>
    mailApi
      .list()
      .then((data) => {
        setMails(data.mails);
        setSummary(data.summary);
      })
      .catch((e) => setMessage(String(e)));

  useEffect(() => {
    reload();
    mailApi.connection().then(setConnection).catch(() => setConnection(null));
  }, []);

  const show = async (id: string) => {
    if (openId === id) {
      setOpenId("");
      return;
    }
    const data = await mailApi.read(id);
    setBody(data.mail?.body || "");
    setOpenId(id);
  };

  const remind = async () => {
    setMessage("");
    try {
      const result = await mailApi.sendReminders(false);
      setMessage(result.message);
      reload();
    } catch (e) {
      setMessage(String(e));
    }
  };

  return (
    <>
      <PageTitle
        title="메일함"
        sub="사내 메일 앱이 보낸 메일과 회신 여부입니다. 회신이 없는 사람에게 리마인드를 보낼 수 있습니다."
      />

      {connection && !connection.sends_real_mail && (
        <Alert tone="warn" style={{ marginBottom: "var(--space-4)" }}>
          지금은 <b>가짜 메일함</b>입니다. 메일이 실제로 나가지 않고 여기에만 쌓입니다.
          회사에서는 <code>.env</code> 의 <code>MAIL_ADAPTER</code> 를 사내 메일로 바꿉니다.
        </Alert>
      )}

      {summary && (
        <Card quiet style={{ marginBottom: "var(--space-4)" }}>
          <Row between nowrap>
            <Row>
              <Tag>보낸 메일 {summary.sent_count}</Tag>
              <Badge tone="ok">회신 {summary.replied_count}</Badge>
              <Badge tone={summary.unreplied_count ? "warn" : "neutral"}>
                미회신 {summary.unreplied_count}
              </Badge>
              <Badge tone={summary.overdue_count ? "crit" : "neutral"}>
                기한 지남 {summary.overdue_count}
              </Badge>
            </Row>
            <Button onClick={remind} small disabled={!summary.unreplied_count}>
              미회신자에게 리마인드
            </Button>
          </Row>
        </Card>
      )}

      {message && (
        <Alert style={{ marginBottom: "var(--space-4)" }}>{message}</Alert>
      )}

      {mails.length === 0 ? (
        <Empty>
          보낸 메일이 없습니다. &ldquo;내 에이전트&rdquo; 화면에서 회의록 정리를
          요청하거나, <code>python scripts/demo_scenario.py</code> 로 시나리오를 한 번
          돌려 보세요.
        </Empty>
      ) : (
        mails.map((mail) => (
          <Card key={mail.id} style={{ marginBottom: "var(--space-3)" }}>
            <Row between nowrap>
              <b>
                {mail.kind === "reminder" ? "🔔 " : "📧 "}
                {mail.subject}
              </b>
              <Badge tone={mail.replied ? "ok" : "warn"}>
                {mail.replied ? "회신 완료" : "회신 대기"}
              </Badge>
            </Row>
            <Muted style={{ marginTop: "var(--space-1)" }}>
              {mail.to_name} &lt;{mail.to_addr}&gt; · 보낸 날짜 {mail.sent_at.slice(0, 10)}
              {dueLabel(mail) && ` · ${dueLabel(mail)}`}
              {mail.reminder_count > 0 && ` · 리마인드 ${mail.reminder_count}회`}
            </Muted>
            <Row style={{ marginTop: "var(--space-3)" }}>
              <Button variant="ghost" small onClick={() => show(mail.id)}>
                {openId === mail.id ? "본문 닫기" : "본문 보기"}
              </Button>
              {!mail.replied && (
                <Button
                  variant="ghost"
                  small
                  onClick={() => mailApi.markReplied(mail.id).then(reload)}
                >
                  회신 온 것으로 표시
                </Button>
              )}
            </Row>
            {openId === mail.id && (
              <Pre style={{ marginTop: "var(--space-3)" }}>{body}</Pre>
            )}
          </Card>
        ))
      )}
    </>
  );
}
