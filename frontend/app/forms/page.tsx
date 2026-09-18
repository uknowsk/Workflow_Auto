"use client";

import { useEffect, useState } from "react";
import { api, Form } from "@/lib/api";
import {
  Alert,
  Badge,
  Button,
  Card,
  Empty,
  Field,
  Grid,
  IconTile,
  Input,
  LinkButton,
  Muted,
  PageTitle,
  Row,
  Section,
  SectionHead,
} from "@/components/ui";

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
      <PageTitle
        title="양식 저장소"
        sub="결과물을 채워 넣을 틀을 중앙 서버에 보관합니다."
      />

      <Muted style={{ marginBottom: "var(--space-5)" }}>
        요청을 실행할 때 양식을 고르면 오케스트레이터가 그 틀에 맞춰 결과를
        작성합니다. 마크다운·텍스트 양식은 자동으로 적용되고, 엑셀·워드는 지금은
        보관과 내려받기까지 됩니다.
      </Muted>

      {forms.length === 0 ? (
        <Empty>아직 올린 양식이 없습니다. 아래에서 파일을 올려 보세요.</Empty>
      ) : (
        <Grid>
          {forms.map((form) => (
            <Card key={form.id} hoverable className="ui-card--stack">
              <Row between nowrap>
                <Row nowrap>
                  <IconTile>📄</IconTile>
                  <b>{form.name}</b>
                </Row>
                {form.is_text && <Badge tone="accent">자동 적용</Badge>}
              </Row>
              <Muted>
                {form.filename} · {form.category} · 올린 사람 {form.uploaded_by || "-"}
              </Muted>
              <Row style={{ marginTop: "var(--space-2)" }}>
                <LinkButton href={api.formDownloadUrl(form.id)} small>
                  내려받기
                </LinkButton>
                <Button
                  variant="danger"
                  small
                  onClick={() => api.deleteForm(form.id).then(reload)}
                >
                  삭제
                </Button>
              </Row>
            </Card>
          ))}
        </Grid>
      )}

      <Section>
        <SectionHead label="양식 올리기" />
        <Card className="ui-card--pad-lg">
          <Field label="양식 이름" htmlFor="form-name">
            <Input
              id="form-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </Field>
          <Field label="분류" hint="예) 보고, 결재, 회의" htmlFor="form-category">
            <Input
              id="form-category"
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            />
          </Field>
          <Field label="파일" htmlFor="form-file">
            <Input
              id="form-file"
              type="file"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
            />
          </Field>
          <Button onClick={upload} disabled={!file || !name}>
            올리기
          </Button>
          {message && (
            <Alert tone="crit" style={{ marginTop: "var(--space-3)" }}>
              {message}
            </Alert>
          )}
        </Card>
      </Section>
    </>
  );
}
