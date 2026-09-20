"use client";

// 앱스토어 카드에서 열리는 상자 두 개.
//   VocModal    : 이 앱에 의견 남기기 / 남들이 남긴 의견 보기 / (등록자면) 답변
//   UpdateModal : 내 앱을 새 버전으로 올리기 / 버전 이력 / 되돌리기
// 앱스토어 화면이 길어지지 않도록 따로 빼 두었습니다.

import { useCallback, useEffect, useState } from "react";
import { api, type App, type AppVersion, type Voc, type VocKind, type VocStatus } from "@/lib/api";
import { KIND_LABEL, KIND_TONE, STATUS_LABEL, STATUS_TONE, day, stars } from "@/lib/voc";
import {
  Alert,
  Badge,
  Button,
  Empty,
  Field,
  Input,
  Modal,
  Muted,
  Row,
  Select,
  Tag,
  Textarea,
} from "@/components/ui";

const KINDS: VocKind[] = ["bug", "idea", "question"];
const STATUSES: VocStatus[] = ["open", "in_progress", "done", "wontfix"];

/** 의견 한 건. 등록자에게는 답변 칸이 같이 보입니다. 의견함 화면에서도 씁니다. */
export function VocRow({
  voc,
  canAnswer,
  mine,
  showApp,
  onChanged,
}: {
  voc: Voc;
  canAnswer: boolean;
  mine: boolean;
  /** 여러 앱의 의견이 섞여 보이는 곳(의견함)에서는 앱 이름도 보여 줍니다. */
  showApp?: boolean;
  onChanged: () => void;
}) {
  const [reply, setReply] = useState(voc.reply);
  const [open, setOpen] = useState(false);

  const save = async (status: VocStatus) => {
    await api.answerVoc(voc.id, { status, reply });
    setOpen(false);
    onChanged();
  };

  return (
    <div className="ui-voc">
      <div style={{ minWidth: 0 }}>
        <Row style={{ marginBottom: "var(--space-2)" }}>
          <Badge tone={STATUS_TONE[voc.status]}>{STATUS_LABEL[voc.status]}</Badge>
          <Tag>{KIND_LABEL[voc.kind]}</Tag>
          {voc.rating > 0 && <Tag>{stars(voc.rating)}</Tag>}
          {voc.app_version && <Tag>v{voc.app_version} 에서</Tag>}
          {showApp && <Tag>{voc.app_name}</Tag>}
        </Row>
        <h3 className="ui-app__name">{voc.title}</h3>
        {voc.body && <p className="ui-app__desc" style={{ whiteSpace: "pre-wrap" }}>{voc.body}</p>}
        <Muted>
          {voc.user_name || voc.user_id} · {day(voc.created_at)}
        </Muted>

        {voc.reply && !open && (
          <Alert tone="ok" style={{ marginTop: "var(--space-3)", whiteSpace: "pre-wrap" }}>
            답변 · {voc.reply}
          </Alert>
        )}

        {open ? (
          <div style={{ marginTop: "var(--space-3)" }}>
            <Field label="답변" hint="의견을 쓴 사람에게 알림으로 갑니다">
              <Textarea
                rows={3}
                value={reply}
                onChange={(e) => setReply(e.target.value)}
                placeholder="예) v1.2 에서 고쳤습니다. 다시 한 번 해 보시겠어요?"
              />
            </Field>
            <Row>
              {STATUSES.map((s) => (
                <Button key={s} small variant={s === voc.status ? "primary" : "ghost"} onClick={() => save(s)}>
                  {STATUS_LABEL[s]}(으)로
                </Button>
              ))}
              <Button small variant="ghost" onClick={() => setOpen(false)}>
                취소
              </Button>
            </Row>
          </div>
        ) : (
          <Row style={{ marginTop: "var(--space-3)" }}>
            {canAnswer && (
              <Button small variant="ghost" onClick={() => setOpen(true)}>
                답변하기
              </Button>
            )}
            {mine && (
              <Button
                small
                variant="ghost"
                onClick={() => api.deleteVoc(voc.id).then(onChanged)}
              >
                지우기
              </Button>
            )}
          </Row>
        )}
      </div>
    </div>
  );
}

export function VocModal({
  app,
  meId,
  open,
  onClose,
  onChanged,
}: {
  app: App;
  meId: string;
  open: boolean;
  onClose: () => void;
  onChanged: () => void;
}) {
  const [list, setList] = useState<Voc[]>([]);
  const [kind, setKind] = useState<VocKind>("bug");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [rating, setRating] = useState(0);
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);

  const reload = useCallback(() => {
    api
      .listAppVoc(app.id)
      .then(setList)
      .catch((e) => {
        setFailed(true);
        setMessage(String(e));
      });
  }, [app.id]);

  useEffect(() => {
    if (open) reload();
  }, [open, reload]);

  const send = async () => {
    setMessage("");
    setFailed(false);
    try {
      await api.sendVoc(app.id, { kind, title, body, rating });
      setTitle("");
      setBody("");
      setRating(0);
      setMessage("보냈습니다. 이 앱을 올린 분에게 알림이 갑니다.");
      reload();
      onChanged();
    } catch (e) {
      setFailed(true);
      setMessage(String(e));
    }
  };

  const isOwner = app.owner_user_id === meId;

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`${app.name} · 의견`}
      sub="안 되는 점이나 있었으면 하는 기능을 남기면 이 앱을 올린 분에게 바로 전달됩니다."
      footer={
        <>
          <Button onClick={send} disabled={!title.trim()}>
            의견 보내기
          </Button>
          <Button variant="ghost" onClick={onClose}>
            닫기
          </Button>
          {message && (
            <Alert tone={failed ? "crit" : "ok"} style={{ flex: 1, minWidth: 240 }}>
              {message}
            </Alert>
          )}
        </>
      }
    >
      <Field label="어떤 이야기인가요?">
        <Select value={kind} onChange={(e) => setKind(e.target.value as VocKind)}>
          {KINDS.map((k) => (
            <option key={k} value={k}>
              {KIND_LABEL[k]}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="한 줄 요약" hint="이것만 보고도 무슨 일인지 알 수 있게">
        <Input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="예) 첨부가 있는 메일은 보내기가 실패합니다"
        />
      </Field>
      <Field label="자세히" hint="어떤 상황에서 무엇이 어떻게 됐는지">
        <Textarea rows={4} value={body} onChange={(e) => setBody(e.target.value)} />
      </Field>
      <Field label="별점" hint="안 매겨도 됩니다">
        <Row>
          {[1, 2, 3, 4, 5].map((n) => (
            <Button
              key={n}
              small
              variant={rating === n ? "primary" : "ghost"}
              onClick={() => setRating(rating === n ? 0 : n)}
            >
              {"★".repeat(n)}
            </Button>
          ))}
        </Row>
      </Field>

      <h3 style={{ marginTop: "var(--space-6)" }}>이미 올라온 의견 {list.length}건</h3>
      <Muted style={{ marginBottom: "var(--space-3)" }}>
        같은 이야기가 이미 있으면 한 줄 보태 주세요. 중복 제보가 줄어듭니다.
      </Muted>
      {list.length === 0 ? (
        <Empty>아직 올라온 의견이 없습니다.</Empty>
      ) : (
        list.map((voc) => (
          <VocRow
            key={voc.id}
            voc={voc}
            canAnswer={isOwner}
            mine={voc.user_id === meId}
            onChanged={() => {
              reload();
              onChanged();
            }}
          />
        ))
      )}
    </Modal>
  );
}

export function UpdateModal({
  app,
  open,
  onClose,
  onUpdated,
}: {
  app: App;
  open: boolean;
  onClose: () => void;
  onUpdated: () => void;
}) {
  const [versions, setVersions] = useState<AppVersion[]>([]);
  const [endpoint, setEndpoint] = useState(app.endpoint);
  const [version, setVersion] = useState("");
  const [note, setNote] = useState("");
  const [ref, setRef] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState("");
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(() => {
    api.listVersions(app.id).then(setVersions).catch(() => undefined);
  }, [app.id]);

  useEffect(() => {
    if (open) reload();
  }, [open, reload]);

  const done = (text: string) => {
    setMessage(text);
    setFailed(false);
    setNote("");
    reload();
    onUpdated();
  };

  const run = async (work: () => Promise<unknown>, text: string) => {
    setBusy(true);
    setMessage("");
    setFailed(false);
    try {
      await work();
      done(text);
    } catch (e) {
      setFailed(true);
      setMessage(String(e));
    } finally {
      setBusy(false);
    }
  };

  const push = () => {
    if (app.source_type === "github") {
      const form = new FormData();
      form.append("ref", ref);
      form.append("note", note);
      return run(() => api.updateFromGithub(app.id, form), "새 버전을 받아 반영했습니다.");
    }
    if (app.source_type === "zip") {
      if (!file) return;
      const form = new FormData();
      form.append("file", file);
      form.append("note", note);
      return run(() => api.updateFromZip(app.id, form), "새 버전을 올렸습니다.");
    }
    return run(
      () => api.updateEndpoint(app.id, { endpoint, version, note }),
      "새 버전으로 바꿨습니다."
    );
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`${app.name} · 업데이트`}
      sub="바로 반영됩니다. 이력이 남으니 문제가 있으면 아래에서 되돌릴 수 있습니다."
      footer={
        <>
          <Button onClick={push} disabled={busy || (app.source_type === "zip" && !file)}>
            {busy ? "올리는 중…" : "새 버전 올리기"}
          </Button>
          <Button variant="ghost" onClick={onClose}>
            닫기
          </Button>
          {message && (
            <Alert tone={failed ? "crit" : "ok"} style={{ flex: 1, minWidth: 240 }}>
              {message}
            </Alert>
          )}
        </>
      }
    >
      {app.source_type === "github" && (
        <>
          <Muted style={{ marginBottom: "var(--space-4)" }}>
            <code>{app.source_url}</code> 에서 최신 코드를 다시 받아옵니다.
          </Muted>
          <Field label="브랜치나 태그" hint="비우면 기본 브랜치">
            <Input value={ref} onChange={(e) => setRef(e.target.value)} placeholder="main" />
          </Field>
        </>
      )}

      {app.source_type === "zip" && (
        <Field label="새 ZIP 파일" hint="어댑터 폴더를 통째로 압축한 파일">
          <Input
            type="file"
            accept=".zip"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </Field>
      )}

      {app.source_type === "manual" && (
        <>
          <Field label="어댑터 주소" hint="주소가 그대로면 그냥 두세요">
            <Input value={endpoint} onChange={(e) => setEndpoint(e.target.value)} />
          </Field>
          <Field label="버전" hint="예) 1.2">
            <Input value={version} onChange={(e) => setVersion(e.target.value)} />
          </Field>
        </>
      )}

      <Field label="무엇이 바뀌었나요?" hint="이 앱을 쓰는 사람들에게 이 문장이 알림으로 갑니다">
        <Textarea
          rows={3}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="예) 첨부 파일이 있는 메일도 보낼 수 있게 고쳤습니다"
        />
      </Field>

      <h3 style={{ marginTop: "var(--space-6)" }}>버전 이력</h3>
      {versions.length === 0 ? (
        <Empty>아직 이력이 없습니다.</Empty>
      ) : (
        versions.map((v) => (
          <div className="ui-voc" key={v.id}>
            <div style={{ minWidth: 0 }}>
              <Row style={{ marginBottom: "var(--space-2)" }}>
                {v.is_current && <Badge tone="ok">지금 쓰는 버전</Badge>}
                <Tag>{v.version ? `v${v.version}` : "버전 표기 없음"}</Tag>
                <Tag>기능 {v.tool_count}개</Tag>
              </Row>
              <p className="ui-app__desc">{v.note || "변경 내용이 적혀 있지 않습니다."}</p>
              <Muted>
                {v.created_by} · {day(v.created_at)}
              </Muted>
            </div>
            {!v.is_current && (
              <Button
                small
                variant="ghost"
                disabled={busy}
                onClick={() =>
                  run(
                    () => api.rollbackVersion(app.id, v.id),
                    `${v.version ? `v${v.version}` : "이전 버전"} 으로 되돌렸습니다.`
                  )
                }
              >
                이걸로 되돌리기
              </Button>
            )}
          </div>
        ))
      )}
    </Modal>
  );
}
