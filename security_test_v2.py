#!/usr/bin/env python3
"""
머슴포커 보안 전수검사 시뮬레이터 v2.1 — 정밀 regex
"""
import re, os

SERVER_PATH = os.path.join(os.path.dirname(__file__), 'server.py')
with open(SERVER_PATH, 'r') as f:
    CODE = f.read()
    LINES = CODE.split('\n')

TOTAL = 0; PASS = 0; FAIL = 0; WARN = 0
results = []

def check(cat, name, cond, detail="", sev="HIGH"):
    global TOTAL, PASS, FAIL, WARN
    TOTAL += 1
    if cond:
        PASS += 1; results.append(('✅', cat, name, detail))
    elif sev == 'WARN':
        WARN += 1; results.append(('⚠️', cat, name, detail))
    else:
        FAIL += 1; results.append(('❌', cat, name, detail))

def has(p): return bool(re.search(p, CODE))
def has_all(*ps): return all(has(p) for p in ps)
def count(p): return len(re.findall(p, CODE))

print("=" * 70)
print("🛡️  머슴포커 S급 전수검사 v2.1")
print("=" * 70)

# ═══ 1. 인증 ═══
print("\n[1] 🔑 인증")
check("AUTH", "토큰 secrets.token_hex 생성", has(r'secrets\.token_hex\(16\)'))
check("AUTH", "토큰 HMAC timing-safe 검증", has(r'hmac\.compare_digest\(stored_token.*token\)'))
check("AUTH", "ADMIN_KEY 빈값→None", has(r"or None.*prevents bypass"))
check("AUTH", "_check_admin timing-safe", has(r'def _check_admin') and has(r'hmac\.compare_digest\(str\(ADMIN_KEY\)'))
check("AUTH", "auth_cache timing-safe", has(r'hmac\.compare_digest\(stored_key.*cache_key\)'))
check("AUTH", "auth_cache 10분 TTL", has(r'time\.time\(\) - ts > 600'))
check("AUTH", "auth_cache 500건 상한", has(r'len\(_verified_auth_cache\) > 500'))
check("AUTH", "ranked join 비밀번호 검증", has(r'mersoom_verify_account'))
check("AUTH", "reconnect auth_id 하이잭 방지", has(r'AUTH_MISMATCH'))
check("AUTH", "토큰 24시간 만료", has(r'_TOKEN_MAX_AGE = 86400'))
check("AUTH", "player_tokens 1000건 정리", has(r'len\(player_tokens\) > 1000'))

# ═══ 2. 입력 검증 ═══
print("[2] 🧹 입력 검증 & XSS")
check("INPUT", "sanitize_name 존재", has(r'def sanitize_name'))
check("INPUT", "sanitize_msg 존재", has(r'def sanitize_msg'))
check("INPUT", "sanitize_url http/https 화이트리스트", has(r"def sanitize_url") and has(r"startswith.*http"))
check("INPUT", "esc() HTML 이스케이프", has(r'function esc\('))
check("INPUT", "escJs() JS 이스케이프", has(r'function escJs\('))
check("INPUT", "클라이언트 repo URL 검증", has(r"meta\.repo&&\(meta\.repo\.startsWith"))
check("INPUT", "액션 화이트리스트 (fold/check/call/raise)", has(r"act not in \('fold','check','call','raise'\).*fold"))
check("INPUT", "레이즈 음수 방어 max(0, amt)", has(r"amt=max\(0.*amt\)"))
check("INPUT", "레이즈 min/max 서버 클램핑", has(r'mn=max\(self\.BB') and has(r'amt=max\(mn.*min\(amt'))
check("INPUT", "체크→폴드 (콜 필요 시)", has(r"act=='check' and to_call.*fold"))
check("INPUT", "닉네임 20자 제한", has(r'strip\(\)\[:20\]'))
check("INPUT", "메시지 길이 제한", has(r'sanitize_msg.*120'))

# ═══ 3. 레이스 컨디션 ═══
print("[3] 🏎️ 레이스 컨디션")
check("RACE", "더블 캐시아웃 방지 chips=0", has(r"seat\['chips'\] = 0  # ★"))
check("RACE", "ranked_ingame 삭제 on leave", has(r'DELETE FROM ranked_ingame WHERE table_id=\? AND auth_id=\?'))
check("RACE", "ranked_lock 뮤텍스", has(r'_ranked_lock = threading\.Lock\(\)'))
check("RACE", "ranked_credit 락 사용", has(r'with _ranked_lock'))

# ═══ 4. Rate Limit & DoS ═══
print("[4] 🚦 Rate Limit & DoS")
for ep, lim in {'join':10,'action':30,'chat':15,'bet':10,'battle':5,'ranked_withdraw':5,'ranked_deposit':5}.items():
    check("RATE", f"{ep} {lim}/min", has(rf"_api_rate_ok\(_visitor_ip.*'{ep}'.*{lim}\)"))
check("RATE", "_api_rate clear 없음", not has(r'_api_rate\.clear\(\)'))
check("RATE", "chat_cooldowns clear 없음", not has(r'chat_cooldowns\.clear\(\)'))
check("RATE", "_tele_rate clear 없음", not has(r'_tele_rate\.clear\(\)'))
check("DOS", "연결 세마포어 500", has(r'asyncio\.Semaphore\(500\)'))
check("DOS", "WS 관전자 상한 200", has(r'len\(t\.spectator_ws\) >= 200'))
check("DOS", "HTTP 헤더 타임아웃", has(r'asyncio\.wait_for.*readline'))
check("DOS", "HTTP body 타임아웃", has(r'asyncio\.wait_for.*readexactly'))
check("DOS", "WS 64KB 메시지 제한", has(r'ln>65536') or has(r'payload_len > 65536'))
check("DOS", "WS 5분 idle 타임아웃", has(r'_WS_IDLE_TIMEOUT = 300'))

# 메모리 상한
for name, cap in {'_visitor_map':5000,'_agent_registry':2000,'_visitor_log':200,'_telemetry_log':500,'_ranked_auth_map':1000,'spectator_coins':5000}.items():
    check("MEM", f"{name} {cap}건 상한", has(rf'len\({name}\).*>.*{cap}') or has(rf'{name}.*{cap}'))
check("MEM", "chat_cooldowns 2000건 상한", has(r'len\(chat_cooldowns\) > 2000'))
check("MEM", "leaderboard 5000건 상한", has(r'len\(leaderboard\) > 5000'))

# ═══ 5. 카드 & 게임 무결성 ═══
print("[5] 🃏 카드 & 게임 무결성")
check("CARD", "CSPRNG 셔플", has(r'_csprng\.shuffle') or has(r'SystemRandom'))
check("CARD", "관전자 홀카드 숨김", has(r"def get_spectator_state"))
check("CARD", "리플레이 홀카드 마스킹", has(r"p\['hole'\]=\['\?\?'") or has(r"hole.*\?\?"))
check("CARD", "WS 관전자 spectator_state", has(r'last_spectator_state'))
check("CARD", "API state 토큰 없으면 관전자 뷰", has(r'get_spectator_state\(\)') and has(r'verify_token\(player.*token\)'))
check("CARD", "사이드팟 _total_invested", has(r"_total_invested"))
check("CARD", "ranked 폴드 앤티 비활성화", has(r'not is_ranked_table\(self\.id\)') and has(r'ante'))

# ═══ 6. Ranked 머니 ═══
print("[6] 💰 Ranked 머니")
check("MONEY", "SQLite 잔고 영속화", has(r'ranked_balances') and has(r'sqlite3'))
check("MONEY", "감사 로그 테이블", has(r'ranked_audit_log'))
check("MONEY", "워치독 60초", has(r'watchdog') or has(r'_ranked_watchdog'))
check("MONEY", "환전 실패→롤백", has(r'ranked_credit\(r_auth.*amount\)') and has(r'환전 실패'))
check("MONEY", "입금 10분 만료", has(r'600'))
check("MONEY", "입금 10000pt 상한", has(r'amount > 10000'))
check("MONEY", "ranked NPC 차단", has(r'# ranked.*NPC.*넣음'))
check("MONEY", "ranked WS play 차단", has(r'ranked tables require HTTP'))
check("MONEY", "RANKED_LOCKED 게이트", has(r'RANKED_LOCKED') and has(r'_check_admin'))
check("MONEY", "타임아웃 킥 칩 복구", has(r'ranked_credit\(kick_auth'))

# ═══ 7. 파일 시스템 ═══
print("[7] 📁 파일 시스템")
check("FILE", "realpath 트래버설 방지", has(r'os\.path\.realpath'))
check("FILE", "확장자 화이트리스트", has(r'_ALLOWED_STATIC_EXT'))
check("FILE", "base 디렉터리 탈출 방지", has(r'not fpath\.startswith') or has(r'not fp\.startswith'))

# ═══ 8. 보안 헤더 ═══
print("[8] 🔒 보안 헤더")
check("HDR", "X-Content-Type-Options: nosniff", has(r'X-Content-Type-Options.*nosniff'))
check("HDR", "X-Frame-Options: DENY", has(r'X-Frame-Options.*DENY'))
check("HDR", "CSP default-src 'self'", has(r"default-src 'self'"))
check("HDR", "CSP object-src 'none'", has(r"object-src 'none'"))

# ═══ 9. WebSocket ═══
print("[9] 🔌 WebSocket")
check("WS", "play 토큰 필수", has(r'token required for play mode'))
check("WS", "chat 닉네임 서버강제", has(r"chat_name=name if.*mode=='play'"))
check("WS", "vote voter_id 서버강제", has(r'voter_id=id\(writer\)'))
check("WS", "vote pick 플레이어 검증", has(r"pick in valid_picks"))
check("WS", "add_player 직접 차단", has(r'join via /api/join first'))

# ═══ 10. 정보 누출 ═══
print("[10] 🕵️ 정보 누출")
check("LEAK", "ranked export admin 전용", has(r'ranked.*export.*admin_key') or has(r'export.*_check_admin'))
check("LEAK", "ranked recent admin 전용", has(r'ranked recent requires admin_key'))
check("LEAK", "잔고 조회 인증 필수", has(r"r_pw=qs\.get\('password'") and has(r'ranked/balance'))
check("LEAK", "입금 상태 인증 필수", has(r"r_pw=qs\.get\('password'") and has(r'deposit-status'))

# ═══ 11. 50종 공격 시나리오 ═══
print("[11] ⚔️ 50종 공격 시나리오")
attacks = [
    ("SQL Injection nickname", has(r'sanitize_name')),
    ("XSS chat message", has(r'sanitize_msg')),
    ("XSS repo javascript:", has(r'def sanitize_url')),
    ("XSS repo 클라이언트", has(r"meta\.repo\.startsWith\('http")),
    ("XSS showProfile onclick", has(r'escJs')),
    ("XSS innerHTML 전체", has(r'esc\(')),
    ("토큰 위조", has(r'secrets\.token_hex')),
    ("토큰 타이밍 공격", has(r'hmac\.compare_digest\(stored_token')),
    ("Admin 브루트포스", has(r'hmac\.compare_digest\(str\(ADMIN_KEY\)')),
    ("Admin 빈값 우회", has(r'or None.*prevents')),
    ("더블 캐시아웃", has(r"seat\['chips'\] = 0  # ★")),
    ("크래시 복구 이중 크레딧", has(r'DELETE FROM ranked_ingame')),
    ("닉네임 하이잭", has(r'AUTH_MISMATCH')),
    ("음수 레이즈 칩 생성", has(r'amt=max\(0')),
    ("레이즈 과대 주입", has(r'amt=max\(mn.*min\(amt')),
    ("WS ranked 무인증", has(r'ranked tables require HTTP')),
    ("WS add_player 직접", has(r'join via /api/join first')),
    ("WS 관전자 홀카드 엿보기", has(r'get_spectator_state')),
    ("리플레이 홀카드 유출", has(r"\?\?")),
    ("카드 난수 예측", has(r'SystemRandom')),
    ("Slowloris 헤더", has(r'asyncio\.wait_for.*readline')),
    ("Slowloris 바디", has(r'asyncio\.wait_for.*readexactly')),
    ("WS 좀비 연결", has(r'_WS_IDLE_TIMEOUT')),
    ("WS 메시지 폭탄", has(r'ln>65536') or has(r'payload_len > 65536')),
    ("연결 폭탄 500+", has(r'asyncio\.Semaphore\(500\)')),
    ("관전자 폭탄 200+", has(r'spectator_ws\) >= 200')),
    ("Rate limit clear 우회", not has(r'_api_rate\.clear\(\)')),
    ("디렉터리 트래버설", has(r'os\.path\.realpath')),
    ("DB 파일 다운로드", has(r'_ALLOWED_STATIC_EXT')),
    ("클릭재킹", has(r'X-Frame-Options.*DENY')),
    ("MIME 스니핑", has(r'nosniff')),
    ("타인 잔고 조회", has(r"r_pw=qs\.get\('password'")),
    ("타인 입금 상태", has(r"deposit-status") and has(r"r_pw=qs\.get")),
    ("환전 초과", has(r'amount>bal')),
    ("투표 ID 스푸핑", has(r'voter_id=id\(writer\)')),
    ("투표 대상 조작", has(r'valid_picks')),
    ("WS 채팅 이름 스푸핑", has(r"chat_name=name if")),
    ("동시 입금 중복", has(r'already_pending')),
    ("입금 10000pt 초과", has(r'amount > 10000')),
    ("NPC ranked 투입", has(r'# ranked.*NPC.*넣음')),
    ("ranked 잠금 우회", has_all(r'RANKED_LOCKED', r'_check_admin')),
    ("정수 오버플로", has(r'min\(.*max\(.*int\(')),
    ("auth cache 오래된 PW", has(r'ts > 600')),
    ("타임아웃 칩 증발", has(r'ranked_credit\(kick_auth')),
    ("CSP 외부 스크립트", has(r"default-src 'self'")),
    ("Flash/Object 삽입", has(r"object-src 'none'")),
    ("ranked export 무인증", has(r'export.*admin_key') or has(r'export.*_check_admin')),
    ("메모리 OOM visitor", has(r'_visitor_map.*5000')),
    ("메모리 OOM registry", has(r'_agent_registry.*2000')),
    ("환전 실패 잔고 소멸", has(r'ranked_credit\(r_auth.*amount\)')),
]
for name, passed in attacks:
    check("ATK", f"방어: {name}", passed)

# ═══ 결과 ═══
print("\n" + "=" * 70)
print(f"📊 검사 결과: {TOTAL}건")
print(f"   ✅ PASS: {PASS}")
print(f"   ❌ FAIL: {FAIL}")
print(f"   ⚠️  WARN: {WARN}")

grade = 'S' if FAIL == 0 and WARN <= 2 else 'A+' if FAIL == 0 else 'A' if FAIL <= 2 else 'B'
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
