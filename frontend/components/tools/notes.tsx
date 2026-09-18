"use client";

// 간단 메모.
//
// 계정에 저장하므로 회사 PC 에서 적어 둔 것이 다른 자리에서도 보입니다.
// 타이핑을 멈추면 1.2초 뒤 스스로 저장합니다. "저장을 깜빡해서 날렸다"가
// 메모에서는 제일 흔한 사고라서요. 로그인 전이거나 서버가 안 뜨면 저장은
// 실패하지만 적던 내용은 화면에 그대로 남습니다.

import { useCallback, useEffect, useRef, useState } from "react";
import { api, Note } from "@/lib/api";
import { Alert, Button, Empty, Input, Muted, Row, Textarea } from "@/components/ui";

export default function NotesTool() {
  const [notes, setNotes] = useState<Note[]>([]);
  const [openId, setOpenId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [state, setState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [error, setError] = useState("");
  const dirtyRef = useRef(false);
  const timerRef = useRef<number | null>(null);

  const reload = useCallback(
    () =>
      api
        .listNotes()
        .then(setNotes)
        .catch((problem) => setError(String(problem instanceof Error ? problem.message : problem))),
    []
  );

  useEffect(() => {
    reload();
  }, [reload]);

  const persist = useCallback(async () => {
    if (!dirtyRef.current) return;
    if (!title.trim() && !body.trim()) return;
    dirtyRef.current = false;
    setState("saving");
    try {
      const payload = { title: title.trim() || "제목 없음", body };
      if (openId) {
        await api.updateNote(openId, payload);
      } else {
        const created = await api.createNote(payload);
        setOpenId(created.id);
      }
      setState("saved");
      setError("");
      reload();
    } catch (problem) {
      setState("error");
      setError(String(problem instanceof Error ? problem.message : problem));
    }
  }, [title, body, openId, reload]);

  // 타이핑이 멈추면 저장합니다.
  useEffect(() => {
    if (!dirtyRef.current) return;
    if (timerRef.current) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(persist, 1200);
    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current);
    };
  }, [title, body, persist]);

  const touch = () => {
    dirtyRef.current = true;
    setState("idle");
  };

  const openNote = (note: Note) => {
    setOpenId(note.id);
    setTitle(note.title);
    setBody(note.body);
    dirtyRef.current = false;
    setState("idle");
  };

  const newNote = () => {
    setOpenId(null);
    setTitle("");
    setBody("");
    dirtyRef.current = false;
    setState("idle");
  };

  const remove = async (id: string) => {
    if (!window.confirm("이 메모를 지울까요?")) return;
    try {
      await api.deleteNote(id);
      if (openId === id) newNote();
      reload();
    } catch (problem) {
      setError(String(problem instanceof Error ? problem.message : problem));
    }
  };

  const stateText =
    state === "saving"
      ? "저장 중…"
      : state === "saved"
        ? "저장했습니다"
        : state === "error"
          ? "저장하지 못했습니다"
          : dirtyRef.current
            ? "적는 중"
            : "";

  return (
    <div className="tool-note">
      <Row between>
        <Button small variant="ghost" onClick={newNote}>
          새 메모
        </Button>
        <Muted>{stateText}</Muted>
      </Row>

      <Input
        value={title}
        placeholder="제목"
        onChange={(event) => {
          setTitle(event.target.value);
          touch();
        }}
      />
      <Textarea
        value={body}
        rows={10}
        placeholder="여기에 적으세요. 잠시 멈추면 알아서 저장됩니다."
        onChange={(event) => {
          setBody(event.target.value);
          touch();
        }}
        onBlur={persist}
      />

      {error && <Alert tone="crit">{error}</Alert>}

      {notes.length ? (
        <div className="ui-rows">
          {notes.map((note) => (
            <div key={note.id} className="tool-note__row">
              <button
                type="button"
                className="tool-note__name"
                aria-current={openId === note.id ? "true" : undefined}
                onClick={() => openNote(note)}
              >
                {note.title || "제목 없음"}
              </button>
              <Muted>{new Date(note.updated_at).toLocaleString("ko-KR")}</Muted>
              <Button variant="danger" small onClick={() => remove(note.id)}>
                지우기
              </Button>
            </div>
          ))}
        </div>
      ) : (
        <Empty>아직 메모가 없습니다. 위에 적으면 계정에 저장됩니다.</Empty>
      )}
    </div>
  );
}
