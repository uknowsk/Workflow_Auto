"use client";

// 계산기.
//
// eval() 은 쓰지 않습니다. 사용자가 적은 글자가 그대로 실행되면 위험하니
// 식을 직접 읽어 사칙연산만 계산합니다(백엔드 도구 모음 앱과 같은 원칙).

import { useEffect, useRef, useState } from "react";
import { Alert, Button, Empty, Muted, Row } from "@/components/ui";

/** 식을 숫자·연산자로 잘라 냅니다. */
function tokenize(text: string): string[] {
  const tokens: string[] = [];
  let index = 0;
  while (index < text.length) {
    const ch = text[index];
    if (ch === " " || ch === ",") {
      index += 1;
    } else if (/[0-9.]/.test(ch)) {
      let num = "";
      while (index < text.length && /[0-9.]/.test(text[index])) {
        num += text[index];
        index += 1;
      }
      tokens.push(num);
    } else if ("+-*/%^()".includes(ch)) {
      tokens.push(ch);
      index += 1;
    } else if (ch === "×") {
      tokens.push("*");
      index += 1;
    } else if (ch === "÷") {
      tokens.push("/");
      index += 1;
    } else {
      throw new Error(`쓸 수 없는 글자입니다: ${ch}`);
    }
  }
  return tokens;
}

/** 재귀 하강 파서. 괄호 > 거듭제곱 > 곱셈/나눗셈 > 덧셈/뺄셈 순으로 묶습니다. */
function parse(tokens: string[]): number {
  let pos = 0;

  const peek = () => tokens[pos];
  const eat = () => tokens[pos++];

  function primary(): number {
    const token = eat();
    if (token === undefined) throw new Error("식이 덜 끝났습니다.");
    if (token === "(") {
      const value = addition();
      if (eat() !== ")") throw new Error("괄호가 짝이 안 맞습니다.");
      return value;
    }
    if (token === "-") return -primary();
    if (token === "+") return primary();
    const value = Number(token);
    if (Number.isNaN(value)) throw new Error(`숫자가 아닙니다: ${token}`);
    return value;
  }

  function power(): number {
    const base = primary();
    if (peek() === "^") {
      eat();
      return base ** power();
    }
    return base;
  }

  function multiplication(): number {
    let value = power();
    while (peek() === "*" || peek() === "/" || peek() === "%") {
      const op = eat();
      const right = power();
      if ((op === "/" || op === "%") && right === 0) {
        throw new Error("0 으로는 나눌 수 없습니다.");
      }
      value = op === "*" ? value * right : op === "/" ? value / right : value % right;
    }
    return value;
  }

  function addition(): number {
    let value = multiplication();
    while (peek() === "+" || peek() === "-") {
      const op = eat();
      const right = multiplication();
      value = op === "+" ? value + right : value - right;
    }
    return value;
  }

  const result = addition();
  if (pos !== tokens.length) throw new Error("식을 끝까지 읽지 못했습니다.");
  return result;
}

export function calculate(expression: string): number {
  return parse(tokenize(expression));
}

function pretty(value: number): string {
  const rounded = Math.round(value * 1e10) / 1e10;
  return rounded.toLocaleString("ko-KR", { maximumFractionDigits: 10 });
}

const KEYS = [
  "7", "8", "9", "/",
  "4", "5", "6", "*",
  "1", "2", "3", "-",
  "0", ".", "(", ")",
];

export default function Calculator() {
  const [expression, setExpression] = useState("");
  const [error, setError] = useState("");
  const [history, setHistory] = useState<{ expression: string; result: string }[]>([]);
  const inputRef = useRef<HTMLInputElement | null>(null);

  // 입력하는 동안 결과를 미리 보여 줍니다. 틀린 식이면 조용히 비워 둡니다.
  let preview = "";
  try {
    if (expression.trim()) preview = pretty(calculate(expression));
  } catch {
    preview = "";
  }

  const run = () => {
    if (!expression.trim()) return;
    try {
      const value = calculate(expression);
      setHistory((prev) => [{ expression, result: pretty(value) }, ...prev].slice(0, 20));
      setExpression(String(Math.round(value * 1e10) / 1e10));
      setError("");
    } catch (problem) {
      setError(problem instanceof Error ? problem.message : String(problem));
    }
  };

  const type = (key: string) => {
    setExpression((prev) => prev + key);
    setError("");
    inputRef.current?.focus();
  };

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  return (
    <div className="tool-calc">
      <input
        ref={inputRef}
        className="tool-calc__display"
        value={expression}
        placeholder="0"
        inputMode="text"
        aria-label="계산식"
        onChange={(event) => {
          setExpression(event.target.value);
          setError("");
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter") run();
        }}
      />
      <div className="tool-calc__preview">{preview ? `= ${preview}` : " "}</div>

      {error && <Alert tone="crit">{error}</Alert>}

      <div className="tool-calc__pad">
        {KEYS.map((key) => (
          <Button key={key} variant="ghost" onClick={() => type(key)}>
            {key === "*" ? "×" : key === "/" ? "÷" : key}
          </Button>
        ))}
        <Button variant="ghost" onClick={() => type("+")}>
          +
        </Button>
        <Button variant="ghost" onClick={() => setExpression((prev) => prev.slice(0, -1))}>
          ⌫
        </Button>
        <Button
          variant="ghost"
          onClick={() => {
            setExpression("");
            setError("");
          }}
        >
          C
        </Button>
        <Button className="tool-calc__equals" onClick={run}>
          =
        </Button>
      </div>

      <Muted>Enter 를 눌러도 계산됩니다. 괄호와 ^(거듭제곱)도 씁니다.</Muted>

      {history.length ? (
        <div className="ui-rows tool-calc__history">
          {history.map((item, index) => (
            <Row key={`${item.expression}-${index}`} between>
              <button
                type="button"
                className="tool-calc__recall"
                onClick={() => setExpression(item.expression)}
              >
                {item.expression}
              </button>
              <strong>{item.result}</strong>
            </Row>
          ))}
        </div>
      ) : (
        <Empty>계산한 식이 여기 쌓입니다. 눌러서 다시 불러올 수 있어요.</Empty>
      )}
    </div>
  );
}
