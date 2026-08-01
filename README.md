# 나란 (NaRan)

지속가능경영보고서의 환경 주장과 공개 환경 데이터를 같은 범위로 정렬한 뒤,
**비교 가능한 수치만 대조**하는 녹색여신 사후관리 보조 도구입니다. 조직경계·지역경계·
Scope·단위·기간이 다르면 숫자를 억지로 계산하지 않고 담당자가 확인할 사항을 제시합니다.

## 심사위원용 빠른 실행

Gemini API 키가 없어도 검증 저장값 모드로 핵심 기능 전체를 실행할 수 있습니다.

### 준비 사항

- Docker Desktop
- Git

### 실행

```bash
git clone <제출한 GitHub 저장소 URL>
cd NaRan
cp .env.example .env
docker compose up --build
```

첫 실행은 이미지 빌드 때문에 시간이 걸릴 수 있습니다. 컨테이너가 모두 실행되면
[http://localhost:3000](http://localhost:3000)에 접속합니다.

- 웹: http://localhost:3000
- API 문서: http://localhost:8000/docs
- 상태 확인: http://localhost:8000/health

화면에서 **검증 저장값**을 선택하고 분석을 실행하면 별도의 API 키나 외부 네트워크 없이
전체 흐름을 확인할 수 있습니다.

## API 키 없이도 평가할 수 있는 기능

검증 저장값 모드는 최종 화면을 통째로 저장해 보여주는 방식이 아닙니다. 실제 보고서에서
미리 추출하고 검증한 주장만 입력값으로 사용하며, 아래 과정은 실행할 때마다 애플리케이션
코드가 수행합니다.

1. 보고서 주장과 공개 데이터 연결
2. 지표·단위·조직경계·지역경계·Scope·산정 방식·기간의 비교 가능성 검사
3. 비교 가능한 수치의 결정론적 차이 계산
4. 6개 분석 상태와 `review_required` 결정
5. 담당자 확인 사항과 추가 자료 요청 질문 제시
6. 담당자 조치 및 append-only 감사 이력 저장
7. 분석 단계와 근거를 AI Agent 실행 과정으로 표시

즉, API 키가 없을 때 대체되는 부분은 **Gemini의 비정형 PDF 주장 추출**뿐입니다.
비교 가능성 판정, 수치 계산, 상태 분류와 담당자 검토 흐름은 동일한 코드로 실행됩니다.

## 데모 사례

| 사례 | 데이터 | 확인할 수 있는 장면 |
| --- | --- | --- |
| 삼성바이오로직스 | 공식 2025 ESG 보고서와 env-info·GIR 검증 저장본 | Scope 1·2·1+2의 표시 자릿수 차이와 범위 정렬 후 대조 |
| 삼성전자 | 공식 2025 지속가능경영보고서와 env-info 검증 저장본 | 기업 전체와 개별 사업장의 조직·지역 범위가 달라 계산을 중단하는 장면 |
| 가상 기업 | 재현 가능한 합성 fixture | 비교에 필요한 정보가 부족할 때 정보 부족으로 분류하고 추가 확인을 제안하는 장면 |

실제 자료와 합성 fixture의 구분 및 사례별 정답은 `fixtures/ground_truth.md`에서 확인할 수
있습니다.

## 두 가지 분석 모드

### 1. 검증 저장값 — 기본·심사용

- Gemini API 키 불필요
- 외부 네트워크 불필요
- 검증된 추출 fixture를 사용해 결과를 안정적으로 재현
- 비교 엔진, 상태 판정, HITL과 감사 이력은 실제 코드로 실행

`.env`의 기본값은 다음과 같습니다.

```dotenv
NARAN_EXECUTION_MODE=demo
```

### 2. Gemini 실시간 — 선택 사항

실시간 모드는 레퍼런스 PDF의 지정 페이지를 Gemini structured output으로 분석해 환경
주장을 추출하고 구조화합니다. 심사위원이 이 기능까지 실행하려면 본인의 Gemini API 키를
프로젝트 루트 `.env`에 설정해야 합니다.

```dotenv
GEMINI_API_KEY=발급받은_API_키
GEMINI_MODEL=gemini-3.6-flash
GEMINI_TIMEOUT_SECONDS=60
NARAN_EXECUTION_MODE=live
```

키를 저장한 뒤 API 컨테이너를 다시 시작합니다.

```bash
docker compose restart api
```

웹에서 **Gemini 실시간**을 선택하고 분석을 실행합니다. Gemini는 보고서의 주장 후보
추출·유형 분류·메타데이터 구조화·원문 위치 연결까지만 담당합니다. 비교 가능성 판정과
차이 계산, 최종 분석 상태 결정은 LLM이 아니라 결정론적 코드가 수행합니다.

API 사용량 제한이나 네트워크 오류가 발생할 수 있으므로 심사 재현에는 검증 저장값 모드를
권장합니다. API 키는 저장소에 포함되지 않으며 `.env`는 Git에서 제외됩니다.

## 테스트

Docker API 컨테이너에서 전체 테스트를 실행합니다.

```bash
docker compose exec api pytest
```

Docker를 사용하지 않는 경우:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

테스트와 `POST /cases/{id}/analyze`의 검증 저장값 모드는 API 키·네트워크 없이 재현됩니다.

## 시연 전 담당자 기록 초기화

분석 결과와 사례 데이터는 유지하고 담당자 조치·확인 완료·추가 자료 요청·감사 이력만
초기화하려면 다음 명령을 실행합니다.

```bash
docker compose exec api python -c "from sqlalchemy import text; from db.session import get_engine; e=get_engine(); c=e.connect(); c.execute(text('DELETE FROM review_item_resolutions')); c.execute(text('DELETE FROM human_reviews')); c.commit(); c.close()"
```

실행 후 브라우저를 새로고침합니다. 전체 SQLite 볼륨까지 삭제하는
`docker compose down -v`는 분석 실행 기록과 사례 데이터도 초기화하므로 주의해야 합니다.

## 로컬 실행 — Docker 미사용

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m db.init_db
uvicorn api.main:app --reload
```

별도 터미널에서 웹을 실행합니다.

```bash
cd web
npm install
npm run dev
```

`DATABASE_URL`을 지정하지 않으면 `db/session.py`가 프로젝트 루트의 로컬 SQLite로
자동 폴백합니다.

## 저장소 구조

```text
naran/       공통 Pydantic 데이터 계약
db/          DB 모델, 비교 가능성 검사, 대조 엔진, PDF 파서, 공개 데이터 정규화
api/         FastAPI, 분석 오케스트레이터, Gemini 추출, HITL·감사 이력 API
web/         Next.js 사용자 화면
fixtures/    검증 사례, 추출 저장값, 공개 데이터 저장본, 정답지
references/  분석 대상 지속가능경영보고서 PDF
tests/       계약·비교 가능성·대조 엔진·API·통합 테스트
docker/      API·웹 Dockerfile
```

설계 원칙과 세부 개발 계획은 `claude.md`, `docs/개발계획.md`를 참고해 주세요.
