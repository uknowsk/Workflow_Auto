// 공식 앱(사내 메일, 할 일)의 화면용 API.
//
// 이 앱들은 플랫폼 안이 아니라 "등록된 앱"이라서, 백엔드(8000)를 거치지 않고
// 자기 주소로 바로 부릅니다. 주소는 .env 의 NEXT_PUBLIC_MAIL_API /
// NEXT_PUBLIC_TASKS_API 로 바꿉니다.

export const MAIL_API =
  process.env.NEXT_PUBLIC_MAIL_API || "http://localhost:9101";
export const TASKS_API =
  process.env.NEXT_PUBLIC_TASKS_API || "http://localhost:9103";

async function call<T>(base: string, path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${base}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers || {}) },
  });
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.json();
}

export type Mail = {
  id: string;
  thread_key: string;
  to_addr: string;
  to_name: string;
  subject: string;
  kind: "normal" | "reminder";
  reply_due: string;
  sent_at: string;
  adapter: string;
  replied: boolean;
  replied_at: string;
  days_left: number | null;
  overdue: boolean;
  reminder_count: number;
};

export type MailSummary = {
  sent_count: number;
  replied_count: number;
  unreplied_count: number;
  overdue_count: number;
};

export type Task = {
  id: string;
  kind: "task" | "order";
  title: string;
  owner: string;
  owner_email: string;
  orderer: string;
  due: string;
  note: string;
  source: string;
  status: "open" | "done";
  days_left: number | null;
  overdue: boolean;
};

export const mailApi = {
  list: (threadKey = "") =>
    call<{ summary: MailSummary; mails: Mail[] }>(
      MAIL_API,
      `/api/mails?thread_key=${encodeURIComponent(threadKey)}`
    ),
  read: (id: string) =>
    call<{ found: boolean; mail: (Mail & { body: string }) | null }>(
      MAIL_API,
      `/api/mails/${id}`
    ),
  markReplied: (id: string) =>
    call<unknown>(MAIL_API, `/api/mails/${id}/replied`, {
      method: "POST",
      body: JSON.stringify({ body: "화면에서 회신 처리" }),
    }),
  sendReminders: (onlyOverdue: boolean) =>
    call<{ sent_count: number; message: string }>(MAIL_API, "/api/reminders", {
      method: "POST",
      body: JSON.stringify({ only_overdue: onlyOverdue }),
    }),
  connection: () =>
    call<{ adapter: string; sends_real_mail: boolean; note?: string }>(
      MAIL_API,
      "/api/connection"
    ),
};

export const tasksApi = {
  list: (status = "open", kind = "all") =>
    call<{ count: number; tasks: Task[] }>(
      TASKS_API,
      `/api/tasks?status=${status}&kind=${kind}&limit=100`
    ),
  add: (body: Record<string, unknown>) =>
    call<Task>(TASKS_API, "/api/tasks", { method: "POST", body: JSON.stringify(body) }),
  complete: (id: string) =>
    call<unknown>(TASKS_API, `/api/tasks/${id}/complete`, { method: "POST" }),
};
