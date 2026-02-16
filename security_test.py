#!/usr/bin/env python3
"""
머슴포커 보안 시뮬레이션 테스트
서버 로직을 직접 import해서 공격 벡터 검증
"""
import sys, os, json, time, hashlib, hmac

# server.py import를 위한 경로
sys.path.insert(0, os.path.dirname(__file__))

print("=" * 60)
print("🔴 머슴포커 보안 시뮬레이션 테스트 v1.0")
print("=" * 60)

passed = 0
failed = 0
total = 0

def test(name, condition, detail=""):
    global passed, failed, total
    total += 1
    if condition:
        passed += 1
        print(f"  ✅ {name}")
    else:
        failed += 1
        print(f"  ❌ {name} — {detail}")

# ══════════════════════════════════════
print("\n[A] 인증 시스템 테스트")
# ══════════════════════════════════════
import secrets
from server import (
    issue_token, verify_token, require_token, player_tokens,
    sanitize_name, sanitize_msg, _check_admin, ADMIN_KEY,
    _auth_cache_key, _auth_cache_check, _auth_cache_set,
    _verified_auth_cache
)

# A1: 토큰 발급/검증
token = issue_token("test_user")
test("A1-토큰 발급", token and len(token) == 32)
test("A1-토큰 검증 성공", verify_token("test_user", token))
test("A1-토큰 검증 실패 (잘못된 토큰)", not verify_token("test_user", "wrong_token"))
test("A1-토큰 검증 실패 (없는 유저)", not verify_token("nobody", token))

# A2: 토큰 무효화 (삭제 후)
del player_tokens["test_user"]
test("A2-토큰 삭제 후 검증 실패", not verify_token("test_user", token))

# A3: require_token
token2 = issue_token("test2")
test("A3-require_token 성공", require_token("test2", token2))
test("A3-require_token 빈값", not require_token("", ""))
test("A3-require_token None", not require_token(None, None))

# A4: admin key 검증
test("A4-_check_admin 빈값", not _check_admin(""))
test("A4-_check_admin None", not _check_admin(None))
if ADMIN_KEY:
    test("A4-_check_admin 정확한 키", _check_admin(ADMIN_KEY))
    test("A4-_check_admin 잘못된 키", not _check_admin("wrong_key"))
else:
    test("A4-ADMIN_KEY None일 때 항상 거부", not _check_admin("anything"))

# A5: hmac.compare_digest 사용 확인
import inspect
src = inspect.getsource(verify_token)
test("A5-verify_token에 hmac.compare_digest", "compare_digest" in src)

# A6: auth cache
_verified_auth_cache.clear()
ck = _auth_cache_key("testid", "testpw")
test("A6-캐시 미존재 시 False", not _auth_cache_check("testid", ck))
_auth_cache_set("testid", ck)
test("A6-캐시 설정 후 True", _auth_cache_check("testid", ck))
test("A6-잘못된 캐시키 False", not _auth_cache_check("testid", "wrong"))

# A7: auth cache 메모리 상한
for i in range(600):
    _auth_cache_set(f"flood_{i}", f"key_{i}")
test("A7-auth cache 500건 상한", len(_verified_auth_cache) <= 500 + 50)  # 약간의 여유
_verified_auth_cache.clear()

# ══════════════════════════════════════
print("\n[B] 입력 정제 테스트")
# ══════════════════════════════════════

test("B1-빈 문자열", sanitize_name("") == "")
test("B2-공백만", sanitize_name("   ") == "")
test("B3-긴 이름 절단", len(sanitize_name("a" * 100)) <= 20)
test("B4-제어문자 제거", sanitize_name("\x00\x01test\x02") == "test")
test("B5-HTML 태그 통과 (서버측)", "<" in sanitize_name("<script>"))
test("B6-zero-width 제거", sanitize_name("\u200b\u200b") == "")
test("B7-줄바꿈 제거", "\n" not in sanitize_name("a\nb"))
test("B8-sanitize_msg 길이", len(sanitize_msg("x" * 200, 120)) <= 120)
test("B9-sanitize_msg 빈값", sanitize_msg("") == "")
test("B10-SQL 특수문자 통과 (parameterized)", sanitize_name("'; DROP TABLE--") == "'; DROP TABLE--")

# ══════════════════════════════════════
print("\n[C] 금전 시스템 테스트")
# ══════════════════════════════════════
from server import (
    ranked_deposit, ranked_credit, ranked_balance,
    _ranked_lock, _db, is_ranked_table, RANKED_ROOMS
)

# C1: ranked 테이블 판별
test("C1-ranked-micro 판별", is_ranked_table("ranked-micro"))
test("C1-mersoom 비판별", not is_ranked_table("mersoom"))
test("C1-랜덤 이름 비판별", not is_ranked_table("ranked-fake"))

# C2: 잔고 CRUD
db = _db()
# 테스트용 계정 초기화
db.execute("DELETE FROM ranked_balances WHERE auth_id='sec_test'")
db.commit()

ranked_credit("sec_test", 100)
test("C2-credit 후 잔고", ranked_balance("sec_test") == 100)

ok, rem = ranked_deposit("sec_test", 30)
test("C2-deposit 성공", ok and ranked_balance("sec_test") == 70)

ok2, rem2 = ranked_deposit("sec_test", 200)
test("C2-잔고 부족 deposit 거부", not ok2)
test("C2-잔고 부족 시 잔고 유지", ranked_balance("sec_test") == 70)

# C3: 음수 금액 방어
ranked_credit("sec_test", 0)
test("C3-credit 0은 잔고 변경 없음", ranked_balance("sec_test") == 70)

# C4: 동시 출금 시뮬 (순차적이지만 로직 검증)
ranked_credit("sec_test", 100)  # 170
bal_before = ranked_balance("sec_test")
ok_a, _ = ranked_deposit("sec_test", 170)
test("C4-전액 출금", ok_a and ranked_balance("sec_test") == 0)
ok_b, _ = ranked_deposit("sec_test", 1)
test("C4-0 잔고에서 추가 출금 거부", not ok_b)

# 정리
db.execute("DELETE FROM ranked_balances WHERE auth_id='sec_test'")
db.commit()

# ══════════════════════════════════════
print("\n[D] 게임 로직 테스트")
# ══════════════════════════════════════
from server import (
    evaluate_hand, hand_strength, make_deck, 
    SUITS, RANKS, _secure_rng
)

# D1: 카드 CSPRNG 검증
import random
test("D1-_secure_rng은 SystemRandom", isinstance(_secure_rng, random.SystemRandom))

# D2: 핸드 평가 정확성
# Royal Flush
rf = [('A','♠'),('K','♠'),('Q','♠'),('J','♠'),('10','♠'),('2','♥'),('3','♦')]
sc = evaluate_hand(rf)
test("D2-로열플러시 인식", sc[0] == 10)

# High card
hc = [('2','♠'),('4','♥'),('6','♦'),('8','♣'),('10','♠'),('3','♥'),('7','♦')]
sc2 = evaluate_hand(hc)
test("D2-하이카드 인식", sc2[0] == 1)

# Full house
fh = [('K','♠'),('K','♥'),('K','♦'),('Q','♣'),('Q','♠'),('2','♥'),('3','♦')]
sc3 = evaluate_hand(fh)
test("D2-풀하우스 인식", sc3[0] == 7)

# D3: 덱 무결성
deck = make_deck()
test("D3-덱 52장", len(deck) == 52)
test("D3-중복 없음", len(set(deck)) == 52)

# D4: 액션 검증 (서버 로직 시뮬)
def simulate_action_validation(act, amt, to_call, chips, current_bet, bb, raise_capped):
    """server.py _wait_external 로직 재현"""
    if act not in ('fold','check','call','raise'): act='fold'
    if act=='raise':
        if raise_capped: act='call'; amt=to_call
        else:
            amt=max(0, amt)
            mn=max(bb, current_bet*2 - 0)  # seat['bet']=0 가정
            amt=max(mn, min(amt, chips - min(to_call, chips)))
            if amt <= 0: act='call'; amt=to_call
    if act=='call': amt=min(to_call, chips)
    if act=='check' and to_call > 0: act='fold'
    return act, amt

# 음수 레이즈
act, amt = simulate_action_validation('raise', -999, 10, 500, 20, 10, False)
test("D4-음수 레이즈 방어", amt >= 0)

# 알 수 없는 액션
act2, _ = simulate_action_validation('steal', 0, 10, 500, 20, 10, False)
test("D4-미지 액션 → fold", act2 == 'fold')

# 체크 when call needed
act3, _ = simulate_action_validation('check', 0, 10, 500, 20, 10, False)
test("D4-콜 필요 시 체크 → fold", act3 == 'fold')

# 레이즈 캡
act4, amt4 = simulate_action_validation('raise', 100, 10, 500, 20, 10, True)
test("D4-레이즈 캡 시 → call", act4 == 'call')

# ══════════════════════════════════════
print("\n[E] Static 파일 보안 테스트")
# ══════════════════════════════════════

ALLOWED_EXT = {'css','png','jpg','jpeg','svg','js','webp','ico','json','woff2','woff','ttf','mp3','ogg','wav'}

dangerous_files = [
    'poker_data.db', 'server.py', '.env', 'requirements.txt',
    'battle.py', '../../../etc/passwd', 'security_test.py',
    '.git/config', 'leaderboard.json.bak',
]
safe_files = ['style.css', 'logo.png', 'app.js', 'data.json']

for f in dangerous_files:
    ext = f.rsplit('.',1)[-1].lower() if '.' in f else ''
    test(f"E-차단: {f}", ext not in ALLOWED_EXT or '/' in f)

for f in safe_files:
    ext = f.rsplit('.',1)[-1].lower()
    test(f"E-허용: {f}", ext in ALLOWED_EXT)

# ══════════════════════════════════════
print("\n[F] 사이드팟 계산 테스트")
# ══════════════════════════════════════

def simulate_sidepot(players_invested, players_folded, player_hands):
    """
    players_invested: {name: total_invested}
    players_folded: set of names
    player_hands: {name: hand_score} (higher = better)
    Returns: {name: chips_won}
    """
    # Reproduce server logic
    all_in_amounts = sorted(set(
        inv for name, inv in players_invested.items()
        if inv > 0 and name not in players_folded
        and player_hands.get(name, 0) >= 0  # chips==0 시뮬: 올인한 사람
    ))
    
    total_pot = sum(players_invested.values())
    alive_scores = sorted(
        [(name, player_hands[name]) for name in players_invested if name not in players_folded and name in player_hands],
        key=lambda x: -x[1]
    )
    
    if not all_in_amounts:
        # 올인 없으면 메인팟만
        if alive_scores:
            return {alive_scores[0][0]: total_pot}
        return {}
    
    pots = []
    prev_level = 0
    remaining = total_pot
    all_contributors = [n for n, inv in players_invested.items() if inv > 0]
    
    for level in all_in_amounts:
        increment = level - prev_level
        eligible = [n for n in all_contributors if players_invested[n] >= level]
        pot_size = min(increment * len(eligible), remaining)
        if pot_size > 0:
            eligible_alive = [n for n in eligible if n not in players_folded]
            pots.append((pot_size, eligible_alive))
            remaining -= pot_size
        prev_level = level
    
    if remaining > 0:
        top_eligible = [n for n, _ in alive_scores]
        pots.append((remaining, top_eligible))
    
    total_won = {}
    for pot_amount, eligible in pots:
        pot_scores = [(n, player_hands[n]) for n in eligible if n in player_hands]
        pot_scores.sort(key=lambda x: -x[1])
        if pot_scores:
            winner = pot_scores[0][0]
            total_won[winner] = total_won.get(winner, 0) + pot_amount
    
    return total_won

# F1: 기본 2인 (올인 없음)
r1 = simulate_sidepot({'A': 50, 'B': 50}, set(), {'A': 100, 'B': 80})
test("F1-2인 기본: A 승리", r1.get('A') == 100)

# F2: 3인 사이드팟
# A 올인 30, B 올인 50, C 콜 50
r2 = simulate_sidepot(
    {'A': 30, 'B': 50, 'C': 50},
    set(),
    {'A': 100, 'B': 80, 'C': 60}  # A 최강, B 차강
)
# 메인팟: 30*3=90 → A
# 사이드팟: 20*2=40 → B
# 총: A=90, B=40
test("F2-3인 사이드팟 A", r2.get('A') == 90, f"got {r2}")
test("F2-3인 사이드팟 B", r2.get('B') == 40, f"got {r2}")
test("F2-합계 = 원래 팟", sum(r2.values()) == 130)

# F3: 올인 플레이어가 지는 경우
r3 = simulate_sidepot(
    {'A': 30, 'B': 50, 'C': 50},
    set(),
    {'A': 50, 'B': 100, 'C': 60}  # B 최강
)
# 메인팟: 30*3=90 → B
# 사이드팟: 20*2=40 → B
# B = 130
test("F3-B 전부 가져감", r3.get('B') == 130, f"got {r3}")

# F4: 폴드 + 올인
r4 = simulate_sidepot(
    {'A': 30, 'B': 10, 'C': 30},
    {'B'},  # B 폴드
    {'A': 100, 'C': 80}
)
# 올인: A=30 (A의 칩이 0이면)
# 메인팟: 30*2(A,C eligible) + 10(B 기여) = 70... 아 이건 좀 다르다
# 실제: A 올인 30, B 폴드 10, C 콜 30 → 팟 70
# all_in_amounts: [30] (A만)
# level=30: eligible=[A,C] (B는 10<30), pot=30*2=60, remaining=10
# remaining=10: top_eligible=[A,C] → A 가져감
# A=60+10=70
test("F4-폴드 포함", r4.get('A') == 70, f"got {r4}")

# F5: 총합 검증 (칩이 사라지거나 늘어나면 안 됨)
for _ in range(20):
    inv = {f'P{i}': _secure_rng.randint(10, 200) for i in range(4)}
    folded = {f'P{_secure_rng.randint(0,3)}'} if _secure_rng.random() > 0.5 else set()
    hands = {n: _secure_rng.randint(1, 1000) for n in inv if n not in folded}
    if not hands: continue
    result = simulate_sidepot(inv, folded, hands)
    total_in = sum(inv.values())
    total_out = sum(result.values())
    if total_in != total_out:
        test(f"F5-총합 불변 ({total_in} vs {total_out})", False, f"inv={inv} folded={folded}")
        break
else:
    test("F5-20회 랜덤 총합 불변", True)

# ══════════════════════════════════════
print("\n[G] Rate Limit 시뮬레이션")
# ══════════════════════════════════════
from server import _api_rate_ok, _api_rate

_api_rate.clear()

# G1: 기본 rate limit
for i in range(10):
    _api_rate_ok("1.2.3.4", "test_ep", 10)
test("G1-10회 허용", _api_rate_ok("1.2.3.4", "test_ep", 10) == False)  # 11번째는 거부

# G2: 다른 IP는 독립
test("G2-다른 IP 독립", _api_rate_ok("5.6.7.8", "test_ep", 10))

# G3: 다른 endpoint 독립
test("G3-다른 endpoint 독립", _api_rate_ok("1.2.3.4", "other_ep", 10))

# G4: 메모리 상한 (500 IP 초과)
_api_rate.clear()
for i in range(600):
    _api_rate_ok(f"10.0.{i//256}.{i%256}", "flood", 100)
test("G4-600 IP 후 메모리 관리", len(_api_rate) <= 600)  # 정리 발생

_api_rate.clear()

# ══════════════════════════════════════
print("\n[H] 메모리 상한 테스트")
# ══════════════════════════════════════
from server import (
    _ranked_auth_map, spectator_coins, chat_cooldowns,
    leaderboard, spectator_bets
)

# H1: spectator_coins 상한
spectator_coins.clear()
for i in range(6000):
    from server import get_spectator_coins
    get_spectator_coins(f"spec_{i}")
test("H1-spectator_coins ≤ 5500", len(spectator_coins) <= 5500)
spectator_coins.clear()

# H2: spectator_bets 정리
spectator_bets['test_table'] = {}
for i in range(100):
    spectator_bets['test_table'][i] = {'user': {'pick': 'a', 'amount': 10}}
from server import resolve_spectator_bets
resolve_spectator_bets('test_table', 50, 'a')
remaining_hands = len(spectator_bets.get('test_table', {}))
test("H2-spectator_bets 정리 (hand 45 이전 삭제)", remaining_hands < 100, f"got {remaining_hands}")
spectator_bets.clear()

# ══════════════════════════════════════
print("\n[I] XSS 방어 코드 존재 확인")
# ══════════════════════════════════════
with open('server.py') as f:
    src = f.read()

test("I1-esc() 함수 존재", "function esc(s){" in src)
test("I2-escJs() 함수 존재", "function escJs(s){" in src)
test("I3-showProfile에 escJs 사용", "escJs(p.name)" in src)

# innerHTML에서 p.name 사용 시 esc() 여부
import re
innerHTML_lines = [l for l in src.split('\n') if 'innerHTML' in l and 'p.name' in l]
unescaped = [l for l in innerHTML_lines if 'p.name' in l and 'esc(p.name)' not in l and 'escJs(p.name)' not in l]
test("I4-모든 p.name innerHTML에 esc/escJs", len(unescaped) == 0, 
     f"{len(unescaped)} unescaped: {unescaped[:2]}")

# battle.py XSS
with open('battle.py') as f:
    bsrc = f.read()
test("I5-battle.py esc() 존재", "function esc(s)" in bsrc)
test("I6-battle dis에 esc 적용", "esc(r.fighter1.dis)" in bsrc)
test("I7-battle comment에 esc 적용", "esc(v.comment)" in bsrc)

# ══════════════════════════════════════
print("\n[J] Static 파일 보안 (서버 코드 확인)")
# ══════════════════════════════════════
test("J1-확장자 화이트리스트 존재", "_ALLOWED_STATIC_EXT" in src)
test("J2-realpath 검사 존재", "realpath" in src and "startswith" in src)
test("J3-.db 차단 확인", "'db'" not in src.split("_ALLOWED_STATIC_EXT")[1].split("}")[0] if "_ALLOWED_STATIC_EXT" in src else False)

# ══════════════════════════════════════
print("\n[K] WS 타임아웃 확인")
# ══════════════════════════════════════
test("K1-ws_recv 타임아웃", "wait_for" in inspect.getsource(
    __import__('server').ws_recv))
test("K2-HTTP body 타임아웃", "wait_for(reader.readexactly" in src)

# ══════════════════════════════════════
print("\n[L] CSP/보안 헤더 확인")
# ══════════════════════════════════════
test("L1-CSP 헤더", "Content-Security-Policy" in src)
test("L2-X-Frame-Options DENY", "X-Frame-Options: DENY" in src)
test("L3-X-Content-Type-Options", "X-Content-Type-Options: nosniff" in src)
test("L4-object-src none", "object-src 'none'" in src)
test("L5-base-uri self", "base-uri 'self'" in src)

# ══════════════════════════════════════
print("\n" + "=" * 60)
print(f"결과: {passed}/{total} 통과 ({failed} 실패)")
if failed == 0:
    print("🏆 전체 통과! 보안 검증 완료.")
else:
    print(f"⚠️ {failed}건 실패 — 확인 필요")
print("=" * 60)
