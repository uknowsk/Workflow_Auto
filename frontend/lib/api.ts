// 백엔드 호출을 한 곳에 모아 둡니다.
// 사용자 구분은 뼈대 단계에서 X-User-Id 헤더 하나로 합니다.
// 사내에 붙일 때는 이 파일과 backend/app/deps.py 만 SSO 로 바꾸면 됩니다.

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";

export function getUserId(): string {
  if (typeof window === "undefined") return "demo";
  return window.localStorage.getItem("userId") || "demo";
}

export function setUserId(value: string) {
  window.localStorage.setItem("userId", value);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-User-Id": getUserId(),
      ...(init.headers || {}),
    },
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${response.status} ${detail}`);
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
  icon: string;
  endpoint: string;
  status: string;
  visibility: "private" | "pending" | "approved";
  owner_user_id: string;
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
  pinned: boolean;
};
export type Run = {
  id: string;
  request_text: string;
  status: "queued" | "running" | "succeeded" | "failed";
  steps: { app: string; tool: string; error: boolean }[];
  result_text: string;
  error: string;
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

export const api = {
  listApps: (mine = false) => request<App[]>(`/api/apps?mine=${mine}`),
  registerApp: (body: Record<string, unknown>) =>
    request<App>("/api/apps", { method: "POST", body: JSON.stringify(body) }),
  refreshApp: (id: string) =>
    request<App>(`/api/apps/${id}/refresh`, { method: "POST" }),
  submitApp: (id: string) =>
    request<App>(`/api/apps/${id}/submit`, { method: "POST" }),
  approveApp: (id: string) =>
    request<App>(`/api/apps/${id}/approve`, { method: "POST" }),
  rejectApp: (id: string) =>
    request<App>(`/api/apps/${id}/reject`, { method: "POST" }),
  listPending: () => request<App[]>("/api/apps/pending"),

  listCards: () => request<Card[]>("/api/cards"),
  createCard: (body: Record<string, unknown>) =>
    request<Card>("/api/cards", { method: "POST", body: JSON.stringify(body) }),
  deleteCard: (id: string) =>
    request<void>(`/api/cards/${id}`, { method: "DELETE" }),

  appRanking: (period = "") =>
    request<Ranking>(`/api/stats/apps${period ? `?period=${period}` : ""}`),

  createRun: (body: Record<string, unknown>) =>
    request<Run>("/api/runs", { method: "POST", body: JSON.stringify(body) }),
  getRun: (id: string) => request<Run>(`/api/runs/${id}`),
};
