"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { CURRENT_USER } from "@/lib/currentUser";

export function SiteHeader() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-20 border-b border-line/70 bg-surface/80 backdrop-blur-md">
      <div className="flex h-16 w-full items-center justify-between px-8 lg:px-12">
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-3">
            <Image
              src="/logo.png"
              alt="KB국민은행"
              width={120}
              height={32}
              className="h-8 w-auto"
              priority
            />
            <span className="h-6 w-px bg-line" />
            <span className="font-logo text-[23.5px] tracking-tight text-ink-strong">
              나란
            </span>
          </Link>
          <nav className="flex items-center gap-1 text-[15px]">
            <Link
              href="/dashboard"
              className={`rounded-full px-3.5 py-2 font-semibold ${
                pathname?.startsWith("/dashboard")
                  ? "bg-brand-soft text-ink-strong"
                  : "text-muted hover:bg-brand-soft hover:text-ink-strong"
              }`}
            >
              현황
            </Link>
            <Link
              href="/cases"
              className={`rounded-full px-3.5 py-2 font-semibold ${
                pathname?.startsWith("/cases")
                  ? "bg-brand-soft text-ink-strong"
                  : "text-muted hover:bg-brand-soft hover:text-ink-strong"
              }`}
            >
              여신 사후관리 대기열
            </Link>
          </nav>
        </div>

        <div className="flex items-center gap-2 border-l border-line pl-4">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-brand-soft text-[13px] font-semibold text-ink-strong">
            {CURRENT_USER.initials}
          </span>
          <div className="hidden leading-tight sm:block">
            <div className="text-xs font-semibold text-ink-strong">{CURRENT_USER.name}</div>
          </div>
        </div>
      </div>
    </header>
  );
}
