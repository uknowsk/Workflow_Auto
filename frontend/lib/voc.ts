// 의견(VOC) 화면에서 같이 쓰는 말과 색.
// 한 곳에 모아 두지 않으면 앱스토어와 의견함에서 같은 상태가 다른 말로 보입니다.
import type { Tone } from "@/components/ui";
import type { VocKind, VocStatus } from "@/lib/api";

export const KIND_LABEL: Record<VocKind, string> = {
  bug: "잘 안 돼요",
  idea: "이런 게 있으면",
  question: "사용법 문의",
};

export const STATUS_LABEL: Record<VocStatus, string> = {
  open: "접수",
  in_progress: "확인 중",
  done: "처리 완료",
  wontfix: "안 고침",
};

export const STATUS_TONE: Record<VocStatus, Tone> = {
  open: "warn",
  in_progress: "accent",
  done: "ok",
  wontfix: "neutral",
};

export const KIND_TONE: Record<VocKind, Tone> = {
  bug: "crit",
  idea: "accent",
  question: "neutral",
};

/** 2026-09-20 처럼 날짜만. 의견함에서는 시각까지 볼 일이 없습니다. */
export function day(iso: string): string {
  return (iso || "").slice(0, 10);
}

/** 별점을 ★★★☆☆ 로. 0 이면 빈 문자열(안 매긴 것). */
export function stars(rating: number): string {
  return rating > 0 ? "★".repeat(rating) + "☆".repeat(5 - rating) : "";
}
