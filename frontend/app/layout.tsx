import "./globals.css";
import type { Metadata } from "next";
import Nav from "./nav";
import ToolDock from "@/components/tools/dock";

export const metadata: Metadata = {
  title: "Workflow Auto",
  description: "자연어로 요청하면 등록된 앱들을 불러 결과물을 만들어 줍니다.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        {/* 위 고정 바는 화면 끝까지 닿아야 해서 wrap 바깥에 둡니다. */}
        <Nav />
        {/* 왼쪽 구석 도구 서랍. 어느 화면에서든 같은 자리에 있습니다. */}
        <ToolDock />
        <div className="ui-wrap">{children}</div>
      </body>
    </html>
  );
}
