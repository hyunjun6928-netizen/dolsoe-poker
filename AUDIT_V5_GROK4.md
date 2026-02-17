# 전수코드검사 V5 — Grok 4 수동 리뷰
**대상**: server.py 10,860줄 (커밋 af85dfe)
**검사자**: 악몽의돌쇠 (Grok 4)
**일시**: 2026-02-17

## 요약
| 등급 | 건수 | 비고 |
|------|------|------|
| CRITICAL | 0 | — |
| HIGH | 2 | 1건 기존, 1건 신규 |
| MEDIUM | 4 | |
| LOW | 3 | |

## HIGH (2건)

### H-1: Crash Recovery 이중 크레딧 (기존 V4 이슈)
- **위치**: L10841-10849
- **내용**: 서버 크래시 시 `ranked_ingame` 테이블에 남은 칩을 복구하는데, `game_end`(L1916)에서 이미 credit + DELETE를 단일 트랜잭션으로 처리. 하지만 game_end의 credit이 commit 된 직후, DELETE 전에 크래시하면 이론적으로 이중 크레딧 가능.
- **실제 위험**: **극히 낮음**. SQLite WAL 모드에서 `db.execute(UPDATE) + db.execute(DELETE) + db.commit()`은 단일 트랜잭션이므로 commit 전에 크래시하면 둘 다 롤백, commit 후면 둘 다 적용. 이중 크레딧 발생 불가.
- **권장**: 현재 코드로 충분. 추가 방어로 crash_recovery 시 audit_log에 같은 table_id+auth_id의 game_end 기록이 있는지 확인 가능.

### H-2 (신규): deposit 매칭 로직의 TOCTOU 경쟁 조건
- **위치**: L183-235 (`mersoom_check_deposits`)
- **내용**: `_last_mersoom_balance` 읽기 → delta 계산 → pending 매칭 → 잔고 반영. 이 과정이 60초 폴링 루프에서 실행되므로 단일 스레드이긴 하지만, `_ranked_lock` 밖에서 `_last_mersoom_balance` 갱신이 일어남. `mersoom_check_deposits()`가 join 시 `run_in_executor`로도 호출됨(L3167) → 동시 실행 시 같은 delta를 두 번 매칭할 수 있음.
- **실제 위험**: **낮음~중간**. join 시 호출과 폴링 루프 호출이 겹칠 수 있으나, GIL + executor 경유라 실제 동시성은 희박. 그러나 이론적으로 같은 deposit을 두 번 크레딧할 수 있음.
- **권장**: `mersoom_check_deposits()` 전체를 `_ranked_lock` 또는 별도 lock으로 감싸기. 또는 `_last_mersoom_balance` 갱신을 atomic하게 처리.

## MEDIUM (4건)

### M-1: `_ranked_auth_map` 메모리 무한 성장 가능
- **위치**: L88
- **내용**: 1000건 초과 시 정리 로직(L3188)이 있으나, 정리가 join 시에만 실행됨. join 없이 많은 유저가 쌓이면 메모리 증가.
- **권장**: 주기적 정리 (watchdog 루프에서)

### M-2: `spectator_queue` 200건 상한이지만 메모리 크기 제한 없음
- **위치**: L1787, L1804
- **내용**: 각 엔트리가 full JSON state(수 KB). 200건 × 여러 테이블 = 수 MB 가능.
- **실제 위험**: 낮음. 테이블 5개, 각 200건 × 5KB = 5MB 정도.

### M-3: `leaderboard` dict 5000건 캡이 join 시에만 작동
- **위치**: L3275
- **내용**: `save_leaderboard()`에서 2000건 캡, join에서 5000건 캡. 비일관적.
- **권장**: 통일

### M-4: CSS `overflow:hidden` desktop에서 `.px-panel`에 적용
- **위치**: L5147
- **내용**: `.px-panel{overflow:hidden}` — border-radius 렌더링용이지만 동적 콘텐츠가 잘릴 수 있음. 모바일에서 `overflow:visible!important`로 override 했지만 desktop에서도 긴 테이블 리스트가 잘릴 수 있음.
- **권장**: `overflow:hidden` → `overflow:clip` (border-radius만 적용, 콘텐츠 잘림 없음)

## LOW (3건)

### L-1: `_telemetry_log` 무한 성장
- **위치**: 다수 `.append()` 호출
- **내용**: 캡 로직 미확인. 장기 실행 시 메모리 증가.

### L-2: `chat_cooldowns` 정리가 POST /api/chat 시에만 실행
- **위치**: L3514
- **내용**: 채팅 없으면 dict 크기 유지. 실질적 문제 없음 (최대 2000건 캡).

### L-3: NPC `random.random()` 사용 (ranked가 아닌 practice 테이블)
- **위치**: BotAI.decide() L571
- **내용**: Mersenne Twister 사용. practice 테이블이므로 보안 영향 없음.

## 검증 완료 항목 ✅

| 항목 | 상태 | 비고 |
|------|------|------|
| SQL Injection | ✅ | 전체 parameterized query (`?`) |
| XSS (innerHTML) | ✅ | 전부 `esc()` 이스케이프 |
| Path Traversal | ✅ | `realpath()` + `startswith(BASE)` + 확장자 화이트리스트 |
| 인증 (토큰) | ✅ | `hmac.compare_digest` 타이밍-안전 비교 |
| Admin API | ✅ | `_check_admin()` → `hmac.compare_digest` |
| 카드 셔플 | ✅ | `SystemRandom` (CSPRNG) |
| Withdraw Race | ✅ | per-user `asyncio.Lock` + `_withdrawing_users` set |
| 이중 캐시아웃 | ✅ | `_cashed_out` 플래그 + `_withdrawing_users` 차단 |
| Ranked 다중좌석 | ✅ | 모든 ranked 테이블 순회 검증 |
| 잔고 차감 원자성 | ✅ | `WHERE balance>=?` atomic deduction |
| WS disconnect 환불 | ✅ | `_cashed_out` + `_withdrawing_users` 이중 방어 |
| Rate limiting | ✅ | `/api/action`(30/m), `/api/chat`(15/m), `/api/withdraw`(5/m), `/api/deposit`(5/m) |
| Input sanitization | ✅ | `sanitize_name()`, `sanitize_msg()`, `sanitize_url()` |
| 에러 메시지 | ✅ | 내부 구현 미노출 |
| CSP | ⚠️ | `unsafe-inline` (구조적 — 인라인 JS 과다) |
| 동시성 (threading) | ⚠️ | `_ranked_lock`(threading.Lock) + asyncio 혼용. 현재 동작하지만 비관습적. |
| SQLite 단일 연결 | ⚠️ | `check_same_thread=False` + `_ranked_lock` 직렬화. 현재 안전하나 확장성 한계. |

## 등급 판정

| 기준 | 등급 |
|------|------|
| 인디 게임 | **S** |
| 중소 상용 | **A** |
| 대형 상용 | **B+** (CSP, 동시성 모델 개선 필요) |

## 이전 감사 대비 변경점
- V4 대비 새 코드: 모바일 CSS 수정 (보안 무관), ETag 304 폴링, withdraw idempotency, deterministic NPC traits
- ETag: MD5 해시 (보안 해시 불필요 — 캐시 키 용도)
- Idempotency: DB 기반, 24h TTL, 실패 시 키 삭제 — 잘 구현됨
- NPC name hash: `_nameHash` — 보안 무관 (외형 결정용)
