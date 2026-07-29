import type { Metadata } from "next";
import "./globals.css";
import { SiteHeader } from "@/components/SiteHeader";

export const metadata: Metadata = {
  title: "나란 — 사후관리 보조",
  description:
    "지속가능경영보고서의 환경 주장과 공개 환경 데이터의 비교 가능성을 먼저 검사하고, 비교 가능한 수치만 대조해 근거와 후속 확인 질문을 제공하는 AI 사후관리 보조 도구",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-bg">
        <SiteHeader />
        <main className="flex w-full flex-1 flex-col">{children}</main>
      </body>
    </html>
  );
}
