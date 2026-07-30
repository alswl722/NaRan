import Link from "next/link";
import { LiveTraceFeed } from "@/components/LiveTraceFeed";

// 2열 배치에서 오른쪽 열만 아래로 어긋나게 — 벽돌쌓기(지그재그) 오프셋
const STAIR_OFFSET = ["", "sm:translate-y-16", "", "sm:translate-y-16"];

const STEPS = [
  {
    t: "여신 사후관리 검토 대기열",
    preview: "보고서가 연결된 관리 건을 검토 필요 순으로 모아둬요",
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
    <div className="flex flex-1 flex-col items-center">
      {/* 히어로 배너 — 원본 시안의 사진 자리에는 이미지를 넣지 않고,
          나란의 실제 판단 트레이스를 그대로 보여준다 */}
      <section className="w-full bg-gradient-to-br from-brand-soft via-surface to-bg px-8 pb-16 pt-14 lg:px-12 lg:pb-24 lg:pt-20">
        <div className="mx-auto grid w-full max-w-6xl items-center gap-12 lg:grid-cols-[1fr_1fr] lg:gap-16">
          <div className="text-center lg:text-left">
            <span
              className="hero-enter inline-flex items-center gap-1.5 rounded-full bg-brand-soft px-3 py-1.5 text-[13.5px] font-bold tracking-wide text-ink-strong"
              style={{ animationDelay: "0ms" }}
            >
              <span className="h-1.5 w-1.5 rounded-full bg-brand" />
              AI 여신 사후관리 보조 도구
            </span>

            <h1
              className="hero-enter mt-5 text-[35.5px] font-extrabold leading-[1.22] tracking-[-0.02em] text-ink-strong lg:text-[43.5px]"
              style={{ animationDelay: "90ms" }}
            >
              잘못된 비교부터
              <br />
              <span className="text-brand">먼저 막습니다</span>
            </h1>

            <p
              className="hero-enter mt-5 text-[16.5px] leading-relaxed text-muted lg:max-w-md"
              style={{ animationDelay: "140ms" }}
            >
              나란은 지속가능경영보고서와 공개 환경 데이터를 비교 대조하여
              담당자에게 근거와 후속 확인 질문까지 준비합니다.
            </p>

            <div
              className="hero-enter mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center lg:justify-start"
              style={{ animationDelay: "180ms" }}
            >
              <Link
                href="/cases"
                className="rounded-2xl bg-brand px-8 py-4 text-[17px] font-bold text-ink-strong shadow-float transition-transform hover:-translate-y-0.5"
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
      </section>

      {/* 카드 섹션 — 소개 텍스트 아래, 순서가 있는 4단계를 왼쪽에서 오른쪽으로 내려가는 계단식으로 배치 */}
      <div className="w-full max-w-6xl px-8 py-20 lg:px-12">
        <div
          className="hero-enter mx-auto max-w-xl text-center"
          style={{ animationDelay: "320ms" }}
        >
          <h2 className="text-[27.5px] font-extrabold leading-snug text-ink-strong lg:text-[31.5px]">
            만나보세요!
            <br />
            <span className="text-brand">나란</span>과 함께하는 여신 사후관리
          </h2>
          <p className="mt-4 text-[16px] leading-relaxed text-muted">
            범위가 다른 숫자를 잘못 비교해 틀린 결론을 내지 않도록.
            <br />
            비교 가능한 값만 대조해 근거와 함께 보여드립니다.
          </p>
        </div>

        <ol className="mx-auto mt-20 grid max-w-2xl grid-cols-1 gap-x-6 gap-y-6 pb-12 sm:grid-cols-2">
          {STEPS.map((s, i) => (
            <li
              key={s.t}
              className={`hero-enter ${STAIR_OFFSET[i]}`}
              style={{ animationDelay: `${380 + i * 70}ms` }}
            >
              <div className="group relative rounded-xl border border-line bg-surface p-4 shadow-card transition-all duration-300 hover:-translate-y-1 hover:shadow-float">
                <div className="flex items-center gap-2">
                  <span className="h-1.5 w-4 shrink-0 rounded-full bg-brand" />
                  <div className="text-[17.5px] font-bold text-ink-strong">
                    {s.t}
                  </div>
                </div>
                <div className="mt-2 break-keep pl-6 text-[15.5px] leading-relaxed text-muted">
                  {s.preview}
                </div>
              </div>
            </li>
          ))}
        </ol>

        <div
          className="hero-enter mt-16 flex justify-center"
          style={{ animationDelay: "700ms" }}
        >
          <Link
            href="/cases"
            className="group inline-flex items-center gap-2 rounded-full bg-ink-strong px-7 py-3.5 text-[16px] font-bold text-surface shadow-card transition-transform hover:-translate-y-0.5"
          >
            여신 사후관리 대기열 바로 확인하기
            <span className="text-brand transition-transform group-hover:translate-x-0.5">
              →
            </span>
          </Link>
        </div>
      </div>
    </div>
  );
}
