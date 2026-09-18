import "./globals.css";
import type { Metadata } from "next";
import Nav from "./nav";

export const metadata: Metadata = {
  title: "Workflow Auto",
  description: "자연어로 요청하면 등록된 앱들을 불러 결과물을 만들어 줍니다.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body>
        <div className="wrap">
          <Nav />
          {children}
        </div>
      </body>
    </html>
  );
}
