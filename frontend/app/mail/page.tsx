"use client";

import { useEffect, useState } from "react";
import { Mail, MailSummary, mailApi } from "@/lib/apps";

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
      <h3>메일함</h3>
      <p className="muted">
        사내 메일 앱이 보낸 메일과 회신 여부입니다. 회신이 없는 사람에게 리마인드를
        보낼 수 있습니다.
      </p>

      {connection && !connection.sends_real_mail && (
        <div className="box" style={{ borderColor: "#f0c36d", background: "#fffbeb" }}>
          지금은 <b>가짜 메일함</b>입니다. 메일이 실제로 나가지 않고 여기에만 쌓입니다.
          회사에서는 <code>.env</code> 의 <code>MAIL_ADAPTER</code> 를 사내 메일로 바꿉니다.
        </div>
      )}

      {summary && (
        <div className="box row" style={{ gap: 20 }}>
          <span>보낸 메일 <b>{summary.sent_count}</b></span>
          <span>회신 <b>{summary.replied_count}</b></span>
          <span>미회신 <b>{summary.unreplied_count}</b></span>
          <span style={{ color: summary.overdue_count ? "#b42318" : undefined }}>
            기한 지남 <b>{summary.overdue_count}</b>
          </span>
          <button onClick={remind} style={{ marginLeft: "auto" }}>
            미회신자에게 리마인드
          </button>
        </div>
      )}

      {message && <p className="muted">{message}</p>}

      {mails.length === 0 && (
        <div className="box muted">
          보낸 메일이 없습니다. &quot;내 에이전트&quot; 화면에서 회의록 정리를
          요청하거나, <code>python scripts/demo_scenario.py</code> 로 시나리오를
          한 번 돌려 보세요.
        </div>
      )}

      {mails.map((mail) => (
        <div className="box" key={mail.id}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <b>
              {mail.kind === "reminder" ? "🔔 " : "📧 "}
              {mail.subject}
            </b>
            <span className="tag" style={{ color: mail.replied ? "#067647" : "#b42318" }}>
              {mail.replied ? "회신 완료" : "회신 대기"}
            </span>
          </div>
          <div className="muted">
            {mail.to_name} &lt;{mail.to_addr}&gt; · 보낸 날짜 {mail.sent_at.slice(0, 10)}
            {dueLabel(mail) && ` · ${dueLabel(mail)}`}
            {mail.reminder_count > 0 && ` · 리마인드 ${mail.reminder_count}회`}
          </div>
          <div className="row" style={{ marginTop: 8 }}>
            <button className="ghost" onClick={() => show(mail.id)}>
              {openId === mail.id ? "본문 닫기" : "본문 보기"}
            </button>
            {!mail.replied && (
              <button className="ghost" onClick={() => mailApi.markReplied(mail.id).then(reload)}>
                회신 온 것으로 표시
              </button>
            )}
          </div>
          {openId === mail.id && <pre style={{ marginTop: 12 }}>{body}</pre>}
        </div>
      ))}
    </>
  );
}
