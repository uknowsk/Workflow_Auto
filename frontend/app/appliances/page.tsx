"use client";

// 가전 신제품 조사 화면.
//   1) 대륙 · 품목 · 제조사를 고르고 «신제품 찾기»
//   2) 가격대(보급형·중급형·프리미엄·최고급) 칸에 제품이 나뉘어 들어옵니다
//   3) 제품을 골라 스펙을 나란히 비교하고, 주기 감시를 걸어 둡니다
// 실제 일은 공식 앱 "가전 신제품 조사"(9119)가 하고, 이 화면은 그 앱을 부르기만 합니다.

import { useEffect, useMemo, useState } from "react";
import {
  APPLIANCE_API,
  ApplianceCatalog,
  Comparison,
  Product,
  Source,
  TrendResult,
  Watch,
  applianceApi,
} from "@/lib/apps";
import {
  Alert,
  Badge,
  Button,
  Card,
  Checkbox,
  Chip,
  Empty,
  Field,
  Grid,
  Input,
  Muted,
  PageTitle,
  Pre,
  Row,
  Section,
  SectionHead,
  Select,
  Table,
  Tabs,
  Tag,
} from "@/components/ui";

type View = "compare" | "sources" | "watches";

const EVERY = [
  { hours: 24, label: "매일" },
  { hours: 168, label: "매주" },
  { hours: 720, label: "매월" },
];

const SOURCE_LABEL: Record<Source["type"], string> = {
  sitemap: "사이트맵",
  listing: "목록 페이지",
  search: "검색",
  manual: "직접 입력",
};

function money(value: number | null, currency = "USD") {
  if (value === null || value === undefined) return "가격 미확인";
  try {
    return new Intl.NumberFormat("ko-KR", {
      style: "currency",
      currency,
      maximumFractionDigits: currency === "KRW" || currency === "JPY" ? 0 : 2,
    }).format(value);
  } catch {
    return `${value.toLocaleString()} ${currency}`;
  }
}

function range(min: number | null, max: number | null) {
  if (min === null) return "";
  return max === null ? `$${min.toLocaleString()} 이상` : `$${min.toLocaleString()} ~ $${max.toLocaleString()}`;
}

function ProductCard({
  product,
  picked,
  onPick,
}: {
  product: Product;
  picked: boolean;
  onPick: () => void;
}) {
  return (
    <Card style={{ marginBottom: "var(--space-3)" }}>
      <Row between nowrap>
        <a href={product.url} target="_blank" rel="noreferrer">
          <b>{product.name || product.model}</b>
        </a>
        {product.is_new && (
          <Badge tone="accent" title={product.new_reason}>
            NEW
          </Badge>
        )}
      </Row>
      <Row style={{ marginTop: "var(--space-2)" }}>
        <Tag>{product.maker}</Tag>
        {product.model && <Tag>{product.model}</Tag>}
      </Row>
      <div style={{ marginTop: "var(--space-2)" }}>
        <b>{money(product.price, product.currency)}</b>
        {product.currency !== "USD" && product.price_usd !== null && (
          <Muted>≈ {money(product.price_usd)}</Muted>
        )}
      </div>
      {product.energy_rating && (
        <div style={{ marginTop: "var(--space-2)" }}>
          <Tag>⚡ {product.energy_rating}</Tag>
        </div>
      )}
      {product.pods?.length > 0 && (
        <div style={{ marginTop: "var(--space-2)" }}>
          <Muted>POD {product.pod_method === "llm" ? "(LLM)" : "(규칙)"}</Muted>
          <ul style={{ margin: 0, paddingLeft: "1.2em" }}>
            {product.pods.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
      )}
      {product.ai_features?.length > 0 && (
        <div style={{ marginTop: "var(--space-2)" }}>
          <Muted>🤖 AI·연결 기능 {product.ai_method === "llm" ? "(LLM)" : "(규칙)"}</Muted>
          <ul style={{ margin: 0, paddingLeft: "1.2em" }}>
            {product.ai_features.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
        </div>
      )}
      {product.new_reason && <Muted style={{ marginTop: "var(--space-2)" }}>{product.new_reason}</Muted>}
      <div style={{ marginTop: "var(--space-2)" }}>
        <Checkbox label="스펙 비교에 담기" checked={picked} onChange={onPick} />
      </div>
    </Card>
  );
}

export default function Appliances() {
  const [catalog, setCatalog] = useState<ApplianceCatalog | null>(null);
  const [region, setRegion] = useState("north_america");
  const [category, setCategory] = useState("cooking");
  const [makers, setMakers] = useState<string[]>([]);
  const [perMaker, setPerMaker] = useState(8);
  const [view, setView] = useState<View>("compare");
  const [mode, setMode] = useState<"fixed" | "quantile">("fixed");
  const [onlyNew, setOnlyNew] = useState(false);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [watches, setWatches] = useState<Watch[]>([]);
  const [every, setEvery] = useState(168);
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<string[]>([]);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [sourceMaker, setSourceMaker] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [trendResult, setTrendResult] = useState<TrendResult | null>(null);
  const [trendBusy, setTrendBusy] = useState(false);

  const regionInfo = catalog?.regions.find((r) => r.key === region);
  const regionMakers = regionInfo?.makers ?? [];
  const categoryLabel = catalog?.categories.find((c) => c.key === category)?.label ?? category;
  // 이름 → tier("글로벌 톱티어" 등) 조회. 대륙은 홈페이지만 고를 뿐, 이 순위는 대륙과 무관합니다.
  const tierOf = (name: string) => catalog?.global_brands.find((b) => b.name === name)?.tier ?? "";

  useEffect(() => {
    applianceApi
      .catalog()
      .then(setCatalog)
      .catch(() =>
        setError(
          `가전 신제품 조사 앱(${APPLIANCE_API})에 연결하지 못했습니다. 앱이 켜져 있는지 확인하세요.`
        )
      );
  }, []);

  // 대륙을 바꾸면 그 대륙에서 살펴볼 후보(글로벌 탑 20) 중 "글로벌 톱티어"만
  // 먼저 고른 상태로 시작합니다. 20개를 한꺼번에 돌리면 한 번에 몇 분씩
  // 걸릴 수 있어서, 나머지(프리미엄·지역 강세)는 필요할 때 칩을 눌러 더합니다.
  useEffect(() => {
    const topTier = regionMakers.filter((m) => tierOf(m.name) === "글로벌 톱티어");
    setMakers((topTier.length ? topTier : regionMakers).map((m) => m.name));
    setSourceMaker(regionMakers[0]?.name ?? "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [region, catalog]);

  const reload = () => {
    if (!catalog) return;
    applianceApi
      .compare(region, category, makers, mode, onlyNew)
      .then(setComparison)
      .catch((e) => setError(String(e)));
    applianceApi
      .sources(region, category)
      .then((d) => setSources(d.sources))
      .catch(() => undefined);
    applianceApi
      .watches()
      .then((d) => setWatches(d.watches))
      .catch(() => undefined);
  };

  useEffect(() => {
    reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [catalog, region, category, makers, mode, onlyNew]);

  const allProducts = useMemo(
    () => [
      ...(comparison?.bands.flatMap((b) => b.products) ?? []),
      ...(comparison?.unpriced ?? []),
    ],
    [comparison]
  );
  const pickedProducts = allProducts.filter((p) => picked.includes(p.id));
  const compareSet = pickedProducts.length ? pickedProducts : allProducts.slice(0, 6);

  const toggleMaker = (name: string) =>
    setMakers((cur) => (cur.includes(name) ? cur.filter((m) => m !== name) : [...cur, name]));

  const togglePick = (id: string) =>
    setPicked((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));

  const scan = async () => {
    setBusy(true);
    setError("");
    setMessage("");
    setLog([]);
    try {
      const result = await applianceApi.scan(region, category, makers, perMaker);
      setLog(result.log || []);
      setMessage(`제품 ${result.product_count}개를 정리했습니다. 그중 신제품 ${result.new_count}개.`);
      reload();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const checkTrends = async () => {
    setTrendBusy(true);
    setError("");
    try {
      const result = await applianceApi.trends(region, category, makers);
      setTrendResult(result);
    } catch (e) {
      setError(String(e));
    } finally {
      setTrendBusy(false);
    }
  };

  const addWatch = async () => {
    setError("");
    try {
      await applianceApi.addWatch({ region, category, makers, every_hours: every });
      setMessage(
        `${regionInfo?.label} ${categoryLabel} 을(를) ${EVERY.find((e) => e.hours === every)?.label} 확인하도록 등록했습니다.`
      );
      reload();
    } catch (e) {
      setError(String(e));
    }
  };

  const addSource = async () => {
    if (!sourceUrl.startsWith("http")) return;
    try {
      await applianceApi.addSource({ maker: sourceMaker, region, category, url: sourceUrl });
      setSourceUrl("");
      reload();
    } catch (e) {
      setError(String(e));
    }
  };

  return (
    <>
      <PageTitle
        title="가전 신제품 조사"
        sub="영향력 기준 글로벌 탑 20 가전사 홈페이지에서 신제품을 찾아 가격 · POD(차별점) · 스펙을 정리하고 가격대별로 비교합니다"
      />

      {error && (
        <Alert tone="crit" style={{ marginBottom: "var(--space-4)" }}>
          {error}
        </Alert>
      )}

      <Card className="ui-card--pad-lg">
        <Grid cols={3}>
          <Field label="대륙" htmlFor="aw-region">
            <Select id="aw-region" value={region} onChange={(e) => setRegion(e.target.value)}>
              {catalog?.regions.map((r) => (
                <option key={r.key} value={r.key}>
                  {r.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="품목" htmlFor="aw-category">
            <Select id="aw-category" value={category} onChange={(e) => setCategory(e.target.value)}>
              {catalog?.categories.map((c) => (
                <option key={c.key} value={c.key}>
                  {c.label}
                </option>
              ))}
            </Select>
          </Field>
          <Field label="회사당 최대 제품 수" htmlFor="aw-per">
            <Select id="aw-per" value={perMaker} onChange={(e) => setPerMaker(Number(e.target.value))}>
              {[4, 8, 15, 30].map((n) => (
                <option key={n} value={n}>
                  {n}개
                </option>
              ))}
            </Select>
          </Field>
        </Grid>

        <Field
          label={`${regionInfo?.label ?? ""} 조사 대상 (글로벌 탑 20)`}
          hint="누르면 빼고 넣을 수 있어요 · 대륙은 홈페이지·통화만 바꿀 뿐 순위를 거르지 않아요"
        >
          {["글로벌 톱티어", "프리미엄", "지역 강세"].map((tier) => {
            const group = regionMakers.filter((m) => tierOf(m.name) === tier);
            if (!group.length) return null;
            return (
              <div key={tier} style={{ marginBottom: "var(--space-2)" }}>
                <Muted>{tier}</Muted>
                <Row>
                  {group.map((m) => (
                    <Chip key={m.name} active={makers.includes(m.name)} onClick={() => toggleMaker(m.name)}>
                      {m.name}
                    </Chip>
                  ))}
                </Row>
              </div>
            );
          })}
        </Field>

        <Row between>
          <Row>
            <Button onClick={scan} disabled={busy || makers.length === 0 || !catalog}>
              {busy ? "홈페이지 돌아보는 중… (몇 분 걸릴 수 있어요)" : "신제품 찾기"}
            </Button>
            <Button
              variant="soft"
              onClick={checkTrends}
              disabled={trendBusy || makers.length === 0 || !catalog}
              title="아직 공식 홈페이지에 안 올라온 발표 직후 신제품도 뉴스·유튜브로 먼저 포착합니다"
            >
              {trendBusy ? "뉴스·유튜브 찾는 중…" : "📰 최근 화제"}
            </Button>
          </Row>
          <Row>
            <Select
              value={every}
              onChange={(e) => setEvery(Number(e.target.value))}
              style={{ width: 110 }}
              aria-label="주기"
            >
              {EVERY.map((e) => (
                <option key={e.hours} value={e.hours}>
                  {e.label}
                </option>
              ))}
            </Select>
            <Button variant="soft" onClick={addWatch} disabled={!catalog || makers.length === 0}>
              주기적으로 확인
            </Button>
          </Row>
        </Row>

        {catalog && (
          <Muted style={{ marginTop: "var(--space-3)" }}>
            POD 뽑기: {catalog.llm_enabled ? "사내 LLM" : "규칙(경쟁사에 없는 특징)"} · 홈페이지 자동 검색:{" "}
            {catalog.search_enabled ? "켜짐" : "꺼짐 (기본 주소 사용)"}
          </Muted>
        )}
      </Card>

      {trendResult && trendResult.ok && (
        <Card className="ui-card--pad-lg" style={{ marginTop: "var(--space-4)" }}>
          <SectionHead
            label="최근 화제 (뉴스·유튜브)"
            note="제품 페이지가 아니라 언론·영상 언급이라 가격·모델은 없어요 — 홈페이지에 아직 안 올라온 신제품을 먼저 알아채는 용도예요"
          />
          {!trendResult.youtube_enabled && (
            <Muted>유튜브 검색은 꺼져 있어요(YOUTUBE_API_KEY 없음) · 뉴스만 보여줘요</Muted>
          )}
          {trendResult.signals.map((s) => (
            <div key={s.maker} style={{ marginTop: "var(--space-3)" }}>
              <b>{s.maker}</b>
              {s.news.length === 0 && s.videos.length === 0 && (
                <Muted style={{ marginLeft: "var(--space-2)" }}>최근 소식 없음</Muted>
              )}
              {s.news.length > 0 && (
                <ul style={{ margin: "var(--space-1) 0", paddingLeft: "1.2em" }}>
                  {s.news.map((n) => (
                    <li key={n.url}>
                      <a href={n.url} target="_blank" rel="noreferrer">
                        {n.title}
                      </a>
                      <Muted> · {n.source}</Muted>
                    </li>
                  ))}
                </ul>
              )}
              {s.videos.length > 0 && (
                <ul style={{ margin: "var(--space-1) 0", paddingLeft: "1.2em" }}>
                  {s.videos.map((v) => (
                    <li key={v.url}>
                      ▶ <a href={v.url} target="_blank" rel="noreferrer">
                        {v.title}
                      </a>
                      <Muted> · {v.channel}</Muted>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </Card>
      )}

      {message && (
        <Alert tone="ok" style={{ marginTop: "var(--space-4)" }}>
          {message}
        </Alert>
      )}
      {log.length > 0 && (
        <details style={{ marginTop: "var(--space-2)" }}>
          <summary>진행 기록 보기</summary>
          <Pre>{log.join("\n")}</Pre>
        </details>
      )}

      <Section>
        <Tabs
          items={[
            { key: "compare", label: "가격대별 비교" },
            { key: "sources", label: `찾은 출처 (${sources.length})` },
            { key: "watches", label: `주기 확인 (${watches.length})` },
          ]}
          value={view}
          onChange={setView}
        />
      </Section>

      {view === "compare" && (
        <>
          <Row style={{ marginBottom: "var(--space-4)" }}>
            <Chip active={mode === "fixed"} onClick={() => setMode("fixed")}>
              품목 기준 가격대 (달러)
            </Chip>
            <Chip active={mode === "quantile"} onClick={() => setMode("quantile")}>
              고른 제품 안에서 4등분
            </Chip>
            <Checkbox label="신제품만" checked={onlyNew} onChange={() => setOnlyNew(!onlyNew)} />
          </Row>

          {!comparison || comparison.total === 0 ? (
            <Empty>아직 모아 둔 제품이 없습니다. 위에서 «신제품 찾기»를 눌러 보세요.</Empty>
          ) : (
            <>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: `repeat(${Math.max(comparison.bands.length, 1)}, minmax(220px, 1fr))`,
                  gap: "var(--space-3)",
                  overflowX: "auto",
                }}
              >
                {comparison.bands.map((band) => (
                  <div key={band.label}>
                    <SectionHead
                      label={`${band.label} · ${band.count}개`}
                      note={`${range(band.min_usd, band.max_usd)}${
                        band.median_usd !== null ? ` · 중간값 $${band.median_usd.toLocaleString()}` : ""
                      }`}
                    />
                    {band.products.length === 0 ? (
                      <Muted>없음</Muted>
                    ) : (
                      band.products.map((p) => (
                        <ProductCard
                          key={p.id}
                          product={p}
                          picked={picked.includes(p.id)}
                          onPick={() => togglePick(p.id)}
                        />
                      ))
                    )}
                  </div>
                ))}
              </div>

              {comparison.unpriced.length > 0 && (
                <Section>
                  <SectionHead label={`가격 미확인 ${comparison.unpriced.length}개`} note="홈페이지에 가격이 없는 제품" />
                  <Grid cols={3}>
                    {comparison.unpriced.map((p) => (
                      <ProductCard key={p.id} product={p} picked={picked.includes(p.id)} onPick={() => togglePick(p.id)} />
                    ))}
                  </Grid>
                </Section>
              )}

              <Section>
                <SectionHead
                  label="스펙 나란히 보기"
                  note={pickedProducts.length ? `고른 제품 ${pickedProducts.length}개` : "고른 제품이 없어 싼 순서로 6개"}
                />
                <div style={{ overflowX: "auto" }}>
                  <Table>
                    <thead>
                      <tr>
                        <th>항목</th>
                        {compareSet.map((p) => (
                          <th key={p.id}>
                            {p.maker}
                            <br />
                            <Muted>{p.model || p.name}</Muted>
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td>가격(달러)</td>
                        {compareSet.map((p) => (
                          <td key={p.id}>{money(p.price_usd)}</td>
                        ))}
                      </tr>
                      <tr>
                        <td>가격대</td>
                        {compareSet.map((p) => (
                          <td key={p.id}>{p.band}</td>
                        ))}
                      </tr>
                      <tr>
                        <td>POD</td>
                        {compareSet.map((p) => (
                          <td key={p.id}>{(p.pods || []).join(" / ")}</td>
                        ))}
                      </tr>
                      <tr>
                        <td>AI·연결 기능</td>
                        {compareSet.map((p) => (
                          <td key={p.id}>{(p.ai_features || []).join(" / ") || "–"}</td>
                        ))}
                      </tr>
                      <tr>
                        <td>에너지 효율</td>
                        {compareSet.map((p) => (
                          <td key={p.id}>{p.energy_rating || "–"}</td>
                        ))}
                      </tr>
                      {comparison.spec_keys.map((key) => (
                        <tr key={key}>
                          <td>{key}</td>
                          {compareSet.map((p) => (
                            <td key={p.id}>{p.specs?.[key] ?? "–"}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                </div>
              </Section>
            </>
          )}
        </>
      )}

      {view === "sources" && (
        <>
          <Muted style={{ marginBottom: "var(--space-3)" }}>
            앱이 스스로 찾아낸 "제품 정보가 올라오는 곳"입니다. 잘 된 곳은 점수가 오르고, 다음 조사에서 먼저 씁니다.
          </Muted>
          {sources.length === 0 ? (
            <Empty>아직 찾은 출처가 없습니다. 한 번 조사하면 여기에 쌓입니다.</Empty>
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>제조사</th>
                  <th>종류</th>
                  <th>주소</th>
                  <th>찾은 제품</th>
                  <th>점수</th>
                </tr>
              </thead>
              <tbody>
                {sources.map((s) => (
                  <tr key={s.id}>
                    <td>{s.maker}</td>
                    <td>{SOURCE_LABEL[s.type] ?? s.type}</td>
                    <td style={{ wordBreak: "break-all" }}>{s.url}</td>
                    <td>{s.hits}</td>
                    <td>{s.score}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}

          <Section>
            <SectionHead label="자동으로 못 찾을 때: 목록 페이지 직접 알려 주기" />
            <Card>
              <Grid cols={3}>
                <Field label="제조사" htmlFor="aw-src-maker">
                  <Select id="aw-src-maker" value={sourceMaker} onChange={(e) => setSourceMaker(e.target.value)}>
                    {regionMakers.map((m) => (
                      <option key={m.name} value={m.name}>
                        {m.name}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label={`${categoryLabel} 목록 페이지 주소`} htmlFor="aw-src-url">
                  <Input
                    id="aw-src-url"
                    placeholder="https://www.geappliances.com/appliances/ranges"
                    value={sourceUrl}
                    onChange={(e) => setSourceUrl(e.target.value)}
                  />
                </Field>
              </Grid>
              <Button small onClick={addSource} disabled={!sourceUrl.startsWith("http")}>
                출처 추가
              </Button>
            </Card>
          </Section>
        </>
      )}

      {view === "watches" && (
        <>
          {watches.length === 0 ? (
            <Empty>주기 확인이 없습니다. 위에서 주기를 고르고 «주기적으로 확인»을 누르세요.</Empty>
          ) : (
            watches.map((w) => {
              const r = catalog?.regions.find((x) => x.key === w.region)?.label ?? w.region;
              const c = catalog?.categories.find((x) => x.key === w.category)?.label ?? w.category;
              return (
                <Card key={w.id} style={{ marginBottom: "var(--space-3)" }}>
                  <Row between nowrap>
                    <b>
                      {r} · {c}
                    </b>
                    <Badge>{EVERY.find((e) => e.hours === w.every_hours)?.label ?? `${w.every_hours}시간마다`}</Badge>
                  </Row>
                  <Muted>
                    {w.makers.length ? w.makers.join(", ") : "글로벌 탑 20 전부"} · 마지막 확인{" "}
                    {w.last_run ? w.last_run.slice(0, 16).replace("T", " ") : "아직"}
                    {w.last_result && ` · ${w.last_result}`}
                  </Muted>
                  <Row style={{ marginTop: "var(--space-2)" }}>
                    <Button
                      small
                      variant="soft"
                      disabled={busy}
                      onClick={async () => {
                        setBusy(true);
                        try {
                          const res = await applianceApi.runWatch(w.id);
                          setLog(res.log || []);
                        } catch (e) {
                          setError(String(e));
                        } finally {
                          setBusy(false);
                          reload();
                        }
                      }}
                    >
                      지금 확인
                    </Button>
                    <Button small variant="ghost" onClick={() => applianceApi.deleteWatch(w.id).then(reload)}>
                      삭제
                    </Button>
                  </Row>
                </Card>
              );
            })
          )}
        </>
      )}
    </>
  );
}
