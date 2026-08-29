"""
posts/shared.json의 각 글이 마지막으로 확인(last_verified)된 지 얼마나 지났는지 점검하고,
기준 일수(STALE_THRESHOLD_DAYS)를 넘긴 글들을 REVIEW_NEEDED.md에 정리한다.

- 이 스크립트는 사실관계를 직접 검증하지는 않는다 (그건 AI/사람이 해야 하는 일).
  대신 "이 글은 오래돼서 한 번 다시 확인해봐야 한다"는 걸 자동으로 표시해주는 역할만 한다.
- REVIEW_NEEDED.md에 오래된 글 목록이 뜨면, 그 목록을 가지고 Claude에게
  "이 글들 최신 정보 기준으로 다시 확인해줘"라고 요청하면 된다.
- 실행: python3 scripts/check_freshness.py
"""

import json
import os
from datetime import date, datetime

POSTS_PATH = "posts/shared.json"
REPORT_PATH = "REVIEW_NEEDED.md"

# 이 일수를 넘긴 글은 "재검토 필요" 목록에 올라감
STALE_THRESHOLD_DAYS = 90


def main():
    posts = json.load(open(POSTS_PATH, encoding="utf-8"))
    today = date.today()

    stale = []
    missing_field = []

    for post in posts:
        last_verified = post.get("last_verified")
        if not last_verified:
            missing_field.append(post["id"])
            continue

        verified_date = datetime.strptime(last_verified, "%Y-%m-%d").date()
        age_days = (today - verified_date).days

        if age_days >= STALE_THRESHOLD_DAYS:
            # 본문 첫 줄을 제목 삼아 요약에 사용
            first_line = post["text"].split("\n")[0]
            stale.append(
                {"id": post["id"], "title": first_line, "age_days": age_days, "last_verified": last_verified}
            )

    stale.sort(key=lambda x: x["age_days"], reverse=True)

    lines = [
        "# 재검토가 필요한 글 목록",
        "",
        f"마지막 점검일: {today.isoformat()}",
        f"기준: 마지막 확인(last_verified)으로부터 {STALE_THRESHOLD_DAYS}일 이상 지난 글",
        "",
    ]

    if not stale and not missing_field:
        lines.append("현재 재검토가 필요한 글이 없습니다. 모든 글이 기준 일수 이내에 확인되었습니다.")
    else:
        if stale:
            lines.append(f"## 기준 일수 초과 ({len(stale)}개)")
            lines.append("")
            lines.append("| id | 제목(본문 첫 줄) | 마지막 확인일 | 경과일 |")
            lines.append("|---|---|---|---|")
            for item in stale:
                lines.append(
                    f"| {item['id']} | {item['title']} | {item['last_verified']} | {item['age_days']}일 |"
                )
            lines.append("")
            lines.append(
                "> 이 목록을 Claude에게 보여주면서 \"이 글들 최신 정보로 다시 확인해줘\"라고 "
                "요청하면, 사실관계를 재검증해서 필요하면 내용을 갱신해줍니다."
            )
            lines.append("")

        if missing_field:
            lines.append(f"## last_verified 값이 없는 글 ({len(missing_field)}개)")
            lines.append("")
            for pid in missing_field:
                lines.append(f"- {pid}")
            lines.append("")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"점검 완료: 전체 {len(posts)}개 중 재검토 필요 {len(stale)}개, 필드 누락 {len(missing_field)}개")
    print(f"리포트 저장: {REPORT_PATH}")


if __name__ == "__main__":
    main()
