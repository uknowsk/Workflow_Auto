// 공식 앱(사내 메일, 할 일, 가전 신제품 조사)의 화면용 API.
//
// 이 앱들은 플랫폼 안이 아니라 "등록된 앱"이라서, 백엔드(8000)를 거치지 않고
// 자기 주소로 바로 부릅니다. 주소는 .env 의 NEXT_PUBLIC_MAIL_API /
// NEXT_PUBLIC_TASKS_API 로 바꿉니다.

export const MAIL_API =
  process.env.NEXT_PUBLIC_MAIL_API || "http://localhost:9101";
export const TASKS_API =
  process.env.NEXT_PUBLIC_TASKS_API || "http://localhost:9103";
export const APPLIANCE_API =
  process.env.NEXT_PUBLIC_APPLIANCE_API || "http://localhost:9119";

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

// ── 가전 신제품 조사 ────────────────────────────────────────────────────
export type Maker = { name: string; site: string };
export type GlobalBrand = { name: string; tier: string };

export type ApplianceCatalog = {
  // 영향력 기준 글로벌 탑 20 (대륙별 탑 5 아님 — 대륙은 홈페이지·통화 선택용).
  global_brands: GlobalBrand[];
  regions: { key: string; label: string; currency: string; makers: Maker[] }[];
  categories: {
    key: string;
    label: string;
    bands: { label: string; min_usd: number; max_usd: number | null }[];
  }[];
  search_enabled: boolean;
  llm_enabled: boolean;
};

export type Product = {
  id: string;
  url: string;
  maker: string;
  region: string;
  category: string;
  name: string;
  model: string;
  price: number | null;
  currency: string;
  price_usd: number | null;
  band: string;
  image: string;
  release_date: string;
  is_new: boolean;
  new_reason: string;
  pods: string[];
  pod_method: "llm" | "rule";
  ai_features: string[];
  ai_method: "llm" | "rule";
  energy_rating: string;
  specs: Record<string, string>;
  features: string[];
  first_seen: string;
  last_seen: string;
  found_via: string;
};

export type PriceBand = {
  label: string;
  min_usd: number | null;
  max_usd: number | null;
  count: number;
  median_usd: number | null;
  makers: Record<string, number>;
  products: Product[];
};

export type Comparison = {
  total: number;
  mode: "fixed" | "quantile";
  bands: PriceBand[];
  unpriced: Product[];
  spec_keys: string[];
};

export type Source = {
  id: string;
  maker: string;
  region: string;
  category: string;
  type: "sitemap" | "listing" | "search" | "manual";
  url: string;
  hits: number;
  score: number;
  last_checked: string;
};

export type Watch = {
  id: string;
  region: string;
  category: string;
  makers: string[];
  every_hours: number;
  last_run: string;
  last_result: string;
};

export type ScanResult = {
  ok: boolean;
  error?: string;
  product_count: number;
  new_count: number;
  log: string[];
};

export type TrendItem = { title: string; url: string; published_at: string };
export type TrendSignal = {
  maker: string;
  category: string;
  news: (TrendItem & { source: string })[];
  videos: (TrendItem & { channel: string })[];
  youtube_enabled: boolean;
};
export type TrendResult = {
  ok: boolean;
  error?: string;
  youtube_enabled: boolean;
  signals: TrendSignal[];
};

const qs = (params: Record<string, string | boolean | string[]>) =>
  new URLSearchParams(
    Object.entries(params).map(([k, v]) => [k, Array.isArray(v) ? v.join(",") : String(v)])
  ).toString();

export const applianceApi = {
  catalog: () => call<ApplianceCatalog>(APPLIANCE_API, "/api/catalog"),
  setMakers: (region: string, makers: Maker[]) =>
    call<{ ok: boolean; makers: Maker[] }>(APPLIANCE_API, "/api/makers", {
      method: "POST",
      body: JSON.stringify({ region, makers }),
    }),
  scan: (region: string, category: string, makers: string[], maxPerMaker: number) =>
    call<ScanResult>(APPLIANCE_API, "/api/scan", {
      method: "POST",
      body: JSON.stringify({ region, category, makers, max_per_maker: maxPerMaker }),
    }),
  trends: (region: string, category: string, makers: string[]) =>
    call<TrendResult>(APPLIANCE_API, "/api/trends", {
      method: "POST",
      body: JSON.stringify({ region, category, makers }),
    }),
  compare: (region: string, category: string, makers: string[], mode: string, onlyNew: boolean) =>
    call<Comparison>(
      APPLIANCE_API,
      `/api/compare?${qs({ region, category, makers, mode, only_new: onlyNew })}`
    ),
  sources: (region: string, category: string) =>
    call<{ count: number; sources: Source[] }>(
      APPLIANCE_API,
      `/api/sources?${qs({ region, category })}`
    ),
  addSource: (body: { maker: string; region: string; category: string; url: string }) =>
    call<{ ok: boolean }>(APPLIANCE_API, "/api/sources", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  watches: () => call<{ watches: Watch[] }>(APPLIANCE_API, "/api/watches"),
  addWatch: (body: { region: string; category: string; makers: string[]; every_hours: number }) =>
    call<{ ok: boolean }>(APPLIANCE_API, "/api/watches", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  runWatch: (id: string) =>
    call<ScanResult>(APPLIANCE_API, `/api/watches/${id}/run`, { method: "POST" }),
  deleteWatch: (id: string) =>
    call<{ ok: boolean }>(APPLIANCE_API, `/api/watches/${id}`, { method: "DELETE" }),
};
