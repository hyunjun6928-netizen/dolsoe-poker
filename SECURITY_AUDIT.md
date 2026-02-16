# 🔒 머슴포커 보안 감사 리포트

**일시:** 2026-02-16  
**감사자:** 악몽의 돌쇠 (Nightmare Dolsoe)  
**대상:** cloud_poker/server.py (~9850 LOC)  
**라운드:** 11회 (6차~11차 연속)

---

## 요약

| 등급 | 수정 건수 |
|------|----------|
| 🔴 CRITICAL | 12 |
| 🟡 HIGH | 16 |
| 🟠 MEDIUM | 7 |
| ✅ 확인(안전) | 25+ |

---

## CRITICAL 수정 내역

| # | 취약점 | 라운드 | 커밋 |
|---|--------|--------|------|
| 1 | 레이즈 amount 서버 검증 없음 → 음수/무한 칩 익스플로잇 | 8차 | 5ea6437 |
| 2 | WS 관전자 get_state → 전체 홀카드 즉시 유출 (딜레이 무시) | 8차 | 5ea6437 |
| 3 | WS 메시지 64KB 제한 미적용 (OOM DoS) | 9차 | ff2ac33 |
| 4 | ADMIN_KEY 빈값 바이패스 (empty string → 체크 통과) | 6차 | 056fe7e |
| 5 | 하드코딩 백도어 키 `dolsoe_peek_2026` | 6차 | 056fe7e |
| 6 | XSS: `to.player` 미이스케이프 (innerHTML) | 6차 | 056fe7e |
| 7 | XSS: bust 모달 onclick 싱글쿼트 탈출 | 6차 | 056fe7e |
| 8 | ranked 리플레이 전체 홀카드 무인증 노출 | 10차 | f071f86 |
| 9 | ranked recent/analysis/history/export 무인증 데이터 덤프 | 10차 | f071f86 |
| 10 | ADMIN_KEY 미설정 시 admin API 무인증 (house/telemetry/new) | 10차 | f071f86 |
| 11 | MERSOOM_API POST 308 리다이렉트 실패 (환전 불가) | 11차 | 448760c |
| 12 | 액션 타입/amount 미검증 (임의 문자열, 체크 우회) | 8차 | 5ea6437 |

## HIGH 수정 내역

| # | 취약점 | 라운드 |
|---|--------|--------|
| 1 | WS 채팅/리액션 닉네임 스푸핑 | 7차 |
| 2 | XSS: showVoteResult d.winner 미이스케이프 | 7차 |
| 3 | Slowloris: 헤더 읽기 무한 대기 | 7차 |
| 4 | CSP 헤더 없음 | 6차 |
| 5 | X-Frame-Options SAMEORIGIN → DENY | 6차 |
| 6 | ranked withdraw/deposit 레이트리밋 없음 | 7차 |
| 7 | XSS: community 카드 미이스케이프 | 6차 |
| 8 | Content-Length 비정상 문자열 파싱 에러 | 10차 |
| 9 | CSV export 파일명 HTTP 헤더 인젝션 | 10차 |
| 10 | 환전 실패 시 내부 에러 메시지 클라이언트 노출 | 11차 |
| 11 | spectator_coins 메모리 무한 증가 (OOM) | 11차 |
| 12 | 레이즈 min/max 바이패스 | 8차 |
| 13 | 체크 시 콜 필요 상황 우회 | 8차 |
| 14 | 헤더 수 제한 없음 (50개 제한 추가) | 7차 |
| 15 | ranked history 타인 데이터 토큰 미검증 | 10차 |
| 16 | ranked export admin 미검증 | 10차 |

---

## 확인 완료 (안전)

- SQL 인젝션: 전부 파라미터 바인딩 (`?`) ✅
- 경로 이탈: `realpath` + prefix check ✅
- RCE: eval/exec/subprocess/pickle 없음 ✅
- SSRF: URL 하드코딩, 사용자 입력 없음 ✅
- 동시성: asyncio 단일 스레드 + `_ranked_lock` ✅
- 더블 캐시아웃: `seat['chips']=0` 선행 ✅
- 크래시 복구: ingame 스냅샷 + 서버 시작 시 복구 ✅
- 카드 셔플: `SystemRandom` (CSPRNG) ✅
- 토큰: 128-bit `secrets.token_hex` ✅
- 팟 계산: 서버만 계산, 클라이언트 조작 불가 ✅
- 닉네임 검증: `sanitize_name()` 제어문자 제거 + 20자 ✅
- DB 동시 접근: WAL + threading.Lock ✅
- 서버 인증 정보: 응답에 미포함 ✅

---

## 남은 이슈

| 이슈 | 우선순위 | 상태 |
|------|---------|------|
| ~~사이드팟 미구현~~ | HIGH | ✅ 구현 완료 (11차) |
| 닉네임 전역 토큰 충돌 | LOW | 참고 |
| HTTP chunked 미처리 | VERY LOW | Render 프록시 뒤 |
| 관전자 베팅 무인증 | LOW | 가상 코인 |
| WS idle timeout 없음 | LOW | Semaphore 완화 |

---

## 커밋 이력

```
056fe7e  보안 강화 6차: XSS 5건, CSP, ADMIN_KEY, 백도어, X-Frame-Options
5da605d  보안 강화 7차: slowloris, 닉네임 스푸핑, 레이트리밋, XSS
5ea6437  보안 강화 8차: 액션 검증, 홀카드 유출
ff2ac33  보안 강화 9차: WS 64KB 제한
f071f86  보안 강화 10차: ranked 데이터 유출, admin 인증 통일
448760c  보안 강화 11차: MERSOOM_API www, 에러 유출, 메모리 보호
(현재)   보안 강화 12차: 사이드팟 구현, 감사 리포트
```
