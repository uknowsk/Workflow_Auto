"use client";

import { useEffect, useState } from "react";
import { api, App, Department, DeptMember, Notice, Usage } from "@/lib/api";
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

type Tab = "pending" | "depts" | "usage" | "audit" | "notices";

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
  const tabs: TabItem<Tab>[] = [
    { key: "pending", label: `승인 대기 ${pending.length}` },
    { key: "depts", label: `부서 ${depts.length}` },
    { key: "usage", label: "Gauss 사용량" },
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

      {tab === "usage" && usage && (
        <Section>
          <Card>
            <b>{usage.period} Gauss 사용량</b>
            <Muted style={{ margin: "var(--space-2) 0 var(--space-4)" }}>
              전체 {usage.all_users?.total_tokens.toLocaleString() ?? "-"} 토큰 · 호출{" "}
              {usage.all_users?.calls ?? "-"}회. 지금은 확인만 하고 한도로 막지는
              않습니다.
            </Muted>
            <Table>
              <thead>
                <tr>
                  <th>사번</th>
                  <th className="num">토큰</th>
                  <th className="num">호출</th>
                </tr>
              </thead>
              <tbody>
                {(usage.by_user || []).map((row) => (
                  <tr key={row.user_id}>
                    <td>{row.user_id}</td>
                    <td className="num">{row.total_tokens.toLocaleString()}</td>
                    <td className="num">{row.calls}</td>
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
