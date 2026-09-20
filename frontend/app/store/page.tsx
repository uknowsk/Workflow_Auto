"use client";

import { useEffect, useMemo, useState } from "react";
import { api, getSession, App, VocCount } from "@/lib/api";
import { UpdateModal, VocModal } from "@/components/apps/app-modals";
import {
  Alert,
  Badge,
  Button,
  Checkbox,
  Chip,
  Empty,
  Field,
  IconTile,
  Input,
  Modal,
  Muted,
  PageTitle,
  Row,
  Tag,
  type Tone,
} from "@/components/ui";

type FormState = {
  [k: string]: string | boolean;
};

const EMPTY: FormState = {
  slug: "",
  name: "",
  endpoint: "http://localhost:9001/mcp",
  description: "",
  usage_hint: "",
  category: "etc",
  capability_tag: "",
  requires_confirmation: false,
  owner: "",
  owner_dept: "",
  owner_contact: "",
  icon: "🧩",
};

const LABEL: Record<string, string> = {
  private: "개인용",
  pending: "승인 대기",
  approved: "공식",
};

const GRADE_TONE: Record<string, Tone> = {
  private: "neutral",
  pending: "warn",
  approved: "accent",
};

type Filter = "all" | "approved" | "pending" | "private";

const FILTERS: [Filter, string][] = [
  ["all", "전체"],
  ["approved", "공식"],
  ["pending", "승인 대기"],
  ["private", "개인용"],
];

export default function Store() {
  const [apps, setApps] = useState<App[]>([]);
  const [form, setForm] = useState({ ...EMPTY });
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  // 등록은 자주 하는 일이 아니라서, 평소에는 목록만 보이고
  // "＋ 앱 등록"을 눌렀을 때만 이 상자가 열립니다.
  const [registerOpen, setRegisterOpen] = useState(false);
  // 앱마다 «의견 3» 을 붙이려고 한 번에 세어 옵니다.
  const [counts, setCounts] = useState<Record<string, VocCount>>({});
  // 열려 있는 상자. 둘 다 앱 카드의 버튼에서 엽니다.
  const [vocApp, setVocApp] = useState<App | null>(null);
  const [updateApp, setUpdateApp] = useState<App | null>(null);
  const [me, setMe] = useState<{ user_id: string; is_admin: boolean } | null>(null);

  const reload = () => {
    api.vocCounts().then(setCounts).catch(() => undefined);
    return api
      .listApps()
      .then(setApps)
      .catch((e) => {
        setFailed(true);
        setMessage(String(e));
      });
  };

  useEffect(() => {
    setMe(getSession());
    reload();
  }, []);

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return apps.filter((app) => {
      if (filter !== "all" && app.visibility !== filter) return false;
      if (!q) return true;
      return [app.name, app.description, app.usage_hint, app.capability_tag, app.owner]
        .filter(Boolean)
        .some((v) => String(v).toLowerCase().includes(q));
    });
  }, [apps, filter, query]);

  const register = async () => {
    setMessage("");
    setFailed(false);
    try {
      const created = await api.registerApp(form);
      setFailed(created.status !== "active");
      setMessage(
        created.status === "active"
          ? `등록 완료. 기능 ${created.tools.length}개를 자동으로 찾았습니다.`
          : `등록은 됐지만 앱에 접속하지 못했습니다: ${created.last_error}`
      );
      setForm({ ...EMPTY });
      if (created.status === "active") setRegisterOpen(false);
      reload();
    } catch (e) {
      setFailed(true);
      setMessage(String(e));
    }
  };

  const field = (key: string, label: string, hint = "") => (
    <Field label={label} hint={hint} htmlFor={`app-${key}`} key={key}>
      <Input
        id={`app-${key}`}
        value={String(form[key] ?? "")}
        onChange={(e) => setForm({ ...form, [key]: e.target.value })}
      />
    </Field>
  );

  return (
    <>
      {/* 목록이 기본 화면이고, 등록은 이 버튼을 눌렀을 때만 열립니다. */}
      <Row between nowrap style={{ alignItems: "flex-end" }}>
        <div style={{ minWidth: 0 }}>
          <PageTitle
            title="앱스토어"
            sub={`등록된 앱 ${apps.length}개 · 필요한 앱을 찾아 내 에이전트에 담아 두세요`}
          />
        </div>
        <Button
          onClick={() => setRegisterOpen(true)}
          style={{ marginBottom: "var(--space-6)" }}
        >
          ＋ 앱 등록
        </Button>
      </Row>

      <Row style={{ marginBottom: "var(--space-3)" }}>
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="앱 이름, 역할, 등록자로 검색"
          aria-label="앱 검색"
          style={{ maxWidth: 320 }}
        />
        {FILTERS.map(([key, label]) => (
          <Chip key={key} active={filter === key} onClick={() => setFilter(key)}>
            {label}
          </Chip>
        ))}
      </Row>

      {shown.length === 0 ? (
        <Empty>
          조건에 맞는 앱이 없습니다. 위의 «＋ 앱 등록»으로 내 앱을 올릴 수 있어요.
        </Empty>
      ) : (
        <div>
          {shown.map((app) => (
            <div className="ui-app" key={app.id}>
              <IconTile large>{app.icon || "🧩"}</IconTile>
              <div>
                <h3 className="ui-app__name">{app.name}</h3>
                <p className="ui-app__desc">{app.description || app.usage_hint}</p>
                <div className="ui-app__meta">
                  <Badge tone={GRADE_TONE[app.visibility] ?? "neutral"}>
                    {LABEL[app.visibility]}
                  </Badge>
                  {app.capability_tag && <Tag>역할 {app.capability_tag}</Tag>}
                  <Tag>
                    {app.runtime_location === "pc" ? "💻 개인 PC" : "🖥️ 서버"}
                  </Tag>
                  {app.requires_confirmation && (
                    <Badge tone="warn">실행 전 확인</Badge>
                  )}
                  {app.status !== "active" && <Badge tone="crit">{app.status}</Badge>}
                  <Tag>
                    등록자 {app.owner || app.owner_user_id || "-"}
                    {app.owner_contact && ` · ${app.owner_contact}`}
                  </Tag>
                  {counts[app.id]?.total ? (
                    <Tag>
                      의견 {counts[app.id].total}
                      {counts[app.id].open ? ` · 안 끝난 ${counts[app.id].open}` : ""}
                      {counts[app.id].rating ? ` · ★${counts[app.id].rating}` : ""}
                    </Tag>
                  ) : null}
                </div>
                <Row style={{ marginTop: "var(--space-3)" }}>
                  <Button variant="ghost" small onClick={() => setVocApp(app)}>
                    💬 의견
                    {counts[app.id]?.open ? ` ${counts[app.id].open}` : ""}
                  </Button>
                  {(app.owner_user_id === me?.user_id || me?.is_admin) && (
                    <Button variant="ghost" small onClick={() => setUpdateApp(app)}>
                      ⬆ 업데이트
                    </Button>
                  )}
                  <Button variant="ghost" small onClick={() => api.refreshApp(app.id).then(reload)}>
                    새로고침
                  </Button>
                  {app.visibility === "private" && (
                    <Button variant="ghost" small onClick={() => api.submitApp(app.id).then(reload)}>
                      공식 등록 신청
                    </Button>
                  )}
                </Row>
              </div>
              <div className="ui-stat">
                <b>{app.tools.length}</b>
                기능
                {app.package_version && (
                  <>
                    <br />v{app.package_version}
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal
        open={registerOpen}
        onClose={() => setRegisterOpen(false)}
        title="내 앱 등록하기"
        sub="처음에는 나만 쓰는 상태로 저장됩니다. 나중에 «공식 등록 신청»을 누르면 관리자 승인으로 넘어갑니다."
        footer={
          <>
            <Button onClick={register} disabled={!form.slug || !form.name}>
              등록하기
            </Button>
            <Button variant="ghost" onClick={() => setRegisterOpen(false)}>
              취소
            </Button>
            {message && (
              <Alert tone={failed ? "crit" : "ok"} style={{ flex: 1, minWidth: 240 }}>
                {message}
              </Alert>
            )}
          </>
        }
      >
        <div>
          <Muted style={{ marginBottom: "var(--space-4)" }}>
            내 앱을 고칠 필요는 없습니다. <code>templates/</code> 의 어댑터를 복사해
            실행한 뒤, 그 주소(<code>.../mcp</code>)를 여기에 넣으면 됩니다. 방법은{" "}
            <code>docs/WRAPPER_PROMPT.md</code> 참고.
          </Muted>

          {field("slug", "앱 ID", "영문 소문자와 - 만. 예) rag-policy")}
          {field("name", "앱 이름")}
          {field("endpoint", "어댑터 주소", "MCP 주소. 보통 /mcp 로 끝납니다")}
          {field("usage_hint", "언제 쓰는 앱인가요?", "오케스트레이터가 이 문장을 보고 고릅니다")}
          {field("capability_tag", "역할 태그", "같은 일을 하는 앱끼리 같은 값. 예) 사내규정검색")}
          {field("description", "설명")}
          {field("category", "분류")}
          {field("owner", "등록자 이름", "앱이 고장났을 때 연락할 사람")}
          {field("owner_dept", "등록자 소속")}
          {field("owner_contact", "연락처", "메일 또는 사내 메신저")}
          {field("icon", "아이콘")}

          <Checkbox
            checked={Boolean(form.requires_confirmation)}
            onChange={(e) =>
              setForm({ ...form, requires_confirmation: e.target.checked })
            }
            label="메일 발송·결재 상신처럼 되돌릴 수 없는 일을 합니다 (실행 전 확인을 받습니다)"
          />

        </div>
      </Modal>

      {vocApp && (
        <VocModal
          app={vocApp}
          meId={me?.user_id || ""}
          open
          onClose={() => setVocApp(null)}
          onChanged={reload}
        />
      )}
      {updateApp && (
        <UpdateModal
          app={updateApp}
          open
          onClose={() => setUpdateApp(null)}
          onUpdated={reload}
        />
      )}
    </>
  );
}
