import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Workflow Auto",
  description: "자연어로 요청하면 등록된 앱들을 불러 결과물을 만들어 줍니다.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <div className="wrap">
          <nav>
            <b>⚙️ Workflow Auto</b>
            <a href="/">내 에이전트</a>
            <a href="/store">앱스토어</a>
            <a href="/stats">이달의 앱</a>
            <a href="/admin">관리자</a>
          </nav>
          {children}
        </div>
      </body>
    </html>
  );
}
