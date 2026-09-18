"use client";

// 그리기 도구.
//
// 밖에서 받아오는 라이브러리 없이 브라우저 캔버스만 씁니다(사내 폐쇄망).
//
// 그린 것을 "그림 데이터"로 남기지 않고 도형 목록으로 들고 있다가 매번 다시
// 그립니다. 그래야 되돌리기가 목록에서 하나 빼는 일로 끝납니다.
// 캔버스 크기는 1600x1000 으로 고정하고 화면에서는 폭에 맞춰 줄여 보여 줍니다.
// 패널을 넓히거나 전체 화면으로 바꿔도 그림이 어긋나지 않게 하려는 것입니다.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, DrawingSummary } from "@/lib/api";
import {
  Alert,
  Button,
  Chip,
  Empty,
  Input,
  Muted,
  Row,
} from "@/components/ui";

const W = 1600;
const H = 1000;

type ToolKind = "pen" | "eraser" | "line" | "rect" | "ellipse" | "arrow" | "text";

type Point = { x: number; y: number };

type Shape =
  | { kind: "pen" | "eraser"; points: Point[]; color: string; width: number }
  | {
      kind: "line" | "rect" | "ellipse" | "arrow";
      from: Point;
      to: Point;
      color: string;
      width: number;
    }
  | { kind: "text"; at: Point; text: string; color: string; size: number }
  | { kind: "image"; src: string };

const TOOLS: { key: ToolKind; label: string; icon: string }[] = [
  { key: "pen", label: "펜", icon: "✏️" },
  { key: "eraser", label: "지우개", icon: "🧽" },
  { key: "line", label: "직선", icon: "／" },
  { key: "rect", label: "사각형", icon: "▭" },
  { key: "ellipse", label: "원", icon: "◯" },
  { key: "arrow", label: "화살표", icon: "→" },
  { key: "text", label: "글자", icon: "T" },
];

const COLORS = [
  "#1a1a17",
  "#ae2e24",
  "#9c5b12",
  "#16734a",
  "#0b6e63",
  "#1d4ed8",
  "#6d28d9",
  "#ffffff",
];

const WIDTHS = [2, 4, 8, 16];

/** 도형 하나를 캔버스에 그립니다. */
function paint(
  ctx: CanvasRenderingContext2D,
  shape: Shape,
  images: Map<string, HTMLImageElement>
) {
  ctx.save();
  if (shape.kind === "image") {
    const img = images.get(shape.src);
    if (img && img.complete) ctx.drawImage(img, 0, 0, W, H);
    ctx.restore();
    return;
  }
  if (shape.kind === "text") {
    ctx.fillStyle = shape.color;
    ctx.font = `${shape.size}px system-ui, "Apple SD Gothic Neo", "Malgun Gothic", sans-serif`;
    ctx.textBaseline = "top";
    shape.text.split("\n").forEach((line, i) => {
      ctx.fillText(line, shape.at.x, shape.at.y + i * shape.size * 1.3);
    });
    ctx.restore();
    return;
  }

  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.lineWidth = shape.width;
  // 지우개는 "흰색으로 칠하기"가 아니라 화면에서 지우는 방식이라,
  // 나중에 배경색을 바꾸거나 그림 위에 겹쳐 그려도 자연스럽게 지워집니다.
  ctx.globalCompositeOperation =
    shape.kind === "eraser" ? "destination-out" : "source-over";
  ctx.strokeStyle = shape.kind === "eraser" ? "#000" : shape.color;

  if (shape.kind === "pen" || shape.kind === "eraser") {
    const pts = shape.points;
    if (pts.length === 1) {
      // 점 하나만 찍은 경우도 보이게 합니다.
      ctx.beginPath();
      ctx.arc(pts[0].x, pts[0].y, shape.width / 2, 0, Math.PI * 2);
      ctx.fillStyle = shape.kind === "eraser" ? "#000" : shape.color;
      ctx.fill();
      ctx.restore();
      return;
    }
    ctx.beginPath();
    ctx.moveTo(pts[0].x, pts[0].y);
    for (let i = 1; i < pts.length; i += 1) ctx.lineTo(pts[i].x, pts[i].y);
    ctx.stroke();
    ctx.restore();
    return;
  }

  // 여기서부터는 두 점(시작·끝)으로 그리는 도형만 남습니다.
  if (
    shape.kind !== "line" &&
    shape.kind !== "rect" &&
    shape.kind !== "ellipse" &&
    shape.kind !== "arrow"
  ) {
    ctx.restore();
    return;
  }
  const { from, to } = shape;
  ctx.beginPath();
  if (shape.kind === "line") {
    ctx.moveTo(from.x, from.y);
    ctx.lineTo(to.x, to.y);
    ctx.stroke();
  } else if (shape.kind === "rect") {
    ctx.rect(from.x, from.y, to.x - from.x, to.y - from.y);
    ctx.stroke();
  } else if (shape.kind === "ellipse") {
    ctx.ellipse(
      (from.x + to.x) / 2,
      (from.y + to.y) / 2,
      Math.abs(to.x - from.x) / 2,
      Math.abs(to.y - from.y) / 2,
      0,
      0,
      Math.PI * 2
    );
    ctx.stroke();
  } else {
    // 화살표: 몸통을 긋고 끝에 날개 두 개를 붙입니다.
    ctx.moveTo(from.x, from.y);
    ctx.lineTo(to.x, to.y);
    ctx.stroke();
    const angle = Math.atan2(to.y - from.y, to.x - from.x);
    const head = Math.max(12, shape.width * 4);
    ctx.beginPath();
    ctx.moveTo(to.x, to.y);
    ctx.lineTo(
      to.x - head * Math.cos(angle - Math.PI / 7),
      to.y - head * Math.sin(angle - Math.PI / 7)
    );
    ctx.moveTo(to.x, to.y);
    ctx.lineTo(
      to.x - head * Math.cos(angle + Math.PI / 7),
      to.y - head * Math.sin(angle + Math.PI / 7)
    );
    ctx.stroke();
  }
  ctx.restore();
}

export default function DrawTool() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const imagesRef = useRef(new Map<string, HTMLImageElement>());
  const draftRef = useRef<Shape | null>(null);
  const textInputRef = useRef<HTMLInputElement | null>(null);
  const drawingRef = useRef(false);

  const [shapes, setShapes] = useState<Shape[]>([]);
  const [redo, setRedo] = useState<Shape[]>([]);
  const [tool, setTool] = useState<ToolKind>("pen");
  const [color, setColor] = useState(COLORS[0]);
  const [width, setWidth] = useState(4);
  const [textAt, setTextAt] = useState<Point | null>(null);
  const [textValue, setTextValue] = useState("");

  const [saved, setSaved] = useState<DrawingSummary[]>([]);
  const [openId, setOpenId] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [showSaved, setShowSaved] = useState(false);

  /** 도형 목록 + 그리는 중인 도형을 한 번에 다시 그립니다. */
  const render = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, W, H);
    shapes.forEach((shape) => paint(ctx, shape, imagesRef.current));
    if (draftRef.current) paint(ctx, draftRef.current, imagesRef.current);
  }, [shapes]);

  useEffect(() => {
    render();
  }, [render]);

  const reloadSaved = useCallback(() => {
    api
      .listDrawings()
      .then(setSaved)
      .catch(() => {
        /* 로그인 전이면 목록이 없을 뿐이라 화면을 막지 않습니다. */
      });
  }, []);

  useEffect(() => {
    reloadSaved();
  }, [reloadSaved]);

  /** 화면 위 좌표를 캔버스 좌표(1600x1000)로 바꿉니다. */
  const toCanvas = (event: React.PointerEvent<HTMLCanvasElement>): Point => {
    const box = event.currentTarget.getBoundingClientRect();
    return {
      x: ((event.clientX - box.left) / box.width) * W,
      y: ((event.clientY - box.top) / box.height) * H,
    };
  };

  const commit = (shape: Shape) => {
    setShapes((prev) => [...prev, shape]);
    setRedo([]);
  };

  const onPointerDown = (event: React.PointerEvent<HTMLCanvasElement>) => {
    const at = toCanvas(event);
    if (tool === "text") {
      setTextAt(at);
      setTextValue("");
      return;
    }
    event.currentTarget.setPointerCapture(event.pointerId);
    drawingRef.current = true;
    draftRef.current =
      tool === "pen" || tool === "eraser"
        ? { kind: tool, points: [at], color, width }
        : { kind: tool, from: at, to: at, color, width };
    render();
  };

  const onPointerMove = (event: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawingRef.current || !draftRef.current) return;
    const at = toCanvas(event);
    const draft = draftRef.current;
    if (draft.kind === "pen" || draft.kind === "eraser") {
      draft.points.push(at);
    } else if (
      draft.kind === "line" ||
      draft.kind === "rect" ||
      draft.kind === "ellipse" ||
      draft.kind === "arrow"
    ) {
      draft.to = at;
    }
    render();
  };

  const onPointerUp = () => {
    if (!drawingRef.current) return;
    drawingRef.current = false;
    const draft = draftRef.current;
    draftRef.current = null;
    if (!draft) return;
    // 클릭만 하고 끌지 않은 도형은 남기지 않습니다(빈 점이 쌓이지 않게).
    if (
      (draft.kind === "line" ||
        draft.kind === "rect" ||
        draft.kind === "ellipse" ||
        draft.kind === "arrow") &&
      Math.abs(draft.to.x - draft.from.x) < 3 &&
      Math.abs(draft.to.y - draft.from.y) < 3
    ) {
      render();
      return;
    }
    commit(draft);
  };

  const addText = () => {
    if (textAt && textValue.trim()) {
      commit({
        kind: "text",
        at: textAt,
        text: textValue,
        color,
        size: Math.max(16, width * 6),
      });
    }
    setTextAt(null);
    setTextValue("");
  };

  const undo = useCallback(() => {
    setShapes((prev) => {
      if (!prev.length) return prev;
      setRedo((r) => [...r, prev[prev.length - 1]]);
      return prev.slice(0, -1);
    });
  }, []);

  const redoOne = useCallback(() => {
    setRedo((prev) => {
      if (!prev.length) return prev;
      setShapes((s) => [...s, prev[prev.length - 1]]);
      return prev.slice(0, -1);
    });
  }, []);

  const clearAll = () => {
    if (shapes.length && !window.confirm("그린 것을 모두 지울까요?")) return;
    setShapes([]);
    setRedo([]);
    setOpenId(null);
    setTitle("");
  };

  // 되돌리기 단축키. 글자 입력 중일 때는 가로채지 않습니다.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const tag = (event.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (!(event.ctrlKey || event.metaKey)) return;
      if (event.key === "z" && !event.shiftKey) {
        event.preventDefault();
        undo();
      } else if (event.key === "y" || (event.key === "z" && event.shiftKey)) {
        event.preventDefault();
        redoOne();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [undo, redoOne]);

  const dataUrl = () => canvasRef.current?.toDataURL("image/png") || "";

  const download = () => {
    const url = dataUrl();
    if (!url) return;
    const link = document.createElement("a");
    link.href = url;
    link.download = `${title.trim() || "그림"}.png`;
    link.click();
  };

  const save = async () => {
    const image = dataUrl();
    if (!image) return;
    setBusy(true);
    setMessage("");
    try {
      const body = {
        title: title.trim() || `그림 ${new Date().toLocaleString("ko-KR")}`,
        image,
        width: W,
        height: H,
      };
      if (openId) {
        await api.updateDrawing(openId, body);
        setMessage("덮어썼습니다.");
      } else {
        const created = await api.createDrawing(body);
        setOpenId(created.id);
        setMessage("저장했습니다.");
      }
      setTitle(body.title);
      reloadSaved();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setBusy(false);
    }
  };

  const open = async (id: string) => {
    setBusy(true);
    setMessage("");
    try {
      const full = await api.getDrawing(id);
      // 불러온 그림은 바닥 한 장으로 깔고, 그 위에 이어서 그립니다.
      const img = new Image();
      img.src = full.image;
      await img.decode().catch(() => undefined);
      imagesRef.current.set(full.image, img);
      setShapes([{ kind: "image", src: full.image }]);
      setRedo([]);
      setOpenId(full.id);
      setTitle(full.title);
      setShowSaved(false);
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: string) => {
    if (!window.confirm("이 그림을 지울까요?")) return;
    try {
      await api.deleteDrawing(id);
      if (openId === id) setOpenId(null);
      reloadSaved();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    }
  };

  // 글자 입력칸은 그려진 다음 차례에 focus 합니다.
  // 누른 그 순간에 focus 하면, 브라우저가 클릭을 마무리하면서 곧바로 focus 를
  // 거둬 가 입력칸이 떴다가 바로 사라집니다.
  useEffect(() => {
    if (!textAt) return;
    const frame = requestAnimationFrame(() => textInputRef.current?.focus());
    return () => cancelAnimationFrame(frame);
  }, [textAt]);

  const textStyle = useMemo(() => {
    if (!textAt) return undefined;
    // 글자 입력칸을 클릭한 자리에 겹쳐 띄웁니다(캔버스 좌표 → 백분율).
    return { left: `${(textAt.x / W) * 100}%`, top: `${(textAt.y / H) * 100}%` };
  }, [textAt]);

  return (
    <div className="tool-draw">
      <Row className="tool-draw__bar">
        {TOOLS.map((item) => (
          <Chip
            key={item.key}
            active={tool === item.key}
            onClick={() => setTool(item.key)}
            title={item.label}
          >
            <span aria-hidden="true">{item.icon}</span> {item.label}
          </Chip>
        ))}
      </Row>

      <Row className="tool-draw__bar">
        <span className="ui-eyebrow">색</span>
        {COLORS.map((value) => (
          <button
            key={value}
            type="button"
            className={`tool-draw__swatch${color === value ? " is-on" : ""}`}
            style={{ background: value }}
            aria-label={`색 ${value}`}
            aria-pressed={color === value}
            onClick={() => setColor(value)}
          />
        ))}
        <span className="ui-eyebrow">굵기</span>
        {WIDTHS.map((value) => (
          <Chip key={value} active={width === value} onClick={() => setWidth(value)}>
            {value}
          </Chip>
        ))}
      </Row>

      <Row className="tool-draw__bar">
        <Button variant="ghost" small onClick={undo} disabled={!shapes.length}>
          되돌리기
        </Button>
        <Button variant="ghost" small onClick={redoOne} disabled={!redo.length}>
          다시하기
        </Button>
        <Button variant="ghost" small onClick={clearAll}>
          전부 지우기
        </Button>
        <Button variant="ghost" small onClick={download}>
          PNG 로 저장
        </Button>
      </Row>

      <div className="tool-draw__stage">
        <canvas
          ref={canvasRef}
          width={W}
          height={H}
          className="tool-draw__canvas"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
        />
        {textAt && (
          <div className="tool-draw__text" style={textStyle}>
            <input
              ref={textInputRef}
              className="ui-input"
              value={textValue}
              placeholder="글자를 쓰고 Enter"
              onChange={(event) => setTextValue(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") addText();
                if (event.key === "Escape") setTextAt(null);
              }}
              onBlur={addText}
            />
          </div>
        )}
      </div>

      <Row className="tool-draw__bar">
        <Input
          value={title}
          placeholder="그림 이름"
          onChange={(event) => setTitle(event.target.value)}
        />
        <Button small onClick={save} disabled={busy}>
          {openId ? "덮어쓰기" : "계정에 저장"}
        </Button>
        {openId && (
          <Button
            variant="ghost"
            small
            onClick={() => {
              setOpenId(null);
              setMessage("이제 저장하면 새 그림으로 남습니다.");
            }}
          >
            새 그림으로
          </Button>
        )}
        <Button variant="ghost" small onClick={() => setShowSaved((on) => !on)}>
          저장한 그림 {saved.length}
        </Button>
      </Row>

      {message && <Alert tone="ok">{message}</Alert>}

      {showSaved &&
        (saved.length ? (
          <div className="ui-rows">
            {saved.map((item) => (
              <div key={item.id} className="tool-draw__saved">
                <button type="button" className="tool-draw__saved-name" onClick={() => open(item.id)}>
                  {item.title || "이름 없음"}
                </button>
                <Muted>{new Date(item.updated_at).toLocaleString("ko-KR")}</Muted>
                <Button variant="danger" small onClick={() => remove(item.id)}>
                  지우기
                </Button>
              </div>
            ))}
          </div>
        ) : (
          <Empty>아직 저장한 그림이 없습니다. 그린 뒤 &quot;계정에 저장&quot;을 눌러 보세요.</Empty>
        ))}
    </div>
  );
}
