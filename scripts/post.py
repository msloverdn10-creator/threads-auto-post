"""
Threads 다중 계정 자동 포스팅 스크립트

핵심 원칙: "한 번 실행할 때 9개 계정에게 서로 다른 글을 확정적으로 배분한다"

- posts_file(예: shared.json)이 같은 계정들을 하나의 그룹으로 묶음
- 그룹마다 하나의 로테이션 큐(indexes/rotation_state__{posts_file}.json)를 유지
- 매 실행 "시작 시점"에 이번 실행에 필요한 개수(계정 수)만큼을 큐에서 한 번에 잘라서 배정
  -> 큐 자체가 항상 "중복 없는 id 목록"으로 유지되므로, 실행 도중에 중복이 생길 여지가 없음
- 큐가 부족하면 아직 큐에 없는(=최근에 안 쓴) id들로 새로 채움 (그래도 부족하면 전체를 다시 셔플)
- 계정 실행 순서, 게시 전 대기 시간은 매번 무작위
- 글에 "reply" 필드가 있으면 본문 게시 후 그 글의 댓글로 이어서 게시 (고정 댓글 역할)
- Threads API 호출이 실패하면(특히 5xx 서버 오류) 최대 3회까지 자동 재시도
"""

import json
import os
import random
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone

import requests

CONFIG_PATH = "accounts_config.json"
POSTS_DIR = "posts"
INDEX_DIR = "indexes"
GRAPH_BASE = "https://graph.threads.net/v1.0"
LAST_RUN_PATH = os.path.join(INDEX_DIR, "last_run.json")

# 실제 게시 실행 사이에 반드시 지켜야 할 최소 간격(시간)
# cron-job.org는 이보다 훨씬 자주(예: 매시간) 워크플로우를 깨우기만 하고,
# 아래 값을 기준으로 이 스크립트가 "아직 시간 안 됐으면 그냥 종료"를 직접 판단한다.
# -> 자정마다 리셋되는 cron의 한계와 무관하게 항상 정확히 N시간 간격이 유지됨.
MIN_INTERVAL_HOURS = 7

# 계정 1개당 최대 지연(초).
# GitHub Actions 무료 사용시간(Private 저장소 월 2,000분) 안에 들어오도록,
# 5분(300초)이 아닌 90초로 낮춤 - 그래도 계정마다 무작위성은 유지되면서
# 회당 실행 시간을 크게 줄여준다 (계산은 README의 "무료 사용량 확인" 항목 참고).
MAX_JITTER_SECONDS = 90
# 컨테이너 생성 후 게시까지 대기(초).
CONTAINER_WAIT_SECONDS = 5
# API 호출 실패 시 재시도 횟수와 대기시간(초, 점점 늘어남)
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = [5, 15, 30]

# 고정 댓글 마지막에 붙는 홈페이지 안내 문구 - 매번 무작위로 하나를 골라서 사용
# (매번 똑같은 문구가 반복되지 않도록 여러 버전을 둠)
FOOTER_LINK = "https://m.site.naver.com/2ceCp"
REPLY_FOOTER_VARIANTS = [
    f"💡 숨은 지원금 찾기\n{FOOTER_LINK}",
    f"🔍 나도 모르게 놓친 지원금이 있는지 확인해보기\n{FOOTER_LINK}",
    f"📋 다른 지원금 정보도 궁금하다면 여기서 확인\n{FOOTER_LINK}",
    f"👉 관련 지원금 목록 보러 가기\n{FOOTER_LINK}",
    f"🗂️ 놓치기 쉬운 지원금들, 한 번에 정리해둠\n{FOOTER_LINK}",
    f"✅ 지원금 종합 정리 페이지\n{FOOTER_LINK}",
    f"이 외에도 확인해볼 만한 지원금들이 있음\n{FOOTER_LINK}",
    f"더 많은 정보가 필요하면 참고하세요\n{FOOTER_LINK}",
]


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    dirname = os.path.dirname(path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def state_path(posts_file):
    # posts_file 예: "shared.json" -> 이미 붙어있는 확장자를 떼고 이름만 사용
    # (떼지 않으면 "rotation_state__shared.json.json"처럼 확장자가 두 번 붙는 버그가 생김)
    base_name = posts_file.rsplit(".", 1)[0]
    safe_name = base_name.replace("/", "_")
    return os.path.join(INDEX_DIR, f"rotation_state__{safe_name}.json")


def get_run_assignments(state, posts, count):
    """이번 실행에 필요한 개수(count)만큼, 서로 겹치지 않는 글을 큐에서 잘라서 반환한다.

    큐(state["queue"])는 항상 "중복 없는 id 목록"으로 유지된다.
    큐가 부족하면 아직 큐에 없는 id들로 채우고, 그것도 부족하면(=pool이 count보다 작으면)
    부득이하게 전체를 다시 섞어서 채운다 (이 경우 이번 실행 안에서 중복이 생길 수 있음 -> 경고 로그 출력).
    """
    all_ids = [p["id"] for p in posts]
    queue = list(state.get("queue", []))

    while len(queue) < count:
        candidates = [i for i in all_ids if i not in queue]
        if not candidates:
            # pool 크기가 count보다 작아서 중복을 피할 수 없는 극단적 상황
            print(
                f"⚠️ 경고: 글 pool 크기({len(all_ids)})가 이번에 필요한 개수({count})보다 작습니다. "
                f"중복 배정이 발생할 수 있습니다."
            )
            candidates = all_ids[:]
        random.shuffle(candidates)
        queue.extend(candidates)
        state["cycle"] = state.get("cycle", 0) + 1

    assigned_ids = queue[:count]
    state["queue"] = queue[count:]

    by_id = {p["id"]: p for p in posts}
    return [by_id[i] for i in assigned_ids]


def publish_to_threads(user_id, token, text, reply_to_id=None, image_url=None):
    """Threads 2단계 게시: 컨테이너 생성 -> 게시. 5xx 서버 오류는 자동 재시도.
    image_url이 있으면 이미지 게시물(캡션=text)로, 없으면 텍스트 게시물로 만든다.
    reply_to_id가 있으면 해당 게시물에 대한 댓글로 게시한다."""
    if image_url:
        create_data = {
            "media_type": "IMAGE",
            "image_url": image_url,
            "text": text,
            "access_token": token,
        }
    else:
        create_data = {
            "media_type": "TEXT",
            "text": text,
            "access_token": token,
        }
    if reply_to_id:
        create_data["reply_to_id"] = reply_to_id

    creation_id = _request_with_retry(
        "POST", f"{GRAPH_BASE}/{user_id}/threads", data=create_data
    )["id"]

    time.sleep(CONTAINER_WAIT_SECONDS)

    return _request_with_retry(
        "POST",
        f"{GRAPH_BASE}/{user_id}/threads_publish",
        data={"creation_id": creation_id, "access_token": token},
    )


def _request_with_retry(method, url, data):
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.request(method, url, data=data, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            last_error = e
            # 4xx(인증/권한/잘못된 요청)는 재시도해도 소용없으므로 즉시 포기
            if status is not None and 400 <= status < 500:
                raise
            if attempt < MAX_RETRIES - 1:
                wait = RETRY_BACKOFF_SECONDS[min(attempt, len(RETRY_BACKOFF_SECONDS) - 1)]
                print(f"  ↳ 요청 실패({status}), {wait}초 후 재시도 ({attempt + 1}/{MAX_RETRIES})")
                time.sleep(wait)
    raise last_error


def build_reply_text(post):
    """게시물의 link_label/link와, 무작위로 고른 footer 문구를 조합해 고정 댓글 텍스트를 만든다."""
    link = post.get("link")
    if not link:
        return None
    link_label = post.get("link_label", "자세히 보기")
    footer = random.choice(REPLY_FOOTER_VARIANTS)
    return f"🔗 {link_label}\n{link}\n\n{footer}"


def run_account(account, post):
    name = account["name"]
    token = os.environ.get(account["token_secret"])
    user_id = os.environ.get(account["id_secret"])

    if not token or not user_id:
        print(f"[{name}] 토큰 또는 계정 ID가 설정되어 있지 않습니다. 건너뜁니다.")
        return

    delay = random.randint(0, MAX_JITTER_SECONDS)
    print(f"[{name}] {delay}초 대기 후 게시 예정 (post_id={post['id']})")
    time.sleep(delay)

    try:
        image_url = post.get("image")
        result = publish_to_threads(user_id, token, post["text"], image_url=image_url)
        kind = "이미지" if image_url else "텍스트"
        print(f"[{name}] 본문({kind}) 게시 완료: {result}")

        reply_text = build_reply_text(post)
        if reply_text:
            main_post_id = result.get("id")
            reply_result = publish_to_threads(
                user_id, token, reply_text, reply_to_id=main_post_id
            )
            print(f"[{name}] 고정 댓글 게시 완료: {reply_result}")
    except requests.HTTPError as e:
        body = e.response.text if e.response is not None else str(e)
        print(f"[{name}] 게시 실패: {e} / 응답: {body}")
    except Exception as e:  # noqa: BLE001
        print(f"[{name}] 예외 발생: {e}")


def should_run_now():
    """마지막 실행으로부터 MIN_INTERVAL_HOURS가 지났는지 확인한다.
    아직 안 지났으면 (False, 남은시간) 반환, 지났으면 (True, 0) 반환."""
    state = load_json(LAST_RUN_PATH, None)
    if not state or "last_run_utc" not in state:
        return True, 0

    last_run = datetime.fromisoformat(state["last_run_utc"])
    now = datetime.now(timezone.utc)
    elapsed_hours = (now - last_run).total_seconds() / 3600

    if elapsed_hours >= MIN_INTERVAL_HOURS:
        return True, 0
    return False, MIN_INTERVAL_HOURS - elapsed_hours


def record_run_time():
    save_json(LAST_RUN_PATH, {"last_run_utc": datetime.now(timezone.utc).isoformat()})


def main():
    ready, remaining_hours = should_run_now()
    if not ready:
        print(
            f"⏳ 마지막 게시로부터 아직 {MIN_INTERVAL_HOURS}시간이 지나지 않았습니다. "
            f"약 {remaining_hours:.1f}시간 더 기다려야 합니다. 이번 실행은 건너뜁니다."
        )
        return

    # 실행이 몇십 분씩 걸릴 수 있으므로, 실제 게시를 시작하기 전에 먼저 시각을 기록해둔다.
    # (이렇게 해야 게시가 진행되는 동안 cron-job.org가 다시 깨워도 중복 실행되지 않음)
    record_run_time()
    print(f"✅ {MIN_INTERVAL_HOURS}시간 간격 조건 충족 - 게시를 시작합니다.")

    accounts = load_json(CONFIG_PATH, [])
    if not accounts:
        print("accounts_config.json을 찾을 수 없거나 비어 있습니다.")
        sys.exit(1)

    # 같은 posts_file을 쓰는 계정끼리 그룹화 (그룹별로 로테이션 큐를 독립적으로 관리)
    groups = defaultdict(list)
    for account in accounts:
        groups[account["posts_file"]].append(account)

    for posts_file, group_accounts in groups.items():
        posts = load_json(os.path.join(POSTS_DIR, posts_file), [])
        if not posts:
            print(f"게시할 글이 없습니다: {posts_file}")
            continue

        state = load_json(state_path(posts_file), {"queue": [], "cycle": 0})

        assignments = get_run_assignments(state, posts, len(group_accounts))
        print(f"[{posts_file}] 이번 실행 배정: {[p['id'] for p in assignments]}")

        # 계정 실행 순서를 매번 무작위로 섞어서 패턴을 더 다양하게
        random.shuffle(group_accounts)

        for account, post in zip(group_accounts, assignments):
            run_account(account, post)

        save_json(state_path(posts_file), state)


if __name__ == "__main__":
    main()
