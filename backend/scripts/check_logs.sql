-- ==============================================================================
-- AskMate 대화 기록 검증용 SQL 스크립트 (Chat Logs Verification Query)
--
-- [파일 개요]
-- 본 SQL 스크립트는 개발자 및 운영자가 로컬 SQLite 데이터베이스(askmate.db)에
-- 직접 접근하여 특정 사용자의 대화 기록 저장 상태를 점검하거나,
-- 백엔드 통합 테스트(test_chat_history.py)에서 API 조회 결과와의 데이터 정합성을
-- 검증하기 위해 사용하는 표준 쿼리문입니다.
--
-- [기술적 설명]
-- 1. 파라미터 바인딩:
--    - `:user_id`: 조회 대상 사용자의 고유 정수 ID (users.id)
-- 2. 시간대 처리:
--    - `created_at` 컬럼은 SQLite의 특성상 시간대 오프셋 없이 UTC 기준으로 저장되어 있습니다.
-- 3. 정렬 기준:
--    - `ORDER BY created_at DESC, id DESC`:
--      가장 최근에 생성된 대화가 상단에 위치하도록 내림차순 정렬하며, 동일 시각(마이크로초 일치)에
--      생성된 레코드가 존재할 경우 고유 기본키(id) 역순으로 정렬하여 일관된 순서를 보장합니다.
-- ==============================================================================

SELECT id, user_id, question, answer, created_at
FROM chats
WHERE user_id = :user_id
ORDER BY created_at DESC, id DESC;
