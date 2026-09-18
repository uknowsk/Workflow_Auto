import "./globals.css";
import "./themes.css";
import type { Metadata } from "next";
import Nav from "./nav";
import { THEME_BOOT_SCRIPT } from "@/lib/theme";

export const metadata: Metadata = {
  title: "Workflow Auto",
  description: "자연어로 요청하면 등록된 앱들을 불러 결과물을 만들어 줍니다.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" data-theme="white">
      <head>
        {/* 화면이 그려지기 전에 저장된 테마를 입힙니다. 없으면 흰 화면이 한 번 번쩍입니다. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT }} />
      </head>
      <body>
        {/* 테마에 따라 이 상자가 '위아래'가 되기도 하고 '좌우'가 되기도 합니다.
            (관제실 테마에서는 왼쪽이 세로 메뉴, 오른쪽이 본문) */}
        <div className="ui-shell">
          <Nav />
          <div className="ui-wrap">{children}</div>
        </div>
      </body>
    </html>
  );
}
