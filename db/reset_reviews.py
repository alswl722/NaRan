"""담당자 기록만 초기화한다.

`python -m db.reset_reviews`로 실행한다. 담당자 조치(human_reviews)와
확인 사항 처리 기록(review_item_resolutions)만 지우고, 사례·보고서·주장·
공개 데이터·분석 실행 기록과 AI 판정(Verdict)은 그대로 둔다. 시연 전에
HITL 화면을 처음 상태로 되돌리는 용도다.
"""

from __future__ import annotations

from sqlalchemy import delete

from db.models import HumanReviewRecord, ReviewItemResolutionRecord
from db.session import get_engine


def reset_reviews() -> dict[str, int]:
    with get_engine().begin() as connection:
        resolutions = connection.execute(delete(ReviewItemResolutionRecord)).rowcount
        reviews = connection.execute(delete(HumanReviewRecord)).rowcount
    return {"review_item_resolutions": resolutions, "human_reviews": reviews}


def main() -> None:
    deleted = reset_reviews()
    print(
        "담당자 기록 초기화 완료: "
        f"human_reviews {deleted['human_reviews']}건, "
        f"review_item_resolutions {deleted['review_item_resolutions']}건 삭제"
    )


if __name__ == "__main__":
    main()
