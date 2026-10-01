"""앱 기동과 배포 사전 검사에서 공유하는 환경 변수 검증. 표준 라이브러리만 사용한다."""

import math
import os


def parse_ai_timeout(value: str) -> float:
    """초 단위의 유한한 양수만 타임아웃으로 허용한다."""
    try:
        timeout = float(value)
    except ValueError:
        raise RuntimeError("AI_TIMEOUT은 초 단위의 유한한 양수여야 합니다.") from None
    if not math.isfinite(timeout) or timeout <= 0:
        raise RuntimeError("AI_TIMEOUT은 초 단위의 유한한 양수여야 합니다.")
    return timeout


if __name__ == "__main__":
    try:
        parse_ai_timeout(os.environ.get("AI_TIMEOUT", "30"))
    except RuntimeError as error:
        raise SystemExit(str(error)) from None
