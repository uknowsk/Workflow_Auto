# 화면 만들 때 보는 문서 (디자인 시스템)

Workflow Auto 의 모든 화면은 같은 색·글꼴·간격을 씁니다.
새 화면을 만들 때 **색상 코드나 px 를 직접 쓰지 마세요.**
아래 컴포넌트를 가져다 쓰면 자동으로 같은 모양이 됩니다.

- 토큰(색·글꼴·여백): `frontend/app/globals.css`
- 컴포넌트: `frontend/components/ui/`
- 스타일 이름: `미니멀 화이트` — 흰 바탕, 옅은 회색 선, 강조색 하나(진한 청록)

---

## 1. 제일 빠른 시작

```tsx
import { PageTitle, Card, Button, Badge, Row } from "@/components/ui";

export default function 내화면() {
  return (
    <>
      <PageTitle title="할 일" sub="오늘 마감 4건" />
      <Card>
        <Row between>
          <b>사양서 검토 회신</b>
          <Badge tone="crit">오늘 마감</Badge>
        </Row>
        <Button>완료 처리</Button>
      </Card>
    </>
  );
}
```

바깥 여백과 위쪽 바·탭은 `app/layout.tsx` 가 이미 씌워 줍니다.
화면 파일에서는 `<div className="wrap">` 같은 걸 다시 만들지 마세요.

---

## 2. 컴포넌트 목록

### 담는 것

| 이름 | 언제 | 예시 |
| --- | --- | --- |
| `Card` | 내용 한 덩어리 | `<Card quiet hoverable>` |
| `Panel` | 제목·개수가 붙은 목록 상자 | `<Panel title="오늘 마감" count={4}>` |
| `Grid` | 카드 여러 개 나란히 | `<Grid cols={3}>` (없으면 폭에 맞춰 자동) |
| `Row` | 한 줄에 나란히 | `<Row between>` 은 양끝 정렬 |
| `Section` | 화면 안의 한 구획 | `<Section>` |

### 제목

| 이름 | 언제 |
| --- | --- |
| `PageTitle` | 화면 맨 위 큰 제목 + 한 줄 설명 |
| `SectionHead` | 구획 제목(작은 대문자) + 오른쪽 링크/버튼 |

```tsx
<SectionHead label="최근 실행" action={<a href="/runs">전체 보기</a>} />
```

### 버튼

```tsx
<Button>기본</Button>                       {/* 이 화면에서 제일 중요한 동작 하나만 */}
<Button variant="ghost">보조</Button>        {/* 나머지 */}
<Button variant="danger">삭제</Button>       {/* 되돌릴 수 없는 것 */}
<Button small />  <Button block />           {/* 작게 / 가로 꽉 */}
<Chip active>필터</Chip>                     {/* 알약 모양, 필터나 추천 문구 */}
<LinkButton href="...">내려받기</LinkButton> {/* 링크인데 버튼처럼 */}
```

한 화면에 기본(진한) 버튼은 하나만 두세요. 나머지는 `ghost` 입니다.

### 입력

```tsx
<Field label="사번" hint="예) E1001" htmlFor="uid">
  <Input id="uid" value={v} onChange={...} />
</Field>

<Textarea rows={4} />
<Select>...</Select>
<Checkbox label="메일을 실제로 보냅니다" checked={...} onChange={...} />
```

`Field` 의 `label` 은 꼭 넣어 주세요. 화면 읽어 주는 프로그램이 이걸 읽습니다.
`htmlFor` 와 입력의 `id` 를 맞춰 두면 라벨을 눌러도 입력으로 들어갑니다.

### 상태 보여 주기

| 이름 | 뜻 | 예시 |
| --- | --- | --- |
| `Badge` | **지금 어떤지** (둥근 알약) | `<Badge tone="ok">완료</Badge>` |
| `Tag` | **무엇인지** 분류 (네모) | `<Tag>메일</Tag>` |
| `Dot` | 아주 작은 상태 점 | `<Dot tone="crit" />` |
| `Bar` | 0~100 막대 | `<Bar percent={72} />` |
| `When` | 날짜·시간 (폭 고른 글씨) | `<When>12분 전</When>` |
| `IconTile` | 앱·카드 앞 네모 아이콘 | `<IconTile large>메일</IconTile>` |

`tone` 은 다섯 가지뿐입니다. 이 뜻을 앱 전체에서 똑같이 씁니다.

- `neutral` — 그냥 정보
- `accent` — 진행 중, 강조
- `ok` — 성공, 완료
- `warn` — 확인 필요, 곧 마감
- `crit` — 실패, 지남

### 알림 · 빈 화면

```tsx
<Alert tone="crit">메일 서버에 연결하지 못했습니다.</Alert>
<Empty>아직 올린 양식이 없습니다. 아래에서 파일을 올려 보세요.</Empty>
<Lines>{앱이 돌려준 여러 줄 글}</Lines>
<Lines boxed>{메일 본문처럼 앞뒤와 구분해야 하는 글}</Lines>
<Pre>{로그·JSON 같은 기계가 쓴 글}</Pre>
```

`Empty` 에는 **다음에 무엇을 하면 되는지**를 적어 주세요.
"없습니다."로만 끝내지 않습니다.

사람이 읽는 한글 문장은 `Pre` 대신 `Lines` 를 씁니다. `Pre` 는 글꼴이
고정폭이라 한글이 띄엄띄엄 보입니다. 둘 다 줄바꿈은 그대로 지킵니다.

### 목록 · 표

```tsx
<List>
  <ListItem tone="crit" title="사양서 회신" meta="박선임 지시" when="오늘 18:00" />
</List>

<Rows>            {/* 테두리로 감싼 줄 목록. 자식 하나가 한 줄 */}
  <div>…</div>
</Rows>

<Table>
  <thead><tr><th>사번</th><th className="num">토큰</th></tr></thead>
  ...
</Table>
```

표에서 숫자 칸에는 `className="num"` 을 주세요. 오른쪽 정렬 + 폭 고른 글씨가 됩니다.

### 탭

- 주소가 바뀌는 탭(화면 이동): `NavTabs` — 위쪽 바에 이미 있습니다.
- 한 화면 안에서 내용만 바꾸는 탭: `Tabs`

```tsx
const [tab, setTab] = useState<"a" | "b">("a");
<Tabs items={[{ key: "a", label: "대기" }, { key: "b", label: "완료" }]}
      value={tab} onChange={setTab} />
```

---

## 3. 토큰 (색·글꼴·여백)

컴포넌트로 안 되는 자리에서는 `style` 에 변수로 넣습니다.

```tsx
<div style={{ marginTop: "var(--space-4)", color: "var(--muted)" }} />
```

| 쓰임 | 변수 |
| --- | --- |
| 페이지 바탕 / 눌린 면 | `--bg` `--surface` `--surface-2` |
| 선 | `--line` `--line-soft` |
| 글자 | `--ink` `--ink-2` `--muted` |
| 강조 | `--accent` `--accent-soft` `--accent-line` |
| 상태 | `--ok` `--warn` `--crit` (+ `-soft` `-line`) |
| 글자 크기 | `--text-xs` `--text-sm` `--text-base` `--text-md` `--text-lg` `--text-xl` |
| 여백 | `--space-1`(4px) ~ `--space-10`(40px) |
| 모서리 | `--radius-sm` `--radius-md` `--radius-lg` `--radius-pill` |

### 지키면 좋은 것

1. **강조색은 하나입니다.** 색으로 구분하고 싶으면 `tone` 을 쓰세요.
2. **여백은 4의 배수만.** `--space-*` 밖의 값은 쓰지 않습니다.
3. **바깥에서 아무것도 안 받아옵니다.** 사내망은 인터넷이 막혀 있어
   구글 폰트·아이콘 CDN·외부 CSS 를 넣으면 회사에서 글꼴이 깨집니다.
   글꼴은 기기에 있는 것만 쓰고(`--font-sans`), 아이콘은 이모지나 글자를 씁니다.
4. **다크 모드는 아직 없습니다.** 나중에 넣을 때 `globals.css` 의
   `:root` 값만 바꾸면 되도록 만들어 뒀으니, 화면 파일에 색을 직접 쓰지 마세요.

---

## 4. 이미 있던 화면은요?

뼈대와 다른 갈래에서 만든 화면이 `.box` `.grid` `.row` `.muted` `.tag`
같은 옛날 클래스를 쓰고 있습니다. 그 이름들도 `globals.css` 에 **새 디자인으로
다시 칠해 뒀기 때문에** 손대지 않아도 새 모양으로 보입니다.

다만 새로 만들거나 크게 고칠 때는 위의 컴포넌트로 바꿔 주세요.
옛날 클래스는 언젠가 지웁니다.

바꾸는 방법은 거의 1:1 입니다.

| 옛날 | 지금 |
| --- | --- |
| `<div className="box">` | `<Card>` |
| `<div className="row">` | `<Row>` |
| `<div className="grid">` | `<Grid>` |
| `<span className="muted">` | `<Muted>` |
| `<span className="tag">` | `<Tag>` 또는 `<Badge tone="...">` |
| `<button className="ghost">` | `<Button variant="ghost">` |
| `<label>…</label><input />` | `<Field label="…"><Input /></Field>` |

---

## 5. 확인하는 법

```bash
cd frontend && npm run build     # 타입·빌드 확인
cd frontend && npm run dev       # localhost:3000 에서 눈으로 확인
```

화면을 하나 만들었으면 브라우저 창을 좁게 줄여 보세요.
가로 560px 아래에서 카드가 한 줄씩 쌓이고 표가 넘치지 않으면 됩니다.

---

## 6. 겹쳐 뜨는 상자 (Modal)

자주 하지 않는 일(앱 등록처럼)은 화면에 늘 펼쳐 두지 말고 버튼 뒤에 넣습니다.
목록이 기본 화면이고, 필요할 때만 상자가 열리는 구조입니다.

```tsx
const [open, setOpen] = useState(false);

<Button onClick={() => setOpen(true)}>＋ 앱 등록</Button>

<Modal
  open={open}
  onClose={() => setOpen(false)}
  title="내 앱 등록하기"
  sub="한 줄 설명"
  footer={<Button onClick={save}>등록하기</Button>}
>
  …입력 칸들…
</Modal>
```

Esc 로 닫히고, 열려 있는 동안 뒤 화면은 따라 스크롤되지 않습니다.

---

## 7. 테마

화면 전체 모양은 `<html data-theme="…">` 한 글자로 갈아 끼웁니다.
화면 코드(.tsx)는 전혀 손대지 않습니다.

| 파일 | 하는 일 |
| --- | --- |
| `app/globals.css` | 기본 테마 "미니멀 화이트" (토큰 + `.ui-*` 규칙) |
| `app/themes.css` | 그 위에 덧씌우는 다른 테마들 |
| `lib/theme.ts` | 고를 수 있는 테마 목록, 저장·적용 |
| `components/ui/theme-picker.tsx` | 오른쪽 위 고르는 메뉴 |
| `backend` `PUT /api/auth/me/settings` | 고른 값을 개인 계정에 저장 |

새 테마를 넣는 자세한 순서는 `app/themes.css` 맨 위 주석에 적어 두었습니다.
**테마가 하나뿐일 때는 고르는 메뉴가 나오지 않습니다.**

틀은 `.ui-shell` 안에 `.ui-nav`(메뉴)와 `.ui-wrap`(본문) 둘뿐이라,
이 둘을 좌우로 세우면 세로 메뉴 테마가 됩니다.

```css
[data-theme="example"] .ui-shell {
  display: grid;
  grid-template-columns: var(--nav-width) minmax(0, 1fr);
}
```
