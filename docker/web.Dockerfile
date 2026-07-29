# 나란 Next.js(프론트) — build context는 레포 루트
# syntax=docker/dockerfile:1로 BuildKit 캐시 마운트를 쓴다 — package-lock.json이
# 안 바뀌면 npm이 레지스트리에서 다시 받지 않고 로컬 캐시에서 설치한다.
# 프로토타입 단계라 dev 모드로 구동(핫리로드). 배포 전환 시 build/start로 바꾼다.
# syntax=docker/dockerfile:1
FROM node:20-slim

WORKDIR /app

# 의존성 파일만 먼저 COPY — package-lock.json이 안 바뀌면 이 레이어부터
# 아래 RUN까지 캐시 히트되어 앱 코드만 바뀐 재빌드는 npm install을 건너뛴다.
COPY web/package.json web/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm ci

# 앱 코드
COPY web ./

EXPOSE 3000

CMD ["npm", "run", "dev"]
