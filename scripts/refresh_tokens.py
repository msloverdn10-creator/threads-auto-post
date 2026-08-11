"""
Threads 장기 액세스 토큰 자동 갱신 스크립트

- ACCOUNT1_TOKEN ~ ACCOUNT9_TOKEN 환경변수(GitHub Secrets)를 읽어 각각 갱신
- 갱신된 토큰을 GitHub Repository Secrets에 자동으로 다시 저장
  (PyNaCl로 GitHub의 공개키에 맞춰 암호화 후 REST API 호출)

사전 준비:
  1. pip install requests pynacl
  2. Settings > Secrets and variables > Actions 에 아래 값 등록
     - GH_PAT : repo 전체 권한(Secrets 쓰기 포함)을 가진 Personal Access Token
     - GH_REPO : "사용자명/저장소명" 형식 (예: msloverdn/threads-auto-post)
  3. 이 스크립트는 정기적으로(예: 매주 1회) 별도 워크플로우에서 실행 권장
     (60일 만료 훨씬 전에 미리 갱신해서 만료로 인한 포스팅 실패를 방지)
"""

import base64
import os
import sys

import requests
from nacl import encoding, public

GRAPH_REFRESH_URL = "https://graph.threads.net/refresh_access_token"
GITHUB_API = "https://api.github.com"

ACCOUNT_NAMES = [f"ACCOUNT{i}" for i in range(1, 9)]  # account9, 10은 Meta 제한 조치로 임시 제외 (재추가 시 range(1, 11)로 복원)


def refresh_token(current_token):
    resp = requests.get(
        GRAPH_REFRESH_URL,
        params={
            "grant_type": "th_refresh_token",
            "access_token": current_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["access_token"], data.get("expires_in")


def get_repo_public_key(repo, pat):
    resp = requests.get(
        f"{GITHUB_API}/repos/{repo}/actions/secrets/public-key",
        headers={
            "Authorization": f"Bearer {pat}",
            "Accept": "application/vnd.github+json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()  # {"key_id": ..., "key": ...}


def encrypt_secret(public_key_b64, secret_value):
    public_key = public.PublicKey(public_key_b64.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def update_github_secret(repo, pat, secret_name, secret_value, key_id, public_key_b64):
    encrypted_value = encrypt_secret(public_key_b64, secret_value)
    resp = requests.put(
        f"{GITHUB_API}/repos/{repo}/actions/secrets/{secret_name}",
        headers={
            "Authorization": f"Bearer {pat}",
            "Accept": "application/vnd.github+json",
        },
        json={"encrypted_value": encrypted_value, "key_id": key_id},
        timeout=30,
    )
    resp.raise_for_status()


def main():
    pat = os.environ.get("GH_PAT")
    repo = os.environ.get("GH_REPO")

    if not pat or not repo:
        print("GH_PAT / GH_REPO 환경변수가 설정되어 있지 않습니다. Secrets 자동 반영을 건너뜁니다.")
        print("대신 갱신된 토큰 값만 로그로 출력합니다 (수동으로 등록해야 함).")

    key_info = None
    if pat and repo:
        key_info = get_repo_public_key(repo, pat)

    any_failed = False

    for name in ACCOUNT_NAMES:
        token_secret_name = f"{name}_TOKEN"
        current_token = os.environ.get(token_secret_name)

        if not current_token:
            print(f"[{name}] 토큰이 없습니다. 건너뜁니다.")
            continue

        try:
            new_token, expires_in = refresh_token(current_token)
            days_left = round(expires_in / 86400, 1) if expires_in else "알 수 없음"
            print(f"[{name}] 갱신 성공. 새 토큰 유효기간 약 {days_left}일")

            if key_info:
                update_github_secret(
                    repo=repo,
                    pat=pat,
                    secret_name=token_secret_name,
                    secret_value=new_token,
                    key_id=key_info["key_id"],
                    public_key_b64=key_info["key"],
                )
                print(f"[{name}] GitHub Secret({token_secret_name}) 자동 업데이트 완료")
            else:
                # Secrets 자동 업데이트가 불가능한 경우를 대비해 마스킹 처리 후 출력
                print(f"::add-mask::{new_token}")
                print(f"[{name}] 새 토큰 값을 수동으로 {token_secret_name}에 등록하세요.")

        except requests.HTTPError as e:
            body = e.response.text if e.response is not None else str(e)
            print(f"[{name}] 갱신 실패: {e} / 응답: {body}")
            any_failed = True
        except Exception as e:  # noqa: BLE001
            print(f"[{name}] 예외 발생: {e}")
            any_failed = True

    if any_failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
