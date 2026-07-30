# 나란 (NaRan)

지속가능경영보고서의 환경 주장과 공개 환경 데이터를 비교 가능한 범위인지
먼저 검사한 뒤, 비교 가능한 수치만 대조해 근거와 후속 확인 질문을
제공하는 AI 사후관리 보조 도구.

## Docker로 실행 (권장)

```bash
cp .env.example .env   # 필요 시 값 채움 — 비워둬도 SQLite/demo 모드로 동작
docker compose up --build
```

- API: http://localhost:8000 (`/health`, `/docs`)
- 웹: http://localhost:3000

첫 빌드는 의존성을 새로 받지만, 이후 앱 코드만 바꾼 재빌드는 BuildKit
캐시 마운트(`--mount=type=cache`)로 `pip`/`npm` 설치 단계를 건너뛴다 —
`docker/api.Dockerfile`, `docker/web.Dockerfile` 참고. Docker Desktop이
BuildKit을 기본 활성화하지 않는 환경이면 `DOCKER_BUILDKIT=1`을 앞에 붙인다.

SQLite 데이터는 `naran-sqlite` 명명 볼륨에 남아 `docker compose down` 후에도
유지된다. 완전히 초기화하려면 `docker compose down -v`.

## 로컬(Docker 없이) 실행

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m db.init_db
uvicorn api.main:app --reload

# 별도 터미널
cd web && npm install && npm run dev
```

## 테스트

```bash
pytest
```

API 키·네트워크 없이도 `pytest`와 `POST /cases/{id}/analyze`(A·B·C)가
전부 재현된다 — `db/session.py`는 `DATABASE_URL` 미설정 시 로컬 SQLite로
자동 폴백하고, LLM 추출은 검증된 fixture 캐시(`verified_cache`)를 쓴다.

## Gemini 실연동

프로젝트 루트의 `.env`에 키를 넣는다. `.env`는 Git에서 제외된다.

```bash
cp .env.example .env
```

```dotenv
GEMINI_API_KEY=발급받은_API_키
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TIMEOUT_SECONDS=30
```

레퍼런스 PDF의 지정 페이지를 실제 Gemini structured output으로 추출한다.

```bash
# 삼성바이오로직스 보고서 p.171
python -m api.agent.live_extract --case a --page 171

# 삼성전자 보고서 p.68
python -m api.agent.live_extract --case b --page 68
```

live 호출이 두 번 실패하면 해당 페이지의 검증 fixture가 있는 경우
`fallback` 결과를 반환한다. fallback 없이 API 오류를 확인하려면:

```bash
python -m api.agent.live_extract --case a --page 171 --no-cache-fallback
```

출력에는 `execution_mode`, 모델명, 시도 횟수, 구조화된 Claim과 실행
트레이스가 포함된다. Gemini는 주장 추출·구조화만 수행하고 비교 가능성
판정과 차이 계산은 기존 결정론적 코드가 수행한다.

## 저장소 구조

```
naran/       공통 Pydantic 데이터 계약
db/          비교 가능성 검사·대조 엔진·PDF 파서·공개 데이터 정규화
api/         FastAPI 앱, 라우터, 오케스트레이터
web/         Next.js 프론트엔드
fixtures/    A·B·C 검증 사례와 정답지
docker/      Dockerfile (api/web)
```

자세한 도메인 원칙과 개발 순서는 `claude.md`, `docs/개발계획.md` 참고.
