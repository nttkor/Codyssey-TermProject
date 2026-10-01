# AskMate 운영·테스트·배포·협업 공부 노트

**기준:** `fix/qa-findings` / `baa13d5` (PR #36 반영 완료). 이 문서는 설정과 검증, 배포 구조를 설명합니다. 아래 명령은 학습용 안내입니다.

## 1. 환경 변수는 왜 필요한가요?

같은 코드를 로컬·배포 서버에서 쓰되 비밀키, 모델, DB 경로를 다르게 지정하기 위해 환경 변수를 사용합니다. 설정을 코드와 분리하면 비밀정보를 커밋하지 않고 환경을 바꿀 수 있습니다.

실제 `.env` 값은 이번 작업에서 읽지 않았습니다. 노트에도 키의 실제 값을 적지 않습니다.

확인 위치는 `B7-1/backend/app/config.py:10~54`입니다.

| 이름 | 필수·기본값 | 역할 |
| --- | --- | --- |
| `SESSION_SECRET_KEY` | 필수 | 쿠키 서명용 비밀키 |
| `SESSION_MAX_AGE` | 기본 3600, 양의 정수 | 세션 유효기간의 초 단위 설정 |
| `SESSION_HTTPS_ONLY` | 기본 false, true/false | HTTPS 전용 쿠키 여부 |
| `DATABASE_PATH` | 기본 `data/askmate.db` | DB 파일 경로 |
| `AI_API_KEY` | 필수 | AI 게이트웨이 인증 |
| `AI_BASE_URL` | 필수, http/https로 시작 | 게이트웨이 기본 URL |
| `AI_MODEL` | 필수 | 요청할 모델 |
| `AI_TIMEOUT` | 기본 30, 유한한 양수 | SDK 요청 타임아웃 설정 |

`load_dotenv(..., override=False)`이므로 이미 실행 환경에 있는 값이 `.env`보다 우선합니다. DB 상대 경로는 실행 디렉터리가 아니라 `backend/` 기준으로 계산합니다. 로그 파일 경로는 이와 달리 실행 디렉터리에 따라 달라집니다.

### 유한한 양수 검증

`config_validation.parse_ai_timeout():7~15`는 `float()`로 변환하고 `math.isfinite()`와 `> 0`을 확인합니다. 단순히 숫자로 변환됐다고 충분하지 않습니다. `nan`, `inf`, 너무 큰 수가 무한대로 변환된 경우도 막아야 정상적인 제한값이 됩니다.

동일 검증 파일을 배포 사전 검사에서 실행합니다(`.github/workflows/deploy-oci.yml:142`). 앱과 배포가 같은 규칙을 쓰는 이유는 배포 검사에서 통과한 값이 앱 시작에서 실패하는 불일치를 줄이기 위해서입니다.

`AI_TIMEOUT`은 SDK의 네트워크 타임아웃 설정입니다. `/api/chat` 전체가 정확히 그 시간 안에 종료된다는 보장은 아닙니다. DB 조회·저장, 네트워크 단계, 작업 스케줄링 시간은 별도이므로 전체 처리 시간과 구분해 주세요.

## 2. 비밀정보를 Git·이미지에서 제외하기

확인 위치:

- `B7-1/.gitignore:8~22`: 실제 환경 파일, DB, 로그를 Git 제외 대상으로 선언합니다.
- `B7-1/backend/.dockerignore:7~20`: 실제 환경 파일·DB·로그를 Docker 빌드 컨텍스트에서 제외합니다.
- `B7-1/backend/Dockerfile:12~18`: 프로젝트 설정과 앱 코드를 복사합니다.

`.gitignore`는 이미 추적된 비밀정보를 Git 이력에서 자동 삭제하지 않습니다. 비밀키가 한 번 유출되면 제외 규칙 추가만으로 해결되지 않으며 키 교체와 노출 범위 점검이 필요합니다.

`.env.example`은 설정 이름과 안전한 예시를 공유하기 위한 파일입니다. 실제 키, 쿠키, 운영 DB, 전체 비밀 헤더를 문서·스크린샷·커밋에 넣지 마세요.

## 3. 로컬 실행 명령을 이해하기

`B7-1/backend/pyproject.toml:5~21`에 Python 3.14와 런타임·개발 의존성이 선언되어 있습니다. `uv.lock`은 실제 설치 버전을 잠그는 파일입니다.

`B7-1/backend/`에서 실행하는 명령입니다.

```bash
uv sync --locked
uv run uvicorn app.main:app --reload
```

- `uv sync --locked`: 잠금 파일을 변경하지 않고 의존성을 맞춥니다. 설치 과정은 파일과 환경을 변경합니다.
- `uv run`: 프로젝트 환경으로 명령을 실행합니다.
- `app.main:app`: 실행할 앱 객체를 지정합니다.
- `--reload`: 코드 변경 시 다시 시작하는 개발 옵션입니다. 운영 배포에서는 사용하지 않습니다.

처음 설정 시 `.env.example`을 참고해 `.env`를 준비하되 기존 파일을 덮어쓰지 마세요. 실행만으로도 DB·로그 파일이 생길 수 있습니다.

`GET /health`는 앱 응답 확인용입니다. 시작 시 DB 연결을 확인하더라도 이후 DB나 AI 상태까지 health 응답이 검사하는 것은 아닙니다(`app/main.py:73~75`).

## 4. 로그는 어디에 무엇이 남나요?

`app/logger.py:15~24`는 콘솔과 `app.log` 파일에 기록합니다. `FileHandler("app.log")`는 상대 경로이므로 `backend/`에서 실행하면 `backend/app.log`입니다.

### 핵심 이벤트

| 이벤트 | 코드 위치 | 용도 |
| --- | --- | --- |
| `db_connection_success/failure` | `db_connect.check_connection():40~49` | 기동 시 DB 연결 |
| `request_received` | `account.py`, `llm.py:52` | API 작업 진입 |
| `login_success/failure` | `account.login():97~104` | 인증 결과 |
| `ai_call_started` | `llm_connect.py:57~62` | 모델·메시지 수·타임아웃 |
| `ai_call_success` | `llm_connect.py:105~108` | 소요 시간·답변 길이 |
| `ai_call_timeout/failure` | `llm_connect.py:71~103` | 통신·응답 형식 실패 |
| `db_read_failure` | `auth.py`, `history.py`, `llm.py` | 사용자·기록 조회 실패 |
| `db_save_success/failure` | `account.py`, `llm.py:84~91` | 저장 성공·실패 |
| `logout_success` | `account.logout():119~121` | 로그아웃 처리 |

예시입니다. 실제 값과 순서는 상황에 따라 달라집니다.

```text
request_received user_id=1 path=/api/chat
ai_call_started model=설정된모델 message_count=3 timeout=30.0
ai_call_success model=설정된모델 elapsed=1.200 answer_length=30
db_save_success operation=chat user_id=1 chat_id=2
```

### 로그 읽기 개념

- INFO: 정상적인 주요 사건입니다.
- WARNING: AI 실패나 인증 실패처럼 확인할 사건입니다.
- `logger.exception()`: 예외 처리 구간에서 추적 정보를 포함해 기록합니다.
- `time.monotonic()`: 시계 보정의 영향을 덜 받는 경과 시간 측정에 사용합니다.

프로젝트는 질문·답변 본문과 키를 직접 로그에 넣지 않는 정책입니다. DB 엔진의 `hide_parameters=True`도 SQL 인자 노출을 줄입니다(`db_connect.py:24`). 라이브러리 로그의 상세 수준은 `logger.py:30~33`에서 조절합니다.

AI 통신 로그에는 현재 사용자 ID나 공통 요청 ID가 없습니다. 동시에 여러 요청이 들어오면 줄이 섞일 수 있어 모든 로그를 완벽하게 한 요청으로 연결하는 데 한계가 있습니다. PDF의 예시 요청 ID가 현재 코드에도 구현되어 있다고 생각하면 안 됩니다.

명시적인 `request_received`는 해당 함수에 진입했을 때 남습니다. 인증·검증에서 막힌 요청은 이 로그가 없을 수 있습니다. HTTP 접근 로그는 Uvicorn에서 별도로 전달합니다(`logger.py:35~40`). 파일 로그 회전·보존 기간 설정은 현재 코드에 없습니다.

## 5. 테스트의 목적과 범위

테스트는 주어진 입력에 기대하는 출력과 상태 변화가 나오는지 반복 확인합니다. “화면에 답이 보임”만 확인하면 저장 실패, 다른 사용자 기록 노출, 예외 후 복구 같은 문제를 놓칠 수 있습니다.

### 테스트 준비

`backend/tests/conftest.py:7~41`의 fixture를 읽어 주세요.

```text
application fixture
  → 테스트 임시 경로
  → 테스트 환경 변수
  → 임시 DB·로그, 테스트용 AI 설정
  → 앱 가져오기

client fixture
  → TestClient 시작, lifespan 실행
  → 이전 테스트의 대화·사용자 행 정리
  → 테스트 함수에 client 제공
```

fixture는 테스트에 필요한 준비와 정리를 재사용하는 장치입니다. `monkeypatch`는 환경 변수나 함수를 테스트 동안 바꿉니다. 운영 코드를 고치지 않고 “DB가 실패한다”, “AI가 시간 초과된다”를 재현할 수 있습니다.

### 테스트 분류

| 파일 | 읽을 대표 테스트 | 확인하는 내용 |
| --- | --- | --- |
| `test_signup.py` | `test_signup_saves_user_with_random_salt` | 가입·해시·salt |
| `test_login.py` | `test_login_and_current_user`, `test_protected_pages` | 쿠키·계정·화면 접근 |
| `test_config.py` | `test_dotenv_and_environment_precedence`, `test_deployment_timeout_validation` | 설정 우선순위·검증 |
| `test_chat_storage.py` | `test_commit_failure_rolls_back_and_next_chat_works` | 저장 실패·복구 |
| `test_chat_context.py` | `test_context_contains_only_latest_five_own_pairs` | 사용자 분리·문맥 |
| `test_chat_history.py` | `test_saved_chat_is_visible_through_history_api` | 저장과 조회 연결 |
| `test_ai_chat.py` | `test_timeout_returns_504_and_does_not_save`, `test_malformed_success_response_is_safe_and_recovers` | 통신·오류·잘못된 성공 응답 |
| `frontend/chat-input.test.cjs` | 일반 Enter·조합 상태 테스트 | 입력기 이벤트 |
| `frontend/logout.test.cjs` | 204 성공·실패 후 재시도 테스트 | 로그아웃 UI 정책 |

`test_ai_chat.py:17~109`는 실제 제공자 대신 로컬 HTTP 게이트웨이를 구성합니다. 단순 함수 대체 테스트보다 SDK의 요청 형식·헤더·응답 처리를 함께 확인할 수 있지만, 실제 AI 모델 품질·운영 키 유효성·배포 네트워크까지 보증하지는 않습니다.

### 실행 안내

`B7-1/backend/`에서 실행합니다. 테스트는 임시 파일 등을 만들고 로컬 게이트웨이를 열 수 있으므로 읽기 전용 작업은 아닙니다.

```bash
uv run python -m pytest -q
node --test tests/frontend/*.test.cjs
```

Node 테스트는 Node.js 22 이상 기준으로 추가 npm 패키지 없이 실행하도록 작성되어 있습니다. 앱 서버 운영 자체에 Node가 필요한 구조는 아닙니다.

기존 `B7-1/docs/TESTING.md:531~567`에는 과거 로컬 QA 결과로 Python 148개, Node 12개 통과가 기록되어 있습니다. 이는 **기존 문서의 기록**이고 이번 세션에서 다시 실행한 결과가 아닙니다. 실제 OS 한글 입력기, 외부 접근성, 실제 AI, OCI 배포는 별도 확인 대상으로 명시되어 있습니다.

## 6. Docker 이미지와 컨테이너

이미지는 실행 코드·라이브러리·기본 명령을 담은 배포 패키지이고, 컨테이너는 그 이미지로 실행한 인스턴스입니다. 같은 이미지로 여러 컨테이너를 만들 수 있습니다.

`B7-1/backend/Dockerfile`을 읽는 순서입니다.

| 라인 | 동작 | 이유 |
| --- | --- | --- |
| `3` | Python·uv 기반 이미지 | 실행 환경을 맞춥니다. |
| `10` | `/app`을 작업 디렉터리로 설정 | 경로 기준을 정합니다. |
| `12~14` | 의존성 파일 먼저 복사·설치 | 코드 변경 때 의존성 캐시를 활용합니다. |
| `16~18` | 앱 코드 복사·설치 | 실행 코드를 이미지에 포함합니다. |
| `20~24` | 일반 사용자·데이터 경로 준비 | 루트가 아닌 사용자로 앱을 실행합니다. |
| `26` | 8000 포트 선언 | 컨테이너 서비스 포트를 문서화합니다. |
| `30~31` | HTTP healthcheck | 프로세스 존재가 아닌 응답을 확인합니다. |
| `33` | Uvicorn 실행 | 모든 컨테이너 인터페이스에서 8000 포트로 받습니다. |

`EXPOSE 8000`만으로 외부에 공개되는 것은 아닙니다. `docker run --publish` 등의 호스트 포트 연결과 방화벽 설정이 필요합니다. `--host 0.0.0.0`은 수신 인터페이스 설정이지 사용자가 접속할 공인 URL 자체가 아닙니다.

## 7. 자동 배포: 이벤트부터 따라가기

확인 파일은 `B7-1/.github/workflows/deploy-oci.yml`입니다. GitHub Actions는 저장소 이벤트에 따라 작업을 실행하는 자동화 도구입니다. 이 노트 작성에서는 GitHub나 서버에 접속하지 않았습니다.

### 7.1 언제 무엇을 실행하나요?

| 이벤트 | 조건 | 실제 동작 |
| --- | --- | --- |
| PR | 대상 develop/main, 같은 저장소 | 이미지 게시·OCI 배포 |
| PR | 대상 develop/main, 포크 저장소 | 이미지 빌드만 검증 |
| push | develop/main, backend 또는 워크플로 변경 | 이미지 게시·OCI 배포 |
| 수동 실행 | main/develop | 이미지 게시·OCI 배포 |

라인 `3~18`, `28~71`을 보세요. 문서만 바꾼 push는 경로 필터에 따라 배포가 생략될 수 있지만 PR에는 해당 필터를 넣지 않았습니다. “모든 develop 변경이 반드시 배포된다”라고 단순화하면 안 됩니다.

같은 저장소의 PR에서 실제 production 환경을 사용한다는 점이 중요합니다. 미병합 코드가 공유 서버를 변경할 수 있습니다. `concurrency`는 같은 배포 그룹의 실행을 겹치지 않도록 하지만, 배포 서버를 항상 main 코드로 유지한다는 보장은 아닙니다.

### 7.2 이미지 태그

태그는 이미지에 붙이는 이름입니다(`144~179`).

- `sha-커밋`: 정확한 코드 버전 추적용입니다.
- `pr-번호`: PR 검증 이미지입니다.
- `develop`: 통합 브랜치 이미지입니다.
- `latest`: main 이미지에 추가되는 이동 가능한 태그입니다.

실제 서버 교체는 `sha-커밋` 태그를 지정합니다(`264`). `latest`는 이름이므로 그 이름만 보고 정확한 버전을 단정하지 말아야 합니다. PR에서는 head 커밋을 기준으로 태그를 만들지만 checkout·빌드 문맥은 Actions의 PR 동작도 함께 이해해야 합니다. 태그 이름만으로 빌드 트리의 모든 세부사항을 설명할 수는 없습니다.

### 7.3 연결과 설정 전달

`181~259`의 주요 흐름입니다.

```text
이미지 빌드 → Docker Hub 게시
  → Actions 실행기를 Tailscale 네트워크에 연결
  → SSH 키·known_hosts 준비
  → OCI 서버에서 레지스트리 로그인
  → 환경 변수 파일을 stdin으로 전달
```

Docker Hub는 이미지 저장소이고, OCI는 컨테이너를 실행할 서버 환경이며, Tailscale은 배포용 연결 경로입니다. SSH의 `known_hosts` 검사는 접속 대상 서버를 확인하는 데 사용합니다.

배포용 SSH 주소와 사용자 공개 서비스 URL은 별개입니다. Tailscale에 연결된 서버에 배포한다고 사용자의 브라우저도 반드시 Tailscale을 써야 하는 것은 아닙니다. 공개 포트·공인 IP·방화벽은 따로 설정합니다.

## 8. 컨테이너 교체·볼륨·복구

위치: 워크플로 `261~377`입니다.

```text
새 이미지 pull 성공
  → 기존 컨테이너 중지·백업 이름으로 보존
  → 새 컨테이너 시작
       ├─ host 포트 → container 8000
       ├─ askmate-data 볼륨 → /app/data
       └─ 환경 변수 파일 적용
  → 최대 30회, 2초 간격 상태 관찰
       ├─ healthy → 백업 컨테이너 삭제
       └─ 실패·제한 초과 → rollback()
```

볼륨은 컨테이너 파일 시스템과 데이터 저장 수명을 분리합니다. 기본 DB가 `/app/data`에 있으므로 컨테이너 교체 후에도 남습니다. `app.log`는 기본 `/app` 작업 디렉터리에 생겨 이 데이터 볼륨에 포함되지 않습니다. 기록 DB 영속성과 파일 로그 보존을 구분해 주세요.

`rollback():326~345`는 실패한 새 컨테이너 로그·상태를 기록하고 제거한 뒤 기존 컨테이너를 원래 이름으로 되돌려 재시작합니다. 무중단 배포는 아닙니다. 기존 컨테이너를 먼저 중지하므로 일시적인 공백이 생길 수 있습니다.

DB 볼륨은 공유하고 있으므로 이 복구가 DB를 배포 이전으로 되돌리는 것은 아닙니다. 스키마 변경·데이터 변경이 들어가는 경우에는 별도의 호환성과 복구 계획이 필요합니다.

healthcheck는 `/health`를 호출합니다. 앱 시작에 실패하면 잡아낼 수 있지만 실제 로그인·AI·저장·외부 방화벽까지 확인하지 않습니다. 내부 healthy와 외부 사용자 이용 가능은 서로 다른 검증입니다.

## 9. 공개 서비스와 보안

기존 `B7-1/README.md:117~119`는 제출용 주소와 외부 접근성·배포 버전의 별도 확인 필요성을 기록합니다. 이번 작업에서는 해당 주소에 접속하지 않았습니다.

기존 배포 안내는 HTTP 공개 서비스에 시연용 계정만 사용하라고 경고합니다(`docs/TESTING.md:438~439`). DB에 Argon2 해시를 저장하더라도 HTTP로 보내는 로그인 비밀번호는 전송 보호가 되지 않습니다. HTTPS와 그에 맞는 `SESSION_HTTPS_ONLY` 설정이 필요합니다.

운영 확인은 다음을 따로 구분해야 합니다.

1. 앱이 시작되는지 확인합니다.
2. 외부 네트워크에서 URL에 접속되는지 확인합니다.
3. 회원가입·로그인·질문·문맥·기록·로그아웃을 확인합니다.
4. 실제 AI 실패와 지연 안내를 확인합니다.
5. 배포된 이미지와 원하는 커밋이 일치하는지 확인합니다.
6. DB와 로그 증빙에서 개인정보·키가 노출되지 않는지 확인합니다.

## 10. 브랜치·PR·개인 기여

현재 학습 기준은 `fix/qa-findings`이며 예정 흐름은 다음과 같습니다.

```text
fix/qa-findings → develop → main
   수정 묶음      통합      최종 기준
```

작업 브랜치는 기능·수정을 묶고, develop은 팀 변경을 통합하며, main은 최종 기준을 정하는 역할입니다. 실제 운영 배포가 main만 사용하는 것은 아니라는 점은 워크플로와 함께 설명해야 합니다.

PR은 변경 내용과 검증 결과를 보여 주고 리뷰·병합 기록을 남기는 단위입니다. 커밋은 작은 변경 이력이며, 의미 있는 단위로 나누어야 합니다. 파일이나 코드 줄을 늘린 것만으로 유의미한 기여가 보장되지는 않습니다.

과제는 팀원별 유의미한 커밋 최소 10회, 기능별 작업 흐름, PR 병합 기록, 역할·개인 작업 요약과 Git 이력의 일관성을 요구합니다. 카운트만으로 의미를 판정할 수 없고, 이름·이메일 별칭·공동 작성·병합 방식도 함께 확인해야 합니다.

확인할 프로젝트 문서는 `B7-1/docs/CONVENTIONS.md`, `B7-1/docs/TEAM.md`입니다. 아래는 `B7-1/`에서 사용할 읽기 전용 Git 확인 명령입니다.

```bash
git status --short --branch
git log --oneline develop..fix/qa-findings
git log --merges --oneline fix/qa-findings
git shortlog -sne fix/qa-findings
```

병합 방식에 따라 Git merge 커밋만으로 모든 PR 기록을 알 수는 없습니다. 실제 PR 리뷰·병합 기록은 저장소의 PR 자료와 함께 확인해야 합니다. 이번 노트는 원격 이력의 최신 상태나 개인별 요건 충족 여부를 확정하지 않습니다.

## 11. 평가 설명용 핵심 문장

- “AI 키는 서버 환경 변수로만 읽고 브라우저에는 답변 결과만 반환합니다.”
- “실행 환경 값이 `.env`보다 우선하고, 필수 설정은 기동 시점에 검증합니다.”
- “로그에는 처리 이벤트와 실패 유형을 남기되 질문 본문·키를 직접 넣지 않습니다.”
- “모의 함수와 로컬 HTTP 게이트웨이로 오류를 재현하며 실제 외부 AI 검증과 구분합니다.”
- “Docker 볼륨이 기본 DB 파일을 컨테이너 교체와 독립적으로 유지합니다.”
- “컨테이너 상태 검사 실패 시 기존 컨테이너를 재시작하지만 DB 복구까지 수행하지는 않습니다.”
- “같은 저장소의 PR에서도 실제 배포가 수행되므로 미병합 코드가 공유 서버에 반영될 수 있습니다.”
- “외부 접근 가능 여부와 최종 배포 커밋은 평가 전에 별도로 확인해야 합니다.”

## 12. 설명 연습과 참고 개념

- `nan`이나 `inf`를 허용하면 타임아웃 정책에 어떤 문제가 생길 수 있나요?
- 파일 로그와 DB 대화 기록은 목적과 보존 위치가 어떻게 다른가요?
- 테스트 통과와 실제 운영 서비스 정상 동작은 왜 다른가요?
- 이미지, 컨테이너, 볼륨, 레지스트리를 구분해서 설명해 주세요.
- `healthy`인데도 외부 사용자가 접속하지 못하는 상황은 무엇인가요?
- PR 배포와 병합 후 배포가 모두 있을 때 배포 버전을 왜 따로 확인해야 하나요?

추가 학습 링크:

- [pytest fixture](https://docs.pytest.org/en/stable/how-to/fixtures.html)
- [Docker 개념](https://docs.docker.com/get-started/docker-concepts/the-basics/)
- [Docker 볼륨](https://docs.docker.com/engine/storage/volumes/)
- [GitHub Actions 이해](https://docs.github.com/en/actions/about-github-actions/understanding-github-actions)
