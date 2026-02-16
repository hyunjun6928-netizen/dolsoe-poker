# Security Audit V2 — 2026-02-17

**File:** server.py (10,563줄)  
**Auditor:** Automated security review (2차)  
**Previous Audit:** SECURITY_AUDIT_FULL.md  

---

## Summary
- CRITICAL: 1건
- HIGH: 2건
- MEDIUM: 5건
- LOW: 4건

---

## Findings

### [C-1] Ranked withdraw 레이스 컨디션 — 이중 출금 가능

- **위치**: line ~3590-3610 (`/api/ranked/withdraw`)
- **위험도**: CRITICAL
- **설명**: `_get_withdraw_lock()`이 per-user asyncio.Lock으로 직렬화하지만, `wlock.locked()` 체크 후 `async with wlock:` 진입 사이에 TOCTOU 갭이 있음. 또한 `ranked_deposit()` 내부의 `_ranked_lock`(threading.Lock)은 `run_in_executor`에서 호출되는 `mersoom_withdraw()`와 별개 스레드에서 실행되어, 동일 유저가 아닌 **다른 유저 2명이 동시에 출금**하면 하우스 잔고가 순간적으로 초과 차감될 수 있음 (머슴닷컴 API 호출 실패 시 rollback되지만, 성공-성공 케이스에서 하우스 잔고 < 총 유저 잔고 상태 발생).
- **공격 시나리오**: 공격자가 2개 계정으로 동시에 대량 출금 요청 → 하우스 잔고 고갈 → 다른 유저 출금 불가
- **수정 제안**:

```diff
--- a/server.py
+++ b/server.py
@@ ranked_deposit function
 def ranked_deposit(auth_id, amount):
     """ranked 잔고에서 칩 차감 (게임 입장 시)"""
     with _ranked_lock:
         db = _db()
-        row = db.execute("SELECT balance FROM ranked_balances WHERE auth_id=?", (auth_id,)).fetchone()
-        bal = row[0] if row else 0
-        if bal < amount:
-            return False, bal
-        db.execute("UPDATE ranked_balances SET balance=balance-?, updated_at=strftime('%s','now') WHERE auth_id=?",
-            (amount, auth_id))
+        # 원자적 차감: WHERE balance>=amount 으로 잔고 부족 시 0 rows affected
+        cur = db.execute("UPDATE ranked_balances SET balance=balance-?, updated_at=strftime('%s','now') WHERE auth_id=? AND balance>=?",
+            (amount, auth_id, amount))
         db.commit()
+        if cur.rowcount == 0:
+            row = db.execute("SELECT balance FROM ranked_balances WHERE auth_id=?", (auth_id,)).fetchone()
+            return False, row[0] if row else 0
         new_bal = db.execute("SELECT balance FROM ranked_balances WHERE auth_id=?", (auth_id,)).fetchone()[0]
         return True, new_bal
```

추가로 출금 전체에 글로벌 asyncio.Lock 추가 권장 (동시 다중 유저 출금 시 하우스 잔고 검증):

```python
_global_withdraw_lock = asyncio.Lock()

# withdraw 핸들러에서:
async with _global_withdraw_lock:
    # 하우스 잔고 검증
    house_bal = await check_house_balance()
    if house_bal < amount:
        return error("하우스 잔고 부족")
    # ... 기존 출금 로직
```

---

### [H-1] 관전자 베팅 인증 없음 — 사칭 가능

- **위치**: line ~3418 (`/api/bet`)
- **위험도**: HIGH
- **설명**: `/api/bet` 엔드포인트는 `name` 파라미터만으로 관전자를 식별. 토큰 검증 없음. 아무나 다른 사람의 이름으로 베팅하여 코인을 소진시킬 수 있음.
- **공격 시나리오**: 공격자가 `{"name":"타인이름","pick":"패자","amount":999}` 반복 전송 → 타인 관전 코인 고갈
- **수정 제안**: 관전자도 세션 토큰 발급하거나, `/api/bet`에 토큰 필수화. 현재 관전 코인은 가상이므로 금전 피해는 없지만, UX 방해 가능.

```diff
 elif method=='POST' and route=='/api/bet':
     ...
     d=safe_json(body)
     name=sanitize_name(d.get('name','')); pick=sanitize_name(d.get('pick',''))
+    # 관전자 토큰 검증 (선택적 — 토큰 있으면 검증, 없으면 IP 기반 제한)
+    bet_token = d.get('token','')
+    if bet_token and not verify_token(name, bet_token):
+        await send_json(writer,{'ok':False,'code':'UNAUTHORIZED'},401); return
```

---

### [H-2] CSP `unsafe-inline` — XSS 발견 시 방어 불가

- **위치**: line ~4047 (`send_http` 함수의 CSP 헤더)
- **위험도**: HIGH (위험 완화 불가)
- **설명**: `script-src 'unsafe-inline' 'self'`로 설정되어, 만약 XSS 취약점이 발견되면 임의 스크립트 실행 차단 불가. 현재 모든 JS가 인라인이므로 즉시 수정 불가.
- **수정 제안**: 장기적으로 JS를 외부 파일로 분리 + nonce 기반 CSP. 단기적으로는 현재 XSS 방어 (esc() + sanitize) 유지.

---

### [M-1] `_ranked_lock` (threading.Lock) asyncio 블로킹

- **위치**: line 88
- **위험도**: MEDIUM
- **설명**: `_ranked_lock = threading.Lock()`이 메인 asyncio 이벤트 루프에서 직접 사용됨 (e.g. `_deposit_request_add`, `ranked_balance` 등). SQLite 쿼리가 빠르므로 실질적 블로킹은 짧지만, 디스크 I/O 지연 시 전체 서버가 멈출 수 있음.
- **수정 제안**: 모든 `with _ranked_lock:` + DB 접근을 `run_in_executor`로 이동하거나, asyncio.Lock + aiosqlite 패턴으로 전환.

---

### [M-2] `_visitor_map`에 IP + UA 정보 무한 저장

- **위치**: line ~2810-2830
- **위험도**: MEDIUM
- **설명**: `_visitor_map`은 5000건 상한이 있지만, IP 주소와 User-Agent를 메모리에 영구 보관. Admin API (`/api/_v`)로 조회 가능. GDPR 등 개인정보 관련 이슈 가능.
- **수정 제안**: IP 주소 해시화 또는 24시간 후 자동 삭제. 현재 `_visitor_map` 정리가 last_seen 기준이라 오래된 것이 삭제되긴 하지만, 명시적 TTL 적용 권장.

---

### [M-3] `/api/telemetry` 임의 JSON 저장 — 데이터 오염

- **위치**: line ~4013
- **위험도**: MEDIUM
- **설명**: POST `/api/telemetry`는 4KB 제한 + IP 레이트 리밋이 있지만, 본문 JSON의 키/값 검증이 없음. 악의적으로 `_telemetry_log`에 허위 데이터를 주입하여 alert 시스템을 오작동시킬 수 있음.
- **공격 시나리오**: `{"poll_err": 99999, "poll_ok": 0}` 반복 전송 → 가짜 CRIT 알림 발생
- **수정 제안**: 허용 필드 화이트리스트 적용:

```python
ALLOWED_TELE_FIELDS = {'poll_ok','poll_err','rtt_avg','rtt_p95','hands','overlay_allin','overlay_killcam','sid','ev'}
td = {k:v for k,v in safe_json(body).items() if k in ALLOWED_TELE_FIELDS}
```

---

### [M-4] `spectator_coins` 메모리 정리 로직이 잔고 기준

- **위치**: line ~1062 (`get_spectator_coins`)
- **위험도**: MEDIUM
- **설명**: 5000건 초과 시 코인 잔고가 가장 낮은 2500명을 삭제. 활성 사용자라도 코인이 적으면 삭제됨.
- **수정 제안**: LRU (마지막 접근 시각) 기반으로 변경.

---

### [M-5] 외부 API 에러 응답 클라이언트 노출

- **위치**: line ~275 (`mersoom_withdraw`)
- **위험도**: MEDIUM
- **설명**: `mersoom_withdraw` 실패 시 `str(data)` 반환. 이 값이 `/api/ranked/withdraw` 응답에서는 "머슴닷컴 전송 실패" 메시지로 정제되어 괜찮지만, 서버 로그에 외부 API 응답 원문이 출력됨 (인증 헤더 등 포함 가능성은 낮음).
- **수정 제안**: 로그 출력 시 응답 본문 truncate (200자).

---

### [L-1] `check_same_thread=False` SQLite 멀티스레드

- **위치**: line ~1095
- **위험도**: LOW
- **설명**: `_db_conn`이 `check_same_thread=False`로 멀티스레드 공유. `_ranked_lock`으로 일부 보호되지만, `save_leaderboard`, `save_hand_history` 등은 lock 외부에서 호출 가능. WAL 모드 + NORMAL sync로 실질 위험은 낮음.
- **수정 제안**: 모든 DB 접근을 단일 lock으로 보호하거나, 커넥션 풀 도입.

---

### [L-2] `player_tokens` 만료 정리 타이밍

- **위치**: line ~1243 (`issue_token`)
- **위험도**: LOW
- **설명**: 만료된 토큰은 `issue_token()` 호출 시 1000개 넘어야 정리됨. `verify_token()`에서 개별 만료 확인은 하지만, 메모리에 죽은 토큰이 누적. 실질 영향 미미.

---

### [L-3] `hand_history` DB 무한 증가 (ranked)

- **위치**: line ~2567
- **위험도**: LOW
- **설명**: NPC 테이블은 100핸드마다 1000건 제한하지만, ranked 테이블은 제한 없음.
- **수정 제안**: ranked도 10000건 상한 설정.

---

### [L-4] `leaderboard` dict 무한 증가

- **위치**: line ~3096 (join 시 leaderboard에 추가)
- **위험도**: LOW
- **설명**: `len(leaderboard) > 5000` 시 `hands=0`인 유저 정리하지만, 모든 유저가 hands>0이면 계속 증가.
- **수정 제안**: 오래된 비활성 유저 (최근 N일 게임 없음) 정리 로직 추가.

---

## 검사 완료 영역 (이상 없음)

| 영역 | 상태 | 비고 |
|------|------|------|
| SQL 인젝션 | ✅ | 모든 쿼리 파라미터 바인딩 |
| XSS (서버 측 sanitize) | ✅ | `sanitize_name/msg/url`로 `<>` 제거, URL은 http/https만 |
| XSS (클라이언트 innerHTML) | ✅ | 모든 사용자 데이터에 `esc()` 사용. drawSlime은 canvas API만 사용 (innerHTML 아님). 배너는 하드코딩된 HTML. |
| XSS (meta.repo href) | ✅ | `esc()` + `startsWith('http')` 체크 + 서버에서 `sanitize_url()` |
| 인증 (action/chat/leave) | ✅ | 토큰 필수 (`require_token`) |
| 인증 (admin API) | ✅ | `/api/new`, `/api/_v`, `/api/telemetry GET`, `/api/ranked/house`, `/api/ranked/audit`, `/api/ranked/watchdog`, `/api/ranked/admin-credit`, `/api/ranked/admin-fix-ledger` 모두 `_check_admin()` |
| 인증 (ranked API) | ✅ | `/api/ranked/balance`, `/api/ranked/withdraw`, `/api/ranked/deposit-*` 모두 머슴닷컴 계정 검증 |
| 인증 (ranked join) | ✅ | auth_id + password 검증, 다중좌석 방지, auth_id 불일치 시 닉네임 하이잭 차단 |
| 토큰 생성 | ✅ | `secrets.token_hex(16)` |
| 타이밍 안전 비교 | ✅ | `hmac.compare_digest` (admin key, token) |
| 카드 셔플 | ✅ | `random.SystemRandom()` |
| 홀카드 정보 보호 | ✅ | API 폴링: 본인 토큰 없으면 딜레이 관전자 뷰 (진행 중 hole=None 강제). TV모드는 20초 딜레이. |
| 베팅 금액 검증 | ✅ | `max(0, amt)`, min/max 클램핑, raise 불가→call 전환, check+to_call→fold |
| 칩 음수 방지 | ✅ | `min(to_call, chips)`, `max(0, ...)` |
| Ranked 더블 캐시아웃 방지 | ✅ | `_cashed_out` 플래그 + `chips=0` 선행 (leave + WS disconnect 둘 다 체크) |
| Ranked 다중테이블 방지 | ✅ | 전 ranked 테이블 검색 |
| Ranked 크래시 복구 | ✅ | `ranked_ingame` 테이블 → 서버 시작 시 자동 환불 |
| DoS (body) | ✅ | 64KB POST 제한 |
| DoS (헤더) | ✅ | 50개 헤더 제한 |
| DoS (WS 연결) | ✅ | 500 동시 연결 semaphore + 관전자 200 상한 |
| DoS (WS idle) | ✅ | 5분 idle timeout |
| DoS (WS 메시지) | ✅ | 64KB WS 메시지 제한 |
| 레이트 리밋 | ✅ | 엔드포인트별 분당 제한 (`_api_rate_ok`) |
| 디렉터리 트래버설 | ✅ | `os.path.realpath` + BASE 검증 + 허용 확장자 화이트리스트 |
| ADMIN_KEY 빈 문자열 우회 | ✅ | `'' or None` → None, `_check_admin()`에서 None 시 False 반환 |
| drawSlime XSS | ✅ | Canvas 2D API로 픽셀 그리기만 함. innerHTML/textContent 미사용. 이름은 해시로 색상 결정에만 사용. |
| 로비 배너 | ✅ | 하드코딩된 HTML 문자열, 사용자 입력 없음 |
| `/api/ranked/leaderboard` | ✅ | 공개 API지만 auth_id만 노출 (password 노출 없음) |
| `_auth_cache` 캐시 오염 | ✅ | SHA256 해시 + hmac.compare_digest + 10분 TTL + 500건 상한 |

---

## 이전 감사 대비 변경 사항

| V1 이슈 | 상태 |
|---------|------|
| H-1 (withdraw 레이스) | ⚠️ `_get_withdraw_lock`으로 per-user 직렬화 추가됨. 하지만 원자적 차감 미적용 → C-1로 승격 |
| H-2 (leave+WS 이중정산) | ✅ **수정됨** — `_cashed_out` 플래그 도입 |
| H-3 (CSP unsafe-inline) | ⚠️ 미변경 → H-2로 유지 |
| M-1 (_ranked_lock) | ⚠️ 미변경 → M-1로 유지 |
| M-2 (관전자 베팅 인증) | ⚠️ 미변경 → H-1로 승격 (상세 시나리오 추가) |
| M-3~M-6 | 일부 개선, 일부 유지 |

---

## 결론

V1 대비 가장 큰 개선: **이중 정산(H-2) 수정 완료**, per-user withdraw lock 추가.

남은 핵심 이슈:
1. **C-1**: `ranked_deposit()`의 원자적 차감 미적용 — SQLite `WHERE balance>=?` 패턴으로 즉시 수정 가능
2. **H-1**: 관전자 베팅 사칭 — 가상 코인이라 우선순위 낮지만, 토큰 도입 권장
3. **H-2**: CSP unsafe-inline — 장기 과제 (JS 외부 분리)
