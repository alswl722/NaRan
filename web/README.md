# 나란 웹 (프론트엔드)

Next.js(App Router) + Tailwind v4. 백엔드 FastAPI(`api/main.py`)를 호출한다.

## 실행

```bash
npm install
cp .env.local.example .env.local   # 필요 시 NEXT_PUBLIC_API_URL 수정
npm run dev
```

백엔드는 저장소 루트에서 별도로 띄운다:

```bash
python -m db.init_db
uvicorn api.main:app --reload
```

## 화면 구성

- `/` — 사후관리 검토 대기열 (장면 1)
- `/cases/[id]` — 주장 카드·비교 조건·대조 결과(장면 3·4), 계산 중단 강조(장면 2),
  분석 실행 후 트레이스 타임라인, HITL 조치 패널

## 디자인 토큰

`app/globals.css`의 `@theme`에 KB 금융그룹 브랜드 컬러(KB Yellow/Gray)를 정의했다.
로고는 `components/SiteHeader.tsx`에 자리만 비워뒀다 — `public/logo.png`를 추가하고
주석 표시된 위치의 `<img>`로 교체하면 된다.
