"use client";

import { useEffect, useState } from "react";
import { Task, tasksApi } from "@/lib/apps";

function dueLabel(task: Task) {
  if (!task.due) return "기한 없음";
  if (task.days_left === null) return task.due;
  if (task.days_left < 0) return `${task.due} (${-task.days_left}일 지남)`;
  if (task.days_left === 0) return `${task.due} (오늘)`;
  return `${task.due} (${task.days_left}일 남음)`;
}

export default function Tasks() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [status, setStatus] = useState("open");
  const [kind, setKind] = useState("all");
  const [title, setTitle] = useState("");
  const [owner, setOwner] = useState("");
  const [due, setDue] = useState("");
  const [orderer, setOrderer] = useState("");
  const [message, setMessage] = useState("");

  const reload = () =>
    tasksApi
      .list(status, kind)
      .then((data) => setTasks(data.tasks))
      .catch((e) => setMessage(String(e)));

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, kind]);

  const add = async () => {
    if (!title) return;
    setMessage("");
    try {
      await tasksApi.add({
        title,
        owner,
        due,
        orderer,
        kind: orderer ? "order" : "task",
      });
      setTitle("");
      setOwner("");
      setDue("");
      setOrderer("");
      reload();
    } catch (e) {
      setMessage(String(e));
    }
  };

  return (
    <>
      <h3>할 일 / 수명업무</h3>
      <p className="muted">
        회의록에서 자동으로 등록된 할 일과, 상급자에게 지시받은 수명업무를 한
        곳에서 봅니다. 기한이 지난 것은 빨갛게 표시됩니다.
      </p>

      <div className="box row">
        <select value={status} onChange={(e) => setStatus(e.target.value)} style={{ width: 140 }}>
          <option value="open">아직 안 한 일</option>
          <option value="done">끝낸 일</option>
          <option value="all">전부</option>
        </select>
        <select value={kind} onChange={(e) => setKind(e.target.value)} style={{ width: 140 }}>
          <option value="all">할 일 + 수명업무</option>
          <option value="task">할 일만</option>
          <option value="order">수명업무만</option>
        </select>
        <span className="muted">{tasks.length}건</span>
      </div>

      {message && <p className="muted">{message}</p>}

      {tasks.length === 0 && <div className="box muted">해당하는 일이 없습니다.</div>}

      {tasks.map((task) => (
        <div className="box" key={task.id}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <b>
              {task.kind === "order" ? "📌 " : "✅ "}
              {task.title}
            </b>
            <span className="tag" style={{ color: task.overdue ? "#b42318" : undefined }}>
              {dueLabel(task)}
            </span>
          </div>
          <div className="muted">
            담당 {task.owner || "미정"}
            {task.orderer && ` · 지시 ${task.orderer}`}
            {task.source && ` · 출처 ${task.source}`}
            {task.status === "done" && " · 완료"}
          </div>
          {task.status === "open" && (
            <div className="row" style={{ marginTop: 8 }}>
              <button className="ghost" onClick={() => tasksApi.complete(task.id).then(reload)}>
                완료
              </button>
            </div>
          )}
        </div>
      ))}

      <h3 style={{ marginTop: 28 }}>직접 추가</h3>
      <div className="box">
        <label>할 일</label>
        <input value={title} onChange={(e) => setTitle(e.target.value)} />
        <div className="grid" style={{ marginTop: 4 }}>
          <div>
            <label>담당자</label>
            <input value={owner} onChange={(e) => setOwner(e.target.value)} />
          </div>
          <div>
            <label>기한 (2026-09-25, 내일, 3일 뒤 …)</label>
            <input value={due} onChange={(e) => setDue(e.target.value)} />
          </div>
          <div>
            <label>지시한 상급자 (적으면 수명업무가 됩니다)</label>
            <input value={orderer} onChange={(e) => setOrderer(e.target.value)} />
          </div>
        </div>
        <div style={{ marginTop: 12 }}>
          <button onClick={add} disabled={!title}>
            추가
          </button>
        </div>
      </div>
    </>
  );
}
