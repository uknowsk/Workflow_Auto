"use client";

// 텍스트 정리: 글자 수·바이트 수 세기, 공백·줄바꿈 정리, JSON 보기 좋게.
//
// 바이트 수는 사내 시스템의 글자 수 제한(대개 UTF-8 기준)을 확인할 때 씁니다.
// 한글 한 글자가 3바이트라 "글자 수는 되는데 안 들어가는" 일이 자주 생깁니다.

import { useMemo, useState } from "react";
import { Alert, Button, Muted, Row, Textarea } from "@/components/ui";

function countBytes(text: string): number {
  return new TextEncoder().encode(text).length;
}

/** 줄 끝 공백, 세 줄 이상 빈 줄, 잇따른 공백을 정리합니다. */
function tidy(text: string): string {
  return text
    .replace(/\r\n/g, "\n")
    .split("\n")
    .map((line) => line.replace(/[ \t]+/g, " ").trimEnd())
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

export default function TextTools() {
  const [text, setText] = useState("");
  const [message, setMessage] = useState("");

  const stats = useMemo(() => {
    const trimmed = text.trim();
    return {
      chars: text.length,
      charsNoSpace: text.replace(/\s/g, "").length,
      bytes: countBytes(text),
      words: trimmed ? trimmed.split(/\s+/).length : 0,
      lines: text ? text.split("\n").length : 0,
    };
  }, [text]);

  const apply = (next: string, note: string) => {
    setText(next);
    setMessage(note);
  };

  const prettyJson = () => {
    try {
      apply(JSON.stringify(JSON.parse(text), null, 2), "JSON 을 보기 좋게 폈습니다.");
    } catch (problem) {
      setMessage(`JSON 이 아닙니다: ${problem instanceof Error ? problem.message : problem}`);
    }
  };

  const minifyJson = () => {
    try {
      apply(JSON.stringify(JSON.parse(text)), "JSON 을 한 줄로 줄였습니다.");
    } catch (problem) {
      setMessage(`JSON 이 아닙니다: ${problem instanceof Error ? problem.message : problem}`);
    }
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setMessage("복사했습니다.");
    } catch {
      setMessage("복사가 막혀 있습니다. 글상자에서 직접 복사해 주세요.");
    }
  };

  return (
    <div className="tool-text">
      <Textarea
        value={text}
        rows={10}
        placeholder="정리할 글을 붙여 넣으세요."
        onChange={(event) => {
          setText(event.target.value);
          setMessage("");
        }}
      />

      <div className="tool-text__stats">
        <span>
          글자 <strong>{stats.chars.toLocaleString("ko-KR")}</strong>
        </span>
        <span>
          공백 빼고 <strong>{stats.charsNoSpace.toLocaleString("ko-KR")}</strong>
        </span>
        <span>
          바이트 <strong>{stats.bytes.toLocaleString("ko-KR")}</strong>
        </span>
        <span>
          단어 <strong>{stats.words.toLocaleString("ko-KR")}</strong>
        </span>
        <span>
          줄 <strong>{stats.lines.toLocaleString("ko-KR")}</strong>
        </span>
      </div>

      <Row>
        <Button variant="ghost" small onClick={() => apply(tidy(text), "공백과 빈 줄을 정리했습니다.")}>
          공백·줄바꿈 정리
        </Button>
        <Button
          variant="ghost"
          small
          onClick={() => apply(text.replace(/\n+/g, " ").replace(/\s+/g, " ").trim(), "한 줄로 붙였습니다.")}
        >
          한 줄로 붙이기
        </Button>
        <Button variant="ghost" small onClick={prettyJson}>
          JSON 펴기
        </Button>
        <Button variant="ghost" small onClick={minifyJson}>
          JSON 줄이기
        </Button>
        <Button variant="ghost" small onClick={copy}>
          복사
        </Button>
        <Button variant="ghost" small onClick={() => apply("", "")}>
          비우기
        </Button>
      </Row>

      {message && <Alert tone="ok">{message}</Alert>}

      <Muted>
        바이트 수는 UTF-8 기준입니다. 한글 한 글자가 3바이트라, 글자 수는 넉넉해도
        사내 시스템의 바이트 제한에 걸릴 수 있습니다.
      </Muted>
    </div>
  );
}
