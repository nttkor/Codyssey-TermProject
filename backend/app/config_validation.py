"""
AskMate 환경 변수 유효성 검증 모듈 (Config Validation)

[파일 개요]
본 모듈은 애플리케이션 기동 시점과 CI/CD 배포 사전 검증(Pre-flight check) 단계에서
공통으로 사용하는 환경 변수 파싱 및 유효성 검증 함수를 제공합니다.
외부 서드파티 패키지에 의존하지 않고 Python 표준 라이브러리(math, os)만으로 작성되어,
의존성 패키지가 설치되지 않은 경량 CI 환경이나 배포 스크립트에서도 단독으로 실행할 수 있습니다.

[주요 역할]
1. AI 서비스 호출 타임아웃(AI_TIMEOUT) 문자열의 부동소수점 변환 및 유효성 검사.
2. NaN(Not a Number), 무한대(Inf, -Inf), 0 이하의 값, 부적절한 문자열 차단.
3. 배포 파이프라인에서 CLI 단독 실행(`python -m app.config_validation`)을 통한 환경 변수 사전 점검.
"""

import math
import os


def parse_ai_timeout(value: str) -> float:
    """AI_TIMEOUT 환경 변수 문자열을 검증하고 초 단위의 부동소수점(float)으로 변환합니다.

    [기술 설명]
    - 입력받은 문자열을 float로 변환한 후, 유한한 양수인지 철저히 검증합니다.
    - float("nan"), float("inf"), float("-inf")와 같은 특수 부동소수점 값은
      수학적/네트워크 타임아웃으로 유효하지 않으므로 math.isfinite()를 통해 걸러냅니다.
    - 음수 또는 0초 타임아웃은 즉시 실패하거나 비정상 동작을 유발하므로 차단합니다.

    Args:
        value (str): 환경 변수 등에서 전달받은 타임아웃 문자열 (예: "30", "12.5")

    Returns:
        float: 검증을 통과한 초 단위의 유한한 양수 타임아웃 값

    Raises:
        RuntimeError: 파싱이 불가능하거나(숫자 형태가 아님), NaN/Inf이거나, 0 이하인 경우 발생
    """
    try:
        timeout = float(value)
    except ValueError:
        # 숫자로 변환할 수 없는 문자열인 경우 예외 발생 (원인 체인 None으로 불필요한 트레이스백 숨김)
        raise RuntimeError("AI_TIMEOUT은 초 단위의 유한한 양수여야 합니다.") from None

    # 유한수 여부(isfinite) 및 양수 여부(> 0) 확인
    if not math.isfinite(timeout) or timeout <= 0:
        raise RuntimeError("AI_TIMEOUT은 초 단위의 유한한 양수여야 합니다.")

    return timeout


if __name__ == "__main__":
    # 배포 전 사전 검사(Pre-flight Check) CLI 진입점:
    # GitHub Actions 워크플로 등에서 본 파일을 직접 실행하여 환경 변수 적합성을 검증합니다.
    try:
        parse_ai_timeout(os.environ.get("AI_TIMEOUT", "30"))
    except RuntimeError as error:
        # 유효하지 않은 설정일 경우 에러 메시지와 함께 비정상 종료(exit code 1) 처리
        raise SystemExit(str(error)) from None
