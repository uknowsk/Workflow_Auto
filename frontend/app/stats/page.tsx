"use client";

import { useEffect, useState } from "react";
import { api, getSession, Ranking, Usage } from "@/lib/api";
import {
  Alert,
  Badge,
  Bar,
  Card,
  Empty,
  Muted,
  PageTitle,
  Row,
  Section,
  SectionHead,
  Tag,
} from "@/components/ui";

export default function Stats() {
  const [data, setData] = useState<Ranking | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [error, setError] = useState("");
  // 앱 순위는 관리자만 봅니다. 주소를 직접 쳐서 들어오면 대시보드로 돌려보냅니다.
  const [allowed, setAllowed] = useState<boolean | null>(null);

  useEffect(() => {
    const session = getSession();
    if (!session) {
      location.href = "/login";
      return;
    }
    if (!session.is_admin) {
      setAllowed(false);
      location.href = "/dashboard";
      return;
    }
    setAllowed(true);
    api.appRanking().then(setData).catch((e) => setError(String(e)));
    api.usage().then(setUsage).catch(() => undefined);
  }, []);

  if (allowed !== true) return null;

  // 1위를 100%로 놓고 막대 길이를 정합니다.
  const top = data?.ranking[0]?.success_calls || 1;

  return (
    <>
      <PageTitle
        title="이달의 앱"
        sub={
          data
            ? `${data.period} · 성공한 호출 수 기준`
            : "성공한 호출 수 기준으로 매깁니다"
        }
      />

      <Muted style={{ marginBottom: "var(--space-5)" }}>
        많이 불렸어도 계속 실패한 앱은 위로 올라오지 않습니다.
      </Muted>

      {usage && (
        <Card quiet>
          <Row between>
            <span>내 Gauss 사용량 ({usage.period})</span>
            <span className="ui-stat">
              <b>{usage.mine.total_tokens.toLocaleString()}</b>
              토큰 · 호출 {usage.mine.calls}회
            </span>
          </Row>
        </Card>
      )}

      {error && (
        <Alert tone="crit" style={{ marginTop: "var(--space-4)" }}>
          {error}
        </Alert>
      )}

      <Section>
        <SectionHead label="순위" />
        {data && data.ranking.length === 0 ? (
          <Empty>이번 달 호출 기록이 아직 없습니다.</Empty>
        ) : (
          data?.ranking.map((row) => (
            <Card key={row.rank} style={{ marginBottom: "var(--space-3)" }}>
              <Row between>
                <Row>
                  <span className="ui-count">{row.rank === 1 ? "🏆" : row.rank}</span>
                  <b>{row.name}</b>
                </Row>
                <Badge tone={row.success_rate >= 95 ? "ok" : "warn"}>
                  성공률 {row.success_rate}%
                </Badge>
              </Row>

              <div style={{ margin: "var(--space-3) 0" }}>
                <Bar percent={(row.success_calls / top) * 100} />
              </div>

              <Row>
                <Tag>성공 {row.success_calls}회 / 전체 {row.total_calls}회</Tag>
                <Tag>사용자 {row.user_count}명</Tag>
                <Tag>
                  등록자 {row.owner.name || row.owner.user_id || "-"}
                  {row.owner.dept && ` · ${row.owner.dept}`}
                  {row.owner.contact && ` · ${row.owner.contact}`}
                </Tag>
              </Row>
            </Card>
          ))
        )}
      </Section>
    </>
  );
}
