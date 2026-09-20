// 백엔드 호출을 한 곳에 모아 둡니다.
// 로그인 토큰은 브라우저에 저장했다가 모든 요청에 붙입니다.
// 사내 SSO 로 바꿀 때는 이 파일과 backend/app/auth/backend.py 만 손보면 됩니다.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

const TOKEN_KEY = "wfa_token";
const USER_KEY = "wfa_user";

export function getToken(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(TOKEN_KEY) || "";
}

export function getSession(): { user_id: string; is_admin: boolean } | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(USER_KEY);
  return raw ? JSON.parse(raw) : null;
}

export function saveSession(token: string, user_id: string, is_admin: boolean) {
  window.localStorage.setItem(TOKEN_KEY, token);
  window.localStorage.setItem(USER_KEY, JSON.stringify({ user_id, is_admin }));
}

export function clearSession() {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(init.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
    ...((init.headers as Record<string, string>) || {}),
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (response.status === 401) {
    clearSession();
    if (typeof window !== "undefined" && !location.pathname.startsWith("/login")) {
      location.href = "/login";
    }
    throw new Error("로그인이 필요합니다.");
  }
  if (!response.ok) {
    let detail = await response.text();
    try {
      detail = JSON.parse(detail).detail ?? detail;
    } catch {
      /* 본문이 JSON 이 아니면 그대로 씁니다 */
    }
    throw new Error(detail);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export type AppTool = { name: string; description: string };
export type App = {
  id: string;
  slug: string;
  name: string;
  description: string;
  usage_hint: string;
  category: string;
  capability_tag: string;
  owner: string;
  owner_dept: string;
  owner_contact: string;
  owner_user_id: string;
  icon: string;
  endpoint: string;
  status: string;
  visibility: "private" | "pending" | "approved";
  requires_confirmation: boolean;
  runtime_location: "server" | "pc";
  source_type: "manual" | "github" | "zip";
  source_url: string;
  package_version: string;
  last_error: string;
  tools: AppTool[];
};
export type Card = {
  id: string;
  title: string;
  description: string;
  icon: string;
  prompt_template: string;
  app_ids: string[];
  recipe_id: string | null;
  pinned: boolean;
};
export type RecipeStep = {
  app_id: string;
  app_name: string;
  tool: string;
  arguments: Record<string, unknown>;
  title: string;
};
export type Recipe = {
  id: string;
  title: string;
  description: string;
  icon: string;
  steps: RecipeStep[];
  final_instruction: string;
  run_count: number;
  last_run_at: string | null;
  // 실행할 때 채워 넣어야 하는 값들. 서버가 {{변수}} 를 읽어 알려 줍니다.
  variables: string[];
};
export type Schedule = {
  id: string;
  title: string;
  description: string;
  enabled: boolean;
  trigger: "once" | "daily" | "interval";
  run_at: string | null;
  at_time: string;
  weekdays: number[];
  interval_minutes: number;
  lead_minutes: number;
  action: "request" | "recipe" | "tool";
  request_text: string;
  recipe_id: string | null;
  variables: Record<string, string>;
  pre_approved: boolean;
  next_run_at: string | null;
  last_run_id: string;
  last_status: string;
  last_error: string;
  run_count: number;
  when_text: string;
};
export type DashboardWidget = {
  key: string;
  title: string;
  icon: string;
  status: "ok" | "empty" | "missing" | "error";
  app: string;
  text: string;
  hint: string;
};
export type Dashboard = {
  user_id: string;
  widgets: DashboardWidget[];
  schedules: {
    id: string;
    title: string;
    when_text: string;
    next_run_at: string;
    last_status: string;
  }[];
  runs: { id: string; request_text: string; status: string; created_at: string }[];
  recipes: { id: string; title: string; icon: string; run_count: number }[];
  ranking: { rank: number; name: string; success_calls: number }[];
};
export type PlanStep = {
  app: string;
  tool: string;
  why: string;
  requires_confirmation: boolean;
};
export type Run = {
  id: string;
  request_text: string;
  status:
    | "queued"
    | "planning"
    | "awaiting_approval"
    | "running"
    | "succeeded"
    | "failed"
    | "rejected";
  plan: PlanStep[];
  plan_summary: string;
  needs_approval: boolean;
  steps: { app: string; tool: string; error: boolean }[];
  result_text: string;
  error: string;
};
export type Form = {
  id: string;
  name: string;
  description: string;
  category: string;
  filename: string;
  is_text: boolean;
  uploaded_by: string;
};
export type Ranking = {
  period: string;
  ranking: {
    rank: number;
    name: string;
    success_calls: number;
    total_calls: number;
    success_rate: number;
    user_count: number;
    owner: { user_id: string; name: string; dept: string; contact: string };
  }[];
};
export type Usage = {
  period: string;
  mine: { total_tokens: number; calls: number };
  all_users?: { total_tokens: number; calls: number };
  by_user?: { user_id: string; total_tokens: number; calls: number }[];
};
export type Notice = {
  id: string;
  kind: string;
  title: string;
  body: string;
  read: boolean;
  at: string;
};

export type Note = {
  id: string;
  title: string;
  body: string;
  pinned: boolean;
  updated_at: string;
};
export type DrawingSummary = {
  id: string;
  title: string;
  width: number;
  height: number;
  updated_at: string;
};
export type DrawingFull = DrawingSummary & { image: string };

// ── 앱 의견(VOC)과 앱 버전 ──────────────────────────────────────────
export type VocKind = "bug" | "idea" | "question";
export type VocStatus = "open" | "in_progress" | "done" | "wontfix";
export type Voc = {
  id: string;
  app_id: string;
  app_name: string;
  owner_user_id: string;
  user_id: string;
  user_name: string;
  kind: VocKind;
  rating: number;
  title: string;
  body: string;
  app_version: string;
  run_id: string;
  status: VocStatus;
  reply: string;
  replied_by: string;
  replied_at: string | null;
  created_at: string;
};
/** 앱스토어 목록에 «의견 3» 을 붙이려고 한 번에 세어 오는 값 */
export type VocCount = {
  total: number;
  open: number;
  rating: number;
  rating_count: number;
};
export type AppVersion = {
  id: string;
  app_id: string;
  version: string;
  note: string;
  endpoint: string;
  source_type: string;
  source_url: string;
  source_ref: string;
  tool_count: number;
  is_current: boolean;
  rolled_back_from: string;
  created_by: string;
  created_at: string;
};

export type Me = {
  user_id: string;
  name: string;
  dept: string;
  contact: string;
  is_admin: boolean;
  /** 개인 계정에 저장된 화면 테마 */
  theme: string;
};

export const api = {
  login: (user_id: string, password: string) =>
    request<{ token: string; user_id: string; name: string; is_admin: boolean }>(
      "/api/auth/login",
      { method: "POST", body: JSON.stringify({ user_id, password }) }
    ),

  me: () => request<Me>("/api/auth/me"),
  saveSettings: (body: { theme?: string }) =>
    request<Me>("/api/auth/me/settings", {
      method: "PUT",
      body: JSON.stringify(body),
    }),

  listApps: (mine = false) => request<App[]>(`/api/apps?mine=${mine}`),
  registerApp: (body: Record<string, unknown>) =>
    request<App>("/api/apps", { method: "POST", body: JSON.stringify(body) }),
  registerZip: (form: FormData) =>
    request<App>("/api/apps/from-zip", { method: "POST", body: form }),
  registerGithub: (form: FormData) =>
    request<App>("/api/apps/from-github", { method: "POST", body: form }),
  refreshApp: (id: string) => request<App>(`/api/apps/${id}/refresh`, { method: "POST" }),
  submitApp: (id: string) => request<App>(`/api/apps/${id}/submit`, { method: "POST" }),
  approveApp: (id: string) => request<App>(`/api/apps/${id}/approve`, { method: "POST" }),
  rejectApp: (id: string) => request<App>(`/api/apps/${id}/reject`, { method: "POST" }),
  listPending: () => request<App[]>("/api/apps/pending"),

  listCards: () => request<Card[]>("/api/cards"),
  createCard: (body: Record<string, unknown>) =>
    request<Card>("/api/cards", { method: "POST", body: JSON.stringify(body) }),
  deleteCard: (id: string) => request<void>(`/api/cards/${id}`, { method: "DELETE" }),

  listForms: () => request<Form[]>("/api/forms"),
  uploadForm: (form: FormData) =>
    request<Form>("/api/forms", { method: "POST", body: form }),
  deleteForm: (id: string) => request<void>(`/api/forms/${id}`, { method: "DELETE" }),
  formDownloadUrl: (id: string) => `${API_BASE}/api/forms/${id}/download`,

  createRun: (body: Record<string, unknown>) =>
    request<Run>("/api/runs", { method: "POST", body: JSON.stringify(body) }),
  getRun: (id: string) => request<Run>(`/api/runs/${id}`),
  approveRun: (id: string) => request<Run>(`/api/runs/${id}/approve`, { method: "POST" }),
  rejectRun: (id: string) => request<Run>(`/api/runs/${id}/reject`, { method: "POST" }),

  listRecipes: () => request<Recipe[]>("/api/recipes"),
  createRecipeFromRun: (body: Record<string, unknown>) =>
    request<Recipe>("/api/recipes/from-run", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  deleteRecipe: (id: string) =>
    request<void>(`/api/recipes/${id}`, { method: "DELETE" }),
  runRecipe: (id: string, variables: Record<string, string>) =>
    request<Run>(`/api/recipes/${id}/run`, {
      method: "POST",
      body: JSON.stringify({ variables }),
    }),

  listSchedules: (includeDone = false) =>
    request<Schedule[]>(`/api/schedules?include_done=${includeDone}`),
  createSchedule: (body: Record<string, unknown>) =>
    request<Schedule>("/api/schedules", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  cancelSchedule: (id: string) =>
    request<Schedule>(`/api/schedules/${id}/cancel`, { method: "POST" }),
  resumeSchedule: (id: string) =>
    request<Schedule>(`/api/schedules/${id}/resume`, { method: "POST" }),
  runScheduleNow: (id: string) =>
    request<Schedule>(`/api/schedules/${id}/run-now`, { method: "POST" }),
  deleteSchedule: (id: string) =>
    request<void>(`/api/schedules/${id}`, { method: "DELETE" }),

  dashboard: () => request<Dashboard>("/api/dashboard"),

  appRanking: () => request<Ranking>("/api/stats/apps"),
  usage: () => request<Usage>("/api/stats/usage"),
  notifications: () => request<Notice[]>("/api/notifications"),
  audit: () => request<Record<string, unknown>[]>("/api/audit?limit=100"),

  // ── 도구 서랍 (메모·그림) ────────────────────────────────────────
  listNotes: () => request<Note[]>("/api/tools/notes"),
  createNote: (body: { title: string; body: string; pinned?: boolean }) =>
    request<Note>("/api/tools/notes", { method: "POST", body: JSON.stringify(body) }),
  updateNote: (id: string, body: { title: string; body: string; pinned?: boolean }) =>
    request<Note>(`/api/tools/notes/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  deleteNote: (id: string) =>
    request<void>(`/api/tools/notes/${id}`, { method: "DELETE" }),

  // ── 앱 의견(VOC) ────────────────────────────────────────────────
  listAppVoc: (appId: string) => request<Voc[]>(`/api/apps/${appId}/voc`),
  sendVoc: (
    appId: string,
    body: { kind: VocKind; title: string; body?: string; rating?: number; run_id?: string }
  ) =>
    request<Voc>(`/api/apps/${appId}/voc`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  vocInbox: (openOnly = false) =>
    request<Voc[]>(`/api/voc/inbox?open_only=${openOnly}`),
  vocSent: () => request<Voc[]>("/api/voc/sent"),
  vocCounts: () => request<Record<string, VocCount>>("/api/voc/counts"),
  answerVoc: (id: string, body: { status?: VocStatus; reply?: string }) =>
    request<Voc>(`/api/voc/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteVoc: (id: string) => request<void>(`/api/voc/${id}`, { method: "DELETE" }),

  // ── 앱 업데이트 ─────────────────────────────────────────────────
  listVersions: (appId: string) => request<AppVersion[]>(`/api/apps/${appId}/versions`),
  updateEndpoint: (
    appId: string,
    body: { endpoint: string; version?: string; note?: string }
  ) =>
    request<App>(`/api/apps/${appId}/update/endpoint`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateFromGithub: (appId: string, form: FormData) =>
    request<App>(`/api/apps/${appId}/update/from-github`, { method: "POST", body: form }),
  updateFromZip: (appId: string, form: FormData) =>
    request<App>(`/api/apps/${appId}/update/from-zip`, { method: "POST", body: form }),
  rollbackVersion: (appId: string, versionId: string) =>
    request<App>(`/api/apps/${appId}/versions/${versionId}/rollback`, { method: "POST" }),

  listDrawings: () => request<DrawingSummary[]>("/api/tools/drawings"),
  getDrawing: (id: string) => request<DrawingFull>(`/api/tools/drawings/${id}`),
  createDrawing: (body: {
    title: string;
    image: string;
    width: number;
    height: number;
  }) =>
    request<DrawingSummary>("/api/tools/drawings", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateDrawing: (
    id: string,
    body: { title: string; image: string; width: number; height: number }
  ) =>
    request<DrawingSummary>(`/api/tools/drawings/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  deleteDrawing: (id: string) =>
    request<void>(`/api/tools/drawings/${id}`, { method: "DELETE" }),
};
