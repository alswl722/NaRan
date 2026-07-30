# 나란 FastAPI(백엔드) — build context는 레포 루트
# syntax=docker/dockerfile:1로 BuildKit 캐시 마운트(--mount=type=cache)를 쓴다 —
# 의존성이 안 바뀌면 pip가 매번 새로 다운로드하지 않고 캐시에서 바로 설치한다.
# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

# 의존성 파일만 먼저 COPY — requirements-dev.txt가 안 바뀌면 이 레이어부터
# 아래 RUN까지 전부 캐시 히트되어 앱 코드만 바뀐 재빌드는 pip를 건너뛴다.
COPY requirements-dev.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements-dev.txt

# 앱 코드
COPY naran ./naran
COPY db ./db
COPY api ./api
COPY fixtures ./fixtures
COPY references ./references

EXPOSE 8000

# /health는 DB를 건드리지 않는 liveness 체크
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)" || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
