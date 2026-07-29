"use client";

import Image from "next/image";
import Link from "next/link";

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-20 border-b border-line/70 bg-surface/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between px-5">
        <Link href="/" className="flex items-center gap-2">
          <Image src="/로고.png" alt="나란" width={120} height={32} className="h-8 w-auto" priority />
        </Link>
        <div className="flex items-center gap-2 border-l border-line pl-4">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-brand-soft text-[11px] font-semibold text-ink-strong">
            담
          </span>
          <div className="hidden leading-tight sm:block">
            <div className="text-xs font-semibold text-ink-strong">사후관리 담당자</div>
            <div className="text-[10px] text-faint">데모용 가상 계정</div>
          </div>
        </div>
      </div>
    </header>
  );
}
