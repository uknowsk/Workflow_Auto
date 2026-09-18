"use client";

import { useEffect, useState } from "react";
import { api, Form } from "@/lib/api";

export default function Forms() {
  const [forms, setForms] = useState<Form[]>([]);
  const [name, setName] = useState("");
  const [category, setCategory] = useState("보고");
  const [file, setFile] = useState<File | null>(null);
  const [message, setMessage] = useState("");

  const reload = () => api.listForms().then(setForms).catch((e) => setMessage(String(e)));
  useEffect(() => {
    reload();
  }, []);

  const upload = async () => {
    if (!file || !name) return;
    setMessage("");
    const body = new FormData();
    body.append("name", name);
    body.append("category", category);
    body.append("file", file);
    try {
      await api.uploadForm(body);
      setName("");
      setFile(null);
      reload();
    } catch (e) {
      setMessage(String(e));
    }
  };

  return (
    <>
      <h3>양식 저장소</h3>
      <p className="muted">
        결과물을 채워 넣을 틀을 중앙 서버에 보관합니다. 요청을 실행할 때 양식을
        고르면 오케스트레이터가 그 틀에 맞춰 결과를 작성합니다.
        <br />
        마크다운·텍스트 양식은 자동으로 적용되고, 엑셀·워드는 지금은 보관과
        내려받기까지 됩니다.
      </p>

      <div className="grid">
        {forms.map((form) => (
          <div className="box" key={form.id} style={{ marginBottom: 0 }}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <b>📄 {form.name}</b>
              {form.is_text && <span className="tag">자동 적용</span>}
            </div>
            <div className="muted">
              {form.filename} · {form.category} · 올린 사람 {form.uploaded_by || "-"}
            </div>
            <div className="row" style={{ marginTop: 8 }}>
              <a href={api.formDownloadUrl(form.id)}>
                <button className="ghost">내려받기</button>
              </a>
              <button
                className="ghost"
                onClick={() => api.deleteForm(form.id).then(reload)}
              >
                삭제
              </button>
            </div>
          </div>
        ))}
      </div>

      <h3 style={{ marginTop: 28 }}>양식 올리기</h3>
      <div className="box">
        <label>양식 이름</label>
        <input value={name} onChange={(e) => setName(e.target.value)} />
        <label>분류</label>
        <input value={category} onChange={(e) => setCategory(e.target.value)} />
        <label>파일</label>
        <input type="file" onChange={(e) => setFile(e.target.files?.[0] || null)} />
        <div style={{ marginTop: 12 }}>
          <button onClick={upload} disabled={!file || !name}>
            올리기
          </button>
        </div>
        {message && <p className="muted">{message}</p>}
      </div>
    </>
  );
}
