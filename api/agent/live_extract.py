"""레퍼런스 PDF 한 페이지를 Gemini live 모드로 추출하는 CLI.

사용 예:
    python -m api.agent.live_extract --case a --page 171

키는 저장소에 기록하지 않고 프로젝트 루트의 .env 또는 셸 환경변수
GEMINI_API_KEY에서만 읽는다.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

from api.agent.document_extract import extract_document_page
from api.agent.gemini_client import (
    GeminiConfigurationError,
    GeminiStructuredClaimClient,
)
from api.agent.llm_extract import VerifiedClaimCache
from api.agent.orchestrator import RunState
from naran.contracts import ExecutionMode, Report


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "fixtures"
REFERENCES = ROOT / "references"
CASE_FILES = {
    "a": (
        "sample_case_a.json",
        "Samsung-Biologics-2025-ESG-Report_KR.pdf",
    ),
    "b": (
        "sample_case_b.json",
        "Samsung_Electronics_Sustainability_Report_2025_ENG.pdf",
    ),
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="레퍼런스 PDF에서 Gemini structured-output 주장을 추출합니다."
    )
    parser.add_argument(
        "--case",
        choices=sorted(CASE_FILES),
        required=True,
        help="a=삼성바이오로직스, b=삼성전자",
    )
    parser.add_argument("--page", type=int, required=True, help="1부터 시작하는 PDF 페이지")
    parser.add_argument(
        "--no-cache-fallback",
        action="store_true",
        help="live 실패 시 fixture 캐시 fallback을 허용하지 않습니다.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    load_dotenv(ROOT / ".env")

    fixture_name, pdf_name = CASE_FILES[args.case]
    case_data = json.loads(
        (FIXTURES / fixture_name).read_text(encoding="utf-8")
    )
    report = Report.model_validate(case_data["report"])
    cache = (
        VerifiedClaimCache()
        if args.no_cache_fallback
        else VerifiedClaimCache.from_fixture_directory(FIXTURES)
    )

    try:
        client = GeminiStructuredClaimClient()
    except GeminiConfigurationError as exc:
        print(f"설정 오류: {exc}", file=sys.stderr)
        print(
            ".env에 GEMINI_API_KEY를 설정하거나 셸 환경변수로 전달하세요.",
            file=sys.stderr,
        )
        return 2

    run = extract_document_page(
        run_id=f"live-extract-{args.case}-{args.page}-{uuid.uuid4().hex[:8]}",
        pdf_path=REFERENCES / pdf_name,
        report=report,
        page=args.page,
        mode=ExecutionMode.LIVE,
        cache=cache,
        client=client,
        model_name=client.model_name,
        prompt_version=client.prompt_version,
    )
    if run.state is RunState.FAILED or run.result is None:
        print(f"추출 실패: {run.error}", file=sys.stderr)
        for event in run.trace:
            print(
                f"[{event.step_type}] {event.stage}: {event.input_summary}",
                file=sys.stderr,
            )
        return 1

    body = {
        "state": run.state,
        "execution_mode": run.result.execution_mode,
        "model": client.model_name,
        "attempts": run.result.attempts,
        "fallback_reason": run.result.failure_reason,
        "claims": [
            claim.model_dump(mode="json") for claim in run.result.claims
        ],
        "trace": [event.model_dump(mode="json") for event in run.trace],
    }
    print(json.dumps(body, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
