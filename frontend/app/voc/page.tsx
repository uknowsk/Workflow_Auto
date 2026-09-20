"use client";

// 의견함 - 내 앱에 온 의견(등록자)과 내가 보낸 의견을 한 화면에서 봅니다.
// 앱스토어에서도 앱마다 의견을 볼 수 있지만, 앱을 여러 개 올린 사람은
// "오늘 나한테 뭐가 왔지"를 한 번에 봐야 하기 때문에 이 화면이 따로 있습니다.

import { useCallback, useEffect, useState } from "react";
import { api, getSession, type Voc } from "@/lib/api";
import { VocRow } from "@/components/apps/app-modals";
import { Alert, Chip, Empty, PageTitle, Row, Tabs } from "@/components/ui";

type Tab = "inbox" | "sent";

export default function VocPage() {
  const [tab, setTab] = useState<Tab>("inbox");
  const [openOnly, setOpenOnly] = useState(true);
  const [inbox, setInbox] = useState<Voc[]>([]);
  const [sent, setSent] = useState<Voc[]>([]);
  const [error, setError] = useState("");
  const [meId, setMeId] = useState("");

  const reload = useCallback(() => {
    api.vocInbox(openOnly).then(setInbox).catch((e) => setError(String(e)));
    api.vocSent().then(setSent).catch((e) => setError(String(e)));
  }, [openOnly]);

  useEffect(() => {
    setMeId(getSession()?.user_id || "");
    reload();
  }, [reload]);

  const list = tab === "inbox" ? inbox : sent;
  const waiting = inbox.filter((v) => v.status === "open").length;

  return (
    <>
      <PageTitle
        title="의견함"
        sub={
          waiting > 0
            ? `내 앱에 아직 답하지 않은 의견이 ${waiting}건 있습니다`
            : "내 앱에 온 의견과 내가 보낸 의견"
        }
      />

      <Row style={{ marginBottom: "var(--space-3)" }}>
        <Tabs
          items={[
            { key: "inbox" as Tab, label: `내 앱에 온 의견 ${inbox.length}` },
            { key: "sent" as Tab, label: `내가 보낸 의견 ${sent.length}` },
          ]}
          value={tab}
          onChange={setTab}
        />
        {tab === "inbox" && (
          <Chip active={openOnly} onClick={() => setOpenOnly(!openOnly)}>
            아직 안 끝난 것만
          </Chip>
        )}
      </Row>

      {error && <Alert tone="crit">{error}</Alert>}

      {list.length === 0 ? (
        <Empty>
          {tab === "inbox"
            ? "내 앱에 온 의견이 없습니다. 앱을 올리면 쓰는 사람들의 의견이 여기로 모입니다."
            : "아직 보낸 의견이 없습니다. 앱스토어에서 앱마다 «💬 의견» 으로 남길 수 있어요."}
        </Empty>
      ) : (
        list.map((voc) => (
          <VocRow
            key={voc.id}
            voc={voc}
            canAnswer={tab === "inbox"}
            mine={voc.user_id === meId}
            showApp
            onChanged={reload}
          />
        ))
      )}
    </>
  );
}
