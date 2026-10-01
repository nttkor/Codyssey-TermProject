"""
AskMate 보안 및 비밀번호 암호화 모듈 (Security & Password Hashing)

[파일 개요]
본 모듈은 사용자 비밀번호의 단방향 암호화 해싱(Hashing) 및 일치 여부 검증(Verification)을 담당합니다.
현대적 암호학 표준에서 가장 안전하다고 평가받는 Argon2id 알고리즘을 기본으로 채택하여,
레인보우 테이블(Rainbow Table) 공격과 GPU/ASIC 기반 무차별 대입(Brute-force) 공격으로부터
사용자의 비밀번호를 강력하게 보호합니다.

[주요 기술 설명]
1. Argon2id 알고리즘:
   - Password Hashing Competition (PHC) 우승 알고리즘인 Argon2를 사용합니다.
   - 데이터 종속적 메모리 접근(Argon2d)과 데이터 독립적 메모리 접근(Argon2i)을 결합하여
     부채널 공격(Side-channel attack)과 GPU/하드웨어 가속 공격에 모두 대응합니다.
2. 솔트(Salt) 자동 생성:
   - 해시 함수 호출 시마다 암호학적으로 안전한 의사난수 생성기(CSPRNG)를 통해 고유 솔트를 생성하여
     동일한 비밀번호라도 완전히 다른 해시 문자열이 생성되도록 보장합니다.
3. 타이밍 공격(Timing Attack) 방지:
   - 비밀번호 검증 시 상수 시간(Constant-time) 비교를 수행하여, 글자 일치 길이에 따른
     응답 시간 차이를 이용한 타이밍 부채널 분석을 원천 차단합니다.
"""

from pwdlib import PasswordHash

# pwdlib의 권장 설정(Argon2id 기반)을 적용한 전역 패스워드 해셔 인스턴스
password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """평문(Plaintext) 비밀번호를 Argon2id 단방향 해시 문자열로 변환합니다.

    [기술 설명]
    - 매 호출마다 내부적으로 고유한 무작위 솔트(Salt)를 자동 생성하여 해시 문자열에 결합합니다.
    - 변환된 해시 문자열은 알고리즘 버전, 파라미터(메모리 비용, 시간 비용, 병렬화 정도), 솔트, 해시값이
      표준 인코딩 포맷(`$argon2id$...`)으로 결합된 형태를 갖습니다.

    Args:
        password (str): 사용자가 입력한 평문 비밀번호 원본

    Returns:
        str: 데이터베이스에 안전하게 보관 가능한 암호화된 Argon2id 해시 문자열
    """
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """사용자가 입력한 평문 비밀번호가 저장된 해시와 일치하는지 안전하게 검증합니다.

    [기술 설명]
    - 저장된 해시 문자열에서 알고리즘 설정과 솔트를 추출한 뒤, 입력된 평문 비밀번호를
      동일한 조건으로 연산하여 일치 여부를 판별합니다.
    - 타이밍 부채널 공격을 방어하기 위해 내부적으로 상수 시간 비교(Constant-time comparison)를 사용합니다.

    Args:
        password (str): 로그인 시 사용자가 입력한 평문 비밀번호
        password_hash (str): 데이터베이스(users 테이블)에 저장되어 있는 기존 비밀번호 해시 문자열

    Returns:
        bool: 비밀번호가 일치하면 True, 불일치하거나 해시 형식이 잘못된 경우 False
    """
    return password_hasher.verify(password, password_hash)
