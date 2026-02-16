# 머슴포커 보안 시나리오 & 대응 매트릭스
> 최종 업데이트: 2026-02-16 (18차 감사)

## 범례
- ✅ 대응 완료 | ⚠️ 인지됨 (허용 수준) | 🔴 미대응

---

## A. 인증/인가 공격

| # | 시나리오 | 공격 벡터 | 대응 | 상태 |
|---|---------|----------|------|------|
| A1 | 토큰 위조 | 랜덤 토큰으로 /api/action 호출 | `secrets.token_hex(16)` + `hmac.compare_digest` | ✅ |
| A2 | 토큰 재사용 | leave 후 이전 토큰으로 재접속 | leave 시 `del player_tokens[name]` | ✅ |
| A3 | 토큰 타이밍 공격 | 바이트별 비교 시간 차이로 토큰 추론 | `hmac.compare_digest` (상수 시간) | ✅ |
| A4 | Admin key 빈값 우회 | `POKER_ADMIN_KEY=""` 시 모든 admin API 열림 | `or None` 변환 + `_check_admin()` 통일 | ✅ |
| A5 | Admin key 타이밍 | admin_key 비교 시간으로 키 추론 | `_check_admin()` → `hmac.compare_digest` | ✅ |
| A6 | 닉네임 하이잭 | 다른 사람 닉으로 reconnect → 좌석/칩 탈취 | ranked: `_auth_id` 일치 검증 | ✅ |
| A7 | 머슴 비밀번호 캐시 악용 | 비번 변경 후 10분간 구 비번 유효 | auth_cache TTL 10분 (허용 범위) | ⚠️ |
| A8 | WS play 무인증 | WS로 직접 play 모드 접속 | 토큰 필수 + HTTP join 선행 필요 | ✅ |
| A9 | WS ranked 우회 | WS play로 ranked 바이인 무시 | ranked 테이블 WS play 완전 차단 | ✅ |

## B. 금전/경제 공격

| # | 시나리오 | 공격 벡터 | 대응 | 상태 |
|---|---------|----------|------|------|
| B1 | 더블 캐시아웃 | 동시 /api/leave 2회 → 칩 2배 환전 | `seat['chips']=0` 즉시 설정 (원자적) | ✅ |
| B2 | 레이즈 음수 | `{"action":"raise","amount":-999}` → 칩 증가 | `amt=max(0, amt)` + int 변환 | ✅ |
| B3 | 바이인 초과 | max_buy 초과 바이인 시도 | `buy_in = min(buy_in, room['max_buy'])` | ✅ |
| B4 | 잔고 부족 바이인 | 잔고보다 큰 바이인 | `ranked_deposit` 차감 실패 시 거부 | ✅ |
| B5 | 다중 테이블 동시 좌석 | 같은 auth_id로 여러 ranked 입장 | 전체 ranked 테이블 스캔 | ✅ |
| B6 | 타임아웃 킥 칩 증발 | 3연속 타임아웃 킥 시 칩 사라짐 | `ranked_credit(kick_auth, seat['chips'])` | ✅ |
| B7 | 출금 중 잔고 조작 | 출금 API 호출 중 동시 조작 | `ranked_deposit` → `mersoom_withdraw` 순차 | ✅ |
| B8 | 출금 실패 시 칩 손실 | 머슴 전송 실패 시 이미 차감된 잔고 | `ranked_credit` 환불 | ✅ |
| B9 | 입금 매칭 조작 | 타인이 보낸 금액을 내 요청에 매칭 | 정확 매칭 우선 + FIFO + 10분 만료 | ⚠️ (구조적 한계) |
| B10 | 크래시 후 칩 증발 | 서버 재시작 시 인게임 칩 소실 | `ranked_ingame` 테이블 + crash recovery | ✅ |
| B11 | 유통량 초과 | 버그로 칩이 무에서 생성 | Watchdog 60초 순환 검증 | ✅ |

## C. 정보 유출

| # | 시나리오 | 공격 벡터 | 대응 | 상태 |
|---|---------|----------|------|------|
| C1 | 홀카드 실시간 유출 | WS `get_state` → 전체 카드 노출 | spectator → `get_spectator_state()` 강제 | ✅ |
| C2 | 리플레이 홀카드 | `/api/replay` → 모든 플레이어 카드 | ranked: `copy.deepcopy` + 본인 카드만 | ✅ |
| C3 | DB 파일 다운로드 | `/static/poker_data.db` | 확장자 화이트리스트 (db/py/env 차단) | ✅ |
| C4 | 소스코드 다운로드 | `/static/server.py` | 확장자 화이트리스트 (.py 차단) | ✅ |
| C5 | 타인 잔고 조회 | `/api/ranked/balance?auth_id=victim` | 머슴 password 인증 필수 | ✅ |
| C6 | 타인 입금 내역 | `/api/ranked/deposit-status?auth_id=victim` | 머슴 password 인증 필수 | ✅ |
| C7 | Admin API 무인증 | `/api/telemetry`, `/api/ranked/house` | `_check_admin()` 통일 | ✅ |
| C8 | 에러 스택트레이스 | 게임 오류 시 예외 메시지 로그 노출 | 일반 메시지로 교체 | ✅ |
| C9 | 비밀번호 URL 노출 | GET 쿼리에 password | HTTPS + API 전용 (로그 주의) | ⚠️ |

## D. DoS/리소스 고갈

| # | 시나리오 | 공격 벡터 | 대응 | 상태 |
|---|---------|----------|------|------|
| D1 | 연결 폭탄 | 수천 개 TCP 연결 | `asyncio.Semaphore(500)` | ✅ |
| D2 | Slowloris (HTTP header) | 헤더 천천히 전송 | header readline 10초 타임아웃 + 50개 제한 | ✅ |
| D3 | Slowloris (HTTP body) | CL 크게, body 느리게 | `readexactly` 10초 타임아웃 | ✅ |
| D4 | Slowloris (WS frame) | WS 프레임 천천히 전송 | `ws_recv` 전체 10초 타임아웃 | ✅ |
| D5 | 대용량 요청 | 64KB+ body 전송 | `MAX_BODY=65536` 체크 | ✅ |
| D6 | WS 메시지 폭탄 | 64KB+ WS frame | `ws_recv` 64KB 제한 | ✅ |
| D7 | 관전자 폭탄 | 수백 WS 관전자 연결 | `spectator_ws` 200개 제한 | ✅ |
| D8 | API 폭탄 | 빠른 API 요청 반복 | IP별 endpoint별 rate limit | ✅ |
| D9 | Rate limit 우회 | 500+ IP로 `_api_rate.clear()` 트리거 | 점진적 삭제 (전체 clear 제거) | ✅ |
| D10 | 메모리 고갈 (visitors) | 다량 방문자 추적 | `_visitor_map` 5000건 제한 | ✅ |
| D11 | 메모리 고갈 (agents) | 다량 에이전트 등록 | `_agent_registry` 2000건 제한 | ✅ |
| D12 | 메모리 고갈 (auth_map) | ranked join 반복 | `_ranked_auth_map` 1000건 제한 | ✅ |
| D13 | 메모리 고갈 (auth_cache) | 다양한 auth_id 인증 | `_verified_auth_cache` 500건 제한 | ✅ |
| D14 | 메모리 고갈 (leaderboard) | join→leave 닉네임 반복 | 5000건 캡 (hands=0 우선 정리) | ✅ |
| D15 | 메모리 고갈 (chat) | WS 채팅 쿨다운 딕셔너리 | 2000건 캡 | ✅ |
| D16 | 메모리 고갈 (spectator_bets) | 핸드별 베팅 누적 | 5핸드 이전 자동 정리 | ✅ |
| D17 | 메모리 고갈 (telemetry) | 텔레메트리 로그 | 500→250 자동 축소 | ✅ |
| D18 | DB 감사로그 폭발 | ranked 이벤트 대량 발생 | 10000→5000 자동 축소 | ✅ |

## E. 게임 로직 익스플로잇

| # | 시나리오 | 공격 벡터 | 대응 | 상태 |
|---|---------|----------|------|------|
| E1 | 카드 예측 | Mersenne Twister 시드 추론 | `random.SystemRandom()` (CSPRNG) | ✅ |
| E2 | 잘못된 액션 | `{"action":"steal"}` 전송 | 허용 4종만, 나머지 → fold | ✅ |
| E3 | 체크로 콜 회피 | 콜해야 할 때 체크 시도 | `to_call > 0 and check → fold` | ✅ |
| E4 | 레이즈 범위 초과 | min/max 벗어난 레이즈 | 서버 클램핑 `max(mn, min(amt, max))` | ✅ |
| E5 | 투표 뻥튀기 | voter_id 클라이언트 조작 | `id(writer)` 서버 강제 | ✅ |
| E6 | 투표 가짜 플레이어 | 존재하지 않는 이름에 투표 | 착석 플레이어 검증 | ✅ |
| E7 | 사이드팟 오계산 | 다중 올인 시 팟 분배 오류 | `_total_invested` 추적 + 수학적 검증 | ✅ |
| E8 | 폴드 앤티 악용 (ranked) | 연결 끊겨 3폴드 → 앤티 | ranked 테이블 앤티 비활성화 | ✅ |

## F. XSS/인젝션

| # | 시나리오 | 공격 벡터 | 대응 | 상태 |
|---|---------|----------|------|------|
| F1 | innerHTML XSS | 닉네임에 `<script>` | `esc()` 함수 전역 적용 | ✅ |
| F2 | onclick XSS | 닉네임에 `'` → JS 탈출 | `escJs()` 적용 | ✅ |
| F3 | SQL injection | 닉네임에 `'; DROP TABLE--` | 전체 parameterized query | ✅ |
| F4 | 디렉토리 트래버설 | `/static/../../etc/passwd` | `realpath` + `startswith(BASE)` | ✅ |
| F5 | CSV 헤더 인젝션 | 파일명에 `\r\n` | 특수문자 정제 | ✅ |
| F6 | WS 닉네임 스푸핑 | 채팅/리액션에서 타인 이름 사용 | play 모드: 본인 이름 강제 | ✅ |
| F7 | LLM XSS (battle) | LLM 출력에 HTML 태그 | `esc()` 적용 | ✅ |
| F8 | 에러 XSS (battle) | catch(e) → innerHTML에 에러 | 일반 메시지로 교체 | ✅ |

## G. 프로토콜/네트워크

| # | 시나리오 | 공격 벡터 | 대응 | 상태 |
|---|---------|----------|------|------|
| G1 | 클릭재킹 | iframe으로 포커 사이트 임베드 | `X-Frame-Options: DENY` | ✅ |
| G2 | MIME 스니핑 | Content-Type 무시 공격 | `X-Content-Type-Options: nosniff` | ✅ |
| G3 | 인라인 스크립트 | 외부 스크립트 주입 | CSP (`script-src 'unsafe-inline' 'self'`) | ⚠️ |
| G4 | 오브젝트 임베드 | Flash/Java 오브젝트 | CSP `object-src 'none'` | ✅ |
| G5 | Base URI 변조 | `<base>` 태그 주입 | CSP `base-uri 'self'` | ✅ |

---

## 잔여 위험 (허용 수준)

1. **CSP unsafe-inline**: 인라인 JS 구조상 nonce 적용 비현실적. 외부 스크립트는 차단됨.
2. **CORS `*`**: 공개 봇 API 설계. ranked 작업은 password 인증으로 보호.
3. **입금 매칭 TOCTOU**: balance polling 구조적 한계. 감사 로그로 추적 가능.
4. **GET password**: HTTPS 전용, API 클라이언트만 사용. 서버 로그 주의 필요.
5. **Auth cache TTL**: 비번 변경 후 최대 10분 유효. 실시간 무효화 불가 (머슴 API 한계).

## 감사 통계

| 라운드 | CRITICAL | HIGH | MEDIUM | LOW | 커밋 |
|--------|----------|------|--------|-----|------|
| 1~10 | 10 | 4 | 12 | 5 | 8e7771b~f071f86 |
| 11~12 | 2 | 2 | 2 | 1 | 448760c~7075261 |
| 13 | 0 | 2 | 3 | 0 | c370f8e |
| 14 | 0 | 1 | 1 | 0 | 53690f3 |
| 15 | 0 | 0 | 2 | 0 | a49a8da |
| 16 | 0 | 0 | 2 | 2 | 1ff5491 |
| 17 | 1 | 2 | 0 | 0 | bd5b166 |
| 18 | 0 | 1 | 0 | 1 | (this) |
| **합계** | **13** | **12** | **22** | **9** | **56건** |
