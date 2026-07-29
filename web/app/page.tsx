import Link from "next/link";
import { LiveTraceFeed } from "@/components/LiveTraceFeed";

const STEPS = [
  {
    t: "사후관리 검토 대기열",
    preview: "보고서가 연결된 관리 건을 검토 필요 순으로 모아둡니다",
  },
  {
    t: "비교 가능성 먼저 검사",
    preview: "조직·지역·Scope·산정 방식이 같은 값인지부터 확인해요",
  },
  {
    t: "다른 범위는 계산 중단",
    preview: "숫자가 달라 보여도 범위가 다르면 차이를 계산하지 않아요",
  },
  {
    t: "근거와 후속 질문",
    preview: "원문·페이지·출처를 남기고, 담당자 확인 질문까지 준비해요",
  },
];

export default function Home() {
  return (
    <div className="flex flex-1 flex-col items-center px-8 pb-20 lg:px-12">
      <div className="grid w-full items-center gap-12 pt-14 lg:grid-cols-[1fr_1fr] lg:gap-16 lg:pt-20">
        <div className="text-center lg:text-left">
          <span
            className="hero-enter inline-flex items-center gap-1.5 rounded-full bg-brand-soft px-3 py-1.5 text-[11.5px] font-bold tracking-wide text-ink-strong"
            style={{ animationDelay: "0ms" }}
          >
            <span className="h-1.5 w-1.5 rounded-full bg-brand" />
            AI 사후관리 보조 도구
          </span>

          <h1
            className="hero-enter mt-5 text-[34px] font-extrabold leading-[1.22] tracking-[-0.02em] text-ink-strong lg:text-[42px]"
            style={{ animationDelay: "90ms" }}
          >
            비교할 수 없는 숫자는
            <br />
            <span className="text-brand">계산을 멈춥니다</span>
          </h1>

          <p
            className="hero-enter mt-5 text-[15px] leading-relaxed text-muted lg:max-w-md"
            style={{ animationDelay: "140ms" }}
          >
            지속가능경영보고서의 환경 주장과 공개 환경 데이터가 비교 가능한
            범위인지 먼저 검사하고, 비교 가능한 수치만 대조해 근거와 후속
            확인 질문을 보여줍니다.
          </p>

          <div
            className="hero-enter mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center lg:justify-start"
            style={{ animationDelay: "180ms" }}
          >
            <Link
              href="/cases"
              className="rounded-2xl bg-brand px-8 py-4 text-[15.5px] font-bold text-ink-strong shadow-float transition-transform hover:-translate-y-0.5"
            >
              대기열 확인하기 →
            </Link>
          </div>
        </div>

        <div
          className="hero-enter flex justify-center lg:justify-end"
          style={{ animationDelay: "240ms" }}
        >
          <LiveTraceFeed />
        </div>
      </div>

      <ol className="mt-20 grid w-full gap-4 text-left sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map((s, i) => (
          <li
            key={s.t}
            className="hero-enter group relative overflow-hidden rounded-2xl border border-line bg-surface p-5 shadow-card transition-all duration-300 hover:-translate-y-1 hover:shadow-float"
            style={{ animationDelay: `${320 + i * 70}ms` }}
          >
            <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-brand-soft text-[13px] font-extrabold text-ink-strong">
              {i + 1}
            </span>
            <div className="mt-3 text-[15.5px] font-bold text-ink-strong">{s.t}</div>
            <div className="mt-1.5 break-keep text-[13.5px] leading-relaxed text-muted">
              {s.preview}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
