// 화면 테마. 색만 바꾸는 게 아니라 배치·글꼴·구분 방식이 통째로 다릅니다.
//
// 모양은 전부 CSS 가 결정합니다. 여기서 하는 일은 <html data-theme="..."> 에
// 이름 하나를 써 넣는 것뿐이고, app/globals.css(기본)와 app/themes.css(나머지)가
// 그 이름을 보고 다른 모양을 입힙니다. 화면 코드는 손대지 않아도 됩니다.

// 테마를 더할 때는 여기와 THEMES, backend/app/api/auth.py 의 THEMES 를 함께 고칩니다.
export type ThemeName = "white";

export const DEFAULT_THEME: ThemeName = "white";

export const THEMES: {
  name: ThemeName;
  label: string;
  /** 고르는 자리에 한 줄로 보여 줄 설명 */
  note: string;
  /** 미리보기용 색 세 가지 (바탕, 선, 강조) */
  swatch: [string, string, string];
}[] = [
  {
    name: "white",
    label: "미니멀 화이트",
    note: "흰 바탕에 여백 넓게. 처음 쓰는 사람에게 가장 편합니다.",
    swatch: ["#ffffff", "#e7e6e0", "#0b6e63"],
  },
  // 테마를 더할 자리입니다. 여기에 한 줄 넣고 app/themes.css 에
  // [data-theme="이름"] 블록을 만들면 고르는 메뉴에 저절로 나옵니다.
  // 테마가 하나뿐일 때는 고르는 메뉴 자체가 나오지 않습니다.
];

const STORAGE_KEY = "wfa_theme";

export function isTheme(value: unknown): value is ThemeName {
  return THEMES.some((t) => t.name === value);
}

export function themeLabel(name: string): string {
  return THEMES.find((t) => t.name === name)?.label ?? name;
}

/** 브라우저에 저장해 둔 테마. 로그인 전이나 서버가 느릴 때 씁니다. */
export function readLocalTheme(): ThemeName {
  if (typeof window === "undefined") return DEFAULT_THEME;
  try {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    return isTheme(saved) ? saved : DEFAULT_THEME;
  } catch {
    // 시크릿 창 등에서 저장소를 막아 둔 경우
    return DEFAULT_THEME;
  }
}

export function writeLocalTheme(name: ThemeName) {
  try {
    window.localStorage.setItem(STORAGE_KEY, name);
  } catch {
    /* 저장이 막혀 있어도 이번 화면에는 적용됩니다 */
  }
}

/** <html> 에 이름을 써 넣습니다. 실제 모양 변경은 CSS 가 합니다. */
export function applyTheme(name: ThemeName) {
  if (typeof document === "undefined") return;
  document.documentElement.setAttribute("data-theme", name);
}

/**
 * 화면이 뜨기 전에 <head> 에서 바로 실행되는 조각.
 * 이게 없으면 흰 화면이 잠깐 번쩍였다가 테마로 바뀝니다.
 */
export const THEME_BOOT_SCRIPT = `
(function(){
  try {
    var t = localStorage.getItem(${JSON.stringify(STORAGE_KEY)});
    var ok = ${JSON.stringify(THEMES.map((t) => t.name))};
    document.documentElement.setAttribute(
      "data-theme", ok.indexOf(t) >= 0 ? t : ${JSON.stringify(DEFAULT_THEME)});
  } catch (e) {
    document.documentElement.setAttribute("data-theme", ${JSON.stringify(DEFAULT_THEME)});
  }
})();
`.trim();
