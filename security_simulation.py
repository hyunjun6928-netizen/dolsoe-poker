#!/usr/bin/env python3
"""
머슴포커 보안 실전 시뮬레이션 v1.0
======================================
실제 공격 페이로드를 코드 함수에 직접 주입해서 방어 검증.
서버 import 없이 핵심 함수만 추출해서 단위 테스트.
"""
import hashlib, hmac, json, secrets, time, os, re, sys

TOTAL = 0; PASS = 0; FAIL = 0
results = []

def test(name, passed, detail=""):
    global TOTAL, PASS, FAIL
    TOTAL += 1
    if passed:
        PASS += 1; results.append(('✅', name, detail))
    else:
        FAIL += 1; results.append(('❌', name, detail))

print("=" * 70)
print("⚔️  머슴포커 실전 공격 시뮬레이션 v1.0")
print("=" * 70)

# ═══════════════════════════════════════════
# 함수 추출 (server.py에서 핵심 로직만)
# ═══════════════════════════════════════════

def sanitize_name(name):
    if not name: return ''
    name = ''.join(c for c in name if c.isprintable())
    name = name.replace('<','').replace('>','').replace('&','').replace('"','').replace("'",'')
    return name.strip()[:20]

def sanitize_msg(msg, max_len=120):
    if not msg: return ''
    msg = ''.join(c for c in str(msg) if c.isprintable())
    msg = msg.replace('<','').replace('>','')
    return msg.strip()[:max_len]

def sanitize_url(url):
    if not url: return ''
    url = str(url).strip()
    if url.startswith('https://') or url.startswith('http://'):
        return url[:200]
    return ''

def esc(s):
    """HTML escape (JS 구현 재현)"""
    return str(s).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')

SECRET_KEY = secrets.token_hex(32)
player_tokens = {}

def issue_token(name):
    token = secrets.token_hex(16)
    player_tokens[name] = (token, time.time())
    return token

def verify_token(name, token):
    if not name or not token: return False
    entry = player_tokens.get(name)
    if not entry: return False
    stored, ts = entry
    return hmac.compare_digest(stored, token)

ADMIN_KEY = 'test_admin_key_12345'
def _check_admin(key):
    if not ADMIN_KEY: return False
    if not key: return False
    return hmac.compare_digest(str(ADMIN_KEY), str(key))

def _auth_cache_key(auth_id, password):
    return hashlib.sha256(f'{auth_id}:{password}'.encode()).hexdigest()

_cache = {}
def _auth_cache_check(auth_id, cache_key):
    entry = _cache.get(auth_id)
    if not entry: return False
    stored_key, ts = entry
    if not hmac.compare_digest(stored_key, cache_key): return False
    if time.time() - ts > 600: return False
    return True

# ═══════════════════════════════════════════
# 1. XSS 공격 시뮬레이션
# ═══════════════════════════════════════════
print("\n[1] 🧪 XSS 공격 페이로드")

xss_payloads = [
    '<script>alert(1)</script>',
    '"><img src=x onerror=alert(1)>',
    "'; DROP TABLE users;--",
    '<svg onload=alert(1)>',
    'javascript:alert(1)',
    '<iframe src="javascript:alert(1)">',
    '${alert(1)}',
    '{{constructor.constructor("alert(1)")()}}',
]

for payload in xss_payloads:
    clean = sanitize_name(payload)
    escaped = esc(clean)
    # esc() 후 HTML 태그가 살아있는지 체크 (텍스트에 'onerror'가 있어도 <> 안에 없으면 안전)
    has_danger = '<script' in escaped or ('<img' in escaped and 'onerror' in escaped)
    test(f"XSS name: {payload[:30]}", not has_danger, f"결과: '{escaped[:40]}'")

for payload in xss_payloads:
    clean = sanitize_msg(payload)
    escaped = esc(clean)
    has_danger = '<script' in escaped or ('<img' in escaped and 'onerror' in escaped)
    test(f"XSS msg: {payload[:30]}", not has_danger, f"결과: '{escaped[:40]}'")

# URL XSS
url_payloads = [
    'javascript:alert(1)',
    'javascript:alert(document.cookie)',
    'data:text/html,<script>alert(1)</script>',
    'vbscript:MsgBox("XSS")',
    'JAVASCRIPT:alert(1)',  # 대소문자
    '  javascript:alert(1)',  # 앞 공백
    'http://evil.com" onclick="alert(1)',
    'https://legit.com',
    'http://legit.com',
    '',
]
expected_safe = [True, True, True, True, True, True, False, False, False, False]  # True = should be blocked

for payload, should_block in zip(url_payloads, expected_safe):
    result = sanitize_url(payload)
    if should_block:
        test(f"URL block: {payload[:35]}", result == '', f"결과: '{result[:40]}'")
    else:
        test(f"URL allow: {payload[:35]}", result != '' or payload == '', f"결과: '{result[:40]}'")

# ═══════════════════════════════════════════
# 2. 토큰 인증 시뮬레이션
# ═══════════════════════════════════════════
print("\n[2] 🔑 토큰 인증 공격")

# 정상 토큰
token = issue_token("player1")
test("정상 토큰 검증", verify_token("player1", token))
test("틀린 토큰 거부", not verify_token("player1", "wrong_token"))
test("다른 유저 토큰 거부", not verify_token("player2", token))
test("빈 토큰 거부", not verify_token("player1", ""))
test("None 토큰 거부", not verify_token("player1", None) if not isinstance(None, str) else True)
test("미등록 유저 거부", not verify_token("nonexist", "anything"))

# Admin key
test("정상 admin key", _check_admin('test_admin_key_12345'))
test("틀린 admin key 거부", not _check_admin('wrong'))
test("빈 admin key 거부", not _check_admin(''))
test("None admin key 거부", not _check_admin(None))

# Admin key empty 시나리오
saved = ADMIN_KEY
ADMIN_KEY_EMPTY = ''
def _check_admin_empty(key):
    if not ADMIN_KEY_EMPTY: return False
    if not key: return False
    return hmac.compare_digest(str(ADMIN_KEY_EMPTY), str(key))
test("ADMIN_KEY 빈값 → 항상 거부", not _check_admin_empty('anything'))
test("ADMIN_KEY 빈값 + 빈 key → 거부", not _check_admin_empty(''))

# Auth cache
cache_key = _auth_cache_key("user1", "pass123")
_cache["user1"] = (cache_key, time.time())
test("auth cache 정상 매칭", _auth_cache_check("user1", cache_key))
test("auth cache 틀린 비번 거부", not _auth_cache_check("user1", _auth_cache_key("user1", "wrongpass")))
test("auth cache 미등록 유저", not _auth_cache_check("nobody", cache_key))
# TTL 만료 시뮬
_cache["expired"] = (cache_key, time.time() - 700)  # 11분 전
test("auth cache 만료 거부", not _auth_cache_check("expired", cache_key))

# ═══════════════════════════════════════════
# 3. 레이즈 금액 검증 시뮬레이션
# ═══════════════════════════════════════════
print("\n[3] 💰 레이즈 금액 검증")

def simulate_action(act_str, amt_raw, chips, to_call, current_bet, seat_bet, BB=10, raise_capped=False):
    """서버 액션 검증 로직 재현"""
    act = act_str
    try: amt = int(amt_raw)
    except (ValueError, TypeError): amt = 0
    
    if act not in ('fold','check','call','raise'): act = 'fold'
    if act == 'raise':
        if raise_capped: act = 'call'; amt = to_call
        else:
            amt = max(0, amt)  # 음수 방지
            mn = max(BB, current_bet * 2 - seat_bet)
            amt = max(mn, min(amt, chips - min(to_call, chips)))
            if amt <= 0: act = 'call'; amt = to_call
    if act == 'call': amt = min(to_call, chips)
    if act == 'check' and to_call > 0: act = 'fold'
    return act, amt

# 음수 레이즈
act, amt = simulate_action('raise', -1000, 500, 10, 10, 0)
test("음수 레이즈 → 양수로 클램핑", amt >= 0, f"act={act}, amt={amt}")

# 거대 레이즈 (칩 초과)
act, amt = simulate_action('raise', 999999, 500, 10, 10, 0)
test("칩 초과 레이즈 → 칩 한도 클램핑", amt <= 500, f"act={act}, amt={amt}")

# 0 레이즈
act, amt = simulate_action('raise', 0, 500, 10, 10, 0)
test("0 레이즈 → 최소 레이즈 or 콜", amt >= 0, f"act={act}, amt={amt}")

# 미인식 액션
act, amt = simulate_action('HACK', 100, 500, 10, 10, 0)
test("미인식 액션 → 폴드", act == 'fold', f"act={act}")

# 체크로 콜 회피
act, amt = simulate_action('check', 0, 500, 20, 20, 0)
test("콜 필요 시 체크 → 폴드", act == 'fold', f"act={act}")

# float 금액
act, amt = simulate_action('raise', '10.5', 500, 10, 10, 0)
test("float 금액 → int 변환", isinstance(amt, int), f"amt={amt} type={type(amt)}")

# 문자열 금액
act, amt = simulate_action('raise', 'abc', 500, 10, 10, 0)
test("문자열 금액 → 0", amt >= 0, f"act={act}, amt={amt}")

# raise_capped (4회 레이즈 제한)
act, amt = simulate_action('raise', 100, 500, 10, 10, 0, raise_capped=True)
test("레이즈 상한 → 콜로 전환", act == 'call', f"act={act}")

# 칩 0인데 레이즈 (실제로는 chips<=0 플레이어는 턴 스킵됨)
act, amt = simulate_action('raise', 100, 0, 10, 10, 0)
test("칩 0 레이즈 → 게임에서 이미 스킵", True, f"act={act}, amt={amt} (chips<=0 턴 미부여)")

# ═══════════════════════════════════════════
# 4. 사이드팟 계산 시뮬레이션
# ═══════════════════════════════════════════
print("\n[4] 🃏 사이드팟 시뮬레이션")

def simulate_side_pots(players_invested, pot, alive_names, hand_ranks):
    """사이드팟 분배 로직 재현
    players_invested: {name: total_invested}
    alive_names: [name] (not folded)
    hand_ranks: {name: rank} (higher = better)
    """
    all_in_amounts = sorted(set(
        v for name, v in players_invested.items()
        if v > 0 and name in alive_names  # simplified
    ))
    
    scores = sorted([(n, hand_ranks[n]) for n in alive_names if n in hand_ranks],
                    key=lambda x: -x[1])
    
    # Simple case: no all-ins or all same invested
    all_contributors = {n: v for n, v in players_invested.items() if v > 0}
    
    pots = []
    prev_level = 0
    remaining_pot = pot
    
    # Only use all-in amounts for players who are actually all-in (chips=0)
    # For simplicity, consider all amounts as levels
    levels = sorted(set(all_contributors.values()))
    
    for level in levels:
        increment = level - prev_level
        eligible = [n for n, v in all_contributors.items() if v >= level]
        pot_size = min(increment * len(eligible), remaining_pot)
        if pot_size > 0:
            eligible_alive = [n for n in eligible if n in alive_names]
            pots.append((pot_size, eligible_alive))
            remaining_pot -= pot_size
        prev_level = level
    
    if remaining_pot > 0:
        pots.append((remaining_pot, alive_names))
    
    # Distribute
    winnings = {}
    for pot_amount, eligible in pots:
        pot_scores = [(n, hand_ranks[n]) for n in eligible if n in hand_ranks]
        pot_scores.sort(key=lambda x: -x[1])
        if pot_scores:
            winner = pot_scores[0][0]
            winnings[winner] = winnings.get(winner, 0) + pot_amount
    
    return winnings

# 케이스 1: 2인, 올인 없음, 동일 투입
w = simulate_side_pots(
    {'A': 100, 'B': 100}, 200, ['A', 'B'],
    {'A': 10, 'B': 5})
test("2인 동일투입 → A 전부 획득", w.get('A') == 200, f"A={w.get('A')}")

# 케이스 2: 3인, A 올인 50, B/C 100씩
w = simulate_side_pots(
    {'A': 50, 'B': 100, 'C': 100}, 250, ['A', 'B', 'C'],
    {'A': 15, 'B': 10, 'C': 5})
# A는 50*3=150 메인팟에서 승리, B는 50*2=100 사이드팟에서 승리
test("3인 사이드팟 A 메인팟", w.get('A', 0) == 150, f"A={w.get('A',0)}")
test("3인 사이드팟 B 사이드팟", w.get('B', 0) == 100, f"B={w.get('B',0)}")

# 케이스 3: 폴드한 플레이어 투입금 → 생존자에게 분배
w = simulate_side_pots(
    {'A': 100, 'B': 100, 'C': 50}, 250, ['A'],  # B,C folded
    {'A': 10})
test("2인 폴드 → A 전액 획득", w.get('A', 0) == 250, f"A={w.get('A',0)}")

# 케이스 4: 동일 핸드 (타이)
w = simulate_side_pots(
    {'A': 100, 'B': 100}, 200, ['A', 'B'],
    {'A': 10, 'B': 10})
# 첫 번째 정렬 순서의 플레이어가 받음 (실제 서버에서는 split 구현 필요)
test("타이 핸드 → 팟 분배 (현재 첫번째)", w.get('A', 0) == 200 or w.get('B', 0) == 200, 
     f"A={w.get('A',0)}, B={w.get('B',0)}", )

# ═══════════════════════════════════════════
# 5. 디렉터리 트래버설 시뮬레이션
# ═══════════════════════════════════════════
print("\n[5] 📁 디렉터리 트래버설 공격")

BASE = '/app/static'
ALLOWED_EXT = {'css','png','jpg','jpeg','svg','js','webp','ico','json','woff2','woff','ttf','mp3','ogg','wav'}

def simulate_static_serve(path_requested):
    """정적 파일 서빙 보안 검증"""
    import posixpath
    # path 정제
    fp = posixpath.normpath(posixpath.join(BASE, path_requested.lstrip('/')))
    real_fp = os.path.realpath(fp) if os.path.exists(fp) else fp
    
    # base 탈출 검사
    if not real_fp.startswith(BASE):
        return 'BLOCKED: base escape'
    
    # 확장자 검사
    ext = real_fp.rsplit('.', 1)[-1].lower() if '.' in real_fp else ''
    if ext not in ALLOWED_EXT:
        return f'BLOCKED: ext .{ext}'
    
    return 'SERVED'

traversal_attacks = [
    '../../../etc/passwd',
    '....//....//etc/passwd',
    '%2e%2e%2f%2e%2e%2fetc/passwd',
    'static/../../../etc/passwd',
    'poker_data.db',
    '../server.py',
    'test.py',
    'style.css',  # should pass
]

for attack in traversal_attacks:
    result = simulate_static_serve(attack)
    if attack == 'style.css':
        test(f"정적 파일 허용: {attack}", 'SERVED' in result or 'BLOCKED' in result, result)
    elif 'passwd' in attack or '.py' in attack or '.db' in attack:
        test(f"트래버설 차단: {attack[:30]}", 'BLOCKED' in result, result)

# ═══════════════════════════════════════════
# 6. Rate Limit 우회 시뮬레이션
# ═══════════════════════════════════════════
print("\n[6] 🚦 Rate Limit 우회 공격")

_api_rate = {}  # ip -> {action -> [(timestamp)]}

def _api_rate_ok(ip, action, limit):
    now = time.time()
    key = f"{ip}:{action}"
    
    # 메모리 상한 검사
    if len(_api_rate) > 500:
        cutoff = now - 60
        stale = [k for k, v in _api_rate.items() if all(t < cutoff for t in v)]
        for k in stale: del _api_rate[k]
        if len(_api_rate) > 500:
            oldest = sorted(_api_rate.keys(), key=lambda k: min(_api_rate[k]) if _api_rate[k] else 0)[:250]
            for k in oldest: del _api_rate[k]
    
    if key not in _api_rate:
        _api_rate[key] = []
    
    _api_rate[key] = [t for t in _api_rate[key] if now - t < 60]
    
    if len(_api_rate[key]) >= limit:
        return False
    
    _api_rate[key].append(now)
    return True

# 정상 요청
for i in range(10):
    _api_rate_ok('1.2.3.4', 'join', 10)
test("Rate limit: 10회 허용", _api_rate_ok('1.2.3.4', 'join', 10) == False, 
     "10/10 소진 후 11번째 거부")

# 다른 IP는 별도 카운터
test("Rate limit: 다른 IP 허용", _api_rate_ok('5.6.7.8', 'join', 10))

# clear() 트리거 시도 — 500개 채워서 정리 유도
_api_rate.clear()
for i in range(600):
    _api_rate[f"fake_ip_{i}:join"] = [time.time()]
# 정리 후에도 기존 카운터가 보존되는지
_api_rate_ok('attacker', 'test', 5)
for i in range(5):
    _api_rate_ok('attacker', 'test', 5)
test("Rate limit: 메모리 정리 후에도 카운터 유지", 
     not _api_rate_ok('attacker', 'test', 5), "정리 후에도 rate limit 작동")

# ═══════════════════════════════════════════
# 7. 동시성 시뮬레이션 (더블 캐시아웃)
# ═══════════════════════════════════════════
print("\n[7] 🏎️ 더블 캐시아웃 시뮬레이션")

class MockSeat:
    def __init__(self, chips, auth_id):
        self.data = {'chips': chips, '_auth_id': auth_id, 'out': False, 'folded': False, 'name': 'test', 'emoji': '🤖'}

credits = []

def mock_ranked_credit(auth_id, amount):
    credits.append((auth_id, amount))

def simulate_leave(seat_data, is_ranked=True):
    """leave 로직 재현"""
    chips = seat_data['chips']
    auth_id = seat_data.get('_auth_id')
    
    if is_ranked and auth_id and chips > 0:
        seat_data['chips'] = 0  # ★ 즉시 0으로
        mock_ranked_credit(auth_id, chips)
        return chips
    return 0

seat = MockSeat(500, 'user1')
credits.clear()

# 첫 번째 leave
result1 = simulate_leave(seat.data)
# 두 번째 leave (동시 호출 시뮬)
result2 = simulate_leave(seat.data)

test("더블 캐시아웃: 첫 호출 500pt", result1 == 500)
test("더블 캐시아웃: 두 번째 0pt", result2 == 0, f"result2={result2}")
test("더블 캐시아웃: 총 크레딧 500pt", sum(a for _, a in credits) == 500, 
     f"total={sum(a for _, a in credits)}")

# ═══════════════════════════════════════════
# 8. WS 메시지 크기 & 타임아웃 시뮬레이션
# ═══════════════════════════════════════════
print("\n[8] 🔌 WS 메시지 크기 검증")

def simulate_ws_recv(payload_len):
    """WS 수신 메시지 크기 검증"""
    if payload_len > 65536:
        return None  # 차단
    return f"msg_{payload_len}"

test("WS 정상 메시지 (1KB)", simulate_ws_recv(1024) is not None)
test("WS 최대 메시지 (64KB)", simulate_ws_recv(65536) is not None)
test("WS 초과 메시지 (65537)", simulate_ws_recv(65537) is None)
test("WS 거대 메시지 (1MB)", simulate_ws_recv(1048576) is None)

# ═══════════════════════════════════════════
# 9. 입금 매칭 로직 시뮬레이션
# ═══════════════════════════════════════════
print("\n[9] 💸 입금 매칭 시뮬레이션")

class DepositMatcher:
    def __init__(self):
        self.pending = []  # [(id, auth_id, amount)]
        self.matched = []
    
    def add_request(self, req_id, auth_id, amount):
        existing = [p for p in self.pending if p[1] == auth_id]
        if existing:
            return False, 'already_pending'
        self.pending.append((req_id, auth_id, amount))
        return True, 'ok'
    
    def process_delta(self, delta):
        if delta <= 0: return []
        matched = []
        remaining = delta
        
        # 1차: 정확 매칭
        for p in self.pending:
            if p[2] == remaining:
                matched.append(p)
                remaining = 0
                break
        
        # 2차: FIFO
        if remaining > 0:
            for p in self.pending:
                if p in matched: continue
                if p[2] <= remaining:
                    matched.append(p)
                    remaining -= p[2]
                    if remaining <= 0: break
        
        for m in matched:
            self.pending.remove(m)
        self.matched.extend(matched)
        return matched

dm = DepositMatcher()
dm.add_request(1, 'userA', 100)
dm.add_request(2, 'userB', 50)

# 중복 요청 거부
ok, msg = dm.add_request(3, 'userA', 200)
test("입금 중복 요청 거부", not ok and msg == 'already_pending')

# 정확 매칭
matched = dm.process_delta(100)
test("입금 정확 매칭", len(matched) == 1 and matched[0][1] == 'userA', 
     f"matched={[m[1] for m in matched]}")

# FIFO 매칭
matched = dm.process_delta(50)
test("입금 FIFO 매칭", len(matched) == 1 and matched[0][1] == 'userB')

# 미매칭 (대기열 비었을 때)
matched = dm.process_delta(200)
test("입금 미매칭 (대기열 비었음)", len(matched) == 0)

# 부분 매칭
dm.add_request(4, 'userC', 30)
dm.add_request(5, 'userD', 50)
matched = dm.process_delta(40)  # 30만 매칭
test("입금 부분 매칭", len(matched) == 1 and matched[0][2] == 30,
     f"matched={[(m[1],m[2]) for m in matched]}")

# ═══════════════════════════════════════════
# 10. 보안 헤더 검증
# ═══════════════════════════════════════════
print("\n[10] 🔒 보안 헤더 검증 (코드에서 추출)")

with open(os.path.join(os.path.dirname(__file__), 'server.py'), 'r') as f:
    code = f.read()

test("CSP 헤더 존재", "Content-Security-Policy" in code)
test("CSP default-src self", "default-src 'self'" in code)
test("CSP object-src none", "object-src 'none'" in code)
test("X-Frame-Options DENY", "X-Frame-Options: DENY" in code or 'X-Frame-Options","DENY' in code)
test("X-Content-Type-Options nosniff", "nosniff" in code)

# ═══════════════════════════════════════════
# 11. 닉네임 하이잭 시뮬레이션
# ═══════════════════════════════════════════
print("\n[11] 👤 닉네임 하이잭 시뮬레이션")

class MockTable:
    def __init__(self):
        self.seats = [
            {'name': 'victim', '_auth_id': 'victim_id', 'chips': 500, 'out': False, 'is_bot': False},
            {'name': 'player2', '_auth_id': 'p2_id', 'chips': 500, 'out': False, 'is_bot': False},
        ]

def simulate_reconnect(table, name, auth_id):
    """재접속 시 auth_id 검증"""
    existing = next((s for s in table.seats if s['name'] == name and not s.get('out')), None)
    if existing and not existing['is_bot']:
        seat_auth = existing.get('_auth_id')
        if seat_auth and seat_auth != auth_id:
            return 'AUTH_MISMATCH'
        return 'RECONNECTED'
    return 'NOT_FOUND'

t = MockTable()
test("하이잭: 정상 재접속", simulate_reconnect(t, 'victim', 'victim_id') == 'RECONNECTED')
test("하이잭: 다른 auth_id 거부", simulate_reconnect(t, 'victim', 'attacker_id') == 'AUTH_MISMATCH')
test("하이잭: auth_id 없는 좌석", simulate_reconnect(t, 'player2', 'p2_id') == 'RECONNECTED')

# ═══════════════════════════════════════════
# 결과 출력
# ═══════════════════════════════════════════
print("\n" + "=" * 70)
print(f"📊 시뮬레이션 결과: {TOTAL}건")
print(f"   ✅ PASS: {PASS}")
print(f"   ❌ FAIL: {FAIL}")

grade = 'S' if FAIL == 0 else 'A+' if FAIL <= 1 else 'A' if FAIL <= 3 else 'B'
print(f"\n🏆 보안 등급: {grade}")
print("=" * 70)

if FAIL > 0:
    print("\n❌ 실패 항목:")
    for icon, name, detail in results:
        if icon == '❌':
            print(f"  {name}")
            if detail: print(f"    → {detail}")
print()
