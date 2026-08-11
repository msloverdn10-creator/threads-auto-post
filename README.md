# Threads 9계정 자동 포스팅

## 폴더 구조
```
threads-auto-post/
├── .github/workflows/
│   ├── post.yml              ← workflow_dispatch (cron-job.org가 외부에서 트리거)
│   └── refresh_tokens.yml    ← 주 1회 토큰 자동 갱신
├── scripts/
│   ├── post.py                ← 메인 게시 스크립트
│   └── refresh_tokens.py      ← 토큰 갱신 스크립트
├── accounts_config.json       ← 계정 9개 설정 (전부 posts/shared.json 참조)
├── posts/
│   └── shared.json            ← 9개 계정이 공용으로 쓰는 글 21개
└── indexes/
    └── rotation_state__shared.json  ← 로테이션 큐 상태 (자동 관리)
```

## 로테이션 방식 (3차 수정) — "실행 시작 시점에 9개를 한 번에 확정 배정"

이전 버전에서 실제 운영 중 여러 계정에 같은 글이 배정되는 문제가 발견되어, 로직을 더 단순하고 명확하게 다시 짰습니다.

동작 방식:
1. 실행이 시작되면, 먼저 큐(대기열)에 이번에 필요한 개수(9개) 이상이 있는지 확인
2. 부족하면 "아직 큐에 없는(=최근에 안 쓴) id들"로 채움 → 큐는 항상 **중복 없는 id 목록**으로 유지됨
3. 큐 맨 앞에서 9개를 통째로 잘라서 9개 계정에 배정 (이 방식은 구조적으로 중복이 생길 수 없음)
4. 배정 결과를 실행 로그 맨 위에 미리 출력 (`이번 실행 배정: [...]`) → 문제 생기면 로그에서 바로 확인 가능
5. 계정별 게시 순서와 대기 시간은 여전히 무작위

10회 연속 실행(디스크 저장 포함)을 시뮬레이션해서 매번 9개 전부 고유하고 21개 글이 골고루 순환되는 것을 확인했습니다.

## API 오류 자동 재시도

Threads API가 일시적으로 `500 Internal Server Error`를 반환하는 경우가 있습니다 (Meta 서버 쪽 문제로, 우리 쪽 코드 문제가 아님). 이제 5xx 서버 오류는 최대 3회까지 자동 재시도(5초 → 15초 → 30초 간격)합니다. 반면 401/403 같은 인증 오류(4xx)는 재시도해도 소용없으므로 즉시 실패 처리됩니다.

## 무료 사용량 확인 (7차 수정)

GitHub Actions는 **Private 저장소 기준 월 2,000분까지 무료**입니다. 아래처럼 계산해서 여유 있게 들어오도록 조정했습니다.

| 항목 | 계산 |
|---|---|
| 실제 게시 실행 빈도 | 하루 24÷7 ≈ 3.43회 |
| 회당 소요 시간 (계정 10개, 무작위 대기 최대 90초로 조정 후) | 계정당 평균 약 65초(대기 45초 평균 + API 처리 20초) × 10 ≈ 약 11분 |
| 월간 실제 게시 시간 | 3.43회 × 30일 × 11분 ≈ **약 1,130분** |
| "아직 시간 안 됨" 확인용 실행 (매시간, bash 사전 체크로 경량화) | 하루 약 20.6회 × 회당 약 8초 ≈ 하루 약 3분, 월간 **약 90분** |
| **월 합계** | **약 1,220분** (무료 한도 2,000분의 약 61%) |

계정을 더 늘리거나 이미지 게시(용량이 커서 조금 더 걸림)까지 고려해도 여유가 있도록 설계했습니다. 그래도 걱정되면 아래 "사용량 직접 확인하는 법"으로 주기적으로 체크해보세요.

### 사용량 직접 확인하는 법
GitHub 저장소 Settings → 좌측 하단 근처 **Billing and plans** (또는 계정 자체의 Settings → Billing) → **Actions** 사용량에서 이번 달 사용한 분(minutes)을 확인할 수 있습니다.

### 그래도 무료 한도가 걱정된다면
- **Public 저장소로 전환**: Public 저장소는 Actions 사용시간이 완전 무제한 무료입니다. 다만 저장소가 공개되면 (토큰/Secrets 값 자체는 노출되지 않지만) 게시 로직, 계정 운영 구조, 글 내용이 누구나 볼 수 있게 됩니다. 이 부분은 사업적으로 괜찮은지 판단이 필요합니다.
- **`MIN_INTERVAL_HOURS`를 늘리기**: `scripts/post.py`에서 값을 7보다 크게(예: 8, 10) 바꾸면 실제 게시 횟수 자체가 줄어 사용량이 더 줄어듭니다.
- **cron-job.org 폴링 주기를 늘리기**: 매시간 대신 2시간마다 깨우도록 하면 "아직 시간 안 됨" 실행 횟수가 절반으로 줄어듭니다 (7시간 정확도는 최대 2시간까지 느슨해질 수 있음).

## 게시 간격을 정확히 7시간으로 — cron-job.org 설정 (차근차근)

### 1단계: cron-job.org에서 기존 job 열기
1. cron-job.org 로그인 → 대시보드에서 지금 쓰고 있는 게시용 cronjob 클릭
2. **Edit** 버튼 클릭

### 2단계: Execution schedule을 "매시간"으로 변경
1. **Execution schedule** 섹션에서 지금 `0 */6 * * *` (또는 "Every 6 hours")로 되어 있을 스케줄을 아래 중 하나로 바꿉니다:
   - **Custom** 선택 후 Crontab expression 입력창에 `0 * * * *` 입력 (매시 정각마다 워크플로우를 깨움)
   - 또는 드롭다운에 "Every 1 hours" 옵션이 있다면 그걸 선택해도 동일합니다
2. 오른쪽 **"Next executions"** 패널에 1시간 간격으로 실행 목록이 뜨는지 확인
3. 페이지 하단 저장 버튼 클릭

> ⚠️ 여기서 헷갈리지 않아야 할 부분: cron-job.org는 이제 "정확히 7시간마다 게시"를 담당하지 않습니다. **그냥 매시간 워크플로우를 깨우기만** 하고, "진짜 게시할 시점인지"는 저장소 안의 `post.py`가 직접 판단합니다. 그래서 cron-job.org 쪽 숫자는 7이 아니라 1(시간)로 맞추는 게 맞습니다.

### 3단계: 실제로 7시간 간격이 지켜지는지 확인
1. 반영 후 GitHub Actions 탭에서 매시간 워크플로우가 실행되는 걸 볼 수 있습니다
2. 대부분의 실행 로그에는 `⏳ N시간 경과, 약 M시간 더 기다려야 합니다`라는 메시지만 있고 몇 초 만에 끝납니다 (Python 설치 단계까지 안 가고 바로 종료 - 이래서 사용량이 절약됩니다)
3. 정확히 7시간이 지난 시점의 실행에서만 `✅ N시간 경과 - 게시를 진행합니다`가 뜨고 실제 게시가 이루어집니다
4. `indexes/last_run.json` 파일을 저장소에서 열어보면 마지막 게시 시각(UTC)이 기록되어 있어서, 언제 다음 게시가 이루어질지 계산해볼 수 있습니다

### 간격을 바꾸고 싶다면
`scripts/post.py` 상단의 `MIN_INTERVAL_HOURS = 7` 숫자만 바꾸면 됩니다. cron-job.org 쪽은 그대로 매시간(또는 그보다 촘촘하게) 유지하면 됩니다.

## 카드뉴스 이미지 자동 첨부

텍스트만 있는 게시물보다 이미지가 있으면 조회수/반응률이 좋아지는 경우가 많아, 각 글 주제에 맞는 카드뉴스 이미지를 자동으로 함께 게시하도록 추가했습니다.

### 동작 방식
- `scripts/generate_cards.py` 실행 시 `posts/shared.json`의 각 글에 대해 1080×1350(4:5) 카드뉴스 이미지를 생성 (`cards/` 폴더)
- 각 글의 `posts/shared.json`에 `image` 필드가 추가되어 있고, 여기에 이미지의 **공개 URL**이 들어감
- `scripts/post.py`가 게시할 때 `image` 필드가 있으면 `media_type: IMAGE`로, 없으면 기존처럼 `media_type: TEXT`로 게시함

### ⚠️ 이미지 호스팅이 별도로 필요합니다
Threads API는 이미지 파일을 직접 업로드받지 않고, **공개적으로 접근 가능한 이미지 URL**을 요구합니다. 지금 저장소가 Private이라 GitHub raw 링크를 Threads가 가져갈 수 없습니다. 그래서:

1. **이미지 전용 Public 저장소를 새로 만듭니다** (예: `threads-post-cards`). 코드나 계정 정보 없이 이미지 파일만 올라가므로 Public이어도 안전합니다.
2. 그 저장소에 `cards/` 폴더 안의 PNG 25개를 저장소 루트에 업로드합니다.
3. 저장소 Settings → Pages → Source를 "Deploy from a branch" → `main` / `(root)`로 설정해서 **GitHub Pages를 켭니다**.
4. 몇 분 후 `https://{깃허브아이디}.github.io/threads-post-cards/info-001.png` 같은 주소로 이미지가 공개됩니다.
5. `posts/shared.json`의 `image` 필드 URL이 이 패턴(`https://msloverdn.github.io/threads-post-cards/{id}.png`)으로 이미 채워져 있으니, 저장소 이름이나 계정명을 다르게 하셨다면 `image` 값을 맞게 수정해주세요.

### 새 글을 추가할 때
`posts/shared.json`에 새 글을 추가하면, `scripts/generate_cards.py`의 `CARD_DATA` 딕셔너리에도 해당 id로 `title`(카드 제목) / `highlights`(핵심 3줄) / `category`(색상 테마용 태그)를 추가하고 스크립트를 다시 실행해야 카드가 생성됩니다. 그 다음 새로 생성된 PNG를 이미지 호스팅 저장소에도 업로드해야 합니다.

## 게시 간격을 정확히 7시간으로 (6차 수정) — 스크립트 자체 게이트 방식

cron 표현식만으로는 "실행 후 정확히 7시간 뒤"를 만들 수 없습니다 (cron은 자정마다 리셋되어 하루 끝에서 간격이 틀어짐). 그래서 방식을 바꿨습니다:

- **cron-job.org는 자주(예: 매시간) 워크플로우를 깨우기만 함** — 실제로 게시할지는 판단하지 않음
- **`post.py`가 직접 판단** — `indexes/last_run.json`에 마지막 실행 시각을 기록해두고, 이번 실행이 그로부터 `MIN_INTERVAL_HOURS`(기본 7시간) 이상 지났는지 확인. 안 지났으면 아무것도 안 하고 조용히 종료
- 이 방식은 cron의 자정 리셋과 무관하게, 실제로 마지막 게시가 끝난 시점 기준 항상 정확히 7시간 뒤에 다음 게시가 이루어짐

### cron-job.org 설정 방법
1. 기존 job의 Execution schedule을 **"Every 1 hours"**(또는 30분 간격을 원하면 Custom `*/30 * * * *`)로 변경
2. 이제 워크플로우는 매시간 호출되지만, 7시간이 안 지났으면 `post.py`가 로그에 "⏳ 아직 N시간 더 기다려야 합니다"만 남기고 바로 종료됨 (실제 게시 없음, 몇 초 만에 끝남)
3. 7시간 조건이 충족된 실행에서만 실제로 게시가 진행됨

### 간격을 바꾸고 싶다면
`scripts/post.py`의 `MIN_INTERVAL_HOURS = 7` 값만 바꾸면 됩니다.

### 참고: GitHub Actions 사용량
매시간 호출 방식이라 "아직 시간 안 됨" 상태로 끝나는 실행이 하루에 여러 번 생기는데, 이런 실행은 몇 초 안에 끝나서 Actions 사용 시간에 미치는 영향은 미미합니다. Private 저장소는 무료 티어에서 월 2,000분을 제공하는데, 실제 게시가 이루어지는 실행(계정 10개 기준 회당 최대 약 45분)이 하루 약 3.4회 발생하는 걸 고려하면 사용량을 가끔 GitHub Actions 사용 내역에서 확인해보시는 걸 권장합니다.

이전에는 모든 글의 고정 댓글에 "💡 숨은 지원금 찾기" 문구가 토씨 하나 안 틀리고 반복됐는데, 이게 스팸 탐지 신호가 될 수 있어서 구조를 바꿨습니다.

- `posts/shared.json`의 각 글은 이제 `reply` 대신 `link_label`(주제별 링크 설명)과 `link`(주제별 URL)만 가짐
- 홈페이지 안내 문구는 `scripts/post.py`의 `REPLY_FOOTER_VARIANTS`에 8가지 버전으로 준비되어 있고, 게시할 때마다 그중 하나를 무작위로 골라 사용
- 최종 고정 댓글은 `🔗 {주제별 설명}\n{주제별 링크}\n\n{무작위로 고른 홈페이지 안내 문구}` 형태로 조합됨
- 문구를 더 추가/수정하고 싶으면 `scripts/post.py`의 `REPLY_FOOTER_VARIANTS` 리스트만 수정하면 됩니다

## 글 구조/이모지 다양화

기존 21개 글이 전부 `📌`/`🤯`/`📆`/`✅`/`🔔` 같은 이모지를 거의 같은 자리에 반복하고, 번호 리스트 구조도 거의 동일해서 자동화 탐지에 취약했습니다. 이번에 22개 글(기존 21개 + 건강보험 본인부담상한제 1개 추가) 전체를 다음과 같이 다양한 스타일로 다시 작성했습니다:

- 번호 매긴 리스트 (1. 2. 3.)
- 대시(-) 또는 가운뎃점(·) 리스트
- Q&A 형식 (Q. / →)
- 이모지 없는 담백한 서술형
- 이모지를 넣되 매번 다른 조합 사용

같은 골격을 기계적으로 반복하지 않도록 글마다 다른 형식을 적용했습니다.

## 설정 순서

1. **posts/shared.json 내용 확인/수정**
   - 21개 글이 이미 들어있습니다. 필요하면 여기서 글을 추가/수정하세요.
   - `id`는 파일 안에서 겹치지 않게 유지하면 됩니다.

2. **GitHub Secrets 등록** (Settings > Secrets and variables > Actions)
   - `ACCOUNT1_TOKEN` ~ `ACCOUNT9_TOKEN`
   - `ACCOUNT1_ID` ~ `ACCOUNT9_ID`
   - (토큰 자동 갱신을 쓰려면) `GH_PAT`: repo 전체 권한을 가진 Personal Access Token

3. **cron-job.org 설정** (post.yml은 이제 `workflow_dispatch`만 있고 자체 schedule은 없음)

   3-1. GitHub에서 `workflow_dispatch`를 외부에서 호출하려면 PAT가 필요합니다.
        (아래 "GH_PAT 발급 방법" 참고 - repo 권한이 있으면 이 PAT를 그대로 재사용 가능)

   3-2. cron-job.org에서 새 작업(Cronjob) 생성:
        - **URL**: `https://api.github.com/repos/{사용자명}/{저장소명}/actions/workflows/post.yml/dispatches`
        - **Method**: POST
        - **Headers**:
          ```
          Authorization: Bearer <GH_PAT 값>
          Accept: application/vnd.github+json
          Content-Type: application/json
          ```
        - **Body (raw JSON)**:
          ```json
          { "ref": "main" }
          ```
        - **스케줄**: 6시간마다 (예: `0 0,6,12,18 * * *` 또는 cron-job.org UI에서 "Every 6 hours" 선택)

   3-3. 저장 후 cron-job.org의 "Test run" 버튼으로 한 번 실행해보고, GitHub Actions 탭에 워크플로우가 실행됐는지 확인

4. **워크플로우 테스트**
   - GitHub Actions 탭 > Threads Multi-Account Auto Post > Run workflow로 수동 실행해서 먼저 확인
   - 이후 cron-job.org 트리거가 정상 작동하는지 확인

## ACCOUNT_ID(계정별 Threads User ID) 확인하는 방법

각 계정의 액세스 토큰을 발급받은 뒤, 아래 URL을 브라우저 주소창이나 curl로 호출하면 됩니다.

```
https://graph.threads.net/v1.0/me?fields=id,username&access_token=여기에_해당_계정_토큰
```

응답 예시:
```json
{ "id": "1234567890123456", "username": "myaccount1" }
```
여기서 `id` 값이 그 계정의 `ACCOUNT1_ID`(GitHub Secret에 등록할 값)입니다. 계정 9개 각각 토큰을 넣어서 9번 반복하면 됩니다.

curl로 하고 싶다면:
```bash
curl "https://graph.threads.net/v1.0/me?fields=id,username&access_token=여기에_토큰"
```

## GH_PAT 발급 방법 (토큰 자동 갱신 + cron-job.org 트리거용)

1. GitHub 우측 상단 프로필 아이콘 > **Settings**
2. 왼쪽 메뉴 맨 아래 **Developer settings**
3. **Personal access tokens > Tokens (classic)** > **Generate new token (classic)**
4. Note(이름)에 `threads-auto-post-pat` 같이 알아보기 쉬운 이름 입력
5. Expiration(만료 기간) 설정 - 만료되면 다시 발급해야 하니 90일 이상 권장
6. Scopes에서 **repo** 전체 체크 (Actions secrets 쓰기 + workflow dispatch 호출에 필요한 권한이 모두 repo scope 안에 포함됨)
7. **Generate token** 클릭 → 생성된 토큰 값을 즉시 복사 (다시 볼 수 없음)
8. 저장소 Settings > Secrets and variables > Actions > **New repository secret**
   - Name: `GH_PAT`
   - Value: 방금 복사한 토큰 값
9. cron-job.org 설정(3-2 단계)의 `Authorization: Bearer` 값에도 동일한 토큰을 사용

> 참고: Fine-grained personal access token을 쓰고 싶다면, 해당 저장소만 선택하고 Repository permissions에서 **Actions: Read and write**, **Secrets: Read and write**를 부여하면 됩니다.

## 캡처 화면에서 삭제해야 할 기존 파일

캡처된 파일 목록 기준으로, 예전(3계정+AI 8계정) 시스템에서 쓰던 아래 파일들은 이제 쓰이지 않으므로 **삭제**하세요:

| 파일 | 이유 |
|---|---|
| **`post.py`** (저장소 루트) | 예전 account1~3용 스크립트. 이제 `scripts/post.py`로 대체됨 |
| **`post_new.py`** (저장소 루트) | Groq AI 자동 생성 방식 스크립트. 더 이상 사용 안 함 |
| **`indexes/shared_used.json`** | 예전 account1~3 공유 글 추적 파일. 새 구조에서는 계정별 `indexes/accountN_used.json`을 사용 |
| **`indexes/used_topics.json`** | 예전 AI 계정(4~8)의 주제 추적 파일. 더 이상 사용 안 함 |

그대로 **유지**해야 할 파일:
- `.github/workflows/post.yml`, `refresh_tokens.yml` (이번에 새로 올린 내용으로 덮어쓰기)
- `posts/account1.json ~ account9.json` (이미 캡처에 보이는 것처럼 새 구조로 잘 만들어져 있음 - 내용만 본인 글로 채우면 됨)
- `indexes/account1_used.json ~ account9_used.json` (account4~9는 새로 추가, account1~3은 내용을 `{"used_ids": [], "cycle": 0}`로 초기화해서 새 형식에 맞추는 것을 권장)
- `accounts_config.json`, `scripts/post.py`, `scripts/refresh_tokens.py` (이번에 올린 새 버전으로 교체)

## 이번 버전에서 바뀐 점

- **계정별 콘텐츠 분리**: 계정마다 별도 posts 파일을 사용해 동일 문구가 여러 계정에 동시에 나가지 않도록 함
- **무작위 지연**: 계정마다 0~5분 사이 무작위 대기 후 게시 → 9개 계정이 정확히 같은 시각에 동시 발행되는 패턴 방지
- **계정 실행 순서 셔플**: 매 실행마다 계정 처리 순서를 무작위로 섞음
- **토큰 자동 갱신**: 60일 만료 훨씬 전(매주)에 미리 갱신하고, GitHub Secrets에 자동 반영

## 참고

- Threads API 게시 한도는 계정당 24시간 250건입니다. 6시간 간격(하루 4건)은 한도의 1.6% 수준이라 API 레이트리밋 문제는 없습니다.
- 글 풀은 현재 48개(버팀목전세자금대출, 실내 피서 명소, 열대야 없는 여행지, 열사병 대처법, 운전면허증 갱신, 장기전세 주택공급 6개 추가)입니다. 현재 계정 수는 8개(account9, 10은 Meta 정책 위반 소명 절차로 임시 제외 중)이며, 글 풀은 계정 수보다 항상 많아야 매 실행 무중복이 보장되니 계정을 다시 늘릴 때 글도 함께 확인해주세요.
- 저장소에 예전 파일(`post.py`/`post_new.py` 루트, `indexes/shared_used.json`, `indexes/used_topics.json`, `indexes/account1~9_used.json`, `posts/account1~9.json`)이 남아있다면 삭제 대상입니다.
- **"글쓰기 지침" 관련 안내**: 손실 프레이밍·허위 경험담·가짜 댓글 유도·PASONA 공식을 지시하는 프롬프트 문서는 이 시스템에 반영하지 않았습니다. `posts/shared.json`의 글은 전부 정보 전달형으로 통일해서 관리하고 있으니, 새 글을 추가할 때도 기존 25개와 같은 톤(사실 위주, 허위 경험담 없음, 과장된 손실 표현 없음)을 유지해주세요.
