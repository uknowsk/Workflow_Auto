"use client";

import { useEffect, useState } from "react";
import {
  api,
  Account,
  AdminErrors,
  AdminSetting,
  App,
  Department,
  DeptMember,
  Notice,
  Usage,
} from "@/lib/api";
import {
  Alert,
  Badge,
  Button,
  Card,
  Empty,
  Field,
  IconTile,
  Input,
  Muted,
  Lines,
  PageTitle,
  Pre,
  Row,
  Section,
  Select,
  Table,
  Tabs,
  Tag,
  type TabItem,
} from "@/components/ui";

type Tab =
  | "pending"
  | "errors"
  | "accounts"
  | "depts"
  | "usage"
  | "settings"
  | "audit"
  | "notices";

function when(iso: string | null) {
  if (!iso) return "-";
  return new Date(iso).toLocaleString("ko-KR", {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function Admin() {
  const [tab, setTab] = useState<Tab>("pending");
  const [pending, setPending] = useState<App[]>([]);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [audit, setAudit] = useState<Record<string, unknown>[]>([]);
  const [notices, setNotices] = useState<Notice[]>([]);
  const [message, setMessage] = useState("");
  // 부서 관리
  const [depts, setDepts] = useState<Department[]>([]);
  const [openDept, setOpenDept] = useState("");
  const [members, setMembers] = useState<DeptMember[]>([]);
  const [newDept, setNewDept] = useState({ code: "", name: "" });
  const [newMember, setNewMember] = useState({ user_id: "", role: "member" });
  // 최근 오류 · 계정 · 운영 설정
  const [errors, setErrors] = useState<AdminErrors | null>(null);
  const [errorDays, setErrorDays] = useState(7);
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [search, setSearch] = useState("");
  const [knobs, setKnobs] = useState<AdminSetting[]>([]);

  const reload = () => {
    setMessage("");
    api
      .listPending()
      .then(setPending)
      .catch(() =>
        setMessage(
          "관리자만 볼 수 있습니다. 백엔드 환경변수 ADMIN_USER_IDS 에 내 사번을 넣거나, 관리자 계정으로 로그인하세요."
        )
      );
    api.listDepartments().then(setDepts).catch(() => undefined);
    api.usage().then(setUsage).catch(() => undefined);
    api.audit().then(setAudit).catch(() => undefined);
    api.notifications().then(setNotices).catch(() => undefined);
    api.adminErrors(errorDays).then(setErrors).catch(() => undefined);
    api.listAccounts().then(setAccounts).catch(() => undefined);
    api.adminSettings().then(setKnobs).catch(() => undefined);
  };

  const run = async (work: () => Promise<unknown>, done = "") => {
    setMessage("");
    try {
      await work();
      if (done) setMessage(done);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    }
  };

  const reloadAccounts = (q = search) =>
    api.listAccounts(q).then(setAccounts).catch(() => undefined);

  const patchAccount = (user_id: string, body: Record<string, unknown>) =>
    run(() => api.updateAccount(user_id, body).then(() => reloadAccounts()));

  const resetPassword = (user_id: string) => {
    const password = prompt(
      `${user_id} 님의 새 비밀번호를 적어 주세요.\n(적어 주신 비밀번호를 본인에게 알려 주셔야 합니다)`
    );
    if (!password) return;
    run(
      () => api.resetPassword(user_id, password),
      `${user_id} 님의 비밀번호를 바꿨습니다. 본인에게 알려 주세요.`
    );
  };

  const moveDept = (user_id: string, now: string) => {
    const code = prompt(
      `${user_id} 님을 옮길 부서 코드를 적어 주세요. 빈 칸으로 두면 부서에서 뺍니다.\n지금 부서: ${now || "(없음)"}`,
      now
    );
    if (code === null) return;
    patchAccount(user_id, { dept_code: code.trim() });
  };

  useEffect(() => {
    reload();
  }, []);

  const openMembers = (code: string) => {
    setOpenDept(code);
    api.listDeptMembers(code).then(setMembers).catch(() => setMembers([]));
  };

  const addDept = async () => {
    setMessage("");
    try {
      await api.createDepartment(newDept);
      setNewDept({ code: "", name: "" });
      reload();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    }
  };

  const addMember = async () => {
    setMessage("");
    try {
      await api.addDeptMember(
        openDept,
        newMember.user_id,
        newMember.role as "member" | "manager"
      );
      setNewMember({ user_id: "", role: "member" });
      openMembers(openDept);
      api.listDepartments().then(setDepts).catch(() => undefined);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    }
  };

  const unread = notices.filter((n) => !n.read).length;
  const tokenLimit =
    knobs.find((k) => k.key === "llm_monthly_token_limit")?.value ?? 0;
  const errorCount = errors
    ? errors.runs.length + errors.app_calls.length + errors.apps_down.length
    : 0;
  const tabs: TabItem<Tab>[] = [
    { key: "pending", label: `승인 대기 ${pending.length}` },
    { key: "errors", label: `최근 오류 ${errorCount}` },
    { key: "accounts", label: `계정 ${accounts.length}` },
    { key: "depts", label: `부서 ${depts.length}` },
    { key: "usage", label: "Gauss 사용량" },
    { key: "settings", label: "설정" },
    { key: "audit", label: "감사 기록" },
    { key: "notices", label: `알림 ${unread}` },
  ];

  return (
    <>
      <PageTitle title="관리자" sub="앱 승인, 사용량, 감사 기록을 여기서 봅니다." />

      <Tabs items={tabs} value={tab} onChange={setTab} />

      {message && (
        <Alert tone="warn" style={{ marginTop: "var(--space-5)" }}>
          {message}
        </Alert>
      )}

      {tab === "pending" && (
        <Section>
          {pending.length === 0 && !message ? (
            <Empty>대기 중인 앱이 없습니다.</Empty>
          ) : (
            pending.map((app) => (
              <Card key={app.id} style={{ marginBottom: "var(--space-3)" }}>
                <Row>
                  <IconTile>{app.icon || "🧩"}</IconTile>
                  <b>{app.name}</b>
                  {app.requires_confirmation && (
                    <Badge tone="warn">되돌릴 수 없는 작업</Badge>
                  )}
                </Row>
                <Muted style={{ margin: "var(--space-2) 0" }}>
                  {app.usage_hint || app.description}
                </Muted>
                <Row style={{ marginBottom: "var(--space-3)" }}>
                  <Tag>
                    올린 사람 {app.owner || app.owner_user_id || "-"}
                    {app.owner_contact && ` · ${app.owner_contact}`}
                  </Tag>
                  <Tag>기능 {app.tools.length}개</Tag>
                  {app.capability_tag && <Tag>역할 {app.capability_tag}</Tag>}
                </Row>
                <Row>
                  <Button onClick={() => api.approveApp(app.id).then(reload)}>
                    공식 승인
                  </Button>
                  <Button variant="ghost" onClick={() => api.rejectApp(app.id).then(reload)}>
                    반려 (개인용으로 되돌림)
                  </Button>
                </Row>
              </Card>
            ))
          )}
        </Section>
      )}

      {tab === "depts" && (
        <Section>
          <Card style={{ marginBottom: "var(--space-4)" }}>
            <b>부서 만들기</b>
            <Muted style={{ margin: "var(--space-2) 0 var(--space-3)" }}>
              부서를 만들고 부서원을 넣어 두면, 그 부서의 공통 앱과 공통 카드가
              부서원 모두의 화면에 같이 보입니다. 담당자(manager)로 넣은 사람만
              부서 공통 앱·카드를 올리고 고칠 수 있습니다.
            </Muted>
            <Row>
              <Field label="부서 코드" htmlFor="dept-code" hint="예) SW1">
                <Input
                  id="dept-code"
                  value={newDept.code}
                  onChange={(e) => setNewDept({ ...newDept, code: e.target.value })}
                />
              </Field>
              <Field label="부서 이름" htmlFor="dept-name" hint="예) SW개발팀">
                <Input
                  id="dept-name"
                  value={newDept.name}
                  onChange={(e) => setNewDept({ ...newDept, name: e.target.value })}
                />
              </Field>
              <Button
                onClick={addDept}
                disabled={!newDept.code.trim() || !newDept.name.trim()}
              >
                부서 추가
              </Button>
            </Row>
          </Card>

          {depts.length === 0 ? (
            <Empty>아직 만든 부서가 없습니다.</Empty>
          ) : (
            depts.map((dept) => (
              <Card key={dept.code} style={{ marginBottom: "var(--space-3)" }}>
                <Row between>
                  <Row>
                    <b>{dept.name}</b>
                    <Tag>{dept.code}</Tag>
                    <Tag>부서원 {dept.member_count}명</Tag>
                    <Tag>공통 앱 {dept.app_count}개</Tag>
                    <Tag>공통 카드 {dept.card_count}장</Tag>
                  </Row>
                  <Row>
                    <Button
                      variant="ghost"
                      small
                      onClick={() =>
                        openDept === dept.code ? setOpenDept("") : openMembers(dept.code)
                      }
                    >
                      {openDept === dept.code ? "닫기" : "부서원 관리"}
                    </Button>
                    <Button
                      variant="ghost"
                      small
                      onClick={() =>
                        api
                          .deleteDepartment(dept.code)
                          .then(reload)
                          .catch((e) => setMessage(String(e)))
                      }
                    >
                      삭제
                    </Button>
                  </Row>
                </Row>

                {openDept === dept.code && (
                  <div style={{ marginTop: "var(--space-3)" }}>
                    <Row>
                      <Field label="사번" htmlFor="member-id">
                        <Input
                          id="member-id"
                          value={newMember.user_id}
                          onChange={(e) =>
                            setNewMember({ ...newMember, user_id: e.target.value })
                          }
                        />
                      </Field>
                      <Field label="역할" htmlFor="member-role">
                        <Select
                          id="member-role"
                          value={newMember.role}
                          onChange={(e) =>
                            setNewMember({ ...newMember, role: e.target.value })
                          }
                        >
                          <option value="member">부서원 (쓰기만)</option>
                          <option value="manager">담당자 (공통 앱·카드 등록)</option>
                        </Select>
                      </Field>
                      <Button onClick={addMember} disabled={!newMember.user_id.trim()}>
                        부서원 넣기
                      </Button>
                    </Row>

                    {members.length === 0 ? (
                      <Empty>아직 이 부서에 묶인 사람이 없습니다.</Empty>
                    ) : (
                      <Table>
                        <thead>
                          <tr>
                            <th>사번</th>
                            <th>이름</th>
                            <th>역할</th>
                            <th />
                          </tr>
                        </thead>
                        <tbody>
                          {members.map((member) => (
                            <tr key={member.user_id}>
                              <td>{member.user_id}</td>
                              <td>{member.name || "-"}</td>
                              <td>
                                {member.role === "manager" ? "담당자" : "부서원"}
                              </td>
                              <td>
                                <Button
                                  variant="ghost"
                                  small
                                  onClick={() =>
                                    api
                                      .removeDeptMember(dept.code, member.user_id)
                                      .then(() => openMembers(dept.code))
                                  }
                                >
                                  빼기
                                </Button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </Table>
                    )}
                  </div>
                )}
              </Card>
            ))
          )}
        </Section>
      )}

      {tab === "errors" && (
        <Section>
          <Row style={{ marginBottom: "var(--space-3)" }}>
            <Muted>며칠 치를 볼까요?</Muted>
            {[1, 7, 30].map((days) => (
              <Button
                key={days}
                variant={days === errorDays ? "primary" : "ghost"}
                small
                onClick={() => {
                  setErrorDays(days);
                  api.adminErrors(days).then(setErrors).catch(() => undefined);
                }}
              >
                {days === 1 ? "오늘" : `${days}일`}
              </Button>
            ))}
          </Row>

          {errorCount === 0 ? (
            <Empty>이 기간에는 실패한 일이 없습니다. 조용한 게 좋은 겁니다.</Empty>
          ) : (
            <>
              {errors!.apps_down.length > 0 && (
                <Card style={{ marginBottom: "var(--space-3)" }}>
                  <b>응답하지 않는 앱 {errors!.apps_down.length}개</b>
                  <Muted style={{ margin: "var(--space-2) 0 var(--space-3)" }}>
                    앱이 꺼져 있거나 주소가 바뀐 경우입니다. 등록자에게 연락하세요.
                  </Muted>
                  <Table>
                    <thead>
                      <tr>
                        <th>앱</th>
                        <th>등록자</th>
                        <th>연락처</th>
                        <th className="num">연속 실패</th>
                        <th>마지막 오류</th>
                      </tr>
                    </thead>
                    <tbody>
                      {errors!.apps_down.map((row) => (
                        <tr key={row.app_id}>
                          <td>{row.app}</td>
                          <td>{row.owner || "-"}</td>
                          <td>{row.contact || "-"}</td>
                          <td className="num">{row.failures}</td>
                          <td>{row.error}</td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                </Card>
              )}

              {errors!.runs.length > 0 && (
                <Card style={{ marginBottom: "var(--space-3)" }}>
                  <b>결과를 못 받은 요청 {errors!.runs.length}건</b>
                  <Muted style={{ margin: "var(--space-2) 0 var(--space-3)" }}>
                    사용자가 기다리다 아무것도 못 받은 경우입니다.
                  </Muted>
                  <Table>
                    <thead>
                      <tr>
                        <th>언제</th>
                        <th>누가</th>
                        <th>무엇을</th>
                        <th>왜 깨졌나</th>
                      </tr>
                    </thead>
                    <tbody>
                      {errors!.runs.map((row) => (
                        <tr key={row.run_id}>
                          <td>{when(row.at)}</td>
                          <td>{row.user_id}</td>
                          <td>{row.request}</td>
                          <td>{row.error}</td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                </Card>
              )}

              {errors!.app_calls.length > 0 && (
                <Card>
                  <b>실패한 앱 호출 {errors!.app_calls.length}건</b>
                  <Muted style={{ margin: "var(--space-2) 0 var(--space-3)" }}>
                    같은 앱이 여러 번 보이면 그 앱을 먼저 고치면 됩니다.
                  </Muted>
                  <Table>
                    <thead>
                      <tr>
                        <th>언제</th>
                        <th>앱 · 기능</th>
                        <th>누가</th>
                        <th>왜 깨졌나</th>
                      </tr>
                    </thead>
                    <tbody>
                      {errors!.app_calls.map((row, i) => (
                        <tr key={i}>
                          <td>{when(row.at)}</td>
                          <td>
                            {row.app} · {row.tool}
                          </td>
                          <td>{row.user_id}</td>
                          <td>{row.error}</td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                </Card>
              )}
            </>
          )}
        </Section>
      )}

      {tab === "accounts" && (
        <Section>
          <Card style={{ marginBottom: "var(--space-3)" }}>
            <Row>
              <Field label="사번 · 이름 · 소속으로 찾기" htmlFor="acc-q">
                <Input
                  id="acc-q"
                  value={search}
                  placeholder="예) E1001, 김로아, SW개발팀"
                  onChange={(e) => {
                    setSearch(e.target.value);
                    reloadAccounts(e.target.value);
                  }}
                />
              </Field>
            </Row>
            <Muted>
              퇴사자는 지우지 않고 <b>끕니다</b>. 그 사람이 남긴 실행·감사 기록이
              주인 없는 줄이 되면 안 되기 때문입니다.
            </Muted>
          </Card>

          {accounts.length === 0 ? (
            <Empty>찾는 계정이 없습니다.</Empty>
          ) : (
            <Table>
              <thead>
                <tr>
                  <th>사번</th>
                  <th>이름</th>
                  <th>부서</th>
                  <th>마지막 로그인</th>
                  <th>상태</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {accounts.map((row) => (
                  <tr key={row.user_id}>
                    <td>{row.user_id}</td>
                    <td>{row.name || "-"}</td>
                    <td>{row.dept_codes.join(", ") || row.dept || "-"}</td>
                    <td>{when(row.last_login_at)}</td>
                    <td>
                      {row.is_admin && <Tag>관리자</Tag>}{" "}
                      {row.is_active ? (
                        <Badge tone="ok">쓰는 중</Badge>
                      ) : (
                        <Badge tone="neutral">꺼짐</Badge>
                      )}
                    </td>
                    <td>
                      <Row>
                        <Button variant="ghost" small onClick={() => resetPassword(row.user_id)}>
                          비번 초기화
                        </Button>
                        <Button
                          variant="ghost"
                          small
                          onClick={() => moveDept(row.user_id, row.dept_codes[0] || "")}
                        >
                          부서 옮기기
                        </Button>
                        <Button
                          variant="ghost"
                          small
                          onClick={() =>
                            patchAccount(row.user_id, { is_active: !row.is_active })
                          }
                        >
                          {row.is_active ? "끄기(퇴사)" : "다시 켜기"}
                        </Button>
                      </Row>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </Section>
      )}

      {tab === "settings" && (
        <Section>
          <Card>
            <b>운영 설정</b>
            <Muted style={{ margin: "var(--space-2) 0 var(--space-4)" }}>
              여기서 바꾼 값은 서버를 다시 띄우지 않아도 바로 적용됩니다.
            </Muted>
            {knobs.map((knob) => (
              <Field key={knob.key} label={knob.label} htmlFor={knob.key}>
                <Row>
                  <Input
                    id={knob.key}
                    type="number"
                    value={String(knob.value)}
                    onChange={(e) =>
                      setKnobs(
                        knobs.map((k) =>
                          k.key === knob.key
                            ? { ...k, value: Number(e.target.value || 0) }
                            : k
                        )
                      )
                    }
                  />
                  <Muted>{knob.hint}</Muted>
                </Row>
              </Field>
            ))}
            <Row style={{ marginTop: "var(--space-4)" }}>
              <Button
                onClick={() =>
                  run(
                    () =>
                      api
                        .saveAdminSettings(
                          Object.fromEntries(knobs.map((k) => [k.key, k.value]))
                        )
                        .then(setKnobs),
                    "저장했습니다."
                  )
                }
              >
                저장
              </Button>
              <Button
                variant="ghost"
                onClick={() =>
                  run(async () => {
                    const { removed } = await api.cleanupNow();
                    const 목록 = Object.entries(removed)
                      .map(([name, count]) => `${name} ${count}건`)
                      .join(", ");
                    setMessage(목록 ? `지웠습니다: ${목록}` : "지울 기록이 없었습니다.");
                  })
                }
              >
                오래된 기록 지금 정리
              </Button>
            </Row>
          </Card>
        </Section>
      )}

      {tab === "usage" && usage && (
        <Section>
          <Card>
            <b>{usage.period} Gauss 사용량</b>
            <Muted style={{ margin: "var(--space-2) 0 var(--space-4)" }}>
              전체 {usage.all_users?.total_tokens.toLocaleString() ?? "-"} 토큰 · 호출{" "}
              {usage.all_users?.calls ?? "-"}회.{" "}
              {tokenLimit > 0
                ? `1인당 월 한도 ${tokenLimit.toLocaleString()} 토큰 — 넘은 사람은 다음 달까지 실행이 막힙니다.`
                : "지금은 한도가 없습니다(0). '설정' 탭에서 1인당 월 한도를 넣으면 켜집니다."}
            </Muted>
            <Table>
              <thead>
                <tr>
                  <th>사번</th>
                  <th className="num">토큰</th>
                  <th className="num">호출</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(usage.by_user || []).map((row) => (
                  <tr key={row.user_id}>
                    <td>{row.user_id}</td>
                    <td className="num">{row.total_tokens.toLocaleString()}</td>
                    <td className="num">{row.calls}</td>
                    <td>
                      {tokenLimit > 0 && row.total_tokens >= tokenLimit && (
                        <Badge tone="crit">한도 넘음</Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </Card>
        </Section>
      )}

      {tab === "audit" && (
        <Section>
          <Card>
            <b>감사 기록 (최근 100건)</b>
            <Muted style={{ margin: "var(--space-2) 0 var(--space-3)" }}>
              누가, 언제, 어떤 앱을 어떤 내용으로 불렀는지 남습니다.
            </Muted>
            <Pre style={{ maxHeight: 460, overflow: "auto" }}>
              {audit
                .map(
                  (row) =>
                    `${row.at}  ${row.actor}  ${row.action}  ${row.target ?? ""}\n    ${JSON.stringify(row.detail)}`
                )
                .join("\n")}
            </Pre>
          </Card>
        </Section>
      )}

      {tab === "notices" && (
        <Section>
          {notices.length === 0 ? (
            <Empty>알림이 없습니다.</Empty>
          ) : (
            notices.map((notice) => (
              <Card key={notice.id} style={{ marginBottom: "var(--space-3)" }}>
                <Row between>
                  <b>{notice.title}</b>
                  {!notice.read && <Badge tone="accent">읽지 않음</Badge>}
                </Row>
                <Lines boxed style={{ marginTop: "var(--space-2)" }}>
                  {notice.body}
                </Lines>
                <Muted style={{ marginTop: "var(--space-2)" }}>{notice.at}</Muted>
              </Card>
            ))
          )}
        </Section>
      )}
    </>
  );
}
