# PDF 원문 열람 + 숫자 좌표 하이라이트

## 배경

주장 카드("원문 나란히 보기")가 텍스트만 보여주던 것에서, 보고서 실물 PDF를
웹에서 직접 열고 근거 숫자가 그 페이지 어디에 있는지 눈으로 확인할 수
있게 확장했다.

## 백엔드

### `api/routers/reports.py` (신규)

| 엔드포인트 | 설명 |
| --- | --- |
| `GET /reports/{id}/pdf` | PDF 바이너리. `FileResponse` — Starlette가 Range 요청을 자동 지원해 커스텀 스트리밍 없이 pdf.js의 부분 로드를 그대로 받는다. |
| `GET /reports/{id}/pdf/meta` | `{"available": bool, "filename"?: str}`. 실물 없음 자체는 정상 응답(404 아님) — C 사례(합성 데이터)에서 프론트가 버튼을 감출지 판단하는 데 씀. |
| `GET /reports/{id}/pdf/highlight?claim_id=...` | claim.value의 PDF 내 좌표(`x0, top, x1, bottom, page, page_width, page_height`, 포인트 단위). 못 찾으면 `{"found": false}`(200) — 페이지 자동 이동 자체는 좌표 유무와 무관하게 동작해야 하므로 404로 막지 않는다. |

`report_id → references/ 파일명` 매핑은 정적 딕셔너리
(`REPORT_ID_TO_FILENAME`)로 관리한다. `source_url`(원본 발행처 URL)은
사례마다 형식이 달라(A는 쿼리 파라미터, B는 경로) 파싱으로 신뢰할 수
없어서 명시적 테이블을 택했다. **기업이 많아지면 이 방식은 코드 수정 없이
확장이 안 된다 — DB에 파일 경로 컬럼을 추가하는 게 맞다. 지금은 A·B·C
데모 스코프라 의도적으로 미루기로 했다(사용자 확인).**

서빙 전 파일의 SHA256을 계산해 `Report.file_hash`와 대조하고 불일치 시
500 — `api/agent/document_extract.py`의 file_hash 검증 습관을 그대로
따른 것. 매핑 테이블이 잘못됐거나 파일이 나중에 바뀌었을 때 조용히 다른
문서를 서빙하지 않기 위함.

### `db/parser.py`에 추가: `find_value_bbox`, `_value_display_variants`

**핵심 발견**: `claim.raw_text` 전체를 PDF에서 찾는 방식은 원리적으로
실패한다. fixture의 `raw_text`(예: "Scope 1 배출량 — 국내 사업장 — 2024 —
71,840.290tCO2eq")는 PDF 원문 그대로가 아니라 사람이 표를 보고 요약한
문장이고, 실제 PDF는 연도별 수치가 한 줄에 나열된 표 형태다. 그래서
문장이 아니라 **`claim.value`(숫자)만** 페이지에서 찾는 방식으로
바꿨다.

여기서 두 번째 문제: DB의 `Numeric` 컬럼이 원본 표시 정밀도를 보존하지
않고 trailing zero를 붙여 돌려준다(예: fixture의 `"71840.290"`이 API
응답에서는 `"71840.2900000000"`). PDF 원문의 실제 표기 자릿수(소수
3자리)를 이 시점에 이미 알 수 없다. 해결책: `Decimal.normalize()`로
유효숫자만 남긴 뒤 소수 0~4자리로 반올림한 후보를 전부 만들고, 각각
콤마 유무 두 표기(`"71840.29"`/`"71,840.29"`, `"71840.290"`/
`"71,840.290"` 등)를 시도한다. pdfplumber의 `extract_words()`가 콤마
포함 숫자를 하나의 토큰으로 뽑아주므로(`"71,840.290"`) 이 중 하나가
반드시 정확히 매치된다.

검증한 실제 값:
- A `claim-a-scope1` (p.171): `71840.290` → 찾음
- A `claim-a-scope2` (p.172): `154678.989` → 찾음
- A `claim-a-scope1-2-total` (p.220): `226519` → 찾음
- B `claim-b-global-scope1-2` (p.68): `14889` → 찾음

성능: 224페이지 13MB PDF에서 단일 페이지 좌표 조회 약 0.16초, 해시 검증
약 11ms — A·B·C 데모 규모에서는 문제없음. 파일이 수백MB급이 되거나
claim 수십 개를 동시에 열람하는 경우엔 반복 계산이 누적될 수 있어
캐싱이 필요해질 것(현재는 미적용, 향후 과제).

### 테스트

- `tests/test_reports_router.py` (12개) — PDF 200/206(Range)/404, meta
  available/unavailable, file_hash 불일치 시 500, highlight
  found/not-found/다른 보고서 claim 거부/미존재 claim 404.
- `tests/test_parser.py`에 8개 추가 — `_value_display_variants`(DB
  패딩값에서 콤마 표기 복원, 정수 케이스, 빈 값), `find_value_bbox`(A
  세 claim, B claim, 없는 값, 범위 밖 페이지).

전체 회귀: 186 passed.

## 프론트엔드

### 설치

```
react-pdf@^10.4.1
```

React 19 peerDependency 공식 지원, `pdfjs-dist`를 내부에 포함해 별도
설치 불필요.

### `components/PdfViewer.tsx` (신규, 이후 팝업→인라인으로 교체)

처음엔 화면 중앙에 뜨는 모달(`PdfViewerModal`)로 만들었으나 "작아서 안
보임" 피드백을 받아 **인라인 임베딩**으로 교체했다:
- 팝업 오버레이 제거, "원문 나란히 보기" details 안에 그대로 펼쳐지는
  카드 형태로 변경.
- 확대/축소 버튼 추가 — `<Page width={...}>`의 렌더링 폭을 360~1400px
  사이에서 160px씩 조절(퍼센트 표시 포함). CSS transform이 아니라 실제
  렌더링 해상도를 바꾸는 방식이라 확대해도 흐려지지 않는다.
- 이전/다음 페이지 버튼으로 `claim.page`(초기값)에서 자유롭게 이동.

**좌표 오버레이**: `GET /pdf/highlight?claim_id=...`로 받은 좌표(PDF
포인트 단위)를, `<Page>`가 실제로 렌더링한 픽셀 크기(`onRenderSuccess`의
`page.height`, 지정한 `width`)와의 비율로 환산해 절대 위치
`<div>`(노란 반투명 배경 + 테두리)로 겹쳐 그린다. `currentPage`가
좌표의 `page`와 다르면(이전/다음으로 페이지를 넘긴 상태) 오버레이를
숨긴다.

SSR 주의: pdf.js는 `DOMMatrix` 등 브라우저 전용 API에 의존해 서버
컴포넌트에서 임포트하면 깨진다. `next/dynamic({ssr:false})` + worker는
CDN이 아니라 번들 경로(`new URL("pdfjs-dist/build/pdf.worker.min.mjs",
import.meta.url)`)로 지정해 오프라인 재현성을 지켰다.

### `components/ClaimCard.tsx`

"원문 나란히 보기" 좌측 블록 헤더에 "원문 PDF 보기/접기" 토글 버튼.
`pdfAvailable` prop이 false면(C 사례) 버튼 대신 "원문 PDF 없음(합성
사례)" 안내만 표시. `PdfViewer`에 `claim.id`를 `claimId`로 넘겨 좌표
오버레이가 이 claim 전용으로 뜨게 한다.

### `app/cases/[id]/page.tsx`

케이스 로드 시 `report_id`로 `/reports/{id}/pdf/meta`를 한 번만 조회해
`pdfAvailable`을 구하고 각 `ClaimCard`에 prop으로 전달(카드마다 반복
조회 방지). 조회 실패해도 `.catch(() => ({available:false}))`로 페이지
전체가 깨지지 않게 함 — 분석 결과 자체의 실패가 아니라 부가 기능
가용성 체크이므로.

### 검증

`tsc --noEmit`, `eslint`, `next build` 모두 통과. 개발 서버 기동 후
`POST /cases/case-a/analyze`, `case-b`를 실제 HTTP로 실행해 claim이
채워진 상태로 만들어두고, `GET /reports/report-a-2024/pdf/highlight`
등을 curl로 확인. 브라우저 상 실제 오버레이 정렬(숫자와 박스가 정확히
겹치는지)은 사용자가 직접 확인.

## 알려진 한계 (의도적으로 남겨둔 것)

- `REPORT_ID_TO_FILENAME` 정적 딕셔너리 — 기업 수가 늘어나면 DB 컬럼
  기반 매핑으로 바꿔야 함.
- PDF를 로컬 `references/`에 저장 — 서버 다중화·대량 기업 시 오브젝트
  스토리지(S3 등) + presigned URL로 전환 필요.
- highlight 조회·file_hash 검증에 캐싱 없음 — 지금 규모(claim 몇 개,
  PDF 파일 2개)에서는 무시 가능한 수준(요청당 십수 ms).
- 텍스트 줄 단위가 아니라 "값 하나"만 박스로 표시 — claim.raw_text
  문장 전체를 강조하는 건 스코프 밖으로 확정(원문이 문장 그대로
  존재하지 않는 구조적 이유).
