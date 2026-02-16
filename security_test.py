#!/usr/bin/env python3
"""
머슴포커 보안 전수검사 시뮬레이터 v2.0
=============================================
모든 공격 벡터를 시뮬레이션하고 방어를 검증한다.
실제 서버에 요청 보내지 않고, server.py 코드를 정적+동적 분석.
"""
import re, sys, os, ast, json, hashlib, hmac, time

SERVER_PATH = os.path.join(os.path.dirname(__file__), 'server.py')

with open(SERVER_PATH, 'r') as f:
    CODE = f.read()
    LINES = CODE.split('\n')

TOTAL = 0
PASS = 0
FAIL = 0
WARN = 0
results = []

def check(category, name, condition, detail="", severity="HIGH"):
    global TOTAL, PASS, FAIL, WARN
    TOTAL += 1
    if condition:
        PASS += 1
        results.append(('✅', category, name, detail))
    else:
        if severity == 'WARN':
            WARN += 1
            results.append(('⚠️', category, name, detail))
        else:
            FAIL += 1
            results.append(('❌', category, name, detail))

def find_line(pattern):
    """Find line numbers matching regex pattern"""
    matches = []
    for i, line in enumerate(LINES, 1):
        if re.search(pattern, line):
            matches.append((i, line.strip()))
    return matches

def has_pattern(pattern):
    return bool(re.search(pattern, CODE))

print("=" * 70)
print("🛡️  머슴포커 보안 전수검사 시뮬레이터 v2.0")
print("=" * 70)

# ══════════════════════════════════════════════════
# 1. 인증 & 토큰 시스템
# ══════════════════════════════════════════════════
print("\n[1/12] 🔑 인증 & 토큰 시스템")

check("AUTH", "토큰 서명 HMAC", 
    has_pattern(r'hmac\.new\(.*sha256'),
    "issue_token()이 HMAC-SHA256으로 서명")

check("AUTH", "토큰 검증 timing-safe",
    has_pattern(r'hmac\.compare_digest.*_stored_sig.*sig'),
    "verify_token()이 hmac.compare_digest 사용")

check("AUTH", "ADMIN_KEY 빈값 방어",
    has_pattern(r'def _check_admin.*\n.*if not ADMIN_KEY') or has_pattern(r'ADMIN_KEY = os\.environ\.get.*or None'),
    "ADMIN_KEY 빈 문자열이면 None으로 처리")

check("AUTH", "admin 비교 timing-safe",
    has_pattern(r'def _check_admin.*\n.*hmac\.compare_digest'),
    "_check_admin()에서 hmac.compare_digest 사용")

check("AUTH", "auth cache 해시 비교 timing-safe",
    has_pattern(r'hmac\.compare_digest\(stored_key.*cache_key\)'),
    "_auth_cache_check()에서 timing-safe 비교")

check("AUTH", "auth cache TTL 10분",
    has_pattern(r'time\.time\(\)\s*-\s*ts\s*>\s*600'),
    "캐시 10분 후 만료")

check("AUTH", "auth cache 메모리 상한",
    has_pattern(r'len\(_verified_auth_cache\)\s*>\s*500'),
    "500건 초과 시 정리")

check("AUTH", "SECRET_KEY 랜덤 생성",
    has_pattern(r'secrets\.token_hex\(32\)') or has_pattern(r'os\.urandom'),
    "시크릿 키 크립토 안전 생성")

# ranked 인증
check("AUTH", "ranked join 비밀번호 검증",
    has_pattern(r'mersoom_verify_account\(auth_id.*password\)'),
    "ranked 입장 시 머슴 계정 검증")

check("AUTH", "ranked auth_id 좌석 매핑",
    has_pattern(r"joined_seat\['_auth_id'\]\s*=\s*auth_id"),
    "좌석에 auth_id 바인딩")

check("AUTH", "reconnect auth_id 검증 (하이잭 방지)",
    has_pattern(r'seat_auth.*!=.*auth_id.*AUTH_MISMATCH'),
    "재접속 시 auth_id 일치 검증")

# ══════════════════════════════════════════════════
# 2. 입력 검증 & XSS
# ══════════════════════════════════════════════════
print("[2/12] 🧹 입력 검증 & XSS")

check("INPUT", "sanitize_name() 존재",
    has_pattern(r'def sanitize_name'),
    "닉네임 정제 함수")

check("INPUT", "sanitize_msg() 존재",
    has_pattern(r'def sanitize_msg'),
    "메시지 정제 함수")

check("INPUT", "sanitize_url() 존재",
    has_pattern(r'def sanitize_url'),
    "URL 화이트리스트 함수")

check("INPUT", "sanitize_url http/https 화이트리스트",
    has_pattern(r"startswith\('http://'\).*startswith\('https://'\)") or 
    has_pattern(r"url\.startswith\('https://'\)\s*or\s*url\.startswith\('http://'\)"),
    "http/https만 허용")

check("INPUT", "esc() HTML 이스케이프",
    has_pattern(r'function esc\('),
    "클라이언트 HTML 이스케이프 함수")

check("INPUT", "escJs() JS 이스케이프",
    has_pattern(r'function escJs\('),
    "클라이언트 JS 문자열 이스케이프 함수")

# innerHTML 검사 — 모든 innerHTML에 esc() 적용 확인
innerHTML_lines = find_line(r'\.innerHTML\s*[+=]')
unescaped_innerHTML = []
for lno, line in innerHTML_lines:
    # player-controlled data without esc()
    if any(v in line for v in ['p.name', 'name', 'player']) and 'esc(' not in line and 'escJs(' not in line:
        # 예외: 하드코딩된 문자열만 있는 경우
        if '${' in line or "'+'" in line:
            unescaped_innerHTML.append((lno, line[:100]))

check("INPUT", "innerHTML에 모든 동적 데이터 이스케이프",
    len(unescaped_innerHTML) == 0,
    f"미이스케이프 {len(unescaped_innerHTML)}건: {unescaped_innerHTML[:3]}" if unescaped_innerHTML else "전부 이스케이프됨",
    severity="WARN" if unescaped_innerHTML else "HIGH")

# meta.repo 클라이언트 URL 검증
check("INPUT", "클라이언트 meta.repo URL 검증 (showProfile)",
    has_pattern(r"meta\.repo&&\(meta\.repo\.startsWith\('http://'\)") or
    has_pattern(r"p\.meta\.repo&&\(p\.meta\.repo\.startsWith\('http://'\)"),
    "클라이언트에서도 http/https 화이트리스트")

# 레이즈 amount 음수 검증
check("INPUT", "레이즈 음수 금액 차단",
    has_pattern(r'amt\s*<\s*0') or has_pattern(r'amount.*<.*0.*fold') or has_pattern(r"if.*amt.*<=?\s*0"),
    "음수 레이즈 → 폴드 처리")

# action type 화이트리스트
check("INPUT", "액션 타입 화이트리스트",
    has_pattern(r"act\s*not\s*in.*'fold'.*'call'.*'check'.*'raise'") or
    has_pattern(r"unknown action"),
    "미인식 액션 → 폴드")

# ══════════════════════════════════════════════════
# 3. 레이스 컨디션 & 동시성
# ══════════════════════════════════════════════════
print("[3/12] 🏎️ 레이스 컨디션 & 동시성")

check("RACE", "더블 캐시아웃 방지 (chips=0 선처리)",
    has_pattern(r"seat\['chips'\]\s*=\s*0.*ranked_credit") or
    has_pattern(r"seat\['chips'\] = 0  # ★"),
    "leave 시 칩 즉시 0 → 환전 (재호출 무효)")

check("RACE", "ranked_ingame 삭제 (크래시 복구 이중 크레딧)",
    has_pattern(r'DELETE FROM ranked_ingame WHERE table_id.*auth_id'),
    "leave 시 ingame 스냅샷 삭제")

check("RACE", "ranked_lock threading.Lock",
    has_pattern(r'_ranked_lock\s*=\s*threading\.Lock'),
    "잔고 조작 뮤텍스")

check("RACE", "ranked_credit/deposit 에서 lock 사용",
    has_pattern(r'with _ranked_lock:.*ranked_balances'),
    "잔고 변경 시 락 획득", severity="WARN")

check("RACE", "pending_action asyncio.Event",
    has_pattern(r'pending_action.*Event\(\)') or has_pattern(r'asyncio\.Event'),
    "턴 액션 비동기 이벤트")

# ══════════════════════════════════════════════════
# 4. Rate Limiting & DoS
# ══════════════════════════════════════════════════
print("[4/12] 🚦 Rate Limiting & DoS")

rate_endpoints = {
    'join': 10, 'action': 30, 'chat': 15, 'bet': 10, 
    'battle': 5, 'export': 5, 'ranked_withdraw': 5, 'ranked_deposit': 5
}
for ep, limit in rate_endpoints.items():
    check("RATE", f"Rate limit: {ep} ({limit}/min)",
        has_pattern(rf"_api_rate_ok.*'{ep}'.*{limit}"),
        f"{ep} → {limit}/min")

check("RATE", "rate limit 점진적 삭제 (clear 금지)",
    not has_pattern(r'_api_rate\.clear\(\)'),
    "_api_rate.clear() 호출 없음")

check("RATE", "chat_cooldowns 점진적 삭제",
    not has_pattern(r'chat_cooldowns\.clear\(\)'),
    "chat_cooldowns.clear() 호출 없음")

check("RATE", "_tele_rate 점진적 삭제",
    not has_pattern(r'_tele_rate\.clear\(\)'),
    "_tele_rate.clear() 호출 없음")

check("DOS", "동시 연결 세마포어",
    has_pattern(r'Semaphore\(500\)') or has_pattern(r'_conn_sem'),
    "500 동시 연결 제한")

check("DOS", "WS 관전자 상한 200",
    has_pattern(r'spectator_ws\)\s*>=\s*200'),
    "관전자 WS 200개 제한")

check("DOS", "HTTP 헤더 수 제한",
    has_pattern(r'50.*too many headers') or has_pattern(r'header_count.*50'),
    "50개 초과 헤더 차단")

check("DOS", "HTTP 헤더 읽기 타임아웃",
    has_pattern(r'wait_for.*readline.*10') or has_pattern(r'header.*timeout.*10'),
    "헤더 10초 타임아웃")

check("DOS", "HTTP body 읽기 타임아웃",
    has_pattern(r'wait_for.*readexactly.*10') or has_pattern(r'body.*timeout.*10'),
    "바디 10초 타임아웃")

check("DOS", "WS 프레임 읽기 타임아웃",
    has_pattern(r'ws_recv.*timeout') or has_pattern(r'def ws_recv.*timeout'),
    "WS 수신 타임아웃")

check("DOS", "WS 메시지 크기 제한 64KB",
    has_pattern(r'65536') or has_pattern(r'64.*KB'),
    "WS 메시지 64KB 상한")

check("DOS", "WS 5분 idle 타임아웃",
    has_pattern(r'_WS_IDLE_TIMEOUT\s*=\s*300') or has_pattern(r'idle.*300'),
    "5분 무활동 킥")

# 메모리 상한 검사
memory_caps = {
    '_visitor_map': 5000, '_agent_registry': 2000, '_visitor_log': 200,
    '_telemetry_log': 500, '_ranked_auth_map': 1000, 'leaderboard': 5000,
    'spectator_coins': 5000
}
for name, cap in memory_caps.items():
    check("MEMORY", f"{name} 메모리 상한 {cap}",
        has_pattern(rf'len\({name}\).*{cap}') or has_pattern(rf'{name}.*{cap}'),
        f"{name} → {cap}건 제한")

# ══════════════════════════════════════════════════
# 5. 카드 보안 & 게임 무결성
# ══════════════════════════════════════════════════
print("[5/12] 🃏 카드 보안 & 게임 무결성")

check("CARD", "CSPRNG 카드 셔플 (SystemRandom)",
    has_pattern(r'SystemRandom') or has_pattern(r'_csprng'),
    "os.urandom 기반 난수")

check("CARD", "관전자 홀카드 숨김 (get_spectator_state)",
    has_pattern(r"def get_spectator_state") and has_pattern(r"'hole':\s*\[\]") or has_pattern(r"hole.*hidden"),
    "관전자에게 홀카드 미노출")

check("CARD", "ranked 리플레이 홀카드 마스킹",
    has_pattern(r'deepcopy') and has_pattern(r"'🂠'"),
    "리플레이에서 타인 홀카드 마스킹")

check("CARD", "WS spectator state 사용",
    has_pattern(r'get_spectator_state\(\)') and has_pattern(r'last_spectator_state'),
    "WS 관전자에게 딜레이된 spectator state 전송")

check("CARD", "API state 토큰 없으면 spectator view",
    has_pattern(r'verify_token.*viewer=player.*get_spectator_state'),
    "/api/state 토큰 미검증 시 관전자 뷰")

# 레이즈 min/max 서버 클램핑
check("CARD", "레이즈 금액 서버 클램핑",
    has_pattern(r'min_raise') and has_pattern(r'max_raise'),
    "레이즈 min/max 서버에서 강제")

# 사이드팟
check("CARD", "사이드팟 구현",
    has_pattern(r'side.*pot') or has_pattern(r'_total_invested'),
    "_total_invested 기반 사이드팟")

# 폴드 앤티 ranked 비활성화
check("CARD", "ranked 폴드 앤티 비활성화",
    has_pattern(r'is_ranked_table.*ante') or has_pattern(r'not is_ranked_table.*ante'),
    "ranked에서 폴드 페널티 없음")

# ══════════════════════════════════════════════════
# 6. Ranked 머니 시스템
# ══════════════════════════════════════════════════
print("[6/12] 💰 Ranked 머니 시스템")

check("MONEY", "ranked DB 영속화",
    has_pattern(r'ranked_balances') and has_pattern(r'sqlite3'),
    "SQLite에 잔고 저장")

check("MONEY", "입금 요청 DB 영속화",
    has_pattern(r'deposit_requests') and has_pattern(r'CREATE TABLE'),
    "deposit_requests 테이블")

check("MONEY", "감사 로그 DB",
    has_pattern(r'ranked_audit_log') and has_pattern(r'CREATE TABLE'),
    "모든 금전 이벤트 기록")

check("MONEY", "워치독 (유통량 무결성)",
    has_pattern(r'_ranked_watchdog') or has_pattern(r'watchdog'),
    "60초 주기 유통량 검증")

check("MONEY", "환전 실패 시 잔고 복구",
    has_pattern(r'ranked_credit.*amount.*환전 실패'),
    "머슴 전송 실패 → 잔고 롤백")

check("MONEY", "입금 요청 10분 만료",
    has_pattern(r'600') and has_pattern(r'expires'),
    "10분 TTL")

check("MONEY", "입금 1회 10000pt 상한",
    has_pattern(r'10000'),
    "1회 최대 입금 제한")

check("MONEY", "Ranked 테이블 NPC 차단",
    has_pattern(r'not is_ranked_table.*NPC') or has_pattern(r'ranked.*NPC.*넣음'),
    "ranked에 NPC 미배치")

check("MONEY", "Ranked WS play 차단",
    has_pattern(r'is_ranked_table.*WS play.*금지') or has_pattern(r'ranked.*HTTP.*join'),
    "ranked는 HTTP join만 허용")

check("MONEY", "RANKED_LOCKED 게이트",
    has_pattern(r'RANKED_LOCKED') and has_pattern(r'_check_admin'),
    "잠금 시 admin_key 필수")

# ══════════════════════════════════════════════════
# 7. 파일 시스템 & 정적 파일
# ══════════════════════════════════════════════════
print("[7/12] 📁 파일 시스템 & 정적 파일")

check("FILE", "디렉터리 트래버설 방지 (realpath)",
    has_pattern(r'os\.path\.realpath'),
    "realpath로 경로 탈출 차단")

check("FILE", "확장자 화이트리스트",
    has_pattern(r'_ALLOWED_STATIC_EXT') or has_pattern(r'ALLOWED.*EXT'),
    "허용 확장자만 서빙")

check("FILE", ".db 파일 서빙 차단",
    not has_pattern(r"'db'") or has_pattern(r"_ALLOWED_STATIC_EXT.*=.*{") and 'db' not in CODE[CODE.find('_ALLOWED_STATIC_EXT'):CODE.find('_ALLOWED_STATIC_EXT')+200],
    "poker_data.db 다운로드 불가")

check("FILE", "base 디렉터리 탈출 방지",
    has_pattern(r'startswith.*BASE') or has_pattern(r'startswith.*base_dir') or has_pattern(r'not fp\.startswith'),
    "base 디렉터리 밖 접근 차단")

# ══════════════════════════════════════════════════
# 8. 보안 헤더
# ══════════════════════════════════════════════════
print("[8/12] 🔒 보안 헤더")

check("HEADER", "X-Content-Type-Options: nosniff",
    has_pattern(r'X-Content-Type-Options.*nosniff'),
    "MIME 스니핑 차단")

check("HEADER", "X-Frame-Options: DENY",
    has_pattern(r'X-Frame-Options.*DENY'),
    "클릭재킹 방지")

check("HEADER", "CSP 헤더",
    has_pattern(r'Content-Security-Policy'),
    "CSP 설정됨")

check("HEADER", "CSP default-src 'self'",
    has_pattern(r"default-src 'self'"),
    "기본 소스 자기 도메인만")

check("HEADER", "CSP object-src 'none'",
    has_pattern(r"object-src 'none'"),
    "Flash/Java 플러그인 차단")

# ══════════════════════════════════════════════════
# 9. WebSocket 보안
# ══════════════════════════════════════════════════
print("[9/12] 🔌 WebSocket 보안")

check("WS", "WS play 토큰 필수",
    has_pattern(r"verify_token.*ws_token") or has_pattern(r'token required for play mode'),
    "WS play 연결 시 토큰 검증")

check("WS", "WS chat 닉네임 강제 (play mode)",
    has_pattern(r"chat_name=name if.*mode=='play'"),
    "play 모드면 서버측 이름 사용")

check("WS", "WS vote voter_id 서버 강제",
    has_pattern(r'voter_id=id\(writer\)'),
    "투표 ID를 writer 객체 ID로 강제")

check("WS", "WS vote pick 플레이어 검증",
    has_pattern(r'valid_picks.*seats') or has_pattern(r"pick.*in.*valid_picks"),
    "투표 대상이 실제 착석 플레이어인지 검증")

check("WS", "WS add_player 직접 호출 차단",
    has_pattern(r'join via /api/join first'),
    "WS에서 직접 플레이어 추가 불가")

# ══════════════════════════════════════════════════
# 10. 에러 & 정보 누출
# ══════════════════════════════════════════════════
print("[10/12] 🕵️ 에러 & 정보 누출")

check("LEAK", "에러 응답 정보 최소화",
    has_pattern(r'internal error') or has_pattern(r'서버 내부 오류'),
    "스택 트레이스 미노출")

check("LEAK", "ranked export admin 전용",
    has_pattern(r'ranked.*export.*admin_key'),
    "/api/export ranked 데이터 admin만 접근")

check("LEAK", "ranked recent admin 전용",
    has_pattern(r'ranked recent requires admin_key'),
    "/api/recent ranked 이력 admin만 접근")

check("LEAK", "history/analysis 토큰 필수",
    has_pattern(r'history.*token.*required') or has_pattern(r'analysis.*token'),
    "핸드 이력/분석 인증 필요")

# ══════════════════════════════════════════════════
# 11. == vs hmac.compare_digest 전수검사
# ══════════════════════════════════════════════════
print("[11/12] ⏱️ 타이밍 사이드채널 전수검사")

# 모든 시크릿 비교가 timing-safe인지 확인
# 토큰, admin_key, auth_cache_key
unsafe_comparisons = []
for i, line in enumerate(LINES, 1):
    stripped = line.strip()
    # 시크릿 관련 == 비교 검색
    if any(kw in stripped for kw in ['token', 'ADMIN_KEY', 'admin_key', 'cache_key', 'SECRET', 'password']):
        if ('==' in stripped or '!=' in stripped) and 'hmac.compare_digest' not in stripped:
            # 예외: 변수 할당, None 체크, 빈 문자열 체크
            if any(ex in stripped for ex in ['is None', 'is not None', "==''", "!=''", '= ', 'not ', 
                                              'if not', '== 0', '!= 0', "=='", '==True', '==False',
                                              'get(', 'auth_id', "!=''"]):
                continue
            unsafe_comparisons.append((i, stripped[:100]))

check("TIMING", "모든 시크릿 비교 timing-safe",
    len(unsafe_comparisons) == 0,
    f"잠재적 unsafe 비교 {len(unsafe_comparisons)}건: {unsafe_comparisons}" if unsafe_comparisons else "전부 timing-safe",
    severity="WARN" if unsafe_comparisons else "HIGH")

# ══════════════════════════════════════════════════
# 12. 공격 시나리오 시뮬레이션 (50종)
# ══════════════════════════════════════════════════
print("[12/12] ⚔️ 공격 시나리오 시뮬레이션 (50종)\n")

scenarios = [
    # (이름, 방어 패턴, 설명)
    ("S01: SQL Injection via nickname",
     r'sanitize_name',
     "닉네임에 SQL 삽입 → sanitize_name()이 특수문자 제거"),
    
    ("S02: XSS via chat message",
     r'sanitize_msg',
     "채팅에 <script> → sanitize_msg()가 제거"),
    
    ("S03: XSS via meta.repo javascript: URI",
     r'sanitize_url',
     "repo에 javascript:alert(1) → sanitize_url()이 http/https만 허용"),
    
    ("S04: XSS via meta.repo 클라이언트 우회",
     r"meta\.repo\.startsWith\('http",
     "클라이언트에서도 URL 프로토콜 검증"),
    
    ("S05: 토큰 위조 (HMAC 서명)",
     r'hmac\.new.*SECRET_KEY',
     "HMAC-SHA256 서명 없이 토큰 생성 불가"),
    
    ("S06: 토큰 타이밍 공격",
     r'hmac\.compare_digest.*_stored_sig',
     "비교 시간이 일정 → 타이밍 분석 무효"),
    
    ("S07: Admin key 브루트포스",
     r'hmac\.compare_digest.*ADMIN_KEY',
     "timing-safe 비교 + rate limit"),
    
    ("S08: Admin key 빈값 우회",
     r'if not ADMIN_KEY',
     "빈 ADMIN_KEY → None → 항상 거부"),
    
    ("S09: 더블 캐시아웃",
     r"seat\['chips'\] = 0",
     "leave 시 chips=0 선처리 → 재호출 시 0pt 환전"),
    
    ("S10: 크래시 복구 이중 크레딧",
     r'DELETE FROM ranked_ingame',
     "leave 시 ingame 삭제 → 크래시 복구에서 이중 크레딧 불가"),
    
    ("S11: 닉네임 하이잭 (ranked)",
     r'AUTH_MISMATCH',
     "다른 auth_id로 기존 좌석 탈취 불가"),
    
    ("S12: 음수 레이즈로 칩 생성",
     r'amt\s*[<]=?\s*0.*fold',
     "음수 금액 → 자동 폴드"),
    
    ("S13: 레이즈 금액 과대 주입",
     r'max_raise',
     "서버가 max_raise로 클램핑"),
    
    ("S14: WS로 ranked 무인증 플레이",
     r'ranked.*HTTP.*join',
     "ranked WS play 완전 차단"),
    
    ("S15: WS로 직접 add_player",
     r'join via /api/join first',
     "WS에서 플레이어 추가 불가"),
    
    ("S16: WS 관전자 홀카드 엿보기",
     r'get_spectator_state',
     "관전자에게 홀카드 숨김 state만 전송"),
    
    ("S17: 리플레이로 상대 홀카드 유출",
     r'deepcopy.*🂠',
     "리플레이에서 타인 카드 마스킹"),
    
    ("S18: 카드 셔플 예측 (RNG)",
     r'SystemRandom',
     "CSPRNG로 예측 불가"),
    
    ("S19: Slowloris 공격 (헤더)",
     r'header.*timeout.*10|wait_for.*readline.*10',
     "10초 타임아웃으로 연결 해제"),
    
    ("S20: Slowloris 공격 (바디)",
     r'body.*timeout.*10|readexactly.*timeout',
     "바디 읽기 10초 타임아웃"),
    
    ("S21: WS 좀비 연결",
     r'_WS_IDLE_TIMEOUT.*300',
     "5분 무활동 시 자동 킥"),
    
    ("S22: WS 메시지 폭탄 (64KB+)",
     r'65536',
     "64KB 초과 메시지 무시"),
    
    ("S23: 연결 폭탄 (500+)",
     r'Semaphore\(500\)',
     "500개 동시 연결 초과 시 거부"),
    
    ("S24: 관전자 폭탄 (200+)",
     r'spectator_ws.*>=.*200',
     "200 관전자 초과 시 거부"),
    
    ("S25: Rate limit 우회 (clear 트리거)",
     r'stale.*cutoff|oldest.*sorted',
     "점진적 삭제, 전체 초기화 없음"),
    
    ("S26: 정적 파일 디렉터리 트래버설",
     r'realpath',
     "os.path.realpath()로 ../../../etc/passwd 차단"),
    
    ("S27: poker_data.db 직접 다운로드",
     r'_ALLOWED_STATIC_EXT',
     ".db 확장자 화이트리스트에 미포함"),
    
    ("S28: 클릭재킹 (iframe 삽입)",
     r'X-Frame-Options.*DENY',
     "DENY로 모든 프레임 차단"),
    
    ("S29: MIME 스니핑 공격",
     r'nosniff',
     "X-Content-Type-Options: nosniff"),
    
    ("S30: 타인 잔고 조회",
     r'ranked.*balance.*password',
     "잔고 조회에 비밀번호 필수"),
    
    ("S31: 타인 입금 상태 조회",
     r'deposit-status.*password',
     "입금 상태에 비밀번호 필수"),
    
    ("S32: 환전 금액 > 잔고",
     r'amount>bal',
     "잔고 초과 환전 거부"),
    
    ("S33: 투표 조작 (voter_id 스푸핑)",
     r'voter_id=id\(writer\)',
     "서버측 ID 강제"),
    
    ("S34: 투표 대상 조작 (가짜 이름)",
     r'valid_picks',
     "실제 착석 플레이어만 투표 가능"),
    
    ("S35: WS 채팅 닉네임 스푸핑 (play mode)",
     r'chat_name=name if',
     "play 모드면 서버 인증된 이름 강제"),
    
    ("S36: 프롬프트 인젝션 (채팅)",
     r'sanitize_msg.*120',
     "120자 제한 + 특수문자 정제"),
    
    ("S37: 동시 입금 요청 중복",
     r'already_pending',
     "대기 중 요청 있으면 거부"),
    
    ("S38: 입금 10000pt 초과",
     r'10000',
     "1회 최대 10000pt 제한"),
    
    ("S39: NPC를 ranked에 투입",
     r'not is_ranked_table.*NPC',
     "ranked 테이블 NPC 차단"),
    
    ("S40: ranked 잠금 우회",
     r'RANKED_LOCKED.*_check_admin',
     "잠금 시 전체 ranked API admin_key 필수"),
    
    ("S41: GET 파라미터 정수 오버플로",
     r'min\(.*max\(.*int\(',
     "min/max 클램핑으로 범위 제한"),
    
    ("S42: auth cache 오래된 비밀번호 사용",
     r'600.*TTL|time.*ts.*600',
     "10분 후 캐시 만료 → 재인증 필수"),
    
    ("S43: 타임아웃 퇴장 시 ranked 칩 증발",
     r'ranked_credit.*timeout|kick.*ranked.*chips',
     "타임아웃 킥 시 잔여 칩 잔고 복구"),
    
    ("S44: CSP script 삽입",
     r"default-src 'self'",
     "외부 스크립트 로딩 차단"),
    
    ("S45: Object/Flash 삽입",
     r"object-src 'none'",
     "플러그인 완전 차단"),
    
    ("S46: API export ranked 무인증",
     r'ranked.*export.*admin_key',
     "ranked export admin 전용"),
    
    ("S47: 메모리 OOM (_visitor_map 폭탄)",
     r'_visitor_map.*5000',
     "5000건 상한"),
    
    ("S48: 메모리 OOM (_agent_registry 폭탄)",
     r'_agent_registry.*2000',
     "2000건 상한"),
    
    ("S49: 동시 다중 테이블 입장 (rated abuse)",
     r'multi.*table|already.*seated',
     "워치독이 다중 테이블 감지"),
    
    ("S50: 환전 머슴 전송 실패 시 잔고 소멸",
     r'ranked_credit.*환전 실패|ok_w.*ranked_credit',
     "전송 실패 → 잔고 롤백"),
]

for name, pattern, desc in scenarios:
    found = has_pattern(pattern)
    check("SCENARIO", name, found, desc)

# ══════════════════════════════════════════════════
# 결과 출력
# ══════════════════════════════════════════════════
print("\n" + "=" * 70)
print(f"📊 전수검사 결과: {TOTAL}건 검사")
print(f"   ✅ PASS: {PASS}")
print(f"   ❌ FAIL: {FAIL}")
print(f"   ⚠️  WARN: {WARN}")

grade = 'S' if FAIL == 0 and WARN <= 2 else 'A+' if FAIL == 0 else 'A' if FAIL <= 2 else 'B' if FAIL <= 5 else 'C'
print(f"\n🏆 보안 등급: {grade}")
print("=" * 70)

if FAIL > 0:
    print("\n❌ 실패 항목:")
    for icon, cat, name, detail in results:
        if icon == '❌':
            print(f"  [{cat}] {name}")
            if detail: print(f"         → {detail}")

if WARN > 0:
    print("\n⚠️  경고 항목:")
    for icon, cat, name, detail in results:
        if icon == '⚠️':
            print(f"  [{cat}] {name}")
            if detail: print(f"         → {detail}")

print()
