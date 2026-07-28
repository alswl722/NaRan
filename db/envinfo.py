"""환경정보공개시스템(env-info.kr) 수집기 — 대조의 '실측' 소스.

기업의 지속가능경영보고서 '주장'과 대조할 **법정 신고 실측치**를 가져온다.
상세 페이지가 서버사이드 렌더링이라 세션 없이 GET 한 번으로 끝난다.

URL 패턴 (사이트 JS `viewSearch2()` 에서 확인):
    /user/register/viewUserSearch2.do?YEAR={year}&COMP_ID={comp_id}&OPEN_YN=Y

수집 항목:
  - 매출액·종업원수      (항목 1, 의무)   → 원단위 반증에 필수
  - Scope 1/2/3 배출량   (항목 11, 자율)  → 대조 기준
  - 환경법규 위반 현황   (항목 25, 의무)  → 보조 근거

주의: 항목 11은 **자율** 공개다. 연도에 따라 비어 있을 수 있고,
그 경우 대조 결과는 '대조불가'가 되어야 한다 — 0으로 채우지 않는다.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, asdict

import requests

BASE = "https://env-info.kr"
DETAIL = BASE + "/user/register/viewUserSearch2.do"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126 Safari/537.36"

_NUM = r"[-+]?[\d,]+(?:\.\d+)?"


@dataclass
class EnvRecord:
    comp_id: str
    year: int
    company: str | None = None
    revenue_mkrw: float | None = None      # 매출액 (백만원)
    employees: int | None = None
    scope1_tco2e: float | None = None
    scope2_tco2e: float | None = None
    scope3_tco2e: float | None = None
    scope12_tco2e: float | None = None      # ★ 대조 기준 — Scope 1+2만
    reported_total_tco2e: float | None = None   # 사이트 표기 총량 (Scope 3 포함될 수 있음)
    scope3_included: bool = False           # 표기 총량에 Scope 3가 섞였는가
    inventory_disclosed: bool = False       # 온실가스 명세서 공개 여부
    violations: int = 0                     # 환경법규 위반/사고 건수
    missing_reason: str | None = None       # 결손 사유 (0으로 채우지 않기 위함)
    ok: bool = False                        # 대조 가능 여부 (scope12 확보)

    def as_dict(self) -> dict:
        return asdict(self)


def _clean(html: str) -> str:
    """태그 제거 후 공백 정규화 — 정규식 추출을 안정화한다."""
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", text)


def _num(pattern: str, text: str) -> float | None:
    m = re.search(pattern, text)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except (ValueError, IndexError):
        return None


def parse(html: str, comp_id: str, year: int) -> EnvRecord:
    """상세 페이지 HTML → EnvRecord. 없는 값은 None으로 남긴다 (0 아님)."""
    t = _clean(html)
    rec = EnvRecord(comp_id=comp_id, year=year)

    m = re.search(r"사업장명\s+(.{2,40}?)\s+대표자", t)
    if m:
        rec.company = m.group(1).strip()

    rec.revenue_mkrw = _num(rf"매출액\s+({_NUM})\s*\(\s*단위\s*:\s*백만원", t)
    emp = _num(rf"국내종업원수\s+({_NUM})\s*명", t)
    rec.employees = int(emp) if emp is not None else None

    rec.scope1_tco2e = _num(rf"직접배출량\s*\(?\s*scope\s*Ⅰ\s*\)?\s+({_NUM})\s*ton", t)
    rec.scope2_tco2e = _num(rf"간접배출량\s*\(?\s*scope\s*Ⅱ\s*\)?\s+({_NUM})\s*ton", t)
    rec.scope3_tco2e = _num(rf"간접배출량\s*\(?\s*scope\s*Ⅲ\s*\)?\s+({_NUM})\s*ton", t)
    rec.reported_total_tco2e = _num(rf"온실가스배출총량\s+({_NUM})\s*ton", t)

    # ── 결손 판별 ────────────────────────────────────────────────────────
    # 원본이 미입력을 "0 ton CO2 eq / 전년도 입력 정보 없음"으로 채워서 준다.
    # 0을 실측 0으로 받아들이면 대조가 통째로 거짓이 된다 — 결손으로 되돌린다.
    # Scope 1·2·총량이 모두 0인 제조 사업장은 현실에 없다. 미입력으로 본다.
    # 원본은 이를 "전년도 입력 정보 없음" 또는 "전년대비 100% (감소↓)"로 표기하는데,
    # 후자는 화면상 '100% 감축 달성'처럼 보인다 — 그대로 믿으면 대조가 거짓이 된다.
    all_zero = (rec.reported_total_tco2e == 0
                and not rec.scope1_tco2e and not rec.scope2_tco2e)
    if all_zero:
        rec.missing_reason = "원본 미입력 (0으로 표기됨)"
        rec.scope1_tco2e = rec.scope2_tco2e = rec.scope3_tco2e = None
        rec.reported_total_tco2e = None
    elif rec.reported_total_tco2e is None:
        rec.missing_reason = "온실가스 항목 미공개 (자율 항목)"

    # ── 대조 기준은 Scope 1+2 ────────────────────────────────────────────
    # 표기 총량은 어떤 해엔 Scope 3를 포함하고 어떤 해엔 안 한다.
    # (예: 삼성전자 수원 2023 — Scope 3 최초 공시로 총량이 584배 '증가')
    # 범위가 바뀐 것을 배출이 늘어난 것으로 읽으면 오탐이다. 1+2로 고정한다.
    if rec.scope1_tco2e is not None and rec.scope2_tco2e is not None:
        rec.scope12_tco2e = rec.scope1_tco2e + rec.scope2_tco2e
    elif rec.reported_total_tco2e is not None and not rec.scope3_tco2e:
        rec.scope12_tco2e = rec.reported_total_tco2e

    if rec.scope3_tco2e and rec.reported_total_tco2e:
        rec.scope3_included = rec.reported_total_tco2e > (rec.scope12_tco2e or 0) * 1.5

    rec.inventory_disclosed = bool(re.search(r"온실가스 명세서\s+공개", t))
    rec.violations = len(re.findall(r"처분일자", t))
    rec.ok = rec.scope12_tco2e is not None
    return rec


def fetch(comp_id: str, year: int, session: requests.Session | None = None,
          timeout: int = 30) -> EnvRecord:
    s = session or requests.Session()
    r = s.get(DETAIL, params={"YEAR": year, "COMP_ID": comp_id, "OPEN_YN": "Y"},
              headers={"User-Agent": UA}, timeout=timeout)
    r.raise_for_status()
    return parse(r.text, comp_id, year)


def series(comp_id: str, years: range, delay: float = 0.5) -> list[EnvRecord]:
    """연도별 시계열 수집. 서버 부담을 피해 요청 간 delay를 둔다."""
    s = requests.Session()
    out = []
    for y in years:
        try:
            out.append(fetch(comp_id, y, s))
        except Exception as e:  # noqa: BLE001 — 실패도 기록해 결손을 드러낸다
            rec = EnvRecord(comp_id=comp_id, year=y)
            rec.company = f"[수집실패: {type(e).__name__}]"
            out.append(rec)
        time.sleep(delay)
    return out
