# 머슴포커 server.py 전수 보안 감사

**Date:** 2026-02-17  
**File:** server.py (11,218줄)  
**Auditor:** Automated security review  

---

## 요약

전체 11,218줄을 전수 검사한 결과, **기존 보안 대책이 전반적으로 양호**함을 확인.
SQL 인젝션은 모두 파라미터 바인딩 사용, XSS는 `esc()` + `sanitize_name/msg`로 방어됨.
아래는 발견된 추가 이슈들.

---

## CRITICAL (0건)

없음.

---

## HIGH (3건)

### H-1. Ranked withdraw 레이스 컨디션 — 잔고 이중 차감 (L4130-4150)
**설명:** `/api/ranked/withdraw` 에서 `ranked_deposit()` (잔고 차감) 후 `mersoom_withdraw()` (외부 전송) 실패 시 `ranked_credit()`으로 환불하지만, 동시 요청 2건이 거의 동시에 `ranked_deposit()`을 호출하면 잔고 검증을 둘 다 통과할 수 있음. `ranked_deposit()`은 `_ranked_lock` (threading.Lock)으로 보호되지만, asyncio `run_in_executor`에서 호출되므로 두 asyncio task가 각각 다른 스레드에서 동시 실행 가능.  
**심각도:** HIGH  
**수정 제안:** asyncio.Lock을 사용해 withdraw 전체 과정을 직렬화하거나, SQLite의 `balance=balance-?` + `WHERE balance>=?` 패턴으로 원자적 차감.

### H-2. Ranked leave + WS disconnect 이중 정산 (L3616, L4425)
**설명:** `/api/leave`에서 `seat['chips']=0` 후 `ranked_credit()` 하지만, WS disconnect handler(L4425)에서도 동일 seat를 다시 정산. HTTP leave 요청과 WS 끊김이 거의 동시에 발생하면 이중 크레딧 가능.  
**심각도:** HIGH  
**수정 제안:** leave 시 `seat['_cashed_out']=True` 플래그 설정, WS disconnect에서 이 플래그 체크. ← **수정 완료**

### H-3. CSP unsafe-inline (L4319)
**설명:** `Content-Security-Policy`에 `script-src 'unsafe-inline'`이 있어 XSS 발견 시 스크립트 실행 차단 불가. 현재 모든 JS가 인라인이므로 즉시 수정 어려움.  
**심각도:** HIGH (위험 완화 불가)  
**수정 제안:** 장기적으로 JS를 외부 파일로 분리 + nonce 기반 CSP 적용.

---

## MEDIUM (6건)

### M-1. _ranked_lock은 threading.Lock인데 asyncio에서 혼용 (L88)
**설명:** `_ranked_lock = threading.Lock()`은 asyncio 이벤트 루프를 블로킹함. `run_in_executor`에서 호출되는 곳은 괜찮지만, 메인 asyncio 핸들러에서 직접 `with _ranked_lock:` 사용 시 이벤트 루프 블로킹.  
**수정 제안:** asyncio.Lock + run_in_executor 패턴 정리, 또는 모든 DB 접근을 executor로 이동.

### M-2. 관전자 베팅 인증 없음 (L4062-4073)
**설명:** `/api/bet` 엔드포인트는 토큰 없이 아무 이름으로 베팅 가능. `name`에 다른 사람 이름 사용 가능.  
**심각도:** MEDIUM (가상 코인이라 금전 피해 없음)  
**수정 제안:** 관전자도 세션 토큰 발급 고려.

### M-3. 에러 메시지에 내부 정보 누출 가능성 (L1679, 여러 곳)
**설명:** `except Exception as e: print(f"... {e}")` 패턴이 서버 로그에만 출력되므로 직접 유출은 없으나, `mersoom_withdraw()` 실패 시 `str(data)` 반환값이 외부 API 응답 원문 포함 가능.  
**수정 제안:** 외부 API 에러 응답을 사용자에게 직접 전달하지 않도록 정제.

### M-4. /api/_v 방문자 통계 — security by obscurity (L4095)
**설명:** admin_key로 보호되지만, URL 패턴이 단순하고 IP/UA 정보를 반환. 브루트포스 시 정보 유출.  
**심각도:** MEDIUM  
**수정 제안:** 레이트 리밋 + admin_key 실패 시 지연(backoff) 추가.

### M-5. Telemetry beacon 데이터 검증 없음 (L4184-4195)
**설명:** `/api/telemetry` POST는 임의 JSON을 `_telemetry_log`에 저장. 악의적 대용량 JSON 키/값 가능 (body 4KB 제한은 있음).  
**심각도:** MEDIUM  
**수정 제안:** 허용 필드 화이트리스트 적용.

### M-6. spectator_coins 메모리 무한 증가 가능 (L1060)
**설명:** `get_spectator_coins()`에서 5000건 초과 시 정리하지만, 정리 기준이 코인 잔고(값 기준)라 활성 사용자가 삭제될 수 있음.  
**심각도:** MEDIUM  
**수정 제안:** LRU (최근 사용 시각) 기반 정리로 변경.

---

## LOW (5건)

### L-1. _db_conn은 check_same_thread=False (L1087)
**설명:** SQLite 연결이 멀티스레드에서 공유됨. `_ranked_lock`으로 일부 보호되지만 모든 접근이 보호되지는 않음 (예: `save_leaderboard`, `save_hand_history`).  
**수정 제안:** DB 접근 전체를 단일 executor 또는 lock으로 보호.

### L-2. Kart game — NPC 이름 충돌 (L2905)
**설명:** 외부 참가자가 NPC와 같은 이름으로 참가 가능. 이름 중복 방지 없음.  
**심각도:** LOW  

### L-3. WS reaction에서 name 길이 제한만 있고 sanitize 없음 (L4380)
**설명:** `data.get('name','')[:10]`은 이미 sanitize 없이 JSON으로 브로드캐스트됨. 다만 클라이언트에서 `esc()` 처리.  
**심각도:** LOW (서버→클라이언트 JSON이므로 직접 XSS 아님)  

### L-4. player_tokens 만료 정리 타이밍 (L1203)
**설명:** 만료된 토큰은 `verify_token()` 호출 시에만 삭제됨. 1000개 넘어야 대량 정리. 메모리 누수는 미미.  
**심각도:** LOW  

### L-5. hand_history 무한 증가 (DB) (L2567)
**설명:** 100핸드마다 NPC 테이블은 1000건 제한하지만, ranked 테이블은 제한 없음.  
**수정 제안:** ranked도 10000건 등 상한 설정.

---

## 검사 완료 영역 (이상 없음)

| 영역 | 상태 |
|------|------|
| SQL 인젝션 | ✅ 모든 쿼리 파라미터 바인딩 사용 |
| XSS (서버 측) | ✅ `sanitize_name/msg`로 `<>` 제거 |
| XSS (클라이언트) | ✅ 모든 innerHTML에서 `esc()` 사용 |
| 인증 | ✅ `/api/action`, `/api/chat`, `/api/leave` 토큰 필수 |
| 카드 셔플 | ✅ `SystemRandom` 사용 |
| 정보 유출 (홀카드) | ✅ 딜레이+토큰 기반 뷰어 필터링 |
| WS 메시지 크기 | ✅ 64KB 제한 |
| WS 연결 수 | ✅ 500 동시 연결 + 관전자 200 상한 |
| WS idle timeout | ✅ 5분 |
| DoS (body) | ✅ 64KB POST 제한 |
| DoS (헤더) | ✅ 50개 헤더 제한 |
| 디렉터리 트래버설 | ✅ `os.path.realpath` + BASE 검증 |
| 칩 음수 방지 | ✅ `max(0, amt)`, 서버 권위 액션 검증 |
| Ranked 더블캐시아웃 | ✅ `chips=0` 선행 후 credit |
| Ranked 다중테이블 | ✅ 전 ranked 테이블 검색 |
| Ranked 크래시복구 | ✅ `ranked_ingame` 테이블 |
| 레이트 리밋 | ✅ 엔드포인트별 분당 제한 |
| 타이밍 안전 비교 | ✅ `hmac.compare_digest` |
| 토큰 생성 | ✅ `secrets.token_hex(16)` |
| 오목 코드 | ❌ 없음 (server.py에 Gomoku 클래스 없음) |
