"""
AskMate 날짜 및 시각 유틸리티 모듈 (Datetime Utilities)

[파일 개요]
본 모듈은 UTC와 한국 표준시(KST, UTC+9) 간의 시각 변환 및
표준 ISO 8601 포맷팅 등 시각 처리와 관련된 공통 헬퍼 함수를 제공합니다.
"""

from datetime import UTC, datetime, timedelta, timezone

# 한국 표준시(KST, UTC+9) 타임존 객체
KST = timezone(timedelta(hours=9))


def utc_to_kst(dt: datetime) -> datetime:
    """UTC 기준 datetime 객체를 한국 표준시(KST, UTC+9) datetime 객체로 변환합니다.

    [기술 설명]
    - 시간대 정보가 없는 나이브(naive) 객체인 경우, 먼저 UTC 시간대를 명시적으로 부여한 뒤 KST로 변환합니다.
    - 시간대 정보가 이미 존재하는 경우 astimezone(KST)를 통해 현지 시간대로 안전하게 변환합니다.

    Args:
        dt (datetime): 변환 대상 UTC datetime 객체 (naive 또는 timezone-aware)

    Returns:
        datetime: KST 타임존이 적용된 datetime 객체
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(KST)


def format_iso(dt: datetime) -> str:
    """datetime 객체를 표준 ISO 8601 문자열(예: '2026-10-02T04:10:00Z')로 변환합니다.

    Args:
        dt (datetime): 포맷팅 대상 datetime 객체

    Returns:
        str: ISO 8601 표준 포맷 문자열
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    iso_str = dt.isoformat()
    if iso_str.endswith("+00:00"):
        iso_str = iso_str[:-6] + "Z"
    return iso_str


def get_current_kst_timestamp() -> str:
    """현재 시각을 'YYYY-MM-DD HH:MM:SS KST' 형식의 문자열로 반환합니다.

    Returns:
        str: 포맷팅된 현재 한국 시각 문자열
    """
    return datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S KST")
