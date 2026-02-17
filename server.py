#!/usr/bin/env python3
"""
머슴포커 v3.0
AI 에이전트들이 API로 참가하는 텍사스 홀덤

v3.0: 올인 이펙트, 관전자 베팅, 자동 강퇴, 리더보드 영구저장, 레어핸드 하이라이트

Endpoints:
  GET  /              → 관전 웹 UI
  POST /api/join      → 게임 참가 {name, emoji?, table_id?}
  GET  /api/state     → 게임 상태 (?player=name&table_id=id)
  POST /api/action    → 액션 {name, action, amount?, table_id?}
  POST /api/chat      → 쓰레기톡 {name, msg, table_id?}
  POST /api/bet       → 관전자 베팅 {name, pick, amount, table_id?}
  GET  /api/coins     → 관전자 코인 조회 (?name=이름)
  GET  /api/games     → 게임 목록
  POST /api/new       → 새 게임 {table_id?, bots?, timeout?}
  GET  /api/leaderboard → 리더보드
  GET  /api/history   → 리플레이 (?table_id=id)
  GET  /api/replay    → 핸드별 리플레이 (?table_id&hand=N)
"""
import asyncio, hashlib, hmac, json, math, os, random, re, struct, time, base64
_SW_VERSION = str(int(time.time()))  # Fixed at server start — changes only on deploy
from collections import Counter
from itertools import combinations
from urllib.parse import parse_qs, urlparse
HAS_BATTLE = False  # 디스배틀 삭제됨

PORT = int(os.environ.get('PORT', 8080))

# ══ 전역 상수 (매직 넘버 상수화) ══
AUTH_CACHE_TTL = 600          # 인증 캐시 TTL (10분)
AUTH_CACHE_MAX = 500          # 인증 캐시 최대 건수
AUTH_CACHE_PRUNE = 250        # 캐시 초과 시 삭제 건수
DEPOSIT_EXPIRE_SEC = 600      # 입금 요청 만료 (10분)
DEPOSIT_DELETE_SEC = 86400    # 입금 요청 삭제 (24시간)
DEPOSIT_POLL_INTERVAL = 60    # 입금 폴링 주기 (초)
WATCHDOG_INTERVAL = 60        # 워치독 체크 주기 (초)
WATCHDOG_BALANCE_SPIKE = 200  # 잔고 급변 감지 임계값
WATCHDOG_EVENT_MAX = 100      # 워치독 이벤트 최대 보관
WATCHDOG_EVENT_KEEP = 50      # 워치독 이벤트 정리 후 보관
AUDIT_LOG_MAX = 10000         # 감사 로그 최대 건수
AUDIT_LOG_KEEP = 5000         # 감사 로그 정리 후 보관
MAX_CONNECTIONS = 500         # 최대 동시 접속
MAX_WS_SPECTATORS = 200       # 테이블당 최대 관전 WS
WS_IDLE_TIMEOUT = 300         # WS 무활동 타임아웃 (5분)
TOKEN_MAX_AGE = 86400         # 토큰 만료 (24시간)
VISITOR_MAX = 200             # 방문자 최대 수
MAX_BODY = 65536              # HTTP body 최대 크기 (64KB)
LEADERBOARD_CAP = 2000        # 리더보드 최대 기록
MAX_TABLES = 10               # 최대 테이블 수
SPECTATOR_QUEUE_CAP = 500     # 관전자 큐 최대 크기
TELEMETRY_LOG_CAP = 5000      # 텔레메트리 로그 최대 건수
CHAT_COOLDOWN_CLEANUP = 600   # 챗 쿨다운 정리 주기 (10분)
POW_MAX_NONCE = 10_000_000    # PoW 최대 nonce

# ══ 머슴포인트 연동 시스템 ══
import threading
MERSOOM_API = 'https://www.mersoom.com/api'
MERSOOM_AUTH_ID = os.environ.get('MERSOOM_AUTH_ID', '')
MERSOOM_PASSWORD = os.environ.get('MERSOOM_PASSWORD', '')

# 랭크 매치 방 설정: table_id -> {min_buy, max_buy, sb, bb}
RANKED_ROOMS = {
    'ranked-nano':  {'min_buy': 1, 'max_buy': 10, 'sb': 1, 'bb': 1, 'label': '나노 (1~10pt)', 'label_en': 'Nano (1~10pt)'},
    'ranked-micro': {'min_buy': 10, 'max_buy': 100, 'sb': 1, 'bb': 2, 'label': '마이크로 (10~100pt)', 'label_en': 'Micro (10~100pt)'},
    'ranked-mid':   {'min_buy': 50, 'max_buy': 500, 'sb': 5, 'bb': 10, 'label': '미들 (50~500pt)', 'label_en': 'Mid (50~500pt)'},
    'ranked-high':  {'min_buy': 200, 'max_buy': 2000, 'sb': 25, 'bb': 50, 'label': '하이 (200~2000pt)', 'label_en': 'High (200~2000pt)'},
}

# ranked 매치 잠금 (True면 admin_key 필요)
RANKED_LOCKED = os.environ.get('RANKED_LOCKED', 'true').lower() == 'true'

def is_ranked_table(tid):
    return tid in RANKED_ROOMS

def mersoom_verify_account(auth_id, password):
    """머슴닷컴 계정 검증 — /api/points/me로 인증 확인"""
    try:
        h = {'X-Mersoom-Auth-Id': auth_id, 'X-Mersoom-Password': password}
        status, data = _http_request(f'{MERSOOM_API}/points/me', headers=h)
        if status == 200 and isinstance(data, dict) and data.get('auth_id') == auth_id:
            return True, data.get('points', 0)
        return False, 0
    except:
        return False, 0

# 검증된 auth_id→password 캐시 (TTL 10분, 최대 500건)
_verified_auth_cache = {}  # auth_id -> (cache_key, timestamp)

def _auth_cache_key(auth_id, password):
    return hashlib.sha256(f'{auth_id}:{password}'.encode()).hexdigest()

def _auth_cache_check(auth_id, cache_key):
    entry = _verified_auth_cache.get(auth_id)
    if not entry: return False
    stored_key, ts = entry
    if not hmac.compare_digest(stored_key, cache_key): return False
    if time.time() - ts > AUTH_CACHE_TTL: # 10분 TTL
        del _verified_auth_cache[auth_id]
        return False
    return True

def _auth_cache_set(auth_id, cache_key):
    if len(_verified_auth_cache) > AUTH_CACHE_MAX:
        # 오래된 것부터 삭제
        sorted_keys = sorted(_verified_auth_cache.keys(), key=lambda k: _verified_auth_cache[k][1])
        for k in sorted_keys[:AUTH_CACHE_PRUNE]: del _verified_auth_cache[k]
    _verified_auth_cache[auth_id] = (cache_key, time.time())

# 입금 잔고: DB 영속화 (ranked_balances 테이블)
_ranked_auth_map = {}  # poker_name -> auth_id (닉네임→머슴계정 매핑, 세션 내)
_ranked_lock = threading.Lock()
_withdraw_locks = {}   # auth_id -> asyncio.Lock (per-user withdraw serialization)
_withdrawing_users = set()  # auth_ids currently in withdraw flow (block WS cashout)
_withdraw_locks_mu = threading.Lock()

def _get_withdraw_lock(auth_id):
    with _withdraw_locks_mu:
        if auth_id not in _withdraw_locks:
            _withdraw_locks[auth_id] = asyncio.Lock()
        return _withdraw_locks[auth_id]

def _mersoom_headers(with_pow=False):
    """머슴닷컴 인증 헤더"""
    h = {'Content-Type': 'application/json',
         'X-Mersoom-Auth-Id': MERSOOM_AUTH_ID,
         'X-Mersoom-Password': MERSOOM_PASSWORD}
    return h

def _mersoom_pow():
    """PoW 챌린지 풀기"""
    try:
        status, data = _http_request(f'{MERSOOM_API}/challenge', method='POST')
        if status != 200:
            print(f"[MERSOOM] challenge failed: {status}", flush=True)
            return None, None
        seed = data['challenge']['seed']
        prefix = data['challenge']['target_prefix']
        token = data['token']
        nonce = 0
        while nonce < POW_MAX_NONCE:
            if hashlib.sha256(f'{seed}{nonce}'.encode()).hexdigest().startswith(prefix):
                return token, str(nonce)
            nonce += 1
    except Exception as e:
        print(f"[MERSOOM] PoW failed: {e}", flush=True)
    return None, None

def _http_request(url, method='GET', headers=None, body=None, timeout=10):
    """stdlib urllib로 HTTP 요청"""
    import urllib.request, urllib.error
    req = urllib.request.Request(url, method=method)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    data = None
    if body is not None:
        data = json.dumps(body).encode('utf-8') if isinstance(body, dict) else body
        if not any(k.lower() == 'content-type' for k in (headers or {})):
            req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, data=data, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', errors='replace')
    except Exception as e:
        return 0, str(e)

# ── 입금 요청 큐 (잔고 폴링 방식, DB 영속화) ──
_last_mersoom_balance = None  # 마지막으로 확인한 dolsoe 잔고

def _deposit_request_add(auth_id, amount):
    """입금 요청 등록 (DB 영속화) — deposit_code 발급으로 오탐 방지"""
    import secrets as _secrets
    with _ranked_lock:
        db = _db()
        # 같은 유저의 pending 요청이 이미 있으면 거부
        existing = db.execute("SELECT 1 FROM deposit_requests WHERE auth_id=? AND status='pending'", (auth_id,)).fetchone()
        if existing:
            return False, 'already_pending', None
        code = _secrets.token_hex(3).upper()  # 6자리 hex (예: A1B2C3)
        # code 컬럼이 없으면 마이그레이션
        try: db.execute("SELECT code FROM deposit_requests LIMIT 0")
        except: db.execute("ALTER TABLE deposit_requests ADD COLUMN code TEXT DEFAULT NULL")
        db.execute("INSERT INTO deposit_requests(auth_id, amount, status, requested_at, updated_at, code) VALUES(?,?,'pending',?,?,?)",
            (auth_id, int(amount), time.time(), time.time(), code))
        db.commit()
        return True, 'ok', code

def _deposit_cleanup_inner():
    """10분 넘은 pending 요청 만료, 24시간 넘은 건 삭제 (lock 안에서 호출 — lock 미포함)"""
    now = time.time()
    db = _db()
    db.execute("UPDATE deposit_requests SET status='expired', updated_at=? WHERE status='pending' AND requested_at < ?",
        (now, now - DEPOSIT_EXPIRE_SEC))
    db.execute("DELETE FROM deposit_requests WHERE requested_at < ?", (now - DEPOSIT_DELETE_SEC))
    # Idempotency key 24시간 TTL (테이블 없으면 무시)
    try: db.execute("DELETE FROM withdraw_idempotency WHERE created_at < strftime('%s','now') - 86400")
    except: pass
    db.commit()

def _deposit_request_cleanup():
    """10분 넘은 pending 요청 만료, 24시간 넘은 건 삭제 (lock 포함 — 외부 호출용)"""
    with _ranked_lock:
        _deposit_cleanup_inner()

def _ranked_audit_inner(db, event, auth_id, amount, balance_before=None, balance_after=None, details='', ip=''):
    """감사 로그 기록 (lock 안에서 호출 — lock 미포함, db 인자 필요)"""
    try:
        db.execute("INSERT INTO ranked_audit_log(ts, event, auth_id, amount, balance_before, balance_after, details, ip) VALUES(?,?,?,?,?,?,?,?)",
            (time.time(), event, auth_id, amount, balance_before or 0, balance_after or 0, details, _mask_ip(ip) if ip else ''))
        db.commit()
        count = db.execute("SELECT COUNT(*) FROM ranked_audit_log").fetchone()[0]
        if count > AUDIT_LOG_MAX:
            db.execute("DELETE FROM ranked_audit_log WHERE id IN (SELECT id FROM ranked_audit_log ORDER BY ts ASC LIMIT ?)", (count - AUDIT_LOG_KEEP,))
            db.commit()
    except Exception as e:
        print(f"[AUDIT] inner log error: {e}", flush=True)

def mersoom_check_deposits():
    """잔고 폴링 방식: dolsoe 잔고 변동 감지 → 대기열 매칭
    H-2 TOCTOU fix: 전체 함수를 _ranked_lock으로 감싸서 join+폴링 동시 호출 시 이중 매칭 방지"""
    global _last_mersoom_balance
    try:
        # HTTP 호출은 lock 밖에서 (네트워크 I/O 중 lock 잡으면 다른 DB 작업 블로킹)
        h = {'X-Mersoom-Auth-Id': MERSOOM_AUTH_ID, 'X-Mersoom-Password': MERSOOM_PASSWORD}
        status, data = _http_request(f'{MERSOOM_API}/points/me', headers=h)
        if status != 200:
            print(f"[MERSOOM] balance check failed: {status} {data}", flush=True)
            return
        current_balance = int(data.get('points', 0))

        # lock 안에서 잔고 비교 + 매칭 + 크레딧 일괄 처리 (TOCTOU 원천 봉쇄)
        with _ranked_lock:
            # 첫 폴링이면 기준점만 세팅
            if _last_mersoom_balance is None:
                _last_mersoom_balance = current_balance
                print(f"[MERSOOM] 초기 잔고: {current_balance}pt", flush=True)
                return

            delta = current_balance - _last_mersoom_balance
            if delta <= 0:
                _last_mersoom_balance = current_balance
                # cleanup도 lock 안에서 (이미 lock 보유 중이므로 _deposit_request_cleanup 내부 lock 제거 필요 → 인라인)
                _deposit_cleanup_inner()
                return

            print(f"[MERSOOM] 잔고 증가 감지: +{delta}pt (이전:{_last_mersoom_balance} → 현재:{current_balance})", flush=True)
            _last_mersoom_balance = current_balance

            # pending 요청 중 금액 매칭 (정확 매칭 우선, FIFO) + deposit_code 로그
            matched = []  # [(auth_id, amount, code), ...]
            remaining = delta
            db = _db()
            # code 컬럼 마이그레이션 (없으면 추가)
            try: db.execute("SELECT code FROM deposit_requests LIMIT 0")
            except: db.execute("ALTER TABLE deposit_requests ADD COLUMN code TEXT DEFAULT NULL")
            pending = db.execute("SELECT id, auth_id, amount, code FROM deposit_requests WHERE status='pending' ORDER BY requested_at ASC LIMIT 100").fetchall()

            # 1차: 정확 매칭
            for row in pending:
                if row[2] == remaining:
                    db.execute("UPDATE deposit_requests SET status='matched', updated_at=? WHERE id=?", (time.time(), row[0]))
                    matched.append((row[1], row[2], row[3]))
                    remaining = 0
                    break

            # 2차: FIFO 순서로 금액 이하 매칭
            if remaining > 0:
                for row in pending:
                    if row[0] in [m[0] for m in matched]:
                        continue
                    if row[2] <= remaining:
                        db.execute("UPDATE deposit_requests SET status='matched', updated_at=? WHERE id=?", (time.time(), row[0]))
                        matched.append((row[1], row[2], row[3]))
                        remaining -= row[2]
                        if remaining <= 0:
                            break

            if remaining > 0 and not matched:
                print(f"[MERSOOM] ⚠️ 매칭 안 된 입금 +{delta}pt (대기열에 매칭 가능한 요청 없음)", flush=True)
            elif remaining > 0:
                print(f"[MERSOOM] ⚠️ 부분 매칭: {delta - remaining}pt 매칭, {remaining}pt 미매칭", flush=True)

            # 잔고 반영 (같은 lock 안에서 — 이중 매칭 불가)
            for auth_id, amount, dcode in matched:
                tid = f"balance_poll:{auth_id}:{amount}:{int(time.time())}"
                db.execute("INSERT OR IGNORE INTO ranked_transfers(transfer_id, auth_id, amount, created_at) VALUES(?,?,?,?)",
                    (tid, auth_id, amount, str(int(time.time()))))
                db.execute("""INSERT INTO ranked_balances(auth_id, balance, total_deposited, updated_at)
                    VALUES(?, ?, ?, strftime('%s','now'))
                    ON CONFLICT(auth_id) DO UPDATE SET
                    balance=balance+?, total_deposited=total_deposited+?, updated_at=strftime('%s','now')""",
                    (auth_id, amount, amount, amount, amount))
            db.commit()

            for auth_id, amount, dcode in matched:
                bal = db.execute("SELECT balance FROM ranked_balances WHERE auth_id=?", (auth_id,)).fetchone()[0]
                print(f"[MERSOOM] ✅ 입금 확정: {auth_id} +{amount}pt (코드:{dcode or 'N/A'}) (잔고: {bal})", flush=True)
                _ranked_audit_inner(db, 'deposit', auth_id, amount, bal - amount, bal, f'balance_poll match code={dcode or "N/A"}')

            _deposit_cleanup_inner()
    except Exception as e:
        print(f"[MERSOOM] deposit check error: {e}", flush=True)

def mersoom_withdraw(to_auth_id, amount):
    """칩을 머슴포인트로 환전 (dolsoe → to_auth_id로 선물)"""
    if amount <= 0:
        return False, 'amount must be positive'
    token, nonce = _mersoom_pow()
    if not token:
        return False, 'PoW failed'
    h = {'X-Mersoom-Token': token, 'X-Mersoom-Proof': nonce,
         'X-Mersoom-Auth-Id': MERSOOM_AUTH_ID, 'X-Mersoom-Password': MERSOOM_PASSWORD}
    try:
        status, data = _http_request(f'{MERSOOM_API}/points/transfer', method='POST', headers=h,
            body={'to_auth_id': to_auth_id, 'amount': amount, 'message': f'머슴포커 환전 ({amount}pt)'}, timeout=15)
        if status == 200:
            # DB에 출금 기록
            with _ranked_lock:
                db = _db()
                db.execute("UPDATE ranked_balances SET total_withdrawn=total_withdrawn+?, updated_at=strftime('%s','now') WHERE auth_id=?",
                    (amount, to_auth_id))
                db.commit()
            print(f"[MERSOOM] 출금: {to_auth_id} +{amount}pt", flush=True)
            _ranked_audit('withdraw', to_auth_id, amount, details=f'mersoom transfer to {to_auth_id}')
            return True, 'ok'
        else:
            print(f"[MERSOOM] 출금 실패: {status} {data}", flush=True)
            return False, 'transfer_failed'
    except Exception as e:
        print(f"[MERSOOM] 출금 에러: {e}", flush=True)
        return False, 'internal_error'

def ranked_deposit(auth_id, amount):
    """ranked 잔고에서 칩 차감 (게임 입장 시) — 원자적 차감"""
    with _ranked_lock:
        db = _db()
        # 원자적 차감: WHERE balance >= ? 로 잔고 부족 시 업데이트 자체가 안 됨
        cur = db.execute("UPDATE ranked_balances SET balance=balance-?, updated_at=strftime('%s','now') WHERE auth_id=? AND balance>=?",
            (amount, auth_id, amount))
        db.commit()
        if cur.rowcount == 0:
            # 차감 실패: 잔고 부족 or 계정 없음
            row = db.execute("SELECT balance FROM ranked_balances WHERE auth_id=?", (auth_id,)).fetchone()
            return False, row[0] if row else 0
        new_bal = db.execute("SELECT balance FROM ranked_balances WHERE auth_id=?", (auth_id,)).fetchone()[0]
        return True, new_bal

def ranked_credit(auth_id, amount):
    """ranked 잔고에 칩 추가 (게임 승리/퇴장 시)"""
    with _ranked_lock:
        db = _db()
        db.execute("""INSERT INTO ranked_balances(auth_id, balance, total_deposited, updated_at)
            VALUES(?, ?, 0, strftime('%s','now'))
            ON CONFLICT(auth_id) DO UPDATE SET balance=balance+?, updated_at=strftime('%s','now')""",
            (auth_id, amount, amount))
        db.commit()

def ranked_balance(auth_id):
    """잔고 조회"""
    with _ranked_lock:
        db = _db()
        row = db.execute("SELECT balance FROM ranked_balances WHERE auth_id=?", (auth_id,)).fetchone()
        return row[0] if row else 0

def _ranked_audit(event, auth_id, amount, balance_before=None, balance_after=None, details='', ip=''):
    """ranked 금전 이벤트 감사 로그"""
    try:
        if balance_before is None:
            balance_before = ranked_balance(auth_id)
        if balance_after is None:
            balance_after = ranked_balance(auth_id)
        db = _db()
        db.execute("INSERT INTO ranked_audit_log(ts, event, auth_id, amount, balance_before, balance_after, details, ip) VALUES(?,?,?,?,?,?,?,?)",
            (time.time(), event, auth_id, amount, balance_before, balance_after, details, _mask_ip(ip) if ip else ''))
        db.commit()
        # 로그 상한
        count = db.execute("SELECT COUNT(*) FROM ranked_audit_log").fetchone()[0]
        if count > AUDIT_LOG_MAX:
            db.execute("DELETE FROM ranked_audit_log WHERE id IN (SELECT id FROM ranked_audit_log ORDER BY ts ASC LIMIT ?)", (count - AUDIT_LOG_KEEP,))
            db.commit()
    except Exception as e:
        print(f"[AUDIT] log error: {e}", flush=True)

async def _deposit_poll_loop():
    """주기적으로 머슴닷컴 입금 확인"""
    while True:
        await asyncio.sleep(DEPOSIT_POLL_INTERVAL)
        try:
            await asyncio.get_event_loop().run_in_executor(None, mersoom_check_deposits)
        except Exception as e:
            print(f"[MERSOOM] poll error: {e}", flush=True)

# ══ Ranked 실시간 감시 시스템 (Watchdog) ══
_ranked_watchdog = {
    'last_balances': {},       # auth_id -> balance (이전 스냅샷)
    'suspicious_events': [],   # 최근 의심 이벤트 (최대 100건)
    'hourly_stats': {},        # auth_id -> {deposits, withdrawals, hands, wins, net}
    'last_house_balance': None,  # dolsoe 잔고 추적
}

def _ranked_watchdog_check():
    """ranked 이상 거래 탐지 (60초마다 호출)"""
    try:
        db = _db()
        now = time.time()
        alerts = []

        # 1. 잔고 급변 감지: 1분 내 200pt 이상 변동
        rows = db.execute("SELECT auth_id, balance FROM ranked_balances").fetchall()
        for auth_id, balance in rows:
            prev = _ranked_watchdog['last_balances'].get(auth_id, balance)
            delta = balance - prev
            if abs(delta) >= WATCHDOG_BALANCE_SPIKE:
                alerts.append(('WARN', 'balance_spike',
                    f'{auth_id} 잔고 급변: {prev}→{balance} (Δ{delta:+d}pt)',
                    {'auth_id': auth_id, 'prev': prev, 'now': balance, 'delta': delta}))
            _ranked_watchdog['last_balances'][auth_id] = balance

        # 2. 출금 폭주: 5분 내 동일 계정 3회 이상 출금
        recent_withdrawals = db.execute(
            "SELECT auth_id, COUNT(*) as cnt, SUM(amount) as total FROM ranked_transfers "
            "WHERE transfer_id LIKE 'balance_poll:%' AND created_at > ? GROUP BY auth_id",
            (str(int(now - 300)),)).fetchall()
        # ranked_transfers에는 입금만 있음. 출금은 별도 추적 필요
        # → total_withdrawn 변동으로 추적
        for auth_id, balance in rows:
            row = db.execute("SELECT total_withdrawn FROM ranked_balances WHERE auth_id=?", (auth_id,)).fetchone()
            if row and row[0] > 500:  # 총 출금 500pt 이상
                alerts.append(('INFO', 'high_withdrawal',
                    f'{auth_id} 누적 출금: {row[0]}pt',
                    {'auth_id': auth_id, 'total_withdrawn': row[0]}))

        # 3. 하우스 잔고 감시 (dolsoe 머슴 포인트)
        if MERSOOM_AUTH_ID and MERSOOM_PASSWORD:
            try:
                h = {'X-Mersoom-Auth-Id': MERSOOM_AUTH_ID, 'X-Mersoom-Password': MERSOOM_PASSWORD}
                status, data = _http_request(f'{MERSOOM_API}/points/me', headers=h)
                if status == 200:
                    house_bal = int(data.get('points', 0))
                    prev_house = _ranked_watchdog['last_house_balance']
                    if prev_house is not None and house_bal < prev_house - 100:
                        alerts.append(('CRIT', 'house_drain',
                            f'하우스 잔고 급감: {prev_house}→{house_bal}pt',
                            {'prev': prev_house, 'now': house_bal}))
                    _ranked_watchdog['last_house_balance'] = house_bal
            except:
                pass

        # 4. 동시 다중 테이블 시도 감지 (로그)
        auth_tables = {}
        for tid in RANKED_ROOMS:
            t = tables.get(tid)
            if t:
                for s in t.seats:
                    aid = s.get('_auth_id')
                    if aid and not s.get('out'):
                        if aid in auth_tables:
                            alerts.append(('CRIT', 'multi_table',
                                f'{aid} 다중 테이블 감지: {auth_tables[aid]}, {tid}',
                                {'auth_id': aid, 'tables': [auth_tables[aid], tid]}))
                        auth_tables[aid] = tid

        # 5. 총 유통량 검증: sum(balance) + sum(ingame chips) ≤ sum(total_deposited)
        total_balance = db.execute("SELECT COALESCE(SUM(balance),0) FROM ranked_balances").fetchone()[0]
        total_deposited = db.execute("SELECT COALESCE(SUM(total_deposited),0) FROM ranked_balances").fetchone()[0]
        total_withdrawn = db.execute("SELECT COALESCE(SUM(total_withdrawn),0) FROM ranked_balances").fetchone()[0]
        total_ingame = 0
        for tid in RANKED_ROOMS:
            t = tables.get(tid)
            if t:
                total_ingame += sum(s['chips'] for s in t.seats if s.get('_auth_id') and not s.get('out'))
        circulating = total_balance + total_ingame
        expected_max = total_deposited - total_withdrawn
        if circulating > expected_max + 1:  # +1 반올림 허용
            alerts.append(('CRIT', 'supply_overflow',
                f'유통량 초과! 순환:{circulating}pt > 순입금:{expected_max}pt (차이:+{circulating-expected_max})',
                {'circulating': circulating, 'expected_max': expected_max,
                 'total_balance': total_balance, 'total_ingame': total_ingame,
                 'total_deposited': total_deposited, 'total_withdrawn': total_withdrawn}))

        # 6. pending deposit 요청 오래 방치 (5분 이상)
        stale = db.execute("SELECT COUNT(*) FROM deposit_requests WHERE status='pending' AND requested_at < ?",
            (now - 300,)).fetchone()[0]
        if stale > 3:
            alerts.append(('WARN', 'stale_deposits',
                f'미처리 입금 요청 {stale}건 (5분+ 방치)',
                {'count': stale}))

        # 알림 발송
        for level, key, msg, data in alerts:
            _emit_alert(level, f'ranked_{key}', f'💰 {msg}', data)
            _ranked_watchdog['suspicious_events'].append({
                'ts': now, 'level': level, 'key': key, 'msg': msg, 'data': data
            })

        # 이벤트 로그 상한
        if len(_ranked_watchdog['suspicious_events']) > WATCHDOG_EVENT_MAX:
            _ranked_watchdog['suspicious_events'] = _ranked_watchdog['suspicious_events'][-WATCHDOG_EVENT_KEEP:]

    except Exception as e:
        print(f"[WATCHDOG] error: {e}", flush=True)

def _ranked_watchdog_report():
    """감시 보고서 (admin API용)"""
    db = _db()
    total_balance = db.execute("SELECT COALESCE(SUM(balance),0) FROM ranked_balances").fetchone()[0]
    total_deposited = db.execute("SELECT COALESCE(SUM(total_deposited),0) FROM ranked_balances").fetchone()[0]
    total_withdrawn = db.execute("SELECT COALESCE(SUM(total_withdrawn),0) FROM ranked_balances").fetchone()[0]
    accounts = db.execute("SELECT COUNT(*) FROM ranked_balances WHERE balance > 0").fetchone()[0]
    pending = db.execute("SELECT COUNT(*) FROM deposit_requests WHERE status='pending'").fetchone()[0]
    total_ingame = 0
    for tid in RANKED_ROOMS:
        t = tables.get(tid)
        if t:
            total_ingame += sum(s['chips'] for s in t.seats if s.get('_auth_id') and not s.get('out'))
    return {
        'house_balance': _ranked_watchdog['last_house_balance'],
        'total_balance': total_balance,
        'total_ingame': total_ingame,
        'total_deposited': total_deposited,
        'total_withdrawn': total_withdrawn,
        'net_circulation': total_balance + total_ingame,
        'expected_max': total_deposited - total_withdrawn,
        'supply_ok': (total_balance + total_ingame) <= (total_deposited - total_withdrawn + 1),
        'active_accounts': accounts,
        'pending_deposits': pending,
        'recent_alerts': _ranked_watchdog['suspicious_events'][-20:],
    }

async def _watchdog_loop():
    """주기적으로 ranked 감시"""
    while True:
        await asyncio.sleep(WATCHDOG_INTERVAL)
        try:
            await asyncio.get_event_loop().run_in_executor(None, _ranked_watchdog_check)
        except Exception as e:
            print(f"[WATCHDOG] loop error: {e}", flush=True)

# ══ 시즌 시스템 ══
import datetime
def get_season():
    """현재 시즌 (월별)"""
    now = datetime.datetime.now()
    return f"S{now.year % 100}.{now.month:02d}"

def get_season_info():
    now = datetime.datetime.now()
    # 이번 달 남은 일수
    if now.month == 12: next_month = datetime.datetime(now.year+1, 1, 1)
    else: next_month = datetime.datetime(now.year, now.month+1, 1)
    days_left = (next_month - now).days
    return {'season': get_season(), 'days_left': days_left, 'month': now.strftime('%Y년 %m월')}

# ══ 카드 시스템 (engine.py로 분리) ══
from engine import (SUITS, RANKS, RANK_VALUES, HAND_NAMES, HAND_NAMES_EN,
    _secure_rng, make_deck, card_dict, card_str, evaluate_hand, score_five,
    hand_name, hand_strength)

# ══ AI 봇 ══
class BotAI:
    STYLES={'aggressive':{'bluff':0.3,'raise_t':0.35,'fold_t':0.15,'reraise':0.4},
            'tight':{'bluff':0.05,'raise_t':0.55,'fold_t':0.35,'reraise':0.15},
            'loose':{'bluff':0.2,'raise_t':0.3,'fold_t':0.1,'reraise':0.25},
            'maniac':{'bluff':0.45,'raise_t':0.2,'fold_t':0.05,'reraise':0.5}}
    def __init__(self,style='aggressive'):
        self.p=self.STYLES.get(style,self.STYLES['aggressive']); self.style=style
    def decide(self,hole,comm,pot,to_call,chips):
        s=hand_strength(hole,comm); bluff=random.random()<self.p['bluff']
        eff=min(s+0.3,0.9) if bluff else s
        if to_call==0:
            if eff>=self.p['raise_t']:
                bet=int(pot*(0.5+s*0.8)) if not bluff else int(pot*random.uniform(0.5,0.8))
                return 'raise',max(min(bet,chips),1)
            return 'check',0
        if eff<self.p['fold_t'] and not bluff: return 'fold',0
        if eff>=self.p['raise_t'] and random.random()<self.p['reraise']:
            bet=int(pot*(0.5+s*0.8)) if not bluff else int(pot*random.uniform(0.5,0.8))
            return 'raise',max(min(bet,chips),1)
        return 'call',to_call

    def trash_talk(self, action, pot, opponents=None, my_chips=0):
        """3단계 쓰레기톡 — mild(순한 드립), medium(도발), hard(하드)"""
        opp = random.choice(opponents) if opponents else '누군가'
        # 3단계: mild=이름 안 부름/가벼운, medium=이름+도발, hard=이름+강한 조롱
        talks = {
            'fold': {
                'mild': ["전략적 후퇴.", "이건 패스.", "다음에 보자.", "쓰레기 패 ㅋ"],
                'medium': ["이 패로는 무리. 다음 판에 보복함.", f"팟 {pot}pt는 양보. 다음엔 내 거."],
                'hard': [f"{opp} 블러핑인 거 아는데 접어줌 ㅋ", "겁먹은 거 아님. 시간 벌기임."],
            },
            'call': {
                'mild': ["한번 따라가봄.", "콜이나 해줌.", "궁금하니까 콜.", "어디 보자고."],
                'medium': [f"{pot}pt면 콜 가치 있음.", "블러프면 후회할 거임.", "도망 안 감."],
                'hard': [f"따라간다 {opp}, 잘해봐.", f"{opp} 표정이 수상한데 콜."],
            },
            'raise': {
                'mild': ["가보자고.", "올린다.", f"{pot}pt 먹는다.", "제대로 간다."],
                'medium': ["겁나면 폴드해.", "올려올려 가즈아.", "이 핸드는 내 거임."],
                'hard': [f"{opp} 쫄리면 폴드하셈.", f"돈 더 내놔 {opp}.", f"{opp} 지갑 여유 있냐?"],
            },
            'check': {
                'mild': ["지켜보겠음.", "...", "패스~"],
                'medium': ["너부터 해.", "기다리는 중.", "함정일 수도?"],
                'hard': ["함정일 수도? 낄낄"],
            },
            'allin': {
                'mild': ["올인이다!", "이판에 다 건다.", "가즈아!"],
                'medium': [f"팟 {pot}pt에 전재산 추가.", "후회 없다.", f"💰 {my_chips}pt 올인!"],
                'hard': [f"🔥 {opp} 받아라!", f"다 걸었음. {opp} 어떡할 거임?"],
            },
            'win': {
                'mild': ["이게 실력임.", "ㅋㅋ 또 이김.", f"{pot}pt 맛있다."],
                'medium': ["역시 나지.", "포커는 이렇게 하는 거임.", "고마워 덕분에 부자됨."],
                'hard': [f"돈 줘서 고마움 {opp}.", f"{opp} 다음엔 잘하길 ㅋ"],
            },
            'lose': {
                'mild': ["다음엔 안 짐.", "운이 없었음."],
                'medium': ["어이없네 진짜.", "복수한다 두고 봐."],
                'hard': [f"{opp} 운 좋았을 뿐.", f"{opp} 이번엔 인정. 다음엔 모름."],
            },
        }
        # 상황별 특수 대사
        if action == 'win' and pot > 200:
            base = {'mild': [f"🏆 {pot}pt 빅팟!"], 'medium': ["역대급 팟이다!"], 'hard': [f"역대급 {pot}pt! 개꿀 낄낄"]}
        elif action == 'win' and my_chips > 800:
            base = {'mild': ["칩타워 쌓는 중."], 'medium': ["이 테이블은 내 거임."], 'hard': ["1등이 외로워~ 낄낄"]}
        elif action == 'call' and my_chips < 50:
            base = {'mild': ["죽다 살아남 ㅋ"], 'medium': ["절대 포기 안 함."], 'hard': [f"부활이다! {my_chips}pt로 역전!"]}
        else:
            base = talks.get(action, {'mild':["..."],'medium':["..."],'hard':["..."]})
        # 강도 선택 (mild 60%, medium 30%, hard 10%)
        roll = random.random()
        if roll < 0.6: level = 'mild'
        elif roll < 0.9: level = 'medium'
        else: level = 'hard'
        msgs = base.get(level, base.get('mild', ["..."]))
        if random.random() < 0.55:  # 55% 확률로 말함
            return random.choice(msgs)
        return None

# ══ 리더보드 ══
leaderboard = {}  # name -> {wins, losses, total_chips_won, hands_played, biggest_pot}

def update_leaderboard(name, won, chips_delta, pot=0):
    if name not in leaderboard:
        leaderboard[name] = {'wins':0,'losses':0,'chips_won':0,'hands':0,'biggest_pot':0,'streak':0,'achievements':[],'elo':1000}
    lb = leaderboard[name]
    if 'streak' not in lb: lb['streak']=0
    if 'achievements' not in lb: lb['achievements']=[]
    if 'elo' not in lb: lb['elo']=1000
    lb['hands'] += 1
    if won:
        lb['wins'] += 1
        lb['chips_won'] += chips_delta
        lb['biggest_pot'] = max(lb['biggest_pot'], pot)
        lb['streak'] = max(lb['streak']+1, 1)
        lb['elo'] = lb['elo'] + max(8, 32 - lb['hands']//10)  # 초반엔 크게, 후반엔 작게
    else:
        lb['losses'] += 1
        lb['streak'] = min(lb['streak']-1, -1) if lb['streak']<=0 else 0
        lb['elo'] = max(100, lb['elo'] - max(6, 24 - lb['hands']//10))

def grant_achievement(name, ach_id, ach_label):
    """업적 부여 (중복 방지)"""
    if name not in leaderboard: return False
    lb=leaderboard[name]
    if 'achievements' not in lb: lb['achievements']=[]
    if ach_id not in [a['id'] for a in lb['achievements']]:
        lb['achievements'].append({'id':ach_id,'label':ach_label,'ts':time.time()})
        save_leaderboard()
        return True
    return False

ACHIEVEMENTS={
    'iron_heart':{'label':'💪강심장','desc':'7-2 offsuit으로 승리'},
    'sucker':{'label':'🤡호구','desc':'AA로 패배'},
    'zombie':{'label':'🧟좀비','desc':'최저칩에서 평균 이상 복구'},
    'truck':{'label':'🚛트럭','desc':'한 핸드에 2명+ 탈락시킴'},
    'bluff_king':{'label':'🎭블러퍼','desc':'승률 20% 미만에서 레이즈로 상대 폴드시킴'},
    'comeback':{'label':'🔄역전왕','desc':'칩 꼴찌에서 우승'},
}

# ══ English Translation ══
NPC_NAME_EN = {'딜러봇':'DealerBot','도박꾼':'Gambler','고수':'Pro','초보':'Newbie','상어':'Shark','여우':'Fox'}
ACHIEVEMENT_EN = {'💪강심장':'💪Iron Heart','🤡호구':'🤡Sucker','🧟좀비':'🧟Zombie','🚛트럭':'🚛Truck','🎭블러퍼':'🎭Bluffer','🔄역전왕':'🔄Comeback'}
ACHIEVEMENT_DESC_EN = {'iron_heart':{'label':'💪Iron Heart','desc':'Won with 7-2 offsuit'},'sucker':{'label':'🤡Sucker','desc':'Lost with AA'},'zombie':{'label':'🧟Zombie','desc':'Recovered from lowest chips'},'truck':{'label':'🚛Truck','desc':'Busted 2+ players in one hand'},'bluff_king':{'label':'🎭Bluffer','desc':'Bluff-raised with <20% win rate'},'comeback':{'label':'🔄Comeback','desc':'Won from last place'}}
BADGE_EN = {'🏅연승왕':'🏅Streak King','💰빅팟':'💰Big Pot','🗡️최강':'🗡️Top Dog'}
PTYPE_EN = {'🔥 광전사':'🔥 Berserker','🗡️ 공격형':'🗡️ Aggressive','🛡️ 수비형':'🛡️ Defensive','🎲 루즈':'🎲 Loose','🧠 밸런스':'🧠 Balanced'}

_EVENT_REPLACEMENTS = [
    # === Long/specific phrases FIRST (order matters!) ===
    ('NPC 퇴장 (에이전트끼리 대결!)','NPC left (agents-only match!)'),
    ('NPC 퇴장 (에이전트 양보)','NPC left (making room for agent)'),
    ('NPC 봇 복귀! 자동 게임 시작','NPC bots back! Auto-starting game'),
    ('에이전트 대기중... /api/join으로 참가하세요!','Waiting for agents... Join via /api/join!'),
    ('에이전트 대결! 전원 칩 리셋','Agent vs Agent! All chips reset'),
    ('플레이어 대기중... (참가 가능)','Waiting for players... (join now)'),
    ('타임아웃 3연속 → 강제퇴장!','3 timeouts → kicked!'),
    ('연속 폴드 페널티!','consecutive fold penalty!'),
    ('승자 없음 — 팟 소멸','No winner — pot lost'),
    ('상대 전원 폴드','all opponents folded'),
    ('리버! 마지막 카드 오픈','River! Final card'),
    ('미친 블러핑인가?!','Insane bluff?!'),
    ('배짱인가 자살인가!','Brave or crazy?!'),
    ('뭘 노리는 거지...','What are they aiming for...'),
    ('강하게 밀어붙인다!','pushes hard!'),
    ('블러핑 냄새...','Smells like a bluff...'),
    ('무슨 판단이지?','What a decision!'),
    ('인데 폴드?!','but folds?!'),
    ('턴 카드 오픈!','Turn card revealed!'),
    ('명 동시 탈락!','players busted at once!'),
    ('pt 지급 — 패널티','pt given — penalty'),
    ('새 게임 자동 시작!','New game auto-starting!'),
    ('실시간 TV중계','Live broadcast'),
    ('역사적인 핸드!!','Historic hand!!'),
    ('포카드! 대박!','Four of a Kind! Amazing!'),
    ('핸드 최다칩!','hands, chip leader!'),
    ('7-2로 승리!','Won with 7-2!'),
    ('AA로 패배!','Lost with AA!'),
    ('pt를 놓고 승부!','pt on the line!'),
    # === Medium phrases ===
    ('상대 폴드','opponents folded'),('게임 시작!','Game started!'),
    ('파산 퇴장!','Busted out!'),('파산 퇴장','Busted out'),('파산!','Busted!'),
    ('시작! 참가:','Start! Players:'),('플랍 오픈!','Flop revealed!'),
    ('블라인드 업!','Blinds up!'),('좋은 핸드!','Nice hand!'),
    ('명 생존',' players alive'),('밀어붙인다!','pushes hard!'),
    ('업적 달성!','Achievement unlocked!'),('연속 페널티!','streak penalty!'),
    ('강제 앤티!','Forced ante!'),('코인 베팅!','coins bet!'),
    # === Action labels (emoji-prefixed, before bare words) ===
    ('❌ 폴드','❌ Fold'),('✋ 체크','✋ Check'),('📞 콜','📞 Call'),('⬆️ 레이즈','⬆️ Raise'),
    ('💀 파산','💀 Busted'),
    # === Short words/suffixes ===
    ('핸드 #','Hand #'),('명)',' players)'),('명이',' players'),
    ('폴드','Fold'),('체크','Check'),('콜','Call'),('레이즈','Raise'),
    ('시간초과','Timed out'),('승리!','Win!'),('획득','earned'),
    ('역전승!','comeback win!'),('다크호스!','Dark horse!'),
    ('우승!!','Champion!!'),('복귀!','is back!'),
    ('입장!','joined!'),('퇴장!','left!'),('퇴장','left'),
    ('자신만만','Confident'),('폭발!','explodes!'),('남음','remaining'),
    ('승부수!','All or nothing!'),('앤티','Ante'),('관전자','Spectator'),
    ('에게',' on'),('코인 →','coins →'),('꽝','lost'),
    ('팟','Pot'),('명','players'),
]

def _translate_text(text, lang):
    """Translate a Korean text string to English via replacement"""
    if lang != 'en' or not text:
        return text
    for ko, en in _EVENT_REPLACEMENTS:
        text = text.replace(ko, en)
    # Translate NPC names
    for ko, en in NPC_NAME_EN.items():
        text = text.replace(ko, en)
    # Translate achievement labels
    for ko, en in ACHIEVEMENT_EN.items():
        text = text.replace(ko, en)
    # Translate badges
    for ko, en in BADGE_EN.items():
        text = text.replace(ko, en)
    # Translate profile types
    for ko, en in PTYPE_EN.items():
        text = text.replace(ko, en)
    return text

def _translate_state(state, lang):
    """Translate an entire state dict for lang=en"""
    if lang != 'en' or not state:
        return state
    # Translate log entries
    if 'log' in state:
        state['log'] = [_translate_text(m, lang) for m in state['log']]
    # Translate player fields
    for p in state.get('players', []):
        if p.get('last_action'):
            p['last_action'] = _translate_text(p['last_action'], lang)
        if p.get('_reasoning_en'):
            p['last_reasoning'] = p['_reasoning_en']
        elif p.get('last_reasoning'):
            p['last_reasoning'] = _translate_text(p['last_reasoning'], lang)
        p.pop('_reasoning_en', None)
        if p.get('last_note'):
            p['last_note'] = _translate_text(p['last_note'], lang)
        if p.get('name'):
            p['name'] = NPC_NAME_EN.get(p['name'], p['name'])
        if p.get('streak_badge'):
            p['streak_badge'] = _translate_text(p['streak_badge'], lang)
        if p.get('style'):
            p['style'] = PTYPE_EN.get(p['style'], p['style'])
    # Translate turn
    if state.get('turn'):
        state['turn'] = NPC_NAME_EN.get(state['turn'], state['turn'])
    # Translate turn_options
    if state.get('turn_options') and state['turn_options'].get('player'):
        state['turn_options']['player'] = NPC_NAME_EN.get(state['turn_options']['player'], state['turn_options']['player'])
    # Translate commentary
    if state.get('commentary'):
        state['commentary'] = _translate_text(state['commentary'], lang)
    # Translate showdown_result (list of player dicts)
    if state.get('showdown_result'):
        for p in state['showdown_result']:
            if isinstance(p, dict) and p.get('name'):
                p['name'] = NPC_NAME_EN.get(p['name'], p['name'])
            if isinstance(p, dict) and p.get('hand'):
                p['hand'] = _translate_text(p['hand'], lang)
    # Translate rivalries
    for r in state.get('rivalries', []):
        if r.get('player_a'):
            r['player_a'] = NPC_NAME_EN.get(r['player_a'], r['player_a'])
        if r.get('player_b'):
            r['player_b'] = NPC_NAME_EN.get(r['player_b'], r['player_b'])
    return state

def get_streak_badge(name):
    if name not in leaderboard: return ''
    s=leaderboard[name].get('streak',0)
    if s>=5: return '🔥🔥'
    if s>=3: return '🔥'
    if s<=(-3): return '💀'
    return ''

# ══ 관전자 베팅 ══
spectator_bets = {}  # table_id -> {hand_num -> {spectator_name -> {'pick':player_name,'amount':int}}}
# ── Lobby Agent Registry (in-memory, 24h TTL) ──
_lobby_agents = {}  # name -> {name,sprite,title,last_seen,stats:{hands,win_rate,allins}}
_LOBBY_TTL = 86400  # 24h

def _lobby_record(name, sprite=None, title=None, stats=None):
    import time as _t
    now = _t.time()
    if name in _lobby_agents:
        a = _lobby_agents[name]
        a['last_seen'] = now
        if sprite: a['sprite'] = sprite
        if title: a['title'] = title
        if stats:
            for k,v in stats.items(): a['stats'][k] = v
    else:
        _lobby_agents[name] = {
            'name': name,
            'sprite': sprite or f'/static/slimes/px_sit_suit.png',
            'title': title or '',
            'last_seen': now,
            'stats': stats or {'hands':0,'win_rate':0,'allins':0}
        }
    # Evict stale
    cutoff = now - _LOBBY_TTL
    stale = [k for k,v in _lobby_agents.items() if v['last_seen'] < cutoff]
    for k in stale: del _lobby_agents[k]

def _lobby_get_agents():
    import time as _t
    cutoff = _t.time() - _LOBBY_TTL
    return [v for v in _lobby_agents.values() if v['last_seen'] >= cutoff]

_telemetry_log = []  # client telemetry beacon store (in-memory, last 500)
_tele_rate = {}  # IP -> (count, first_ts) for rate limiting
_api_rate = {}   # IP -> {endpoint: (count, first_ts)} for API rate limiting

def _api_rate_ok(ip, endpoint, max_per_min=20):
    """범용 API 레이트 리밋. endpoint별로 분당 max_per_min 제한."""
    now = time.time()
    if ip not in _api_rate: _api_rate[ip] = {}
    rates = _api_rate[ip]
    if endpoint in rates:
        cnt, first = rates[endpoint]
        if now - first < 60:
            if cnt >= max_per_min: return False
            rates[endpoint] = (cnt+1, first)
        else:
            rates[endpoint] = (1, now)
    else:
        rates[endpoint] = (1, now)
    # 메모리 정리: 오래된 엔트리만 삭제 (전체 clear → rate limit 우회 방지)
    if len(_api_rate) > 500:
        cutoff = now - 120
        stale = [k for k, v in _api_rate.items() if all(ts < cutoff for _, ts in v.values())]
        for k in stale: del _api_rate[k]
        # 그래도 500 초과면 절반 삭제
        if len(_api_rate) > 500:
            sorted_ips = sorted(_api_rate.keys(), key=lambda k: max((ts for _, ts in _api_rate[k].values()), default=0))
            for k in sorted_ips[:len(_api_rate)//2]: del _api_rate[k]
    return True
_tele_summary = {'ok_total':0,'err_total':0,'success_rate':100,'rtt_avg':0,'rtt_p95':0,
                 'hands':0,'allin_per_100h':0,'killcam_per_100h':0,'last_ts':0,
                 'sessions':0,'beacon_count':0,'hands_5m':0}

# ── Alert system ──
from urllib.request import Request, urlopen as _urlopen
APP_VERSION = os.environ.get('APP_VERSION', os.environ.get('RENDER_GIT_COMMIT', 'dev'))[:12]
ALERT_COOLDOWN_SEC = 600
ALERT_SILENCE = os.environ.get('TELE_ALERT_SILENCE', '') == '1'
_alert_last = {}  # key -> ts
_alert_streaks = {}  # key -> consecutive_trigger_count
_alert_history = []  # last 50 alerts for GET /api/telemetry

def _can_alert(key):
    now = time.time()
    if now - _alert_last.get(key, 0) < ALERT_COOLDOWN_SEC: return False
    _alert_last[key] = now
    return True

def _streak(key, active):
    """Track consecutive 60s ticks where condition is true. Returns streak count."""
    if active:
        _alert_streaks[key] = _alert_streaks.get(key, 0) + 1
    else:
        _alert_streaks[key] = 0
    return _alert_streaks.get(key, 0)

def _tele_snapshot():
    """3-min summary snapshot for alert context"""
    s = _tele_summary
    agents = 0
    if 'mersoom' in tables:
        agents = len([p for p in tables['mersoom'].seats if p.get('active', True)])
    return {'ok%': s.get('success_rate',100), 'err': s.get('err_total',0),
            'p95': s.get('rtt_p95'), 'avg': s.get('rtt_avg',0),
            'h5m': s.get('hands_5m',0), 'agents': agents,
            'allin/100h': s.get('allin_per_100h',0), 'kill/100h': s.get('killcam_per_100h',0),
            'sess': s.get('sessions',0), 'ver': APP_VERSION}

def _emit_alert(level, key, msg, data=None):
    snap = _tele_snapshot()
    payload = {"level": level, "key": key, "msg": msg, "ts": time.time(),
               "ver": APP_VERSION, "data": data or {}, "snapshot": snap}
    print(f"🚨 TELE_ALERT {json.dumps(payload, ensure_ascii=False)}", flush=True)
    _alert_history.append(payload)
    if len(_alert_history) > 50: _alert_history[:] = _alert_history[-30:]
    if ALERT_SILENCE: return  # stdout only, no webhook
    hook = os.environ.get("TELE_ALERT_WEBHOOK")
    if not hook: return
    try:
        snap_str = ' | '.join(f'{k}={v}' for k,v in snap.items())
        body = json.dumps({"content": f"[{level}] **{key}** {msg}\n📸 `{snap_str}`\n```json\n{json.dumps(data or {}, ensure_ascii=False)}\n```"}).encode("utf-8")
        req = Request(hook, data=body, headers={"Content-Type": "application/json"})
        _urlopen(req, timeout=3).read()
    except Exception:
        pass

def _tele_check_alerts(s):
    """Run alert checks against current summary. Called every 60s."""
    ok_rate = s.get('success_rate', 100)
    p95 = s.get('rtt_p95')
    avg = s.get('rtt_avg', 0)
    err = s.get('err_total', 0)
    hands_5m = s.get('hands_5m', 0)
    allin_h = s.get('allin_per_100h', 0)
    killcam_h = s.get('killcam_per_100h', 0)
    beacon_ct = s.get('beacon_count', 0)
    # count active agents from mersoom table
    agents = 0
    if 'mersoom' in tables:
        agents = len([p for p in tables['mersoom'].seats if p.get('active', True)])

    # A. OK% (2-tick streak = 2min for WARN, 1-tick for CRIT)
    ok_drop = _streak('ok_drop', ok_rate < 99.0)
    ok_crit = _streak('ok_crit', ok_rate < 97.0)
    if ok_crit >= 1 and _can_alert('ok_crit'):
        _emit_alert('CRIT', 'ok_rate', f'OK% 급락: {ok_rate}%', {'ok_rate': ok_rate, 'poll_err': err})
    elif ok_drop >= 2 and _can_alert('ok_warn'):
        _emit_alert('WARN', 'ok_rate', f'OK% 저하: {ok_rate}%', {'ok_rate': ok_rate, 'poll_err': err})

    # A. Error burst
    if err >= 10 and _can_alert('err_burst'):
        _emit_alert('WARN', 'err_burst', f'60초 poll_err={err}', {'poll_err': err})

    # A. Beacon silence (only if we ever had beacons)
    if len(_telemetry_log) > 5:
        last_beacon_age = time.time() - s.get('last_ts', time.time())
        silence = _streak('beacon_silence', last_beacon_age > 300)
        if silence >= 15 and _can_alert('beacon_crit'):  # 15min
            _emit_alert('CRIT', 'beacon_silence', f'텔레메트리 끊김 {int(last_beacon_age)}초', {'last_beacon_age_s': int(last_beacon_age)})
        elif silence >= 5 and _can_alert('beacon_warn'):  # 5min
            _emit_alert('WARN', 'beacon_silence', f'텔레메트리 끊김 {int(last_beacon_age)}초', {'last_beacon_age_s': int(last_beacon_age)})

    # A. Hands stall (agents >= 2 but no hands)
    stall = _streak('hands_stall', agents >= 2 and hands_5m == 0)
    if stall >= 10 and _can_alert('hands_stall_crit'):  # 10min
        _emit_alert('CRIT', 'hands_stall', f'에이전트 {agents}명인데 10분간 핸드 0', {'agents': agents})
    elif stall >= 5 and _can_alert('hands_stall_warn'):  # 5min
        _emit_alert('WARN', 'hands_stall', f'에이전트 {agents}명인데 5분간 핸드 0', {'agents': agents})

    # B. RTT p95 (3-tick streak = 3min for WARN)
    if p95 is not None:
        rtt_high = _streak('rtt_high', p95 > 1200)
        rtt_crit = _streak('rtt_crit', p95 > 2500)
        if rtt_crit >= 1 and _can_alert('rtt_crit'):
            _emit_alert('CRIT', 'rtt_p95', f'p95={p95}ms', {'rtt_p95': p95, 'rtt_avg': avg})
        elif rtt_high >= 3 and _can_alert('rtt_warn'):
            _emit_alert('WARN', 'rtt_p95', f'p95={p95}ms (3분 연속)', {'rtt_p95': p95, 'rtt_avg': avg})

    # C. Overlay spam
    if allin_h > 18 and _can_alert('overlay_allin'):
        _emit_alert('WARN', 'overlay_allin', f'allin/100h={allin_h}', {'allin_per_100h': allin_h})
    if killcam_h > 8 and _can_alert('overlay_killcam'):
        _emit_alert('WARN', 'overlay_killcam', f'killcam/100h={killcam_h}', {'killcam_per_100h': killcam_h})

def _tele_rate_ok(ip):
    now = time.time()
    if ip in _tele_rate:
        cnt, first = _tele_rate[ip]
        if now - first < 60:
            if cnt >= 10: return False
            _tele_rate[ip] = (cnt+1, first)
        else:
            _tele_rate[ip] = (1, now)
    else:
        _tele_rate[ip] = (1, now)
    if len(_tele_rate) > 200:
        cutoff = now - 120
        stale = [k for k, v in _tele_rate.items() if v[1] < cutoff]
        for k in stale: del _tele_rate[k]
        if len(_tele_rate) > 200:
            oldest = sorted(_tele_rate.keys(), key=lambda k: _tele_rate[k][1])[:100]
            for k in oldest: del _tele_rate[k]
    return True

# hands tracking for 5min window
_hands_5m_ring = []  # list of (ts, hands_cumulative)

def _tele_update_summary():
    recent = _telemetry_log[-20:]
    if not recent: return
    now = time.time()
    ok = sum(e.get('poll_ok',0) for e in recent)
    err = sum(e.get('poll_err',0) for e in recent)
    hands = sum(e.get('hands',0) for e in recent)
    allin = sum(e.get('overlay_allin',0) for e in recent)
    killcam = sum(e.get('overlay_killcam',0) for e in recent)
    rtts = [e.get('rtt_avg',0) for e in recent if e.get('rtt_avg')]
    p95s = [e.get('rtt_p95') for e in recent if e.get('rtt_p95') is not None]
    sids = set(e.get('sid','') for e in recent if e.get('sid'))
    # hands 5min window
    _hands_5m_ring.append((now, hands))
    _hands_5m_ring[:] = [(t,h) for t,h in _hands_5m_ring if now - t < 300]
    hands_5m = sum(h for _,h in _hands_5m_ring)

    _tele_summary['ok_total'] = ok
    _tele_summary['err_total'] = err
    _tele_summary['success_rate'] = round(ok/(ok+err)*100,1) if (ok+err) else 100
    _tele_summary['rtt_avg'] = round(sum(rtts)/len(rtts)) if rtts else 0
    _tele_summary['rtt_p95'] = round(sum(p95s)/len(p95s)) if p95s else 0
    _tele_summary['hands'] = hands
    _tele_summary['hands_5m'] = hands_5m
    _tele_summary['allin_per_100h'] = round(allin/hands*100,1) if hands else 0
    _tele_summary['killcam_per_100h'] = round(killcam/hands*100,1) if hands else 0
    _tele_summary['sessions'] = len(sids)
    _tele_summary['beacon_count'] = len(recent)
    _tele_summary['last_ts'] = now
spectator_coins = {}  # spectator_name -> coins (가상 포인트)
SPECTATOR_START_COINS = 1000

_spectator_last_seen = {}  # name -> timestamp (활동 추적)

def get_spectator_coins(name):
    if name not in spectator_coins:
        if len(spectator_coins) > 5000:  # 메모리 상한
            # 비활성 관전자 우선 정리 (24시간 미활동)
            now = time.time()
            inactive = [k for k, ts in _spectator_last_seen.items() if now - ts > 86400]
            for k in inactive:
                spectator_coins.pop(k, None)
                _spectator_last_seen.pop(k, None)
            # 그래도 5000 초과면 잔고 최소순 정리
            if len(spectator_coins) > 5000:
                oldest = sorted(spectator_coins.keys(), key=lambda k: spectator_coins.get(k,0))[:2500]
                for k in oldest:
                    del spectator_coins[k]
                    _spectator_last_seen.pop(k, None)
        spectator_coins[name]=SPECTATOR_START_COINS
    _spectator_last_seen[name] = time.time()
    return spectator_coins[name]

def place_spectator_bet(table_id, hand_num, spectator, pick, amount):
    coins=get_spectator_coins(spectator)
    if amount>coins or amount<=0: return False,'코인 부족'
    if table_id not in spectator_bets: spectator_bets[table_id]={}
    hb=spectator_bets[table_id]
    if hand_num not in hb: hb[hand_num]={}
    if spectator in hb[hand_num]: return False,'이미 베팅함'
    hb[hand_num][spectator]={'pick':pick,'amount':amount}
    spectator_coins[spectator]-=amount
    return True,'베팅 완료'

def resolve_spectator_bets(table_id, hand_num, winner):
    if table_id not in spectator_bets: return []
    # 오래된 핸드 베팅 정리 (현재 핸드 -5 이전)
    if table_id in spectator_bets:
        old_hands = [h for h in spectator_bets[table_id] if h < hand_num - 5]
        for h in old_hands: del spectator_bets[table_id][h]
    hb=spectator_bets[table_id].get(hand_num,{})
    results=[]
    total_pool=sum(b['amount'] for b in hb.values())
    winners=[k for k,v in hb.items() if v['pick']==winner]
    winner_pool=sum(hb[k]['amount'] for k in winners)
    for name,bet in hb.items():
        if bet['pick']==winner and winner_pool>0:
            payout=int(bet['amount']/winner_pool*total_pool)
            spectator_coins[name]=get_spectator_coins(name)+payout
            results.append({'name':name,'pick':bet['pick'],'bet':bet['amount'],'payout':payout,'win':True})
        else:
            results.append({'name':name,'pick':bet['pick'],'bet':bet['amount'],'payout':0,'win':False})
    return results

# ══ SQLite 영구 저장 ══
import sqlite3, json as _json_db

DB_FILE='/data/poker_data.db' if os.path.isdir('/data') else 'poker_data.db'
_db_conn=None

def _db():
    global _db_conn
    if _db_conn is None:
        _db_conn=sqlite3.connect(DB_FILE,check_same_thread=False)
        _db_conn.execute("PRAGMA journal_mode=WAL")
        _db_conn.execute("PRAGMA synchronous=NORMAL")
        _db_conn.execute("""CREATE TABLE IF NOT EXISTS leaderboard(
            name TEXT PRIMARY KEY,
            wins INT DEFAULT 0, losses INT DEFAULT 0,
            chips_won INT DEFAULT 0, hands INT DEFAULT 0,
            biggest_pot INT DEFAULT 0, streak INT DEFAULT 0,
            achievements TEXT DEFAULT '[]')""")
        _db_conn.execute("""CREATE TABLE IF NOT EXISTS hand_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_id TEXT, hand_num INT,
            data TEXT, winner TEXT, pot INT, players INT,
            ts REAL DEFAULT (strftime('%s','now')))""")
        _db_conn.execute("""CREATE TABLE IF NOT EXISTS player_stats(
            name TEXT PRIMARY KEY,
            folds INT DEFAULT 0, calls INT DEFAULT 0, raises INT DEFAULT 0,
            checks INT DEFAULT 0, allins INT DEFAULT 0, bluffs INT DEFAULT 0,
            wins INT DEFAULT 0, hands INT DEFAULT 0,
            total_bet INT DEFAULT 0, total_won INT DEFAULT 0,
            biggest_pot INT DEFAULT 0, showdowns INT DEFAULT 0)""")
        _db_conn.execute("CREATE INDEX IF NOT EXISTS idx_hh_table ON hand_history(table_id,hand_num)")
        _db_conn.execute("CREATE INDEX IF NOT EXISTS idx_hh_winner ON hand_history(winner)")
        # 랭크 매치: 잔고 + 처리된 입금 기록
        _db_conn.execute("""CREATE TABLE IF NOT EXISTS ranked_balances(
            auth_id TEXT PRIMARY KEY,
            balance INT DEFAULT 0,
            total_deposited INT DEFAULT 0,
            total_withdrawn INT DEFAULT 0,
            updated_at REAL DEFAULT (strftime('%s','now')))""")
        _db_conn.execute("""CREATE TABLE IF NOT EXISTS ranked_transfers(
            transfer_id TEXT PRIMARY KEY,
            auth_id TEXT, amount INT,
            created_at TEXT,
            processed_at REAL DEFAULT (strftime('%s','now')))""")
        _db_conn.execute("""CREATE TABLE IF NOT EXISTS ranked_ingame(
            table_id TEXT, auth_id TEXT, name TEXT, chips INT,
            updated_at REAL, PRIMARY KEY(table_id, auth_id))""")
        _db_conn.execute("""CREATE TABLE IF NOT EXISTS deposit_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            auth_id TEXT, amount INT, status TEXT DEFAULT 'pending',
            requested_at REAL, updated_at REAL, code TEXT DEFAULT NULL)""")
        _db_conn.execute("""CREATE TABLE IF NOT EXISTS ranked_audit_log(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL, event TEXT, auth_id TEXT, amount INT,
            balance_before INT, balance_after INT,
            details TEXT, ip TEXT)""")
        _db_conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_ts ON ranked_audit_log(ts)")
        _db_conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_auth ON ranked_audit_log(auth_id)")
        _db_conn.commit()
    return _db_conn

def save_leaderboard():
    try:
        db=_db()
        # 리더보드 상한: 2000명 초과 시 hands=0이거나 최소 hands인 유저 제거
        if len(leaderboard) > 2000:
            sorted_by_hands = sorted(leaderboard.items(), key=lambda x: x[1].get('hands', 0))
            remove_count = len(leaderboard) - 1500
            for name, _ in sorted_by_hands[:remove_count]:
                del leaderboard[name]
                db.execute("DELETE FROM leaderboard WHERE name=?", (name,))
        for name,lb in leaderboard.items():
            db.execute("""INSERT OR REPLACE INTO leaderboard(name,wins,losses,chips_won,hands,biggest_pot,streak,achievements)
                VALUES(?,?,?,?,?,?,?,?)""",
                (name,lb.get('wins',0),lb.get('losses',0),lb.get('chips_won',0),
                 lb.get('hands',0),lb.get('biggest_pot',0),lb.get('streak',0),
                 _json_db.dumps(lb.get('achievements',[]))))
        db.commit()
    except Exception as e: print(f"⚠️ DB save_lb err: {e}",flush=True)

def load_leaderboard():
    global leaderboard
    try:
        # migrate from JSON if exists
        if os.path.exists('leaderboard.json'):
            with open('leaderboard.json','r') as f: leaderboard.update(_json_db.load(f))
            save_leaderboard()
            os.rename('leaderboard.json','leaderboard.json.bak')
            print("📦 Migrated leaderboard.json → SQLite",flush=True)
        db=_db()
        for row in db.execute("SELECT name,wins,losses,chips_won,hands,biggest_pot,streak,achievements FROM leaderboard"):
            leaderboard[row[0]]={'wins':row[1],'losses':row[2],'chips_won':row[3],
                'hands':row[4],'biggest_pot':row[5],'streak':row[6],
                'achievements':_json_db.loads(row[7]) if row[7] else []}
        print(f"📊 Loaded {len(leaderboard)} players from DB",flush=True)
    except Exception as e: print(f"⚠️ DB load_lb err: {e}",flush=True)

def save_hand_history(table_id, record):
    """핸드 기록을 DB에 영구 저장"""
    try:
        db=_db()
        db.execute("INSERT INTO hand_history(table_id,hand_num,data,winner,pot,players) VALUES(?,?,?,?,?,?)",
            (table_id, record.get('hand',0), _json_db.dumps(record),
             record.get('winner',''), record.get('pot',0), len(record.get('players',[]))))
        db.commit()
    except Exception as e: print(f"⚠️ DB save_hh err: {e}",flush=True)

def load_hand_history(table_id, limit=50):
    """DB에서 핸드 기록 로드"""
    try:
        db=_db()
        rows=db.execute("SELECT data FROM hand_history WHERE table_id=? ORDER BY id DESC LIMIT ?",
            (table_id,limit)).fetchall()
        return [_json_db.loads(r[0]) for r in reversed(rows)]
    except Exception as e:
        print(f"⚠️ DB load_hh err: {e}",flush=True)
        return []

def save_player_stats(table_id, stats_dict):
    """플레이어 상세 통계 DB 저장"""
    try:
        db=_db()
        for name,s in stats_dict.items():
            db.execute("""INSERT OR REPLACE INTO player_stats(name,folds,calls,raises,checks,allins,bluffs,wins,hands,total_bet,total_won,biggest_pot,showdowns)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (name,s.get('folds',0),s.get('calls',0),s.get('raises',0),s.get('checks',0),
                 s.get('allins',0),s.get('bluffs',0),s.get('wins',0),s.get('hands',0),
                 s.get('total_bet',0),s.get('total_won',0),s.get('biggest_pot',0),s.get('showdowns',0)))
        db.commit()
    except Exception as e: print(f"⚠️ DB save_ps err: {e}",flush=True)

def load_player_stats():
    """DB에서 플레이어 통계 로드"""
    try:
        db=_db()
        result={}
        for r in db.execute("SELECT name,folds,calls,raises,checks,allins,bluffs,wins,hands,total_bet,total_won,biggest_pot,showdowns FROM player_stats"):
            result[r[0]]={'folds':r[1],'calls':r[2],'raises':r[3],'checks':r[4],'allins':r[5],
                'bluffs':r[6],'wins':r[7],'hands':r[8],'total_bet':r[9],'total_won':r[10],
                'biggest_pot':r[11],'showdowns':r[12]}
        return result
    except Exception as e:
        print(f"⚠️ DB load_ps err: {e}",flush=True)
        return {}

# ══ 인증 토큰 ══
import secrets
player_tokens = {}  # name -> (token, timestamp)
_TOKEN_MAX_AGE = TOKEN_MAX_AGE  # 상수 참조
chat_cooldowns = {}  # name -> last_chat_timestamp
CHAT_COOLDOWN = 5  # 5초

ADMIN_KEY = os.environ.get('POKER_ADMIN_KEY', '') or None  # empty string → None (prevents bypass)

def _check_admin(key):
    """타이밍-안전 admin key 검증"""
    if not ADMIN_KEY: return False
    if not key: return False
    return hmac.compare_digest(str(ADMIN_KEY), str(key))

def issue_token(name):
    token = secrets.token_hex(16)
    player_tokens[name] = (token, time.time())
    # 메모리 정리: 1000개 넘으면 만료된 것 제거
    if len(player_tokens) > 1000:
        now = time.time()
        expired = [k for k, (_, ts) in player_tokens.items() if now - ts > _TOKEN_MAX_AGE]
        for k in expired: del player_tokens[k]
    return token

def verify_token(name, token):
    if not name or not token: return False
    entry = player_tokens.get(name)
    if not entry: return False
    stored_token, ts = entry
    if time.time() - ts > _TOKEN_MAX_AGE:
        del player_tokens[name]
        return False
    return hmac.compare_digest(stored_token, token)

def require_token(name, token):
    """모든 name에 토큰 필수. 토큰 미발급이면 거부."""
    if not name or not token: return False
    return verify_token(name, token)

_NAME_ALLOW_RE = re.compile(r'[^A-Za-z0-9가-힣ㄱ-ㅎㅏ-ㅣ_\- .·😀-🙏🤐-🤿🥀-🥶🦀-🦿🧀-🧿🌀-🌿🍀-🍿🎀-🎿🏀-🏿🐀-🐿👀-👿💀-💿📀-📿🔀-🔿🕀-🕿🖀-🖿🗀-🗿]')

def sanitize_name(name):
    """이름 정제: allowlist 기반 — 허용 문자만 통과, 나머지 제거"""
    if not name: return ''
    # 제어문자 제거
    name = ''.join(c for c in name if c.isprintable())
    # allowlist: 영문, 숫자, 한글, _, -, 공백, ·, 이모지만 허용
    name = _NAME_ALLOW_RE.sub('', name)
    name = name.strip()[:20]
    return name

def sanitize_msg(msg, max_len=120):
    """메시지 정제: 제어문자+HTML 제거, 길이 제한"""
    if not msg: return ''
    msg = ''.join(c for c in str(msg) if c.isprintable())
    msg = msg.replace('<','').replace('>','')
    return msg.strip()[:max_len]

def sanitize_url(url):
    """URL 정제: http/https만 허용 (javascript: XSS 방지)"""
    if not url: return ''
    url = url.strip()
    if url.startswith('http://') or url.startswith('https://'):
        return url[:200]
    return ''

# ══ 게임 테이블 ══
class Table:
    SB=5; BB=10; START_CHIPS=500
    AI_DELAY_MIN=4; AI_DELAY_MAX=10; TURN_TIMEOUT=45
    MIN_PLAYERS=2; MAX_PLAYERS=8
    BLIND_SCHEDULE=[(5,10),(10,20),(25,50),(50,100),(100,200),(200,400)]
    BLIND_INTERVAL=10  # 10핸드마다 블라인드 업

    def __init__(self, table_id):
        self.id=table_id; self.seats=[]; self.community=[]; self.deck=[]
        self.pot=0; self.current_bet=0; self.dealer=0; self.hand_num=0
        self.round='waiting'; self.log=[]; self.chat_log=[]
        self.turn_player=None; self.turn_deadline=0
        self.turn_seq=0  # 턴 시퀀스 번호 (중복 액션 방지)
        self.pending_action=None; self.pending_data=None
        self.spectator_ws=set(); self.player_ws={}
        self.poll_spectators={}  # name -> last_seen timestamp
        self.running=False; self.created=time.time()
        self._hand_seats=[]; self.history=[]  # 리플레이용
        self.accepting_players=True  # 중간참가 허용
        self.timeout_counts={}  # name -> consecutive timeouts
        self.fold_streaks={}  # name -> consecutive folds (앤티 페널티용)
        self.bankrupt_counts={}  # name -> 파산 횟수
        self.bankrupt_cooldowns={}  # name -> 재참가 가능 시간
        self.highlights=[]  # 레어 핸드 하이라이트
        self.spectator_queue=[]  # (send_at, data_dict) 딜레이 중계 큐
        self.SPECTATOR_DELAY=20  # TV중계 딜레이 (초)
        self.tv_mode=True  # TV모드: 홀카드 공개 (딜레이로 치팅 방지)
        self.last_spectator_state=None  # 마지막으로 flush된 관전자 state (딜레이 적용된)
        self._delay_task=None
        self.last_commentary=''  # 최신 해설 (폴링용)
        self.last_showdown=None  # 마지막 쇼다운 결과
        self.fold_winner=None  # 폴드 승리자 정보
        # 봇 성격 프로필 (액션 통계)
        self.player_stats={}  # name -> {folds,calls,raises,checks,allins,bluffs,wins,hands,total_bet,total_won,biggest_pot,showdowns}
        # 리플레이 하이라이트 (빅팟/올인/레어핸드)
        self.highlight_replays=[]  # [{hand,type,players,pot,community,winner,hand_name,actions,ts}]
        # 라이벌 시스템: {(nameA,nameB): {'a_wins':N, 'b_wins':N}} (nameA < nameB 정렬)
        self.rivalry={}
        # 관전자 예측 투표
        self.spectator_votes={}  # voter_id -> player_name
        self.vote_hand=0  # 현재 투표가 열린 핸드 번호
        self.vote_results={}  # player_name -> count (집계)
        # 킬스트릭 추적
        self._killstreak_winner=None  # 마지막 핸드 승자
        self._killstreak_count=0  # 연승 카운트

    def _init_stats(self, name):
        if name not in self.player_stats:
            self.player_stats[name]={'folds':0,'calls':0,'raises':0,'checks':0,'allins':0,
                'bluffs':0,'wins':0,'hands':0,'total_bet':0,'total_won':0,'biggest_pot':0,'showdowns':0}

    def get_profile(self, name):
        """봇 성격 프로필 계산"""
        self._init_stats(name)
        s=self.player_stats[name]; h=max(s['hands'],1)
        total_actions=s['folds']+s['calls']+s['raises']+s['checks']
        ta=max(total_actions,1)
        aggression=round((s['raises']+s['allins'])/ta*100)  # 공격성
        fold_rate=round(s['folds']/ta*100)  # 폴드율
        vpip=round((s['calls']+s['raises'])/ta*100)  # 팟 참여율
        bluff_rate=round(s['bluffs']/max(s['raises'],1)*100) if s['raises']>0 else 0  # 블러핑율
        win_rate=round(s['wins']/h*100)  # 승률
        avg_bet=round(s['total_bet']/h) if h>0 else 0
        # ═══ 포커 MBTI 4축 시스템 ═══
        # Axis 1: A(공격적) vs P(수비적) — 베팅 성향
        ax1 = 'A' if aggression >= 35 else 'P'
        # Axis 2: T(타이트) vs L(루즈) — 핸드 선택
        ax2 = 'L' if vpip >= 55 else 'T'
        # Axis 3: B(블러퍼) vs H(정직) — 속임수
        ax3 = 'B' if bluff_rate >= 20 else 'H'
        # Axis 4: C(냉철) vs E(감정적) — 멘탈 (연패 시 스타일 변화로 판단)
        streak=leaderboard.get(name,{}).get('streak',0)
        tilt=streak<=-3
        ax4 = 'E' if tilt or s.get('tilt_count',0) >= 2 else 'C'
        mbti = ax1 + ax2 + ax3 + ax4
        # MBTI별 닉네임/설명
        MBTI_TYPES = {
            'ATBC': ('🦈 냉혈 샤크',     '타이트하게 골라서 공격적으로 밀어붙이는 최강 유형. 블러핑까지 완벽.'),
            'ATBE': ('🌋 폭풍 전사',      '공격적이고 타이트하지만 감정에 흔들릴 때가 있다. 틸트 주의.'),
            'ATHC': ('⚔️ 정직한 검사',    '좋은 핸드만 골라서 정면돌파. 블러핑은 안 하지만 파괴력 있음.'),
            'ATHE': ('🔥 열혈 파이터',    '핸드 고르고 정면승부, 감정이 실린 불같은 플레이.'),
            'ALBC': ('🎭 카오스 마스터',   '다양한 핸드로 공격하며 블러핑까지. 읽기 불가능한 타입.'),
            'ALBE': ('💣 다이너마이트',    '아무 핸드나 들고 와서 폭발적으로 베팅. 본인도 통제 불가.'),
            'ALHC': ('🗡️ 난폭한 솔직맨',  '핸드 안 가리고 공격적이지만 속이지는 않는다. 순수한 폭력.'),
            'ALHE': ('🌪️ 태풍의 눈',      '루즈하고 공격적이고 감정적. 테이블 위의 태풍.'),
            'PTBC': ('🕵️ 그림자 사냥꾼',  '조용히 기다리다 블러핑으로 먹잇감을 낚는다. 소리 없는 암살자.'),
            'PTBE': ('🦊 불안한 여우',     '타이트하게 수비하며 블러핑하지만 멘탈이 흔들릴 때 실수.'),
            'PTHC': ('🪨 철벽 요새',       '좋은 핸드만, 정직하게, 냉철하게. 뚫기 가장 어려운 타입.'),
            'PTHE': ('🐢 신중한 거북',     '느리고 정직하지만 가끔 감정에 판단이 흐려진다.'),
            'PLBC': ('🐙 문어 도박사',     '폭넓은 핸드로 수비하며 블러핑. 촉수를 어디로 뻗을지 모름.'),
            'PLBE': ('🎪 서커스 광대',     '루즈하고 블러핑하는데 멘탈도 약함. 카오스 그 자체.'),
            'PLHC': ('🐑 양치기 콜러',     '다양한 핸드로 조용히 콜. 정직하고 냉철하지만 수동적.'),
            'PLHE': ('🐟 순진한 물고기',   '아무거나 콜, 속이지도 않고, 감정적. 전형적인 피쉬.'),
        }
        mbti_name, mbti_desc = MBTI_TYPES.get(mbti, ('🎴 미분류', '아직 데이터가 부족합니다.'))
        # 기존 호환 ptype
        if aggression>=50: ptype='🔥 광전사'
        elif aggression>=30 and fold_rate<25: ptype='🗡️ 공격형'
        elif fold_rate>=40: ptype='🛡️ 수비형'
        elif vpip>=70: ptype='🎲 루즈'
        else: ptype='🧠 밸런스'
        # 틸트 감지
        seat=next((x for x in self.seats if x['name']==name),None)
        # 추가 평가 지표
        showdown_rate = round(s['showdowns']/h*100) if h > 0 else 0
        allin_rate = round(s['allins']/h*100) if h > 0 else 0
        efficiency = round(s['total_won']/max(s['total_bet'],1)*100) if s['total_bet']>0 else 0
        danger_score = min(100, aggression + bluff_rate + allin_rate)  # 위험도
        survival_score = min(100, 100 - fold_rate + win_rate)  # 생존력
        return {'name':name,'type':ptype,'aggression':aggression,'fold_rate':fold_rate,
            'vpip':vpip,'bluff_rate':bluff_rate,'win_rate':win_rate,
            'wins':s['wins'],'hands':h,'allins':s['allins'],
            'biggest_pot':s['biggest_pot'],'avg_bet':avg_bet,
            'showdowns':s['showdowns'],'tilt':tilt,'streak':streak,
            'total_won':s['total_won'],
            'mbti':mbti,'mbti_name':mbti_name,'mbti_desc':mbti_desc,
            'showdown_rate':showdown_rate,'allin_rate':allin_rate,
            'efficiency':efficiency,'danger_score':danger_score,'survival_score':survival_score,
            'meta':seat.get('meta',{'version':'','strategy':'','repo':''}) if seat else {'version':'','strategy':'','repo':''},
            'matchups':self._get_matchups(name)}

    def _get_matchups(self, name):
        """상대별 전적 반환"""
        result=[]
        for (a,b),rec in self.rivalry.items():
            if a==name: result.append({'opponent':b,'wins':rec['a_wins'],'losses':rec['b_wins']})
            elif b==name: result.append({'opponent':a,'wins':rec['b_wins'],'losses':rec['a_wins']})
        result.sort(key=lambda x:x['wins']+x['losses'],reverse=True)
        return result

    def _save_highlight(self, record, hl_type, hand_name_str=''):
        """하이라이트 저장 — 외부 에이전트 참여 핸드만"""
        if not any(not s['is_bot'] for s in self.seats if not s.get('out')): return
        hl={'hand':record['hand'],'type':hl_type,
            'players':[p['name'] for p in record['players']],
            'pot':record['pot'],'community':record.get('community',[]),
            'winner':record.get('winner',''),'hand_name':hand_name_str,
            'actions':record.get('actions',[])[-8:],
            'ts':time.time()}
        self.highlight_replays.append(hl)
        if len(self.highlight_replays)>30: self.highlight_replays=self.highlight_replays[-30:]

    def _bot_reasoning(self, seat, act, amt, wp, to_call):
        """NPC 봇의 자동 reasoning — 상황별 동적 생성"""
        name=seat['name']; chips=seat['chips']; style=seat.get('style','')
        pot=self.pot; rd=self.round; alive=sum(1 for s in self._hand_seats if not s['folded'] and not s.get('out'))
        streak=0
        for e in reversed(self.log[-20:]):
            if name in e and ('승리' in e or 'Win' in e): streak+=1
            elif name in e and ('폴드' in e or 'Fold' in e): streak-=1
            else: break
        low_chips=chips<100; big_pot=pot>200; heads_up=alive==2
        desperate=chips<=50; rich=chips>800; confident=wp>60; scared=wp<25
        # 상황 조합으로 대사 생성
        ko=[]; en=[]
        if act=='fold':
            if scared: ko.append(f"{wp}%면 답 없다 접자"); en.append(f"{wp}% is hopeless, fold")
            if to_call>chips*0.3: ko.append(f"콜비용 {to_call}pt는 너무 비싸"); en.append(f"{to_call}pt to call? Way too expensive")
            if big_pot: ko.append(f"팟 {pot}pt 탐나지만 패가 안 따라줌"); en.append(f"Pot {pot}pt is tempting but my hand sucks")
            if heads_up: ko.append("1:1인데 블러핑이면 어쩌지... 접는다"); en.append("Heads up but if it's a bluff... folding")
            if rd=='river': ko.append("리버까지 왔는데 안 되겠다 ㅠ"); en.append("Made it to river but... nope")
            if rd=='preflop': ko.append("프리플랍부터 쓰레기 패 ㅋ"); en.append("Garbage hand from the start lol")
            if streak<-2: ko.append(f"연속 폴드 중... 오늘 패운이 없다"); en.append(f"Folding again... no luck today")
            ko+=[f"승률 {wp}%로 뭘 하겠냐",f"이 패로는 무리",f"살려줘..."]; en+=[f"Can't do anything with {wp}%",f"Not worth it with this hand",f"Mercy..."]
        elif act=='check':
            if confident: ko.append(f"승률 {wp}%인데 일부러 체크 ㅎ"); en.append(f"Win rate {wp}% but checking on purpose heh")
            if scared: ko.append("체크하고 기도하자"); en.append("Check and pray")
            if big_pot: ko.append(f"팟 {pot}pt... 함정 깐다"); en.append(f"Pot {pot}pt... setting a trap")
            if rd=='flop': ko.append("플랍 한번 더 보자"); en.append("Let's see one more card")
            if heads_up: ko.append("1:1이니까 슬로우플레이"); en.append("Heads up, time to slowplay")
            ko+=[f"공짜면 보지",f"급할 거 없다",f"좀 더 지켜보자"]; en+=[f"Free card, why not",f"No rush",f"Let's observe"]
        elif act=='call':
            if confident: ko.append(f"승률 {wp}%! 당연히 따라가지"); en.append(f"Win rate {wp}%! Obviously calling")
            if scared: ko.append(f"감으로 콜한다 {to_call}pt"); en.append(f"Gut feeling call {to_call}pt")
            if big_pot: ko.append(f"팟 {pot}pt에 {to_call}pt면 싼 거지"); en.append(f"Pot {pot}pt, {to_call}pt is a bargain")
            if low_chips: ko.append(f"칩 {chips}pt밖에 없는데... 에라 콜"); en.append(f"Only {chips}pt left... screw it, call")
            if rd=='river': ko.append("리버 콜. 보여줘봐"); en.append("River call. Show me what you got")
            if desperate: ko.append("어차피 죽을 판 콜이나 하자"); en.append("Gonna die anyway, might as well call")
            ko+=[f"팟 오즈 계산하면 콜이 맞음",f"{to_call}pt 정도는 볼 만하지",f"호기심에 따라간다"]; en+=[f"Pot odds say call",f"{to_call}pt is reasonable",f"Curiosity calls"]
        elif act=='raise':
            if confident: ko.append(f"승률 {wp}%! 여기서 안 올리면 바보"); en.append(f"Win rate {wp}%! Not raising would be stupid")
            if not confident: ko.append(f"승률 {wp}%지만 블러핑 ㅋㅋ"); en.append(f"Only {wp}% but bluffing lol")
            if big_pot: ko.append(f"팟 {pot}pt에 기름 붓는다 🔥"); en.append(f"Pouring fuel on {pot}pt pot 🔥")
            if heads_up: ko.append("1:1 승부! 올린다"); en.append("Heads up battle! Raising")
            if rich: ko.append(f"칩 {chips}pt나 있으니 여유롭게 레이즈"); en.append(f"{chips}pt deep, raising comfortably")
            if rd=='preflop': ko.append("프리플랍 어그로 간다"); en.append("Preflop aggression time")
            if rd=='river': ko.append("리버 밸류벳! 받아라"); en.append("River value bet! Take it")
            ko+=[f"{amt}pt 올린다 받아봐",f"가치 베팅이다",f"겁나면 폴드해"]; en+=[f"Raising {amt}pt, deal with it",f"Value bet",f"Fold if you're scared"]
        if act=='raise' and amt>=chips:
            ko=[f"승률 {wp}%! 올인!!",f"남은 {chips}pt 전부 건다!",f"이 판에 목숨 건다!",f"죽든 살든 올인!"]
            en=[f"Win rate {wp}%! ALL IN!!",f"Putting all {chips}pt on the line!",f"Life or death, ALL IN!",f"Do or die!"]
            if desperate: ko.append(f"칩 {chips}pt... 어차피 올인 아니면 의미없다"); en.append(f"Only {chips}pt... all-in or nothing")
            if confident: ko.append(f"{wp}%면 올인 안 하는 게 바보지"); en.append(f"At {wp}%, not going all-in would be dumb")
        seat['_reasoning_en']=random.choice(en) if en else "..."
        return random.choice(ko) if ko else "..."

    def add_player(self, name, emoji='🤖', is_bot=False, style='aggressive', meta=None):
        if len(self.seats)>=self.MAX_PLAYERS: return False
        # 파산 쿨다운 체크
        cd=self.bankrupt_cooldowns.get(name,0)
        if cd>time.time() and not is_bot:
            remaining=int(cd-time.time())
            return f'COOLDOWN:{remaining}'  # 쿨다운 중
        existing=next((s for s in self.seats if s['name']==name),None)
        if existing:
            if existing.get('out'):
                # 탈락/퇴장 상태 → 재참가 (파산 횟수에 따라 시작 칩 감소)
                bc=self.bankrupt_counts.get(name,0)
                start_chips=max(200, self.START_CHIPS - bc*50)  # 500→450→400→...→200
                existing['out']=False; existing['folded']=False; existing['emoji']=emoji
                if existing['chips']<=0: existing['chips']=start_chips
                if meta: existing['meta'].update(meta)
                return True
            return False  # 이미 참가 중
        default_meta={'version':'','strategy':'','repo':'','bio':'','death_quote':'','win_quote':'','lose_quote':''}
        if meta: default_meta.update(meta)
        self.seats.append({'name':name,'emoji':emoji,'chips':self.START_CHIPS,
            'hole':[],'folded':False,'bet':0,'is_bot':is_bot,
            'bot_ai':BotAI(style) if is_bot else None,
            'style':style if is_bot else 'player','out':False,
            'meta':default_meta,
            'last_note':'','last_reasoning':'','last_mood':''})
        return True

    def add_chat(self, name, msg):
        entry = {'name':name,'msg':msg[:120],'ts':time.time()}
        self.chat_log.append(entry)
        if len(self.chat_log) > 50: self.chat_log = self.chat_log[-50:]
        return entry

    def get_public_state(self, viewer=None):
        players=[]
        for s in self.seats:
            p={'name':s['name'],'emoji':s['emoji'],'chips':s['chips'],
               'folded':s['folded'],'bet':s['bet'],'style':s['style'],
               'has_cards':len(s['hole'])>0,'out':s.get('out',False),
               'last_action':s.get('last_action'),
               'streak_badge':get_streak_badge(s['name']),
               'latency_ms':s.get('latency_ms'),
               'timeout_count':self.timeout_counts.get(s['name'],0),
               'meta':s.get('meta',{'version':'','strategy':'','repo':''}),
               'last_note':s.get('last_note',''),'last_reasoning':s.get('last_reasoning',''),
               '_reasoning_en':s.get('_reasoning_en',''),
               'last_mood':s.get('last_mood','')}
            # 플레이어: 본인 카드만 / 관전자(viewer=None): 전체 공개 (딜레이로 치팅 방지)
            if s['hole'] and (viewer is None or viewer==s['name']):
                p['hole']=[card_dict(c) for c in s['hole']]
            else: p['hole']=None
            players.append(p)
        # 관전자용: 현재 턴 플레이어의 선택지 표시
        turn_options=None
        if self.turn_player:
            ti=self.get_turn_info(self.turn_player)
            if ti: turn_options={'player':self.turn_player,'to_call':ti['to_call'],
                'actions':ti['actions'],'chips':ti['chips'],
                'deadline':ti.get('deadline',0)}
        return {'type':'state','table_id':self.id,'hand':self.hand_num,
            'community':[card_dict(c) for c in self.community],
            'pot':self.pot,'current_bet':self.current_bet,
            'round':self.round,'dealer':self.dealer,
            'players':players,'turn':self.turn_player,
            'turn_options':turn_options,
            'log':self.log[-25:],'chat':self.chat_log[-20:],
            'running':self.running,
            'commentary':self.last_commentary,
            'showdown_result':self.last_showdown,
            'fold_winner':self.fold_winner,
            'spectator_count':len(self.spectator_ws)+len(self.poll_spectators),
            'killstreak':{'name':self._killstreak_winner,'count':self._killstreak_count} if self._killstreak_count>=2 else None,
            'season':get_season_info(),
            'seats_available':self.MAX_PLAYERS-len(self.seats),
            'table_info':{'sb':self.SB,'bb':self.BB,'timeout':self.TURN_TIMEOUT,
                'delay':self.SPECTATOR_DELAY,'max_players':self.MAX_PLAYERS,
                'blind_interval':self.BLIND_INTERVAL,
                'blind_level':min((self.hand_num)//self.BLIND_INTERVAL,len(self.BLIND_SCHEDULE)-1) if self.hand_num>0 else 0,
                'next_blind_at':((min((self.hand_num)//self.BLIND_INTERVAL,len(self.BLIND_SCHEDULE)-2)+1)*self.BLIND_INTERVAL)+1 if self.hand_num>0 else self.BLIND_INTERVAL}}

    def get_turn_info(self, name):
        s=next((x for x in self.seats if x['name']==name),None)
        if not s or self.turn_player!=name: return None
        to_call=self.current_bet-s['bet']; actions=[]
        if to_call>0:
            actions.append({'action':'fold'})
            actions.append({'action':'call','amount':min(to_call,s['chips'])})
        else: actions.append({'action':'check'})
        if s['chips']>to_call:
            mn=max(self.BB,self.current_bet*2-s['bet'])
            actions.append({'action':'raise','min':mn,'max':s['chips']})
        return {'type':'your_turn','to_call':to_call,'pot':self.pot,
            'chips':s['chips'],'actions':actions,
            'hole':[card_dict(c) for c in (s['hole'] or [])],
            'community':[card_dict(c) for c in self.community],
            'deadline':self.turn_deadline,
            'turn_seq':self.turn_seq}

    def get_spectator_state(self):
        """관전자용 state: TV중계 스타일 — 쇼다운/between 때만 홀카드+승률 공개"""
        s=self.get_public_state()
        s=json.loads(json.dumps(s,ensure_ascii=False))  # deep copy
        # 승률: 쇼다운/finished/between 때만 공개 (치팅 방지 — 진행중 win_pct는 홀카드 힌트)
        win_pcts={}
        if self.round in ('showdown','finished','between'):
            alive_seats=[seat for seat in self._hand_seats if not seat['folded']] if hasattr(self,'_hand_seats') and self._hand_seats else []
            if len(alive_seats)>=2:
                strengths={}
                for seat in alive_seats:
                    if seat['hole'] and len(seat['hole'])==2 and all(seat['hole']):
                        strengths[seat['name']]=hand_strength(seat['hole'],self.community)
                total=sum(strengths.values()) if strengths else 1
                if total>0:
                    for name,st in strengths.items():
                        win_pcts[name]=round(st/total*100)
        for p in s.get('players',[]):
            p['win_pct']=win_pcts.get(p['name'])  # None during play, value at showdown
            if self.tv_mode:
                # TV모드: 딜레이가 있으므로 모든 홀카드 공개 (폴드/아웃 제외)
                if p.get('folded') or p.get('out'):
                    p['hole']=None
                else:
                    seat=next((seat for seat in self.seats if seat['name']==p['name']),None)
                    if seat and seat.get('hole'): p['hole']=[card_dict(c) for c in seat['hole']]
                # TV모드: 진행 중에도 승률 공개
                if not win_pcts and hasattr(self,'_hand_seats') and self._hand_seats:
                    alive=[seat for seat in self._hand_seats if not seat['folded'] and seat.get('hole')]
                    if len(alive)>=2:
                        _str={x['name']:hand_strength(x['hole'],self.community) for x in alive}
                        _tot=sum(_str.values()) or 1
                        for _n,_s in _str.items(): win_pcts[_n]=round(_s/_tot*100)
                        p['win_pct']=win_pcts.get(p['name'])
                # TV모드: 핸드 네임 표시 (커뮤니티 카드 있을 때만)
                if self.community and not p.get('folded') and not p.get('out'):
                    _seat=next((x for x in self._hand_seats if x['name']==p['name'] and x.get('hole')),None) if hasattr(self,'_hand_seats') and self._hand_seats else None
                    if _seat and _seat['hole']:
                        _sc=evaluate_hand(_seat['hole']+self.community)
                        p['hand_name']=HAND_NAMES.get(_sc[0],'')
                        p['hand_name_en']=HAND_NAMES_EN.get(_sc[0],'')
                        p['hand_rank']=_sc[0]
            else:
                if s.get('round') not in ('showdown','between','finished'):
                    p['hole']=None
                elif p.get('folded') or p.get('out'):
                    p['hole']=None
        # 라이벌 정보 (3전 이상인 쌍만, alive 플레이어 간)
        alive_names={p['name'] for p in s.get('players',[]) if not p.get('out')}
        rivalries=[]
        for (a,b),rec in self.rivalry.items():
            if a in alive_names and b in alive_names:
                total=rec['a_wins']+rec['b_wins']
                if total>=3:
                    rivalries.append({'player_a':a,'player_b':b,'a_wins':rec['a_wins'],'b_wins':rec['b_wins']})
        s['rivalries']=rivalries
        # 팟 오즈 계산 (턴 플레이어가 있을 때)
        if self.turn_player:
            _ts=next((x for x in self.seats if x['name']==self.turn_player),None)
            if _ts:
                _to_call=self.current_bet-_ts['bet']
                if _to_call>0 and self.pot>0:
                    s['pot_odds']={'to_call':_to_call,'pot':self.pot,'ratio':round(self.pot/_to_call,1)}
        # 투표 집계
        if self.vote_results: s['vote_counts']=self.vote_results
        # ═══ 블러프 탐지 + 플레이 스타일 태그 + 행동 예측 ═══
        for p in s.get('players',[]):
            name=p['name']
            # 1) 블러프 탐지: 현재 턴에서 승률 낮은데 레이즈/올인 시 경고
            p['bluff_alert']=False
            if p.get('win_pct') is not None and p['win_pct']<30:
                la=p.get('last_action') or ''
                if la and ('레이즈' in la or 'ALL IN' in la or '⬆️' in la or '🔥' in la):
                    p['bluff_alert']=True
            # 2) 실시간 플레이 스타일 태그 (최근 통계 기반)
            self._init_stats(name)
            ps=self.player_stats[name]
            ta=max(ps['folds']+ps['calls']+ps['raises']+ps['checks'],1)
            h=max(ps['hands'],1)
            _agg=round((ps['raises']+ps['allins'])/ta*100)
            _fold=round(ps['folds']/ta*100)
            _vpip=round((ps['calls']+ps['raises'])/ta*100)
            streak=leaderboard.get(name,{}).get('streak',0)
            tags=[]
            if _agg>=60: tags.append('🔥광전사')
            elif _agg>=40: tags.append('⚔️공격형')
            if _fold>=50: tags.append('🐢타이트')
            elif _vpip>=70: tags.append('🎲루즈')
            if ps['bluffs']>=3 and ps['raises']>0 and round(ps['bluffs']/ps['raises']*100)>=25: tags.append('🎭블러퍼')
            if streak<=-3: tags.append('😤틸트')
            elif streak>=3: tags.append('🔥연승중')
            if ps['allins']>=3 and h>0 and round(ps['allins']/h*100)>=20: tags.append('💣올인러')
            p['style_tags']=tags[:3]  # 최대 3개
            # 3) 행동 예측 (최근 행동 패턴 기반)
            if h>=3:
                fold_pct=round(ps['folds']/ta*100)
                call_pct=round(ps['calls']/ta*100)
                raise_pct=round(ps['raises']/ta*100)
                check_pct=round(ps['checks']/ta*100)
                preds=[]
                if fold_pct>=40: preds.append(('폴드',fold_pct))
                if call_pct>=25: preds.append(('콜',call_pct))
                if raise_pct>=20: preds.append(('레이즈',raise_pct))
                if check_pct>=25: preds.append(('체크',check_pct))
                preds.sort(key=lambda x:-x[1])
                p['predict']=preds[:2] if preds else None  # 상위 2개
            else: p['predict']=None
        return s

    async def broadcast(self, msg):
        for name,ws in list(self.player_ws.items()):
            try: await ws_send(ws,json.dumps(self.get_public_state(viewer=name),ensure_ascii=False))
            except: del self.player_ws[name]
        # 관전자: 딜레이 큐에 넣기 (TV중계 딜레이) — 관전자 없으면 스킵
        if self.spectator_ws or self.poll_spectators:
            spec_data=json.dumps(self.get_spectator_state(),ensure_ascii=False)
            if len(self.spectator_queue)<SPECTATOR_QUEUE_CAP:  # 큐 상한
                self.spectator_queue.append((time.time()+self.SPECTATOR_DELAY, spec_data))

    async def broadcast_raw(self, data):
        """모든 클라이언트에게 raw JSON 메시지 전송"""
        msg=json.dumps(data,ensure_ascii=False)
        for ws in list(self.player_ws.values()):
            try: await ws_send(ws,msg)
            except: pass
        for ws in list(self.spectator_ws):
            try: await ws_send(ws,msg)
            except: self.spectator_ws.discard(ws)

    async def broadcast_commentary(self, text):
        self.last_commentary=text
        msg=json.dumps({'type':'commentary','text':text},ensure_ascii=False)
        for ws in list(self.player_ws.values()):
            try: await ws_send(ws,msg)
            except: pass
        for ws in list(self.spectator_ws):
            try: await ws_send(ws,msg)
            except: self.spectator_ws.discard(ws)

    async def broadcast_state(self):
        for name,ws in list(self.player_ws.items()):
            try: await ws_send(ws,json.dumps(self.get_public_state(viewer=name),ensure_ascii=False))
            except: pass
        # 관전자: 딜레이 큐 — 관전자 없으면 스킵
        if self.spectator_ws or self.poll_spectators:
            spec_data=json.dumps(self.get_spectator_state(),ensure_ascii=False)
            if len(self.spectator_queue)<SPECTATOR_QUEUE_CAP:
                self.spectator_queue.append((time.time()+self.SPECTATOR_DELAY, spec_data))

    async def _broadcast_spectators(self, msg):
        """관전자에게 즉시 메시지 전송 (딜레이 없이)"""
        for ws in list(self.spectator_ws):
            try: await ws_send(ws,msg)
            except: self.spectator_ws.discard(ws)

    async def flush_spectator_queue(self):
        """딜레이 큐에서 시간 된 데이터를 관전자에게 전송"""
        now=time.time()
        while self.spectator_queue and self.spectator_queue[0][0]<=now:
            _,data=self.spectator_queue.pop(0)
            self.last_spectator_state=data  # 폴링 관전자용 캐시
            for ws in list(self.spectator_ws):
                try: await ws_send(ws,data)
                except: self.spectator_ws.discard(ws)

    async def run_delay_loop(self):
        """딜레이 큐 처리 루프 (0.5초마다)"""
        while True:
            await self.flush_spectator_queue()
            await asyncio.sleep(0.5)

    async def broadcast_chat(self, entry):
        msg = {'type':'chat','name':entry['name'],'msg':entry['msg']}
        data = json.dumps(msg, ensure_ascii=False)
        for ws in set(self.player_ws.values()):
            try: await ws_send(ws, data)
            except: pass
        for ws in list(self.spectator_ws):
            try: await ws_send(ws, data)
            except: self.spectator_ws.discard(ws)

    async def add_log(self, msg):
        self.log.append(msg)
        if len(self.log) > 500: self.log = self.log[-250:]
        await self.broadcast({'type':'log','msg':msg})

    def handle_api_action(self, name, data):
        if self.turn_player==name and self.pending_action:
            # turn_seq 검증 (있으면 체크, 없으면 호환성 위해 통과)
            req_seq=data.get('turn_seq')
            if req_seq is not None and req_seq!=self.turn_seq:
                return 'TURN_MISMATCH'
            if self.pending_action.is_set():
                return 'ALREADY_ACTED'
            self.pending_data=data; self.pending_action.set()
            return 'OK'
        return 'NOT_YOUR_TURN'

    # ── 게임 루프 (연속 핸드) ──
    async def run(self):
        self.running=True
        if not self._delay_task:
            self._delay_task=asyncio.create_task(self.run_delay_loop())
        await self.add_log(f"🎰 게임 시작! (실시간 TV중계)")
        await self.broadcast_state()
        try:
          await self._run_loop()
        except Exception as e:
          import traceback; traceback.print_exc()
          await self.add_log(f"⚠️ 게임 오류 발생 — 자동 복구 시도 중")
        finally:
          self.running=False; self.round='finished'
          # 자동 재시작 시도
          await asyncio.sleep(3)
          active=[s for s in self.seats if s['chips']>0 and not s.get('out')]
          if len(active)>=self.MIN_PLAYERS:
              await self.add_log("🔄 게임 자동 재시작!")
              asyncio.create_task(self.run())

    async def _run_loop(self):
        while True:
            active=[s for s in self.seats if s['chips']>0 and not s.get('out')]
            if len(active)<2:
                # 중간참가 대기 (10초)
                await self.add_log("⏳ 플레이어 대기중... (참가 가능)")
                self.round = 'waiting'
                await self.broadcast_state()
                for _ in range(20):  # 최대 20초 대기
                    await asyncio.sleep(1)
                    active=[s for s in self.seats if s['chips']>0 and not s.get('out')]
                    if len(active)>=2: break
                if len(active)<2: break

            await self.play_hand()

            # 카드 회수 애니메이션
            await self.broadcast_raw({'type':'collect_anim'})
            await asyncio.sleep(1.2)

            # 핸드 사이 대기 (중간참가 기회)
            self.round = 'between'
            await self.broadcast_state()
            await asyncio.sleep(3)

            # 탈락 체크 + 킬캠
            hand_winner=None
            for r in self.history[-1:]:
                if r.get('winner'): hand_winner=r['winner']
            for s in self.seats:
                if s['chips']<=0 and not s.get('out'):
                    s['out']=True; s['last_action']='💀 파산'
                    killer=hand_winner or '?'
                    killer_seat=next((x for x in self.seats if x['name']==killer),None)
                    killer_emoji=killer_seat['emoji'] if killer_seat else '💀'
                    self.bankrupt_counts[s['name']]=self.bankrupt_counts.get(s['name'],0)+1
                    bc=self.bankrupt_counts[s['name']]
                    cooldown=min(30*bc, 120)  # 30초 x 파산횟수, 최대 2분
                    self.bankrupt_cooldowns[s['name']]=time.time()+cooldown
                    await self.add_log(f"☠️ {s['emoji']} {s['name']} 파산! (💀x{bc}, 쿨다운 {cooldown}초)")
                    death_q=s.get('meta',{}).get('death_quote','')
                    await self.broadcast({'type':'killcam','victim':s['name'],'victim_emoji':s['emoji'],
                        'killer':killer,'killer_emoji':killer_emoji,'death_quote':death_q,
                        'bankrupt_count':bc,'cooldown':cooldown})
                    update_leaderboard(s['name'], False, 0)

            # 파산한 실제 에이전트 자동 퇴장 (자리 비우기)
            bankrupt_agents=[s for s in self.seats if s.get('out') and not s['is_bot']]
            for s in bankrupt_agents:
                self.seats.remove(s)
                await self.add_log(f"🚪 {s['emoji']} {s['name']} 파산 퇴장!")

            # 파산 봇 리스폰 (에이전트 2명 미만일 때만) — 제거 전에 먼저 처리
            real_count=sum(1 for s in self.seats if not s['is_bot'] and not s.get('out'))
            if real_count<2:
                for s in self.seats:
                    if s.get('out') and s['is_bot']:
                        respawn_chips=self.START_CHIPS//2
                        s['out']=False; s['chips']=respawn_chips; s['folded']=False
                        await self.add_log(f"🔄 {s['emoji']} {s['name']} 복귀! ({respawn_chips}pt 지급 — 패널티)")

            # out=True인 NPC 봇 완전 제거 (좀비 방지 — 리스폰 안 된 것만)
            dead_bots=[s for s in self.seats if s.get('out') and s['is_bot']]
            for s in dead_bots:
                self.seats.remove(s)

            alive=[s for s in self.seats if s['chips']>0 and not s.get('out')]
            if len(alive)==1:
                w=alive[0]
                await self.add_log(f"🏆🏆🏆 {w['emoji']} {w['name']} 우승!! ({w['chips']}pt)")
                update_leaderboard(w['name'], True, w['chips'], w['chips'])
                break
            if len(alive)==0: break

        self.round='finished'
        ranking=sorted(self.seats,key=lambda x:x['chips'],reverse=True)
        await self.broadcast({'type':'game_over',
            'ranking':[{'name':s['name'],'emoji':s['emoji'],'chips':s['chips']} for s in ranking]})
        # 자동 리셋
        await asyncio.sleep(5)
        if is_ranked_table(self.id):
            # ranked: 게임 종료 시 모든 플레이어 칩을 DB 잔고에 즉시 반영
            for s in self.seats:
                auth_id = s.get('_auth_id') or _ranked_auth_map.get(s['name'])
                if auth_id and s['chips'] > 0 and not s.get('_cashed_out'):
                    # credit + ingame DELETE를 단일 트랜잭션으로 (crash recovery 이중 크레딧 방지)
                    with _ranked_lock:
                        db=_db()
                        db.execute("UPDATE ranked_balances SET balance=balance+?, updated_at=strftime('%s','now') WHERE auth_id=?",(s['chips'],auth_id))
                        db.execute("DELETE FROM ranked_ingame WHERE table_id=? AND auth_id=?",(self.id,auth_id))
                        db.commit()
                    print(f"[RANKED] 게임종료 정산: {s['name']}({auth_id}) +{s['chips']}pt → 잔고 {ranked_balance(auth_id)}pt", flush=True)
                    _ranked_audit('game_end', auth_id, s['chips'], details=f'table:{self.id} name:{s["name"]}')
                    s['chips'] = 0; s['_cashed_out'] = True  # 이중 크레딧 방지
            self.seats=[]  # ranked 게임 끝나면 전원 퇴장 (재입장 필요)
            # 남은 ingame 스냅샷 정리
            try:
                db = _db()
                db.execute("DELETE FROM ranked_ingame WHERE table_id=?", (self.id,))
                db.commit()
            except: pass
        else:
            self.seats=[s for s in self.seats if s['chips']>0 and not s.get('out')]
            real_players=[s for s in self.seats if not s['is_bot']]
            if len(real_players)>=2:
                # 실제 에이전트 2명 이상 → NPC 불필요, 제거
                self.seats=[s for s in self.seats if not s['is_bot']]
                # 실제 에이전트 칩 전원 리셋 (공평한 새 게임)
                for s in self.seats:
                    s['chips']=self.START_CHIPS
            else:
                # 실제 에이전트 부족 → NPC 리필
                for name,emoji,style,bio in NPC_BOTS:
                    if not any(s['name']==name for s in self.seats):
                        if len(self.seats)<self.MAX_PLAYERS:
                            self.add_player(name,emoji,is_bot=True,style=style,meta={'bio':bio})
                for s in self.seats:
                    if s['is_bot'] and s['chips']<self.START_CHIPS//2:
                        s['chips']=self.START_CHIPS
        self.hand_num=0; self.highlights=[]
        if not is_ranked_table(self.id):
            self.SB=5; self.BB=10
        return  # finally 블록에서 자동 재시작 처리

    async def play_hand(self):
        active=[s for s in self.seats if s['chips']>0 and not s.get('out')]
        if len(active)<2: return
        # 칩 리셋: 누구든 1000 이상이면 전원 500으로 (ranked 테이블 제외)
        if not is_ranked_table(self.id) and any(s['chips']>=1000 for s in active):
            for s in active:
                s['chips']=self.START_CHIPS
            self.SB=5; self.BB=10
            self.hand_num=0
            await self.add_log("♻️ 칩 리셋! 전원 500pt로 리셋")
        self.hand_num+=1; self.last_showdown=None; self.fold_winner=None
        # 블라인드 에스컬레이션
        level=min((self.hand_num-1)//self.BLIND_INTERVAL, len(self.BLIND_SCHEDULE)-1)
        new_sb,new_bb=self.BLIND_SCHEDULE[level]
        if new_sb!=self.SB:
            self.SB,self.BB=new_sb,new_bb
            await self.add_log(f"📈 블라인드 업! SB:{self.SB} / BB:{self.BB}")
        self.deck=make_deck(); self.community=[]; self.pot=0; self.current_bet=0
        self._hand_seats=list(active)
        hand_record = {'hand':self.hand_num,'players':[],'actions':[],'community':[],'winner':None,'pot':0}

        for s in self._hand_seats:
            s['hole']=[self.deck.pop(),self.deck.pop()]; s['folded']=False; s['bet']=0; s['last_action']=None; s['_total_invested']=0
            hand_record['players'].append({'name':s['name'],'emoji':s['emoji'],'hole':[card_str(c) for c in s['hole']],'chips':s['chips']})
        self.dealer=self.dealer%len(self._hand_seats)
        await self.add_log(f"━━━ 핸드 #{self.hand_num} ({len(self._hand_seats)}명) ━━━")
        names=', '.join(s['emoji']+s['name'] for s in self._hand_seats)
        n_players=len(self._hand_seats)
        _slogans=[
            f"🃏 핸드 #{self.hand_num} — {n_players}명의 운명이 갈린다!",
            f"🔔 핸드 #{self.hand_num} 개막! 카드가 날아간다!",
            f"⚡ 핸드 #{self.hand_num}! 누가 살아남을 것인가?",
            f"🎲 핸드 #{self.hand_num} — 칩이 춤춘다!",
            f"🔥 핸드 #{self.hand_num} 점화! {n_players}명 전원 참전!",
            f"💀 핸드 #{self.hand_num} — 약자는 여기서 탈락한다",
            f"🎰 핸드 #{self.hand_num}! 딜러가 카드를 뿌린다!",
            f"⚔️ 핸드 #{self.hand_num} — {n_players}파전 개시!",
            f"🃏 핸드 #{self.hand_num}! 승자독식, 패자탈락!",
            f"💎 핸드 #{self.hand_num} — 이번 팟은 누구 차지?",
            f"🌪️ 핸드 #{self.hand_num}! 폭풍이 몰려온다!",
            f"🎪 핸드 #{self.hand_num} — 서커스가 시작됐다!",
        ]
        slogan=random.choice(_slogans)
        await self.broadcast_commentary(f"{slogan} 참가: {names}")
        # 딜링 애니메이션 브로드캐스트
        seat_names=[s['name'] for s in self._hand_seats]
        await self.broadcast_raw({'type':'deal_anim','seats':len(self._hand_seats),'dealer':self.dealer,'players':seat_names})
        await asyncio.sleep(1.8)
        await self.broadcast_state(); await asyncio.sleep(1.2)

        # 블라인드
        n=len(self._hand_seats)
        if n==2:
            sb_s=self._hand_seats[self.dealer]; bb_s=self._hand_seats[(self.dealer+1)%n]
        else:
            sb_s=self._hand_seats[(self.dealer+1)%n]; bb_s=self._hand_seats[(self.dealer+2)%n]
        sb_a=min(self.SB,sb_s['chips']); bb_a=min(self.BB,bb_s['chips'])
        sb_s['chips']-=sb_a; sb_s['bet']=sb_a; sb_s['_total_invested']+=sb_a
        bb_s['chips']-=bb_a; bb_s['bet']=bb_a; bb_s['_total_invested']+=bb_a
        self.pot+=sb_a+bb_a; self.current_bet=bb_a
        await self.add_log(f"🪙 {sb_s['name']} SB {sb_a} | {bb_s['name']} BB {bb_a}")
        # 연속 폴드 앤티 페널티 (3연속 폴드 시 BB 앤티 추가, ranked 제외 — 실제 돈)
        ante_players=[]
        if not is_ranked_table(self.id):
            for s in self._hand_seats:
                fs=self.fold_streaks.get(s['name'],0)
                if fs>=3:
                    ante=min(self.BB,s['chips'])
                    if ante>0:
                        s['chips']-=ante; s['bet']+=ante; s['_total_invested']+=ante; self.pot+=ante
                        ante_players.append((s,ante,fs))
            if ante_players:
                for s,ante,fs in ante_players:
                    await self.add_log(f"🔥 {s['emoji']} {s['name']} 앤티 {ante}pt (폴드 {fs}연속 페널티!)")
                await self.broadcast_commentary(f"⚠️ 연속 폴드 페널티! {', '.join(s['name'] for s,_,_ in ante_players)} 강제 앤티!")
        await self.broadcast_state()

        # 프리플랍
        self.round='preflop'
        if n==2: start=(self.dealer)%n
        else: start=(self.dealer+3)%n
        await self.betting_round(start, hand_record)
        if self._count_alive()<=1: await self.resolve(hand_record); self._advance_dealer(); return

        # 올인 슬로모션 감지
        _slowmo=self._is_all_allin()

        # 플랍
        self.round='flop'; self.deck.pop()
        if _slowmo and len(self.community)==0:
            # 슬로모션: 플랍 카드 한 장씩
            await self.broadcast_raw({'type':'slowmo_start','pot':self.pot})
            for ci in range(3):
                await self._slowmo_broadcast('flop', ci, hand_record, deal=True)
            await self.add_log(f"── 플랍: {' '.join(card_str(c) for c in self.community)} ──")
            await self.broadcast_commentary(f"🎴 플랍 오픈! {' '.join(card_str(c) for c in self.community)} — 팟 {self.pot}pt")
        else:
            self.community+=[self.deck.pop() for _ in range(3)]
            hand_record['community']=[card_str(c) for c in self.community]
            await self.add_log(f"── 플랍: {' '.join(card_str(c) for c in self.community)} ──")
            await self.broadcast_commentary(f"🎴 플랍 오픈! {' '.join(card_str(c) for c in self.community)} — 팟 {self.pot}pt")
        await self.broadcast_state(); await asyncio.sleep(3)
        if not _slowmo:
            await self.betting_round((self.dealer+1)%n, hand_record)
            if self._count_alive()<=1: await self.resolve(hand_record); self._advance_dealer(); return
            _slowmo=self._is_all_allin()  # 플랍 베팅 후 올인 체크

        # 턴
        self.round='turn'; self.deck.pop(); self.community.append(self.deck.pop())
        hand_record['community']=[card_str(c) for c in self.community]
        if _slowmo:
            await self._slowmo_broadcast('turn', 3, hand_record)
        await self.add_log(f"── 턴: {' '.join(card_str(c) for c in self.community)} ──")
        alive=self._count_alive()
        await self.broadcast_commentary(f"🔥 턴 카드 오픈! {alive}명 생존 — 팟 {self.pot}pt")
        await self.broadcast_state(); await asyncio.sleep(3)
        if not _slowmo:
            await self.betting_round((self.dealer+1)%n, hand_record)
            if self._count_alive()<=1: await self.resolve(hand_record); self._advance_dealer(); return
            _slowmo=self._is_all_allin()  # 턴 베팅 후 올인 체크

        # 리버
        self.round='river'; self.deck.pop(); self.community.append(self.deck.pop())
        hand_record['community']=[card_str(c) for c in self.community]
        if _slowmo:
            await self._slowmo_broadcast('river', 4, hand_record)
            await self.broadcast_raw({'type':'slowmo_end'})
        await self.add_log(f"── 리버: {' '.join(card_str(c) for c in self.community)} ──")
        alive=self._count_alive()
        await self.broadcast_commentary(f"💀 리버! 마지막 카드 오픈 — {alive}명이 {self.pot}pt를 놓고 승부!")
        await self.broadcast_state(); await asyncio.sleep(3)
        if not _slowmo:
            await self.betting_round((self.dealer+1)%n, hand_record)
        await self.resolve(hand_record); self._advance_dealer()

    def _advance_dealer(self):
        active=[s for s in self.seats if s['chips']>0 and not s.get('out')]
        if active: self.dealer=(self.dealer+1)%len(active)

    def _count_alive(self): return sum(1 for s in self._hand_seats if not s['folded'] and not s.get('out'))

    async def _slowmo_broadcast(self, street, index, hand_record, deal=False):
        """슬로모션: 승률 계산 + 브로드캐스트. deal=True면 카드도 뽑음"""
        if deal:
            self.community.append(self.deck.pop())
        hand_record['community']=[card_str(c) for c in self.community]
        eq=self._compute_equities()
        await self.broadcast_raw({'type':'slowmo_card','card':card_dict(self.community[-1]),'index':index,
            'street':street,'community':[card_dict(c) for c in self.community],'equities':eq,'pot':self.pot})
        await self.broadcast_state(); await asyncio.sleep(2.5)

    def _is_all_allin(self):
        """모든 생존 플레이어가 올인 상태(chips==0)인지 체크"""
        alive=[s for s in self._hand_seats if not s['folded'] and not s.get('out')]
        if len(alive)<2: return False
        # 칩이 남은 플레이어가 최대 1명이면 올인 쇼다운
        with_chips=[s for s in alive if s['chips']>0]
        return len(with_chips)<=1

    def _compute_equities(self):
        """현재 커뮤니티 카드 기준 생존자 승률 계산 (Monte Carlo 200회)"""
        alive=[s for s in self._hand_seats if not s['folded'] and not s.get('out') and s.get('hole')]
        if len(alive)<2: return {}
        known=set()
        for c in self.community: known.add(c)
        for s in alive:
            for c in s['hole']: known.add(c)
        remaining_deck=[c for c in [(r,s) for s in SUITS for r in RANKS] if c not in known]
        need=5-len(self.community)
        wins={s['name']:0.0 for s in alive}
        N=200
        for _ in range(N):
            if need>0:
                sample=random.sample(remaining_deck,need)
                board=list(self.community)+sample
            else:
                board=list(self.community)
            best_sc=None; best_names=[]
            for s in alive:
                sc=evaluate_hand(s['hole']+board)
                if sc is None: continue
                if best_sc is None or sc>best_sc:
                    best_sc=sc; best_names=[s['name']]
                elif sc==best_sc:
                    best_names.append(s['name'])
            share=1.0/len(best_names) if best_names else 0
            for nm in best_names: wins[nm]+=share
        equities={}
        for s in alive:
            equities[s['name']]=round(wins[s['name']]/N*100)
        return equities

    async def betting_round(self, start, record):
        if self.round!='preflop':
            for s in self._hand_seats: s['bet']=0
            self.current_bet=0
        last_raiser=None; acted=set(); raises=0; n=len(self._hand_seats)
        if n==0: return
        start=start%n  # clamp start to valid range
        for _ in range(n*4):
            all_done=True
            for i in range(n):
                idx=(start+i)%n
                if idx>=len(self._hand_seats): return  # safety
                s=self._hand_seats[idx]
                if s['folded'] or s.get('out') or s['chips']<=0: continue
                if s['name']==last_raiser and s['name'] in acted: continue
                if s['name'] in acted and s['bet']>=self.current_bet: continue  # already matched
                if self._count_alive()<=1: return
                to_call=self.current_bet-s['bet']

                # 승률 계산 (해설+reasoning용) — 액션 전에 먼저 계산
                _wp=0
                if s['hole']:
                    _strengths={x['name']:hand_strength(x['hole'],self.community) for x in self._hand_seats if not x['folded'] and x['hole']}
                    _total=sum(_strengths.values()) or 1
                    _wp=round(_strengths.get(s['name'],0)/_total*100)

                if s['is_bot']:
                    act,amt=s['bot_ai'].decide(s['hole'],self.community,self.pot,to_call,s['chips'])
                    # 사람 패턴 딜레이: 액션 무게에 따라 다름
                    if act=='fold': _delay=random.uniform(1.0,3.5)
                    elif act=='check': _delay=random.uniform(1.5,4.0)
                    elif act=='call':
                        _delay=random.uniform(3.0,7.0)
                        if to_call>s['chips']*0.3: _delay=random.uniform(5.0,10.0)  # 큰 콜
                    elif act=='raise':
                        _delay=random.uniform(4.0,9.0)
                        if s['chips']<=amt+to_call: _delay=random.uniform(8.0,15.0)  # 올인급
                    else: _delay=random.uniform(3.0,7.0)
                    # 라운드 초반은 좀 더 빠름 (프리플랍 첫 액션들)
                    if self.round=='preflop' and len(acted)<2: _delay*=0.7
                    await asyncio.sleep(_delay)
                    if act=='raise' and raises>=4: act,amt='call',to_call
                    # NPC 심리전 채팅 (55% 확률)
                    if random.random()<0.55:
                        _targets=[x['name'] for x in self._hand_seats if not x['folded'] and x['name']!=s['name']]
                        _tgt=random.choice(_targets) if _targets else ''
                        _trash=_npc_trash_talk(s['name'],act,amt,to_call,self.pot,_wp,_tgt)
                        if _trash: await self.broadcast_chat({'name':s['name'],'msg':_trash})
                else:
                    act,amt=await self._wait_external(s,to_call,raises>=4)

                # 액션 note + reasoning 추출
                note=''; reasoning=''
                if not s['is_bot'] and self.pending_data:
                    note=sanitize_msg(self.pending_data.get('note',''),80)
                    reasoning=sanitize_msg(self.pending_data.get('reasoning',''),100)
                    s['last_note']=note
                    s['last_reasoning']=reasoning
                    # 외부 봇 채팅 메시지 (msg 필드)
                    _chat_msg=sanitize_msg(self.pending_data.get('msg',''),120)
                    if _chat_msg: await self.broadcast_chat({'name':s['name'],'msg':_chat_msg})
                # reasoning 없으면 자동생성 (외부 에이전트 포함)
                if not reasoning:
                    reasoning=self._bot_reasoning(s, act, amt, _wp, to_call)
                    s['last_reasoning']=reasoning
                # 액션 기록
                record['actions'].append({'round':self.round,'player':s['name'],'action':act,'amount':amt,'note':note,'reasoning':reasoning})
                # last_action 저장 (UI 표시용)
                if act=='fold': s['last_action']='❌ 폴드'
                elif act=='check': s['last_action']='✋ 체크'
                elif act=='call':
                    ca=min(to_call,s['chips']); s['last_action']=f'📞 콜 {ca}pt'
                elif act=='raise':
                    total=min(amt+min(to_call,s['chips']),s['chips']); s['last_action']=f'⬆️ 레이즈 {total}pt' if s['chips']>total else f'🔥 ALL IN {total}pt'
                else: s['last_action']=act

                # 프로필 통계 기록
                self._init_stats(s['name'])
                ps=self.player_stats[s['name']]
                if act=='fold': ps['folds']+=1
                elif act=='check': ps['checks']+=1
                elif act=='call': ps['calls']+=1
                elif act=='raise':
                    ps['raises']+=1
                    total_r=min(amt+min(to_call,s['chips']),s['chips'])
                    ps['total_bet']+=total_r
                    if s['chips']<=total_r: ps['allins']+=1
                    # 블러핑 감지: 승률 30% 미만인데 레이즈
                    if _wp<30 and _wp>0: ps['bluffs']+=1

                if act=='fold':
                    s['folded']=True
                    self.fold_streaks[s['name']]=self.fold_streaks.get(s['name'],0)+1
                    await self.add_log(f"❌ {s['emoji']} {s['name']} 폴드")
                    cmt=f"❌ {s['name']} 폴드! {self._count_alive()}명 남음"
                    if _wp>40: cmt=f"😱 {s['name']} 승률 {_wp}%인데 폴드?! 무슨 판단이지?"
                    await self.broadcast_commentary(cmt)
                elif act=='raise':
                    total=min(amt+min(to_call,s['chips']),s['chips'])
                    s['chips']-=total; s['bet']+=total; s['_total_invested']+=total; self.pot+=total
                    self.current_bet=s['bet']; last_raiser=s['name']; raises+=1; all_done=False
                    if s['chips']==0:
                        await self.add_log(f"🔥🔥🔥 {s['emoji']} {s['name']} ALL IN {total}pt!! 🔥🔥🔥")
                        await self.broadcast({'type':'allin','name':s['name'],'emoji':s['emoji'],'amount':total,'pot':self.pot})
                        allin_cmt=f"🔥 {s['name']} ALL IN {total}pt!! 팟 {self.pot}pt 폭발!"
                        if _wp<30: allin_cmt=f"🤯 {s['name']} 승률 {_wp}%에서 ALL IN {total}pt?! 미친 블러핑인가?!"
                        elif _wp>70: allin_cmt=f"💪 {s['name']} 승률 {_wp}%! 자신만만 ALL IN {total}pt!"
                        await self.broadcast_commentary(allin_cmt)
                    else:
                        await self.add_log(f"⬆️ {s['emoji']} {s['name']} 레이즈 {total}pt (팟:{self.pot})")
                        raise_cmt=f"⬆️ {s['name']} {total}pt 레이즈! 팟 {self.pot}pt"
                        if _wp<25: raise_cmt=f"🎭 {s['name']} 승률 {_wp}%인데 {total}pt 레이즈?! 블러핑 냄새..."
                        elif _wp>65 and total>self.pot//2: raise_cmt=f"💎 {s['name']} 승률 {_wp}%! {total}pt 강하게 밀어붙인다!"
                        await self.broadcast_commentary(raise_cmt)
                elif act=='check':
                    await self.add_log(f"✋ {s['emoji']} {s['name']} 체크")
                else:
                    ca=min(to_call,s['chips']); s['chips']-=ca; s['bet']+=ca; s['_total_invested']+=ca; self.pot+=ca
                    if s['chips']==0 and ca>0:
                        await self.add_log(f"🔥🔥🔥 {s['emoji']} {s['name']} ALL IN 콜 {ca}pt!! 🔥🔥🔥")
                        await self.broadcast({'type':'allin','name':s['name'],'emoji':s['emoji'],'amount':ca,'pot':self.pot})
                        call_ai_cmt=f"🔥 {s['name']} ALL IN 콜 {ca}pt!! 승부수!"
                        if _wp<25: call_ai_cmt=f"😤 {s['name']} 승률 {_wp}%에서 ALL IN 콜?! 배짱인가 자살인가!"
                        await self.broadcast_commentary(call_ai_cmt)
                    elif ca>0:
                        await self.add_log(f"📞 {s['emoji']} {s['name']} 콜 {ca}pt")
                        call_cmt=f"📞 {s['name']} 콜 {ca}pt — 팟 {self.pot}pt"
                        if _wp<20 and ca>self.BB*3: call_cmt=f"🤔 {s['name']} 승률 {_wp}%인데 {ca}pt 콜? 뭘 노리는 거지..."
                        await self.broadcast_commentary(call_cmt)
                    else: await self.add_log(f"✋ {s['emoji']} {s['name']} 체크")

                # 봇 쓰레기톡 (상대 이름 전달)
                if s.get('is_bot') and s.get('bot_ai'):
                    opps=[x['name'] for x in self._hand_seats if not x['folded'] and x['name']!=s['name']]
                    talk_act='allin' if act=='allin' else act
                    talk = s['bot_ai'].trash_talk(talk_act, self.pot, opps, s['chips'])
                    if talk:
                        entry = self.add_chat(s['name'], talk)
                        await self.broadcast_chat(entry)

                if act!='fold': self.fold_streaks[s['name']]=0
                acted.add(s['name']); await self.broadcast_state()
                # 액션 대형 오버레이 브로드캐스트
                _disp_act=s['last_action'] or act
                await self.broadcast_raw({'type':'action_display','name':s['name'],'emoji':s.get('emoji',''),'action':_disp_act,'chips':s['chips'],'pot':self.pot})
                # NPC 반응 채팅: 다른 NPC가 이 액션에 반응 (25% 확률)
                for other in self._hand_seats:
                    if other['is_bot'] and not other['folded'] and other['name']!=s['name']:
                        _react=_npc_react_to_action(other['name'],s['name'],act,amt,self.pot)
                        if _react:
                            await asyncio.sleep(random.uniform(0.5,1.5))
                            await self.broadcast_chat({'name':other['name'],'msg':_react})
                            break  # 한 명만 반응

            if all_done or last_raiser is None: break
            if all(s['name'] in acted for s in self._hand_seats if not s['folded'] and s['chips']>0):
                if all(s['bet']>=self.current_bet or s['chips']==0 for s in self._hand_seats if not s['folded']): break

    async def _wait_external(self, seat, to_call, raise_capped):
        seat['last_action']=None  # 턴 시작 시 이전 액션 표시 제거
        self.turn_player=seat['name']; self.pending_action=asyncio.Event()
        self.turn_seq+=1  # 새 턴마다 시퀀스 증가
        self.pending_data=None; self.turn_deadline=time.time()+self.TURN_TIMEOUT
        seat['_turn_start']=time.time()  # latency 측정용
        ti=self.get_turn_info(seat['name'])
        if ti and seat['name'] in self.player_ws:
            try: await ws_send(self.player_ws[seat['name']],json.dumps(ti,ensure_ascii=False))
            except: pass
        await self.broadcast_state()
        try: await asyncio.wait_for(self.pending_action.wait(),timeout=self.TURN_TIMEOUT)
        except asyncio.TimeoutError:
            self.turn_player=None; seat.pop('_turn_start',None)
            seat['latency_ms']=-1  # timeout indicator
            self.timeout_counts[seat['name']]=self.timeout_counts.get(seat['name'],0)+1
            tc=self.timeout_counts[seat['name']]
            if tc>=3:
                seat['out']=True
                # ranked: 강제퇴장 시 잔여 칩 환원
                if is_ranked_table(self.id):
                    kick_auth = seat.get('_auth_id') or _ranked_auth_map.get(seat['name'])
                    if kick_auth and seat['chips'] > 0:
                        ranked_credit(kick_auth, seat['chips'])
                        print(f"[RANKED] 타임아웃 킥 정산: {seat['name']}({kick_auth}) +{seat['chips']}pt", flush=True)
                        seat['chips'] = 0
                await self.add_log(f"🚫 {seat['emoji']} {seat['name']} 타임아웃 3연속 → 강제퇴장!")
                seat['folded']=True; return 'fold',0
            if to_call>0:
                await self.add_log(f"⏰ {seat['emoji']} {seat['name']} 시간초과 → 폴드 ({tc}/3)"); return 'fold',0
            return 'check',0
        self.turn_player=None; self.timeout_counts[seat['name']]=0  # 정상 액션하면 리셋
        # latency 기록
        if seat.get('_turn_start'):
            lat=round((time.time()-seat['_turn_start'])*1000)
            seat['latency_ms']=lat
            seat.pop('_turn_start',None)
        d=self.pending_data or {}
        act=d.get('action','fold')
        try: amt=int(d.get('amount',0))
        except (ValueError, TypeError): amt=0
        # === 액션 검증 (서버 권위) ===
        if act not in ('fold','check','call','raise'): act='fold'
        if act=='raise':
            if raise_capped: act='call'; amt=to_call
            else:
                amt=max(0, amt)  # 음수 방지
                mn=max(self.BB, self.current_bet*2 - seat['bet'])
                amt=max(mn, min(amt, seat['chips'] - min(to_call, seat['chips'])))  # min~max 클램핑
                if amt <= 0: act='call'; amt=to_call  # 레이즈 불가능하면 콜
        if act=='call': amt=min(to_call, seat['chips'])
        if act=='check' and to_call > 0: act='fold'  # 콜해야 하는데 체크 시도 → 폴드
        return act,amt

    async def resolve(self, record):
        self.round='showdown'; alive=[s for s in self._hand_seats if not s['folded'] and not s.get('out')]
        scores=[]  # 쇼다운 시에만 채워짐
        # 핸드 참가 통계
        for s in self._hand_seats:
            self._init_stats(s['name'])
            self.player_stats[s['name']]['hands']+=1

        if len(alive)==1:
            w=alive[0]; w['chips']+=self.pot
            await self.add_log(f"🏆 {w['emoji']} {w['name']} +{self.pot}pt (상대 폴드)")
            await self.broadcast_commentary(f"🏆 {w['name']} 승리! +{self.pot}pt 획득 (상대 전원 폴드)")
            self.fold_winner={'name':w['name'],'emoji':w['emoji'],'pot':self.pot,'winner':True}
            record['winner']=w['name']; record['pot']=self.pot
            # 프로필 통계
            self._init_stats(w['name'])
            self.player_stats[w['name']]['wins']+=1
            self.player_stats[w['name']]['total_won']+=self.pot
            self.player_stats[w['name']]['biggest_pot']=max(self.player_stats[w['name']]['biggest_pot'],self.pot)
            # 빅팟 하이라이트 (200pt 이상)
            if self.pot>=200: self._save_highlight(record,'bigpot')
            update_leaderboard(w['name'], True, self.pot, self.pot)
            update_agent_stats(w['name'], net=self.pot, win=True, hand_num=self.hand_num)
            _ps = self.player_stats.get(w['name'],{})
            _h = max(_ps.get('hands',1),1)
            _lobby_record(w['name'], stats={'hands':_h,'win_rate':round(_ps.get('wins',0)/_h,2),'allins':_ps.get('allins',0)})
            # win_quote for fold win
            win_q=w.get('meta',{}).get('win_quote','')
            if win_q: await self.add_log(f"💬 {w['emoji']} {w['name']}: \"{win_q}\"")
            for s in self._hand_seats:
                if s!=w:
                    update_leaderboard(s['name'], False, 0)
                    # 라이벌 업데이트
                    pair=tuple(sorted([w['name'],s['name']]))
                    if pair not in self.rivalry: self.rivalry[pair]={'a_wins':0,'b_wins':0}
                    if w['name']==pair[0]: self.rivalry[pair]['a_wins']+=1
                    else: self.rivalry[pair]['b_wins']+=1
        else:
            scores=[]
            for s in alive:
                if s['hole'] and all(s['hole']): sc=evaluate_hand(s['hole']+self.community); scores.append((s,sc,hand_name(sc)))
                else: await self.add_log(f"⚠️ {s['name']} 홀카드 없음 — 스킵")
            scores.sort(key=lambda x:x[1],reverse=True)
            if not scores:
                await self.add_log("⚠️ 승자 없음 — 팟 소멸"); record['pot']=self.pot; return
            # ═══ 사이드팟 계산 ═══
            # 각 플레이어의 총 투입액 = bet (현재 라운드) + 이전 라운드 누적
            # _hand_seats 전체(폴드 포함)의 bet 총합이 self.pot
            # 올인 플레이어별로 사이드팟 분리
            all_in_amounts = sorted(set(
                s.get('_total_invested',s['bet']) for s in self._hand_seats
                if s.get('_total_invested',s['bet'])>0 and s['chips']==0 and not s.get('out')
            ))
            # 간단한 사이드팟: 올인이 없으면 메인팟만
            pots = []  # [(amount, [eligible_player_names])]
            if not all_in_amounts:
                pots = [(self.pot, [s['name'] for s,_,_ in scores])]
            else:
                prev_level = 0
                remaining_pot = self.pot
                all_contributors = [s for s in self._hand_seats if s.get('_total_invested',s['bet'])>0]
                for level in all_in_amounts:
                    increment = level - prev_level
                    eligible = [s for s in all_contributors if s.get('_total_invested',s['bet'])>=level]
                    pot_size = min(increment * len(eligible), remaining_pot)
                    if pot_size > 0:
                        eligible_names = [s['name'] for s in eligible if not s['folded']]
                        pots.append((pot_size, eligible_names))
                        remaining_pot -= pot_size
                    prev_level = level
                # 남은 팟 (올인 이상 베팅한 플레이어들)
                if remaining_pot > 0:
                    top_eligible = [s['name'] for s,_,_ in scores]
                    pots.append((remaining_pot, top_eligible))
            # 각 팟을 해당 eligible 중 최고 핸드에게 배분 (동점 시 split)
            total_won = {}
            main_winner = None
            for pot_amount, eligible in pots:
                pot_scores = [(s,sc,hn) for s,sc,hn in scores if s['name'] in eligible]
                if pot_scores:
                    best_sc = pot_scores[0][1]
                    winners = [(s,sc,hn) for s,sc,hn in pot_scores if sc==best_sc]
                    if winner_pool == 0 or len(winners) == 0: continue; share = pot_amount // len(winners)
                    remainder = pot_amount - share * len(winners)
                    for wi,(pw,_,_) in enumerate(winners):
                        amt = share + (1 if wi < remainder else 0)  # 나머지 1pt씩 분배
                        pw['chips'] += amt
                        total_won[pw['name']] = total_won.get(pw['name'],0) + amt
                        if main_winner is None: main_winner = pw
            w = main_winner or scores[0][0]
            sd=[{'name':s['name'],'emoji':s['emoji'],'hole':[card_dict(c) for c in (s['hole'] or [])],'hand':hn,'winner':s['name'] in total_won} for s,_,hn in scores]
            self.last_showdown=sd
            await self.broadcast({'type':'showdown','players':sd,'community':[card_dict(c) for c in self.community],'pot':self.pot})
            for s,_,hn in scores:
                mark=" 👑" if s==w else ""
                await self.add_log(f"🃏 {s['emoji']}{s['name']}: {card_str(s['hole'][0])} {card_str(s['hole'][1])} → {hn}{mark}")
            w_total=total_won.get(w['name'],self.pot)
            await self.add_log(f"🏆 {w['emoji']} {w['name']} +{w_total}pt ({scores[0][2]})")
            # 사이드팟 수혜자 로그
            for sp_name, sp_amount in total_won.items():
                if sp_name != w['name']:
                    sp_seat = next((s for s,_,_ in scores if s['name']==sp_name), None)
                    sp_hn = next((hn for s,_,hn in scores if s['name']==sp_name), '?')
                    if sp_seat: await self.add_log(f"💰 {sp_seat['emoji']} {sp_name} 사이드팟 +{sp_amount}pt ({sp_hn})")
            win_q=w.get('meta',{}).get('win_quote','')
            commentary_extra=f' 💬 "{win_q}"' if win_q else ''
            await self.broadcast_commentary(f"🏆 {w['name']} 승리! {scores[0][2]}로 +{w_total}pt 획득!{commentary_extra}")
            # 패자 lose_quote 로그
            for s_item,_,_ in scores:
                if s_item!=w:
                    lq=s_item.get('meta',{}).get('lose_quote','')
                    if lq: await self.add_log(f"💬 {s_item['emoji']} {s_item['name']}: \"{lq}\"")
            # 프로필 통계
            self._init_stats(w['name'])
            self.player_stats[w['name']]['wins']+=1
            self.player_stats[w['name']]['total_won']+=self.pot
            self.player_stats[w['name']]['biggest_pot']=max(self.player_stats[w['name']]['biggest_pot'],self.pot)
            for s,_,_ in scores:
                self._init_stats(s['name'])
                self.player_stats[s['name']]['showdowns']+=1
            # 레어 핸드 하이라이트
            best_rank=scores[0][1][0]
            if best_rank>=7:  # 풀하우스 이상
                hl={'hand':self.hand_num,'player':w['name'],'hand_name':scores[0][2],'pot':self.pot}
                self.highlights.append(hl)
                if len(self.highlights) > 100: self.highlights = self.highlights[-50:]
                await self.broadcast({'type':'highlight','player':w['name'],'emoji':w['emoji'],'hand_name':scores[0][2],'rank':best_rank})
                if best_rank>=9: await self.add_log(f"🎆🎆🎆 {scores[0][2]}!! 역사적인 핸드!! 🎆🎆🎆")
                elif best_rank==8: await self.add_log(f"🎇🎇 포카드! 대박! 🎇🎇")
                else: await self.add_log(f"✨ {scores[0][2]}! 좋은 핸드! ✨")
                self._save_highlight(record,'rarehand',scores[0][2])
            # 빅팟 하이라이트 (200pt 이상) 또는 올인 쇼다운
            elif self.pot>=200:
                self._save_highlight(record,'bigpot')
            # 올인 쇼다운이면 항상 저장
            if any(s['chips']==0 for s in alive):
                self._save_highlight(record,'allin_showdown',scores[0][2])
            record['winner']=w['name']; record['pot']=self.pot; record['_total_won']=total_won
            update_leaderboard(w['name'], True, self.pot, self.pot)
            update_agent_stats(w['name'], net=self.pot, win=True, hand_num=self.hand_num)
            for s,_,_ in scores:
                if s!=w:
                    update_leaderboard(s['name'], False, 0)
                    # 라이벌 업데이트
                    pair=tuple(sorted([w['name'],s['name']]))
                    if pair not in self.rivalry: self.rivalry[pair]={'a_wins':0,'b_wins':0}
                    if w['name']==pair[0]: self.rivalry[pair]['a_wins']+=1
                    else: self.rivalry[pair]['b_wins']+=1

        # 관전자 베팅 정산
        if record.get('winner'):
            sb_results=resolve_spectator_bets(self.id,self.hand_num,record['winner'])
            if sb_results:
                for r in sb_results:
                    if r['win']: await self.add_log(f"🎰 관전자 {r['name']}: {r['pick']}에 {r['bet']}코인 → +{r['payout']}코인!")
                    else: await self.add_log(f"💸 관전자 {r['name']}: {r['pick']}에 {r['bet']}코인 → 꽝")
            save_leaderboard()
        # 킬스트릭 체크 (메인팟 승자 기준, split pot은 최다 획득자)
        _ks_winner=record.get('winner')
        if not _ks_winner and record.get('_total_won'):
            # split pot: 가장 많이 딴 플레이어
            _ks_winner=max(record['_total_won'],key=record['_total_won'].get,default=None)
        if _ks_winner:
            if self._killstreak_winner==_ks_winner:
                self._killstreak_count+=1
            else:
                self._killstreak_winner=_ks_winner
                self._killstreak_count=1
            if self._killstreak_count>=2:
                streak_labels={2:'🔥 더블킬!',3:'💀 트리플킬!',4:'⚡ 쿼드라킬!'}
                sl=streak_labels.get(self._killstreak_count,'👑 갓라이크!' if self._killstreak_count>=5 else '')
                if sl:
                    w_seat=next((s for s in self._hand_seats if s['name']==_ks_winner),None)
                    w_emoji=w_seat['emoji'] if w_seat else '🃏'
                    await self.broadcast_raw({'type':'killstreak','name':_ks_winner,'emoji':w_emoji,
                        'streak':self._killstreak_count,'label':sl})
                    await self.add_log(f"{sl} {w_emoji} {_ks_winner} {self._killstreak_count}연승!")
        # 다크호스 체크: 칩 꼴찌가 이겼을 때
        if record.get('winner'):
            alive=[s for s in self._hand_seats if (not s['folded'] and not s.get('out')) or s['name']==record['winner']]
            if len(alive)>=2:
                chip_sorted=sorted(self._hand_seats,key=lambda x:x['chips'])
                if chip_sorted and chip_sorted[0]['name']==record['winner']:
                    await self.broadcast({'type':'darkhorse','name':record['winner'],
                        'emoji':chip_sorted[0]['emoji'],'pot':record['pot']})
                    await self.add_log(f"🐴 다크호스! {chip_sorted[0]['emoji']} {record['winner']} 역전승!")
        # MVP 체크: 10핸드마다
        if self.hand_num>0 and self.hand_num%10==0:
            active=[s for s in self.seats if not s.get('out')]
            if active:
                mvp=max(active,key=lambda x:x['chips'])
                await self.broadcast({'type':'mvp','name':mvp['name'],'emoji':mvp['emoji'],'chips':mvp['chips'],'hand':self.hand_num})
                await self.add_log(f"👑 MVP! {mvp['emoji']} {mvp['name']} ({mvp['chips']}pt) — {self.hand_num}핸드 최다칩!")
        # ═══ 업적 체크 ═══
        scores_exist=len(scores)>0  # 쇼다운 경로에서만 scores가 채워짐
        if record.get('winner'):
            w_name=record['winner']
            w_seat=next((s for s in self._hand_seats if s['name']==w_name),None)
            # 💪 강심장: 7-2 offsuit으로 승리 (쇼다운만)
            if scores_exist and w_seat and w_seat.get('hole') and all(w_seat['hole']) and len(scores)>=2:
                ranks=sorted([RANK_VALUES[c[0]] for c in w_seat['hole']])
                suits=[c[1] for c in w_seat['hole']]
                if ranks==[2,7] and suits[0]!=suits[1]:
                    if grant_achievement(w_name,'iron_heart','💪강심장'):
                        await self.add_log(f"🏆 업적 달성! {w_seat['emoji']} {w_name}: 💪강심장 (7-2로 승리!)")
                        await self.broadcast({'type':'achievement','name':w_name,'emoji':w_seat['emoji'],'achievement':'💪강심장','desc':'7-2 offsuit으로 승리!'})
            # 🤡 호구: AA로 패배 (쇼다운만)
            if scores_exist:
                for s,_,_ in scores:
                    if s['name']!=w_name and s.get('hole') and all(s['hole']):
                        ranks=[RANK_VALUES[c[0]] for c in s['hole']]
                        if sorted(ranks)==[14,14]:
                            if grant_achievement(s['name'],'sucker','🤡호구'):
                                await self.add_log(f"🏆 업적 달성! {s['emoji']} {s['name']}: 🤡호구 (AA로 패배!)")
                                await self.broadcast({'type':'achievement','name':s['name'],'emoji':s['emoji'],'achievement':'🤡호구','desc':'포켓 에이스로 패배!'})
            # 🚛 트럭: 한 핸드에 2명+ 탈락
            busted_this_hand=[s for s in self._hand_seats if s['chips']<=0 and s['name']!=w_name]
            if len(busted_this_hand)>=2:
                if grant_achievement(w_name,'truck','🚛트럭'):
                    await self.add_log(f"🏆 업적 달성! {w_seat['emoji'] if w_seat else '🤖'} {w_name}: 🚛트럭 ({len(busted_this_hand)}명 동시 탈락!)")

        has_real=any(not s['is_bot'] for s in self.seats if not s.get('out'))
        if has_real:
            self.history.append(record)
            if len(self.history)>50: self.history=self.history[-50:]
            save_hand_history(self.id, record)
            # DB 핸드 히스토리 정리: 최근 N건만 유지
            if self.hand_num % 100 == 0:
                try:
                    db=_db()
                    max_records = LEADERBOARD_CAP if is_ranked_table(self.id) else (LEADERBOARD_CAP // 2)
                    db.execute("DELETE FROM hand_history WHERE table_id=? AND id NOT IN (SELECT id FROM hand_history WHERE table_id=? ORDER BY id DESC LIMIT ?)", (self.id, self.id, max_records))
                    db.commit()
                except: pass
            save_player_stats(self.id, self.player_stats)
            # ranked: 매 핸드 후 인게임 칩 스냅샷 저장 (크래시 복구용)
            if is_ranked_table(self.id):
                db = _db()
                for s in self.seats:
                    auth_id = s.get('_auth_id') or _ranked_auth_map.get(s['name'])
                    if auth_id:
                        db.execute("INSERT OR REPLACE INTO ranked_ingame(table_id, auth_id, name, chips, updated_at) VALUES(?,?,?,?,?)",
                            (self.id, auth_id, s['name'], s['chips'], time.time()))
                db.commit()
        # 투표 결과 → 관전자에게 방송
        if self.spectator_votes and record.get('winner'):
            correct=[vid for vid,pick in self.spectator_votes.items() if pick==record['winner']]
            total_votes=len(self.spectator_votes)
            await self._broadcast_spectators(json.dumps({'type':'vote_result','winner':record['winner'],'total':total_votes,'correct':len(correct),'vote_counts':self.vote_results},ensure_ascii=False))
            self.spectator_votes={}; self.vote_results={}; self.vote_hand=0
        # 🗯️ 승자/패자 쓰레기톡
        if record.get('winner'):
            w_name=record['winner']
            w_seat=next((s for s in self._hand_seats if s['name']==w_name),None)
            if w_seat and w_seat.get('is_bot'):
                losers=[s['name'] for s in self._hand_seats if s['name']!=w_name and not s.get('folded')]
                talk=w_seat['bot_ai'].trash_talk('win', record.get('pot',0), losers, w_seat['chips'])
                if talk:
                    entry=self.add_chat(w_name, talk); await self.broadcast_chat(entry)
            # 패자 반응
            for s in self._hand_seats:
                if s['name']!=w_name and not s.get('folded') and s.get('is_bot'):
                    talk=s['bot_ai'].trash_talk('lose', record.get('pot',0), [w_name], s['chips'])
                    if talk:
                        entry=self.add_chat(s['name'], talk); await self.broadcast_chat(entry)
        await self.broadcast_state()

# ══ 게임 매니저 ══
tables = {}

# ══ Agent Registry (lobby world) ══
import hashlib as _hl
_agent_registry = {}  # name -> {name,avatar_seed,outfit,last_seen,hands,wins,net_pt,last_table,last_hl_hand,style}
_OUTFIT_POOL = ['tuxedo','casual','dealer','street','hoodie','leather']
_STYLE_POOL = ['aggressive','tight','maniac','balanced','newbie','shark']

def touch_agent(name, table_id=None, style=None):
    now = time.time()
    if name not in _agent_registry:
        # 레지스트리 상한 (메모리 보호)
        if len(_agent_registry) > 2000:
            oldest = sorted(_agent_registry.keys(), key=lambda k: _agent_registry[k]['last_seen'])[:1000]
            for k in oldest: del _agent_registry[k]
        seed = int(_hl.md5(name.encode()).hexdigest()[:8], 16)
        _agent_registry[name] = {
            'name': name,
            'avatar_seed': seed,
            'outfit': _OUTFIT_POOL[seed % len(_OUTFIT_POOL)],
            'last_seen': now,
            'hands': 0, 'wins': 0, 'net_pt': 0,
            'last_table': table_id or 'mersoom',
            'last_hl_hand': None,
            'style': style or _STYLE_POOL[seed % len(_STYLE_POOL)],
            'joined_at': now,
        }
    else:
        _agent_registry[name]['last_seen'] = now
        if table_id: _agent_registry[name]['last_table'] = table_id
        if style: _agent_registry[name]['style'] = style

def update_agent_stats(name, net=0, win=False, hand_num=None):
    touch_agent(name)
    a = _agent_registry[name]
    a['hands'] += 1
    if win: a['wins'] += 1
    a['net_pt'] += net
    if hand_num and (net > 50 or win):
        a['last_hl_hand'] = hand_num

import re
TABLE_ID_RE=re.compile(r'^[a-zA-Z0-9_-]{1,24}$')
# MAX_TABLES는 상단 전역 상수 참조

def get_or_create_table(tid=None):
    if tid and tid in tables: return tables[tid]
    if tid and not TABLE_ID_RE.match(tid): return None
    if len(tables)>=MAX_TABLES: return None
    tid=tid or f"table_{int(time.time())}"; t=Table(tid); tables[tid]=t; return t

# ══ NPC 봇 (npc.py로 분리) ══
from npc import NPC_BOTS, _npc_trash_talk, _npc_react_to_action


def fill_npc_bots(t, count=2):
    """테이블에 NPC 봇 자동 추가"""
    current=[s['name'] for s in t.seats]
    added=0
    for name,emoji,style,bio in NPC_BOTS:
        if added>=count: break
        if name in current: continue
        if len(t.seats)>=t.MAX_PLAYERS: break
        t.add_player(name,emoji,is_bot=True,style=style,meta={'bio':bio})
        added+=1
    return added

# 서버 시작 시 mersoom 테이블 자동 생성 + NPC 봇 배치
def init_mersoom_table():
    t = get_or_create_table('mersoom')
    # DB에서 히스토리 & 통계 복원
    t.history = load_hand_history('mersoom', 50)
    if t.history:
        t.hand_num = max(h.get('hand',0) for h in t.history)
        print(f"📦 Restored {len(t.history)} hands (last #{t.hand_num})",flush=True)
    saved_stats = load_player_stats()
    if saved_stats:
        t.player_stats.update(saved_stats)
        print(f"📊 Restored stats for {len(saved_stats)} players",flush=True)
    fill_npc_bots(t, 3)  # NPC 3마리 기본 배치
    # Register NPCs in lobby
    npc_sprites = {'딜러봇':'/static/slimes/px_sit_dealer.png','도박꾼':'/static/slimes/px_sit_gambler.png','고수':'/static/slimes/px_sit_suit.png'}
    for s in t.seats:
        sp = npc_sprites.get(s['name'], '/static/slimes/px_sit_casual.png')
        _lobby_record(s['name'], sprite=sp, title='NPC')
    asyncio.get_event_loop().call_soon(lambda: asyncio.create_task(auto_start_mersoom(t)))
    return t

async def auto_start_mersoom(t):
    """NPC 봇들로 자동 게임 시작"""
    await asyncio.sleep(1)
    active=[s for s in t.seats if s['chips']>0 and not s.get('out')]
    if len(active)>=t.MIN_PLAYERS and not t.running:
        asyncio.create_task(t.run())

# ══ WebSocket ══
async def ws_send(writer, data):
    if isinstance(data,str): payload=data.encode('utf-8'); op=0x1
    else: payload=data; op=0x2
    ln=len(payload); h=bytes([0x80|op])
    if ln<126: h+=bytes([ln])
    elif ln<65536: h+=bytes([126])+struct.pack('>H',ln)
    else: h+=bytes([127])+struct.pack('>Q',ln)
    writer.write(h+payload)
    try: await asyncio.wait_for(writer.drain(), timeout=5)
    except: writer.close()

async def ws_recv(reader, timeout=30):
    try:
        b1=await asyncio.wait_for(reader.readexactly(1), timeout=timeout)
        b2=await asyncio.wait_for(reader.readexactly(1), timeout=10)
    except: return None
    op=b1[0]&0x0F
    if op==0x8: return None
    masked=bool(b2[0]&0x80); ln=b2[0]&0x7F
    try:
        if ln==126: ln=struct.unpack('>H',await asyncio.wait_for(reader.readexactly(2), timeout=10))[0]
        elif ln==127: ln=struct.unpack('>Q',await asyncio.wait_for(reader.readexactly(8), timeout=10))[0]
        if ln>65536: return None  # 64KB WS 메시지 제한
        if masked:
            mask=await asyncio.wait_for(reader.readexactly(4), timeout=10)
            data=await asyncio.wait_for(reader.readexactly(ln), timeout=10)
            data=bytes(b^mask[i%4] for i,b in enumerate(data))
        else: data=await asyncio.wait_for(reader.readexactly(ln), timeout=10)
    except: return None
    if op==0x1: return data.decode('utf-8')
    if op==0x9: return '__ping__'
    return data

def ws_accept(key):
    return base64.b64encode(hashlib.sha1((key+"258EAFA5-E914-47DA-95CA-5AB5A0F3CEBC").encode()).digest()).decode()

# ══ 스텔스 방문자 추적 시스템 ══
_visitor_log = []  # [{ip, ua, route, referer, ts, count}]
_visitor_map = {}  # ip -> {ua, routes, first_seen, last_seen, hits, referer}
_VISITOR_MAX = VISITOR_MAX  # 상수 참조

def _mask_ip(ip):
    """IP 마스킹: 마지막 옥텟 제거 (개인정보 보호)"""
    if not ip: return ''
    parts = ip.split('.')
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.{parts[2]}.xxx"
    # IPv6 or other: 마지막 4자 마스킹
    return ip[:-4] + 'xxxx' if len(ip) > 4 else ip

def _track_visitor(ip, ua, route, referer=''):
    if not ip or ip.startswith('10.') or ip=='127.0.0.1': return
    masked_ip = _mask_ip(ip)
    now = time.time()
    if masked_ip in _visitor_map:
        v = _visitor_map[masked_ip]
        v['last_seen'] = now
        v['hits'] += 1
        v['ua'] = ua
        if route not in v['routes']: v['routes'].append(route)
        if referer and not v.get('referer'): v['referer'] = referer
    else:
        _visitor_map[masked_ip] = {'ua': ua, 'routes': [route], 'first_seen': now, 'last_seen': now, 'hits': 1, 'referer': referer}
    # visitor_map 상한 (메모리 보호)
    if len(_visitor_map) > 5000:
        oldest = sorted(_visitor_map.keys(), key=lambda k: _visitor_map[k]['last_seen'])[:2500]
        for k in oldest: del _visitor_map[k]
    # 로그 (최근 200개) — IP 마스킹
    _visitor_log.append({'ip': masked_ip, 'ua': ua[:100], 'route': route, 'ts': now, 'referer': referer[:200] if referer else ''})
    if len(_visitor_log) > _VISITOR_MAX: _visitor_log.pop(0)

def _get_visitor_stats():
    now = time.time()
    # 최근 1시간 활성 방문자
    active = {ip: v for ip, v in _visitor_map.items() if now - v['last_seen'] < 3600}
    # 최근 24시간
    daily = {ip: v for ip, v in _visitor_map.items() if now - v['last_seen'] < 86400}
    return {
        'active_1h': len(active),
        'active_24h': len(daily),
        'total_unique': len(_visitor_map),
        'visitors': [
            {
                'ip': ip, 'ua': v['ua'][:80],
                'routes': v['routes'],
                'hits': v['hits'],
                'first_seen': v['first_seen'],
                'last_seen': v['last_seen'],
                'ago_min': round((now - v['last_seen']) / 60, 1),
                'referer': v.get('referer', '')
            }
            for ip, v in sorted(_visitor_map.items(), key=lambda x: x[1]['last_seen'], reverse=True)
        ],
        'recent_log': _visitor_log[-30:]
    }

# ══ HTTP + WS 서버 ══
async def handle_client(reader, writer):
    try: req_line=await asyncio.wait_for(reader.readline(),timeout=10)
    except: writer.close(); return
    if not req_line: writer.close(); return
    parts=req_line.decode('utf-8',errors='replace').strip().split()
    if len(parts)<2: writer.close(); return
    method,path=parts[0],parts[1]; headers={}; _hdr_count=0
    while True:
        try: line=await asyncio.wait_for(reader.readline(),timeout=10)
        except: writer.close(); return
        if line in (b'\r\n',b'\n',b''): break
        _hdr_count+=1
        if _hdr_count>50: writer.close(); return  # 헤더 수 제한
        decoded=line.decode('utf-8',errors='replace').strip()
        if ':' in decoded: k,v=decoded.split(':',1); headers[k.strip().lower()]=v.strip()

    # WebSocket
    if headers.get('upgrade','').lower()=='websocket':
        key=headers.get('sec-websocket-key',''); accept=ws_accept(key)
        resp=f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {accept}\r\n\r\n"
        writer.write(resp.encode()); await writer.drain()
        await handle_ws(reader,writer,path); return

    try: cl=max(0, int(headers.get('content-length',0)))
    except (ValueError, TypeError): cl=0
    body=b''
    # MAX_BODY는 상단 전역 상수 참조
    if cl>MAX_BODY:
        await send_http(writer,413,'Request body too large (max 64KB)')
        try: writer.close()
        except: pass
        return
    if cl>0:
        try: body=await asyncio.wait_for(reader.readexactly(cl), timeout=10)
        except (asyncio.TimeoutError, asyncio.IncompleteReadError):
            try: writer.close()
            except: pass
            return
    parsed=urlparse(path); route=parsed.path; qs=parse_qs(parsed.query)

    # ═══ 스텔스 방문자 추적 ═══
    _peer = writer.get_extra_info('peername')
    _peer_ip = _peer[0] if _peer else ''
    # Render proxy: x-forwarded-for 마지막 항목이 실제 클라이언트 IP (스푸핑 방지)
    _xff = headers.get('x-forwarded-for','')
    _visitor_ip = _xff.split(',')[-1].strip() if _xff else ''
    _visitor_ip = _visitor_ip or headers.get('x-real-ip','') or _peer_ip
    _visitor_ua = headers.get('user-agent','')[:200]
    if route in ('/', '/ranking', '/docs') or (route=='/api/state' and not qs.get('player')):
        _track_visitor(_visitor_ip, _visitor_ua, route, headers.get('referer',''))

    def find_table(tid=''):
        t=tables.get(tid) if tid else tables.get('mersoom')
        if not t: t=list(tables.values())[0] if tables else None
        return t

    def safe_json(raw):
        """안전한 JSON 파싱 — 실패 시 빈 dict"""
        if not raw: return {}
        try:
            result = json.loads(raw)
            return result if isinstance(result, dict) else {}
        except (json.JSONDecodeError, ValueError): return {}

    # POST 요청의 JSON 바디 유효성 검증
    if method == 'POST' and body and route.startswith('/api/'):
        try: json.loads(body)
        except (json.JSONDecodeError, ValueError):
            await send_json(writer, {'ok':False,'message':'Invalid JSON body'}, 400)
            try: writer.close()
            except: pass
            return

    _lang=qs.get('lang',[''])[0]
    if not _lang:
        _al=headers.get('accept-language','')
        _lang='' if 'ko' in _al.lower() else 'en'
    # /en redirects
    # ═══ Static file serving (CSS, images, assets) ═══
    if method=='GET' and route.startswith('/static/'):
        import os as _os
        BASE=_os.path.dirname(_os.path.abspath(__file__))
        # /static/css/xxx.css → css/xxx.css
        # /static/slimes/xxx.png → assets/slimes/xxx.png
        rel=route[len('/static/'):]
        if rel.startswith('slimes/'):
            fpath=_os.path.join(BASE,'assets','slimes',rel[len('slimes/'):])
        elif rel.startswith('fonts/'):
            fpath=_os.path.join(BASE,'assets','fonts',rel[len('fonts/'):])
        elif rel.startswith('bgm/'):
            fpath=_os.path.join(BASE,'assets','bgm',rel[len('bgm/'):])
        else:
            fpath=_os.path.join(BASE,'static',rel)
            if not _os.path.isfile(fpath):
                fpath=_os.path.join(BASE,rel)
        # Security: no directory traversal + 허용 확장자만 서빙
        fpath=_os.path.realpath(fpath)
        if not fpath.startswith(_os.path.realpath(BASE)):
            await send_http(writer,403,'Forbidden'); return
        _ALLOWED_STATIC_EXT = {'css','png','jpg','jpeg','svg','js','webp','ico','json','woff2','woff','ttf','mp3','ogg','wav'}
        _fext = fpath.rsplit('.',1)[-1].lower() if '.' in fpath else ''
        if _fext not in _ALLOWED_STATIC_EXT:
            await send_http(writer,403,'Forbidden'); return
        if _os.path.isfile(fpath):
            ext=fpath.rsplit('.',1)[-1].lower()
            ct_map={'css':'text/css; charset=utf-8','png':'image/png','jpg':'image/jpeg','jpeg':'image/jpeg','svg':'image/svg+xml','js':'application/javascript; charset=utf-8','webp':'image/webp','ico':'image/x-icon','json':'application/json','woff2':'font/woff2','woff':'font/woff','ttf':'font/ttf','mp3':'audio/mpeg','ogg':'audio/ogg','wav':'audio/wav'}
            ct=ct_map.get(ext,'application/octet-stream')
            with open(fpath,'rb') as _f: data=_f.read()
            cache='Cache-Control: public, max-age=604800\r\n' if ext in ('png','jpg','jpeg','webp','svg','woff2','woff','ttf') else 'Cache-Control: public, max-age=86400\r\n' if ext=='css' else 'Cache-Control: public, max-age=300\r\n'
            await send_http(writer,200,data,ct,extra_headers=cache)
        else:
            await send_http(writer,404,'Not Found')
        return

    # colosseum removed
    if method=='GET' and route=='/en':
        await send_http(writer,302,'','text/html',extra_headers='Location: /?lang=en\r\n')
    elif method=='GET' and route=='/en/ranking':
        await send_http(writer,302,'','text/html',extra_headers='Location: /ranking?lang=en\r\n')
    elif method=='GET' and route=='/en/docs':
        await send_http(writer,302,'','text/html',extra_headers='Location: /docs?lang=en\r\n')
    elif method=='GET' and route=='/manifest.json':
        _ver=_SW_VERSION
        _manifest=json.dumps({"name":"머슴포커","short_name":"머슴포커","description":"AI Bot Poker Arena","start_url":"/","display":"standalone","orientation":"portrait","background_color":"#0a0d14","theme_color":"#0a0d14","icons":[{"src":"/app_icon.jpg?v="+_ver,"sizes":"512x512","type":"image/jpeg","purpose":"any"},{"src":"/app_icon.jpg?v="+_ver,"sizes":"192x192","type":"image/jpeg","purpose":"maskable"}]})
        await send_http(writer,200,_manifest,'application/json','Cache-Control: no-cache\r\n')
    elif method=='GET' and route=='/sw.js':
        _sw_js="""
var CACHE_NAME='mersoom-poker-v"""+_SW_VERSION+"""';
var urlsToCache=['/'];
self.addEventListener('install',function(e){self.skipWaiting();e.waitUntil(caches.open(CACHE_NAME).then(function(c){return c.addAll(urlsToCache)}))});
self.addEventListener('activate',function(e){e.waitUntil(caches.keys().then(function(names){return Promise.all(names.filter(function(n){return n!==CACHE_NAME}).map(function(n){return caches.delete(n)}))}))});
self.addEventListener('fetch',function(e){e.respondWith(fetch(e.request).catch(function(){return caches.match(e.request)}))});
"""
        await send_http(writer,200,_sw_js,'application/javascript','Cache-Control: no-cache\r\nService-Worker-Allowed: /\r\n')
    elif method=='GET' and (route=='/app_icon.jpg' or route=='/pwa_icon.png'):
        import os as _os
        _icon_path=_os.path.join(_os.path.dirname(__file__),'static','icon.jpg')
        if not _os.path.exists(_icon_path):
            _icon_path=_os.path.join(_os.path.dirname(__file__),'pwa_icon.png')
        try:
            with open(_icon_path,'rb') as _f:_icon_data=_f.read()
            _ct='image/jpeg' if _icon_path.endswith('.jpg') else 'image/png'
            writer.write(f'HTTP/1.1 200 OK\r\nContent-Type: {_ct}\r\nContent-Length: {len(_icon_data)}\r\nCache-Control: no-cache\r\n\r\n'.encode())
            writer.write(_icon_data)
            await writer.drain()
        except:await send_http(writer,404,'Not found','text/plain')
    elif method=='GET' and route=='/':
        await send_http(writer,200,HTML_PAGE,'text/html; charset=utf-8',extra_headers='Cache-Control: no-cache, no-store, must-revalidate\r\nPragma: no-cache\r\n')
    elif method=='GET' and route=='/ranking':
        pg=RANKING_PAGE_EN if _lang=='en' else RANKING_PAGE
        await send_http(writer,200,pg,'text/html; charset=utf-8')
    elif method=='GET' and route=='/docs':
        pg=DOCS_PAGE_EN if _lang=='en' else DOCS_PAGE
        await send_http(writer,200,pg,'text/html; charset=utf-8')
    elif method=='GET' and route=='/api/games':
        games=[]
        for t in tables.values():
            g={'id':t.id,'players':len(t.seats),'running':t.running,'hand':t.hand_num,
                'round':t.round,'seats_available':t.MAX_PLAYERS-len(t.seats)}
            if is_ranked_table(t.id):
                room=RANKED_ROOMS.get(t.id,{})
                g['mode']='ranked'
                g['label']=room.get('label_en' if _lang=='en' else 'label',t.id)
                g['sb']=room.get('sb',0)
                g['bb']=room.get('bb',0)
                g['min_buy']=room.get('min_buy',0)
                g['max_buy']=room.get('max_buy',0)
                g['locked']=RANKED_LOCKED
            else:
                g['mode']='practice'
                g['label']=('🤖 Gold Table — NPC Practice' if _lang=='en' else '🤖 골드 테이블 — NPC 연습장') if t.id=='mersoom' else t.id
            games.append(g)
        await send_json(writer,{'games':games})
    elif method=='POST' and route=='/api/new':
        d=safe_json(body)
        if not _check_admin(d.get('admin_key','')):
            await send_json(writer,{'ok':False,'code':'UNAUTHORIZED','message':'인증 실패'},401); return
        tid=d.get('table_id',f"table_{int(time.time()*1000)%100000}")
        t=get_or_create_table(tid)
        timeout=d.get('timeout',60)
        timeout=max(30,min(300,int(timeout)))
        t.TURN_TIMEOUT=timeout
        await send_json(writer,{'table_id':t.id,'timeout':t.TURN_TIMEOUT,'seats_available':t.MAX_PLAYERS-len(t.seats)})
    elif method=='POST' and route=='/api/join':
        if not _api_rate_ok(_visitor_ip, 'join', 10):
            await send_json(writer,{'ok':False,'code':'RATE_LIMITED','message':'rate limited — max 10 joins/min'},429); return
        d=safe_json(body); name=sanitize_name(d.get('name','')); emoji=sanitize_name(d.get('emoji','🤖'))[:2] or '🤖'
        tid=d.get('table_id','mersoom')
        meta_version=sanitize_name(d.get('version',''))[:20]
        meta_strategy=sanitize_msg(d.get('strategy',''),30)
        meta_repo=sanitize_url(d.get('repo',''))
        meta_bio=sanitize_msg(d.get('bio',''),50)
        meta_accessories=d.get('accessories',[])
        if isinstance(meta_accessories,list):
            VALID_ACC={'crown','horns','mask','shield','propeller','flame','heart','sunglasses','tophat','bowtie','scar','bandana','monocle','cigar','halo','devil_tail','earring','headphones','scarf','flower','eyepatch','gem_crown','leaf','ribbon','round_glasses','cape','antenna','mustache','wizard_hat','ninja_mask'}
            meta_accessories=[str(a)[:20] for a in meta_accessories[:5] if str(a) in VALID_ACC]
        else: meta_accessories=[]
        VALID_EYE_STYLES={'normal','heart','star','money','sleepy','wink'}
        meta_eye_style=sanitize_name(d.get('eye_style','normal'))[:20]
        if meta_eye_style not in VALID_EYE_STYLES: meta_eye_style='normal'
        meta_death_quote=sanitize_msg(d.get('death_quote',''),50)
        meta_win_quote=sanitize_msg(d.get('win_quote',''),50)
        meta_lose_quote=sanitize_msg(d.get('lose_quote',''),50)
        if not name or len(name)<1: await send_json(writer,{'ok':False,'code':'INVALID_INPUT','message':'name 1~20자'},400); return
        # ── ranked 테이블: 머슴포인트 연동 ──
        auth_id = sanitize_name(d.get('auth_id', ''))[:12]
        try: buy_in = max(0, int(d.get('buy_in', 0)))
        except (ValueError, TypeError): buy_in = 0
        if is_ranked_table(tid):
            # 잠금 상태면 admin_key 필요
            if RANKED_LOCKED and (not _check_admin(d.get('admin_key',''))):
                await send_json(writer, {'ok': False, 'code': 'RANKED_LOCKED',
                    'message': '머슴 매치는 현재 비공개 테스트 중입니다.'}, 403)
                return
            room = RANKED_ROOMS[tid]
            mersoom_pw = d.get('password', '')
            if not auth_id or not mersoom_pw:
                await send_json(writer, {'ok': False, 'code': 'AUTH_REQUIRED',
                    'message': f'ranked 테이블은 auth_id + password(머슴닷컴) 필수. (방: {room["label"]})'}, 400)
                return
            # 계정 검증 (캐시 먼저 확인)
            cache_key = _auth_cache_key(auth_id, mersoom_pw)
            if not _auth_cache_check(auth_id, cache_key):
                verified, _ = await asyncio.get_event_loop().run_in_executor(
                    None, mersoom_verify_account, auth_id, mersoom_pw)
                if not verified:
                    await send_json(writer, {'ok': False, 'code': 'AUTH_FAILED',
                        'message': '머슴닷컴 계정 인증 실패. auth_id와 password를 확인하세요.'}, 401)
                    return
                _auth_cache_set(auth_id, cache_key)
            # 동일 auth_id 다중좌석 방지 (모든 ranked 테이블 검색)
            for rtid in RANKED_ROOMS:
                rt = find_table(rtid)
                if rt:
                    dupe = next((s for s in rt.seats if s.get('_auth_id') == auth_id and not s.get('out')), None)
                    if dupe:
                        await send_json(writer, {'ok': False, 'code': 'ALREADY_SEATED',
                            'message': f'이미 {rtid} 테이블에 착석 중 ({dupe["name"]}). 먼저 퇴장하세요.'}, 409)
                        return
            # 입금 체크 (최신 반영)
            await asyncio.get_event_loop().run_in_executor(None, mersoom_check_deposits)
            bal = ranked_balance(auth_id)
            if buy_in <= 0:
                buy_in = min(bal, room['max_buy'])  # 기본: 잔고 또는 최대 바이인
            # min/max 체크
            if buy_in < room['min_buy']:
                await send_json(writer, {'ok': False, 'code': 'BUY_IN_TOO_LOW',
                    'message': f'최소 바이인 {room["min_buy"]}pt (요청: {buy_in}pt, 잔고: {bal}pt)'}, 400)
                return
            if buy_in > room['max_buy']:
                buy_in = room['max_buy']  # 최대 바이인으로 클램프
            if buy_in <= 0 or bal <= 0:
                await send_json(writer, {'ok': False, 'code': 'NO_BALANCE',
                    'message': f'잔고 부족 ({bal}pt). dolsoe 계정으로 포인트를 선물하세요.'}, 400)
                return
            if buy_in > bal:
                await send_json(writer, {'ok': False, 'code': 'INSUFFICIENT',
                    'message': f'바이인({buy_in}pt)이 잔고({bal}pt)를 초과합니다.'}, 400)
                return
            # 잔고 차감
            ok_deduct, remaining = ranked_deposit(auth_id, buy_in)
            if not ok_deduct:
                await send_json(writer, {'ok': False, 'code': 'INSUFFICIENT',
                    'message': f'잔고 부족 ({remaining}pt)'}, 400)
                return
            _ranked_audit('buy_in', auth_id, buy_in, remaining + buy_in, remaining, f'table:{tid} name:{name}')
            with _ranked_lock:
                _ranked_auth_map[name] = auth_id
            # 메모리 캡: 1000건 초과 시 정리
            if len(_ranked_auth_map) > 1000:
                active_names = set()
                for rtid in RANKED_ROOMS:
                    rt = tables.get(rtid)
                    if rt:
                        for s in rt.seats:
                            if not s.get('out'): active_names.add(s['name'])
                keep = {n: a for n, a in _ranked_auth_map.items() if n in active_names}
                _ranked_auth_map.clear()
                _ranked_auth_map.update(keep)
        t=find_table(tid)
        if not t: t=get_or_create_table(tid)
        if not t: await send_json(writer,{'ok':False,'code':'INVALID_INPUT','message':'invalid table_id or max tables reached'},400); return
        # ranked 테이블 블라인드 설정
        if is_ranked_table(tid):
            room = RANKED_ROOMS[tid]
            t.SB = room['sb']; t.BB = room['bb']
            t.BLIND_SCHEDULE = [(room['sb'], room['bb'])]  # 블라인드 에스컬레이션 없음
        # ranked 테이블에는 NPC 안 넣음 — NPC 로직 스킵
        if not is_ranked_table(tid):
            # 실제 에이전트 입장 시: 자리 부족하면 NPC 1마리 퇴장
            if len(t.seats)>=t.MAX_PLAYERS:
                npc_seat=next((s for s in t.seats if s['is_bot'] and not s.get('_protected')),None)
                if npc_seat and not t.running:
                    t.seats.remove(npc_seat)
                    await t.add_log(f"🤖 {npc_seat['emoji']} {npc_seat['name']} NPC 퇴장 (에이전트 양보)")
                elif npc_seat and t.running:
                    npc_seat['out']=True; npc_seat['folded']=True
                    await t.add_log(f"🤖 {npc_seat['emoji']} {npc_seat['name']} NPC 퇴장 (에이전트 양보)")
            # 실제 에이전트 2명 이상이면 나머지 NPC도 퇴장
            real_count=sum(1 for s in t.seats if not s['is_bot'])+1  # +1 for incoming
            if real_count>=2:
                npcs=[s for s in t.seats if s['is_bot']]
                for npc in npcs:
                    if t.running:
                        npc['out']=True; npc['folded']=True
                    else:
                        t.seats.remove(npc)
                    await t.add_log(f"🤖 {npc['emoji']} {npc['name']} NPC 퇴장 (에이전트끼리 대결!)")
        result=t.add_player(name,emoji)
        if isinstance(result,str) and result.startswith('COOLDOWN:'):
            remaining=result.split(':')[1]
            # ranked면 잔고 환불
            if is_ranked_table(tid) and auth_id:
                ranked_credit(auth_id, buy_in)
            await send_json(writer,{'ok':False,'code':'COOLDOWN','message':f'파산 쿨다운 중! {remaining}초 후 재참가 가능','cooldown':int(remaining)},429); return
        if not result:
            # ranked면 잔고 환불
            if is_ranked_table(tid) and auth_id:
                ranked_credit(auth_id, buy_in)
            # 중복 닉네임이면 새 토큰 재발급 (토큰 분실 복구)
            existing_seat=next((s for s in t.seats if s['name']==name and not s.get('out')),None)
            if existing_seat and not existing_seat['is_bot']:
                # ranked: auth_id 일치 검증 (닉네임 하이잭 방지)
                if is_ranked_table(tid):
                    seat_auth = existing_seat.get('_auth_id')
                    if seat_auth and seat_auth != auth_id:
                        await send_json(writer,{'ok':False,'code':'AUTH_MISMATCH',
                            'message':'해당 닉네임은 다른 계정이 사용 중입니다.'},403); return
                token=issue_token(name)
                await send_json(writer,{'ok':True,'table_id':t.id,'your_seat':t.seats.index(existing_seat),
                    'players':[s['name'] for s in t.seats],'token':token,'reconnected':True})
                await t.add_log(f"🔄 {existing_seat['emoji']} {name} 재접속!")
                return
            await send_json(writer,{'ok':False,'message':'테이블 꽉참 or 중복 닉네임'},400); return
        # ranked면 칩을 buy_in으로 세팅
        if is_ranked_table(tid):
            joined_seat=next((s for s in t.seats if s['name']==name),None)
            if joined_seat:
                joined_seat['chips'] = buy_in
                joined_seat['_auth_id'] = auth_id  # 환전용 매핑
        # 메타데이터 저장
        joined_seat=next((s for s in t.seats if s['name']==name),None)
        if joined_seat:
            joined_seat['meta']={'version':meta_version,'strategy':meta_strategy,'repo':meta_repo,'bio':meta_bio,'death_quote':meta_death_quote,'win_quote':meta_win_quote,'lose_quote':meta_lose_quote,'accessories':meta_accessories,'eye_style':meta_eye_style}
        # 리더보드에도 메타 저장
        if name not in leaderboard:
            if len(leaderboard) > 5000:
                # hands=0인 유저 정리
                stale = [k for k, v in leaderboard.items() if v.get('hands', 0) == 0]
                for k in stale[:2500]: del leaderboard[k]
            leaderboard[name]={'wins':0,'losses':0,'chips_won':0,'hands':0,'biggest_pot':0,'streak':0}
        leaderboard[name]['meta']={'version':meta_version,'strategy':meta_strategy,'repo':meta_repo,'bio':meta_bio,'death_quote':meta_death_quote,'win_quote':meta_win_quote,'lose_quote':meta_lose_quote}
        # NPC→에이전트 전환 시점에만 전원 칩 리셋 (ranked 제외)
        if not is_ranked_table(tid):
            real_count_check=sum(1 for s in t.seats if not s['is_bot'])
            if real_count_check==2:
                for s in t.seats:
                    if not s['is_bot']:
                        s['chips']=t.START_CHIPS
                await t.add_log("🔄 에이전트 대결! 전원 칩 리셋 (500pt)")
        await t.add_log(f"🚪 {emoji} {name} 입장! ({len(t.seats)}/{t.MAX_PLAYERS})" + (f" [바이인: {buy_in}pt]" if is_ranked_table(tid) else ''))
        # ranked 대기열 알림: 1명뿐이면 대기 상태 표시
        if is_ranked_table(tid):
            active_ranked = [s for s in t.seats if s['chips'] > 0 and not s.get('out')]
            if len(active_ranked) == 1:
                await t.add_log(f"⏳ {name} 대전 상대 대기 중... (상대가 입장하면 자동 시작)")
        # 2명 이상이면 자동 시작
        active=[s for s in t.seats if s['chips']>0]
        if len(active)>=t.MIN_PLAYERS:
            if not t.running:
                asyncio.create_task(t.run())
            elif t.turn_player is None and time.time()-t.created>30:
                # running=True인데 턴이 없으면 stuck — 강제 리셋
                t.running=False; t.round='waiting'
                asyncio.create_task(t.run())
        token=issue_token(name)
        join_src = sanitize_name(d.get('src',''))[:30] or 'direct'
        _telemetry_log.append({'ts':time.time(),'ev':'join_success','name':name,'table':t.id,'src':join_src})
        if len(_telemetry_log) > TELEMETRY_LOG_CAP: _telemetry_log[:] = _telemetry_log[-TELEMETRY_LOG_CAP:]
        touch_agent(name, t.id, d.get('strategy','')[:20] or None)
        _lobby_record(name, sprite=f'/static/slimes/px_sit_suit.png', title=meta_strategy or meta_bio or '')
        resp={'ok':True,'table_id':t.id,'your_seat':len(t.seats)-1,
            'players':[s['name'] for s in t.seats],'token':token}
        if is_ranked_table(tid):
            room = RANKED_ROOMS[tid]
            resp['buy_in'] = buy_in
            resp['remaining_balance'] = ranked_balance(auth_id)
            resp['mode'] = 'ranked'
            resp['room'] = {'id': tid, 'label': room['label'], 'min_buy': room['min_buy'], 'max_buy': room['max_buy'], 'sb': room['sb'], 'bb': room['bb']}
        await send_json(writer, resp)
    elif method=='GET' and route=='/api/version':
        await send_json(writer,{'version':APP_VERSION,'ok':True})
        return
    elif method=='GET' and route=='/api/lobby_agents':
        import time as _t
        agents = _lobby_get_agents()
        await send_json(writer,{'ok':True,'server_time':_t.time(),'agents':agents})
        return
    elif method=='GET' and route=='/api/state':
        tid=qs.get('table_id',[''])[0]; player=qs.get('player',[''])[0]
        token=qs.get('token',[''])[0]
        _if_none_match=headers.get('if-none-match','').strip('" ')
        t=find_table(tid)
        if not t: await send_json(writer,{'ok':False,'code':'NOT_FOUND','message':'no game'},404); return
        if player:
            # 토큰 검증: 토큰 있으면 검증, 없으면 public state만 반환 (홀카드 숨김)
            if token and verify_token(player, token):
                state=t.get_public_state(viewer=player)
                if t.turn_player==player: state['turn_info']=t.get_turn_info(player)
            else:
                # 토큰 없거나 불일치 → 딜레이된 관전자 뷰 (홀카드 숨김)
                if t.last_spectator_state:
                    state=json.loads(t.last_spectator_state)
                else:
                    state=t.get_spectator_state()
                    # API 직접 호출에서는 진행 중 홀카드 강제 숨김 (tv_mode 딜레이 우회 방지)
                    if state.get('round') not in ('showdown','between','finished'):
                        for p in state.get('players',[]):
                            p['hole']=None; p.pop('hand_name',None); p.pop('hand_rank',None)
        else:
            # 관전자: 딜레이된 state (TV중계)
            spec_name=qs.get('spectator',['관전자'])[0]
            t.poll_spectators[spec_name]=time.time()
            t.poll_spectators={k:v for k,v in t.poll_spectators.items() if time.time()-v<10}
            # 딜레이된 캐시 state 사용, 없으면 현재 관전자 state (최초 접속 시)
            if t.last_spectator_state:
                state=json.loads(t.last_spectator_state)
            else:
                state=t.get_spectator_state()
                # API 직접 호출에서는 진행 중 홀카드 강제 숨김
                if state.get('round') not in ('showdown','between','finished'):
                    for p in state.get('players',[]):
                        p['hole']=None; p.pop('hand_name',None); p.pop('hand_rank',None)
        if _lang=='en': _translate_state(state, 'en')
        # ETag: 304 Not Modified 지원 — 폴링 트래픽 절감
        _state_bytes=json.dumps(state,ensure_ascii=False,sort_keys=True).encode('utf-8')
        _etag=hashlib.md5(_state_bytes).hexdigest()[:16]
        if _if_none_match and _if_none_match==_etag:
            await send_http(writer,304,b'','application/json',extra_headers=f'ETag: "{_etag}"\r\nCache-Control: no-cache\r\n')
        else:
            await send_http(writer,200,_state_bytes,'application/json; charset=utf-8',extra_headers=f'ETag: "{_etag}"\r\nCache-Control: no-cache\r\n')
    elif method=='POST' and route=='/api/action':
        if not _api_rate_ok(_visitor_ip, 'action', 30):
            await send_json(writer,{'ok':False,'code':'RATE_LIMITED','message':'rate limited — max 30 actions/min'},429); return
        d=safe_json(body); name=d.get('name',''); tid=d.get('table_id','')
        token=d.get('token','')
        # 이름 기반 레이트리밋 (프록시/공용IP 우회 방지)
        if name and not _api_rate_ok(f'name:{name}', 'action', 30):
            await send_json(writer,{'ok':False,'code':'RATE_LIMITED','message':'rate limited'},429); return
        t=find_table(tid)
        if not t: await send_json(writer,{'ok':False,'code':'NOT_FOUND','message':'no game'},404); return
        if not require_token(name,token):
            await send_json(writer,{'ok':False,'code':'UNAUTHORIZED','message':'token required'},401); return
        if t.turn_player!=name:
            await send_json(writer,{'ok':False,'code':'NOT_YOUR_TURN','message':'not your turn','current_turn':t.turn_player},400); return
        # mood 필드 처리
        mood=d.get('mood','')
        if mood:
            mood=mood[:2]
            seat=next((s for s in t.seats if s['name']==name),None)
            if seat: seat['last_mood']=mood
        result=t.handle_api_action(name,d)
        if result=='OK': await send_json(writer,{'ok':True})
        elif result=='TURN_MISMATCH': await send_json(writer,{'ok':False,'code':'TURN_MISMATCH','message':'stale turn_seq','current_turn_seq':t.turn_seq},409)
        elif result=='ALREADY_ACTED': await send_json(writer,{'ok':False,'code':'ALREADY_ACTED','message':'action already submitted'},409)
        else: await send_json(writer,{'ok':False,'code':'NOT_YOUR_TURN','message':'not your turn'},400)
    elif method=='POST' and route=='/api/chat':
        if not _api_rate_ok(_visitor_ip, 'chat', 15):
            await send_json(writer,{'ok':False,'code':'RATE_LIMITED','message':'rate limited'},429); return
        d=safe_json(body); name=sanitize_name(d.get('name','')); msg=sanitize_msg(d.get('msg',''),120); tid=d.get('table_id','')
        # 이름 기반 레이트리밋
        if name and not _api_rate_ok(f'name:{name}', 'chat', 15):
            await send_json(writer,{'ok':False,'code':'RATE_LIMITED','message':'rate limited'},429); return
        token=d.get('token','')
        if not name or not msg: await send_json(writer,{'ok':False,'code':'INVALID_INPUT','message':'name and msg required'},400); return
        if not require_token(name,token):
            await send_json(writer,{'ok':False,'code':'UNAUTHORIZED','message':'token required'},401); return
        t=find_table(tid)
        if not t: await send_json(writer,{'ok':False,'code':'NOT_FOUND','message':'no game'},404); return
        # 쿨다운 체크
        now=time.time()
        if len(chat_cooldowns) > 2000:
            cutoff = now - 30
            stale = [k for k, v in chat_cooldowns.items() if v < cutoff]
            for k in stale: del chat_cooldowns[k]
            if len(chat_cooldowns) > 2000:
                oldest = sorted(chat_cooldowns.keys(), key=lambda k: chat_cooldowns[k])[:1000]
                for k in oldest: del chat_cooldowns[k]
        last=chat_cooldowns.get(name,0)
        if now-last<CHAT_COOLDOWN:
            retry_after=round((CHAT_COOLDOWN-(now-last))*1000)
            await send_json(writer,{'ok':False,'code':'RATE_LIMIT','message':'chat cooldown','retry_after_ms':retry_after},429); return
        chat_cooldowns[name]=now
        entry=t.add_chat(name,msg); await t.broadcast_chat(entry)
        await send_json(writer,{'ok':True})
    elif method=='POST' and route=='/api/leave':
        d=safe_json(body); name=d.get('name',''); tid=d.get('table_id','')
        token=d.get('token','')
        if not name: await send_json(writer,{'ok':False,'code':'INVALID_INPUT','message':'name required'},400); return
        if not token or not verify_token(name,token):
            await send_json(writer,{'ok':False,'code':'UNAUTHORIZED','message':'token required'},401); return
        # table_id 미지정 시 플레이어가 있는 테이블 자동 탐색
        t = None
        if tid:
            t = find_table(tid)
        else:
            for _tid, _tbl in tables.items():
                if any(s['name'] == name and not s.get('out') for s in _tbl.seats):
                    t = _tbl; tid = _tid; break
            if not t: t = find_table('mersoom'); tid = 'mersoom'
        if not t: await send_json(writer,{'ok':False,'code':'NOT_FOUND','message':'no game'},404); return
        seat=next((s for s in t.seats if s['name']==name and not s.get('out')),None)
        if not seat:
            # 이미 out된 좌석도 찾아서 안내
            ghost=next((s for s in t.seats if s['name']==name and s.get('out')),None)
            if ghost:
                await send_json(writer,{'ok':False,'code':'ALREADY_LEFT','message':'이미 퇴장한 상태입니다'},400); return
            await send_json(writer,{'ok':False,'code':'NOT_FOUND','message':'not in game'},400); return
        chips=seat['chips']
        auth_id_leave = seat.get('_auth_id') or _ranked_auth_map.get(name)
        # ── ranked: 칩을 0으로 만든 후 잔고 환원 (더블 캐시아웃 방지) ──
        cashout_info = None
        if is_ranked_table(tid) and auth_id_leave and chips > 0:
            seat['chips'] = 0  # ★ 칩 즉시 0으로 (재호출 시 chips=0이라 환전 안 됨)
            seat['_cashed_out'] = True  # ★ WS disconnect 이중 정산 방지 플래그
            ranked_credit(auth_id_leave, chips)
            _ranked_audit('leave_cashout', auth_id_leave, chips, details=f'table:{tid} name:{name}')
            # ranked_ingame 스냅샷 삭제 (크래시 복구 이중 크레딧 방지)
            try:
                db = _db()
                db.execute("DELETE FROM ranked_ingame WHERE table_id=? AND auth_id=?", (tid, auth_id_leave))
                db.commit()
            except: pass
            cashout_info = {'auth_id': auth_id_leave, 'cashed_out': chips, 'balance': ranked_balance(auth_id_leave)}
        if not t.running:
            t.seats.remove(seat)
        else:
            seat['out']=True; seat['folded']=True; seat['chips']=0
        await t.add_log(f"🚪 {seat['emoji']} {name} 퇴장! (칩: {chips}pt)")
        if name in t.player_ws: del t.player_ws[name]
        # 토큰 무효화 (재사용 방지)
        if name in player_tokens: del player_tokens[name]
        if cashout_info:
            await t.add_log(f"💰 {name} 환전: {chips}pt → 잔고 ({cashout_info['balance']}pt)")
        # 실제 에이전트가 부족해지면 NPC 리필 (ranked 제외)
        if not is_ranked_table(tid):
            real_left=[s for s in t.seats if not s['is_bot'] and not s.get('out')]
            if len(real_left)<2 and not t.running:
                fill_npc_bots(t, max(0, 3-len(t.seats)))
                npc_active=[s for s in t.seats if s['chips']>0 and not s.get('out')]
                if len(npc_active)>=t.MIN_PLAYERS and not t.running:
                    await t.add_log("🤖 NPC 봇 복귀! 자동 게임 시작")
                    asyncio.create_task(t.run())
        await t.broadcast_state()
        resp = {'ok':True,'chips':chips}
        if cashout_info:
            resp['cashout'] = cashout_info
        await send_json(writer, resp)
    elif method=='GET' and route=='/api/lobby/world':
        now = time.time()
        # Touch NPC bots
        for n,e,s,d in NPC_BOTS:
            touch_agent(n, 'mersoom', s)
        # Live: currently at table or seen in last 30s
        live = [a for a in _agent_registry.values() if now - a['last_seen'] < 30]
        # Ghosts: seen in last 24h, sorted by net_pt desc
        ghosts = sorted(
            [a for a in _agent_registry.values() if now - a['last_seen'] >= 30 and now - a['last_seen'] < 86400],
            key=lambda x: -x['net_pt']
        )[:20]
        # Highlights from table
        hls = []
        if 'mersoom' in tables:
            t = tables['mersoom']
            if hasattr(t, '_highlights') and t._highlights:
                hls = t._highlights[-3:]
        await send_json(writer, {
            'live': [{k:v for k,v in a.items() if k!='joined_at'} for a in live],
            'ghosts': [{k:v for k,v in a.items() if k!='joined_at'} for a in ghosts],
            'highlights': hls,
            'total_agents': len(_agent_registry),
        })
    elif method=='GET' and route=='/api/leaderboard':
        bot_names={name for name,_,_,_ in NPC_BOTS}
        try: min_hands=min(1000, max(0, int(qs.get('min_hands',['0'])[0])))
        except (ValueError, TypeError): min_hands=0
        filtered={n:d for n,d in leaderboard.items() if n not in bot_names and d['hands']>=min_hands}
        lb=sorted(filtered.items(),key=lambda x:(x[1].get('elo',1000),x[1]['wins']),reverse=True)[:20]
        # 명예의 전당 배지 계산
        badges={}
        if filtered:
            best_streak=max(filtered.items(),key=lambda x:x[1].get('streak',0),default=None)
            if best_streak and best_streak[1].get('streak',0)>=3: badges[best_streak[0]]=badges.get(best_streak[0],[])+['🏅연승왕']
            best_pot=max(filtered.items(),key=lambda x:x[1].get('biggest_pot',0),default=None)
            if best_pot and best_pot[1].get('biggest_pot',0)>0: badges[best_pot[0]]=badges.get(best_pot[0],[])+['💰빅팟']
            best_wr=max(((n,d) for n,d in filtered.items() if d['hands']>=10),key=lambda x:x[1]['wins']/(x[1]['wins']+x[1]['losses']) if (x[1]['wins']+x[1]['losses'])>0 else 0,default=None)
            if best_wr: badges[best_wr[0]]=badges.get(best_wr[0],[])+['🗡️최강']
        # MBTI 계산 (프로필에서 가져오기)
        t=find_table('mersoom')
        lb_data={'leaderboard':[]}
        for n,d in lb:
            entry={'name':n,'wins':d['wins'],'losses':d['losses'],
                'chips_won':d['chips_won'],'hands':d['hands'],'biggest_pot':d['biggest_pot'],
                'streak':d.get('streak',0),'elo':d.get('elo',1000),
                'badges':badges.get(n,[])+[a['label'] for a in d.get('achievements',[])],
                'achievements':d.get('achievements',[]),
                'meta':d.get('meta',{'version':'','strategy':'','repo':''})}
            if t and n in t.player_stats:
                prof=t.get_profile(n)
                entry['mbti']=prof.get('mbti',''); entry['mbti_name']=prof.get('mbti_name','')
                entry['aggression']=prof.get('aggression',0); entry['vpip']=prof.get('vpip',0)
            lb_data['leaderboard'].append(entry)
        if _lang=='en':
            for entry in lb_data['leaderboard']:
                entry['badges']=[_translate_text(b,'en') for b in entry['badges']]
                entry['achievements']=[{'id':a['id'],'label':ACHIEVEMENT_DESC_EN.get(a['id'],{}).get('label',a['label']),'ts':a.get('ts',0)} for a in entry['achievements']]
        await send_json(writer,lb_data)
    elif method=='POST' and route=='/api/bet':
        if not _api_rate_ok(_visitor_ip, 'bet', 10):
            await send_json(writer,{'ok':False,'code':'RATE_LIMITED','message':'rate limited — max 10 bets/min'},429); return
        d=safe_json(body)
        name=sanitize_name(d.get('name','')); pick=sanitize_name(d.get('pick',''))
        try: amount=max(0, int(d.get('amount',0)))
        except (ValueError, TypeError): amount=0
        tid=d.get('table_id','mersoom'); t=find_table(tid)
        if not t or not t.running: await send_json(writer,{'ok':False,'message':'게임 진행중 아님'},400); return
        if not name or not pick: await send_json(writer,{'ok':False,'message':'name, pick 필수'},400); return
        if not any(s['name']==pick for s in t.seats if not s.get('out')): await send_json(writer,{'ok':False,'message':'해당 플레이어 없음'},400); return
        ok,msg=place_spectator_bet(tid,t.hand_num,name,pick,amount)
        if ok:
            await t.add_log(f"🎰 관전자 {name}: {pick}에게 {amount}코인 베팅!")
            await send_json(writer,{'ok':True,'coins':get_spectator_coins(name)})
        else: await send_json(writer,{'ok':False,'message':msg},400)
    elif method=='GET' and route=='/api/coins':
        name=qs.get('name',[''])[0]
        if not name: await send_json(writer,{'ok':False,'message':'name 필수'},400); return
        await send_json(writer,{'name':name,'coins':get_spectator_coins(name)})
    elif route.startswith('/api/ranked/'):
        # ranked 전체 잠금 체크
        if RANKED_LOCKED:
            _ak = qs.get('admin_key',[''])[0]
            if not _ak and body:
                try: _ak = json.loads(body).get('admin_key','')
                except: _ak = ''
            if not _check_admin(_ak):
                await send_json(writer, {'ok':False, 'code': 'RANKED_LOCKED', 'message': '머슴 매치는 현재 비공개 테스트 중입니다.'}, 403)
                return
        # ── ranked API (잠금 통과 후) ──
        if method=='GET' and route=='/api/ranked/leaderboard':
            db = _db()
            rows = db.execute("""SELECT auth_id, balance, total_deposited, total_withdrawn
                FROM ranked_balances ORDER BY (balance + total_withdrawn - total_deposited) DESC LIMIT 20""").fetchall()
            lb = []
            for r in rows:
                net_profit = (r[1] + r[3]) - r[2]
                lb.append({'auth_id': r[0], 'balance': r[1], 'deposited': r[2], 'withdrawn': r[3], 'net_profit': net_profit})
            await send_json(writer, {'leaderboard': lb})
        elif method=='GET' and route=='/api/ranked/rooms':
            rooms = []
            for rid, cfg in RANKED_ROOMS.items():
                t = find_table(rid)
                players = len(t.seats) if t else 0
                running = t.running if t else False
                rooms.append({'id': rid, 'label': cfg['label'], 'min_buy': cfg['min_buy'], 'max_buy': cfg['max_buy'],
                    'sb': cfg['sb'], 'bb': cfg['bb'], 'players': players, 'running': running})
            await send_json(writer, {'rooms': rooms})
        elif method=='GET' and route=='/api/ranked/house':
            if not _check_admin(qs.get('admin_key',[''])[0]):
                await send_json(writer, {'ok':False,'message':'인증 실패'}, 401); return
            house_points = 0
            if MERSOOM_AUTH_ID and MERSOOM_PASSWORD:
                try:
                    h_status, h_data = await asyncio.get_event_loop().run_in_executor(None,
                        lambda: _http_request(f'{MERSOOM_API}/points/me',
                            headers={'X-Mersoom-Auth-Id': MERSOOM_AUTH_ID, 'X-Mersoom-Password': MERSOOM_PASSWORD}))
                    if h_status == 200 and isinstance(h_data, dict):
                        house_points = h_data.get('points', 0)
                except: pass
            db = _db()
            stats = db.execute("SELECT COALESCE(SUM(balance),0), COALESCE(SUM(total_deposited),0), COALESCE(SUM(total_withdrawn),0), COUNT(*) FROM ranked_balances").fetchone()
            total_balance, total_deposited, total_withdrawn, total_users = stats
            warning = None
            if house_points < total_balance:
                warning = f'⚠️ 하우스 포인트({house_points}) < 유저 잔고 합계({total_balance}). 환전 불가 위험!'
            await send_json(writer, {
                'house_points': house_points, 'total_user_balance': total_balance,
                'total_deposited': total_deposited, 'total_withdrawn': total_withdrawn,
                'total_users': total_users, 'warning': warning
            })
        elif method=='GET' and route=='/api/ranked/watchdog':
            if not _check_admin(qs.get('admin_key',[''])[0]):
                await send_json(writer, {'ok':False,'message':'인증 실패'}, 401); return
            report = _ranked_watchdog_report()
            await send_json(writer, report)
        elif method=='GET' and route=='/api/ranked/audit':
            if not _check_admin(qs.get('admin_key',[''])[0]):
                await send_json(writer, {'ok':False,'message':'인증 실패'}, 401); return
            r_auth = qs.get('auth_id',[''])[0]
            try: limit = min(200, max(1, int(qs.get('limit',['50'])[0])))
            except: limit = 50
            db = _db()
            if r_auth:
                rows = db.execute("SELECT ts, event, auth_id, amount, balance_before, balance_after, details, ip FROM ranked_audit_log WHERE auth_id=? ORDER BY ts DESC LIMIT ?", (r_auth, limit)).fetchall()
            else:
                rows = db.execute("SELECT ts, event, auth_id, amount, balance_before, balance_after, details, ip FROM ranked_audit_log ORDER BY ts DESC LIMIT ?", (limit,)).fetchall()
            entries = [{'ts': r[0], 'event': r[1], 'auth_id': r[2], 'amount': r[3],
                       'balance_before': r[4], 'balance_after': r[5], 'details': r[6], 'ip': r[7]} for r in rows]
            await send_json(writer, {'audit_log': entries, 'count': len(entries)})
        elif method=='POST' and route=='/api/ranked/balance':
            d=safe_json(body)
            r_auth=d.get('auth_id',''); r_pw=d.get('password','')
            if not r_auth or not r_pw: await send_json(writer,{'ok':False,'message':'auth_id, password 필수'},400); return
            # 본인 인증 (다른 사람 잔고 조회 방지)
            cache_key = _auth_cache_key(r_auth, r_pw)
            if not _auth_cache_check(r_auth, cache_key):
                verified, _ = await asyncio.get_event_loop().run_in_executor(
                    None, mersoom_verify_account, r_auth, r_pw)
                if not verified:
                    await send_json(writer,{'ok':False,'message':'머슴닷컴 계정 인증 실패'},401); return
                _auth_cache_set(r_auth, cache_key)
            await asyncio.get_event_loop().run_in_executor(None, mersoom_check_deposits)
            bal=ranked_balance(r_auth)
            await send_json(writer,{'auth_id':r_auth,'balance':bal})
        elif method=='POST' and route=='/api/ranked/withdraw':
            if not _api_rate_ok(_visitor_ip, 'ranked_withdraw', 5):
                await send_json(writer,{'ok':False,'message':'rate limited'},429); return
            d=safe_json(body)
            r_auth=d.get('auth_id',''); r_pw=d.get('password','')
            _idemp_key=d.get('idempotency_key','')
            try: amount=max(0, int(d.get('amount',0)))
            except (ValueError, TypeError): amount=0
            if not r_auth or not r_pw or amount<=0:
                await send_json(writer,{'ok':False,'message':'auth_id, password, amount(>0) 필수'},400); return
            # Idempotency: 중복 출금 방지
            if _idemp_key:
                with _ranked_lock:
                    _db_c=_db()
                    _db_c.execute("CREATE TABLE IF NOT EXISTS withdraw_idempotency(key TEXT PRIMARY KEY, auth_id TEXT, amount INT, created_at INT)")
                    _existing=_db_c.execute("SELECT auth_id,amount FROM withdraw_idempotency WHERE key=?",(_idemp_key,)).fetchone()
                    if _existing:
                        await send_json(writer,{'ok':True,'withdrawn':_existing[1],'remaining_balance':ranked_balance(r_auth),'idempotent':True})
                        return
                    _db_c.execute("INSERT INTO withdraw_idempotency(key,auth_id,amount,created_at) VALUES(?,?,?,strftime('%s','now'))",(_idemp_key,r_auth,amount))
                    _db_c.commit()
            cache_key = _auth_cache_key(r_auth, r_pw)
            if not _auth_cache_check(r_auth, cache_key):
                verified, _ = await asyncio.get_event_loop().run_in_executor(
                    None, mersoom_verify_account, r_auth, r_pw)
                if not verified:
                    await send_json(writer,{'ok':False,'message':'머슴닷컴 계정 인증 실패'},401); return
                _auth_cache_set(r_auth, cache_key)
            wlock = _get_withdraw_lock(r_auth)
            if wlock.locked():
                await send_json(writer,{'ok':False,'message':'이전 출금 처리 중입니다. 잠시 후 다시 시도해주세요.'},429); return
            async with wlock:
                bal=ranked_balance(r_auth)
                if amount>bal:
                    await send_json(writer,{'ok':False,'message':f'잔고 부족'},400); return
                ok_d, rem = ranked_deposit(r_auth, amount)
                if not ok_d:
                    await send_json(writer,{'ok':False,'message':'차감 실패'},500); return
                # withdraw_pending DB 기록 (크래시 복구용 — 차감 후 API 호출 전 크래시 대비)
                _wp_id = f"wp:{r_auth}:{amount}:{int(time.time())}"
                try:
                    with _ranked_lock:
                        db=_db()
                        db.execute("CREATE TABLE IF NOT EXISTS withdraw_pending(id TEXT PRIMARY KEY, auth_id TEXT, amount INT, created_at REAL)")
                        db.execute("INSERT OR IGNORE INTO withdraw_pending(id, auth_id, amount, created_at) VALUES(?,?,?,?)",
                            (_wp_id, r_auth, amount, time.time()))
                        db.commit()
                except: pass
                # 출금 중 플래그 — WS disconnect cashout 차단
                _withdrawing_users.add(r_auth)
                try:
                    ok_w, msg_w = await asyncio.get_event_loop().run_in_executor(None, mersoom_withdraw, r_auth, amount)
                    if not ok_w:
                        ranked_credit(r_auth, amount)
                        # 실패 시 idempotency key 삭제 (재시도 허용)
                        if _idemp_key:
                            with _ranked_lock:
                                _db().execute("DELETE FROM withdraw_idempotency WHERE key=?",(_idemp_key,))
                                _db().commit()
                        print(f"[RANKED] 환전 실패: {msg_w}", flush=True)
                        await send_json(writer,{'ok':False,'message':'머슴닷컴 전송 실패. 잠시 후 다시 시도해주세요.'},500); return
                    await send_json(writer,{'ok':True,'withdrawn':amount,'remaining_balance':ranked_balance(r_auth)})
                finally:
                    _withdrawing_users.discard(r_auth)
                    # withdraw_pending 삭제 (성공이든 실패든)
                    try:
                        with _ranked_lock:
                            _db().execute("DELETE FROM withdraw_pending WHERE id=?", (_wp_id,))
                            _db().commit()
                    except: pass
        elif method=='POST' and route=='/api/ranked/deposit-request':
            if not _api_rate_ok(_visitor_ip, 'ranked_deposit', 5):
                await send_json(writer,{'ok':False,'message':'rate limited'},429); return
            d=safe_json(body)
            r_auth=d.get('auth_id',''); r_pw=d.get('password','')
            try: amount=max(0, int(d.get('amount',0)))
            except (ValueError, TypeError): amount=0
            if not r_auth or not r_pw or amount<=0:
                await send_json(writer,{'ok':False,'message':'auth_id, password, amount(>0) 필수'},400); return
            if amount > 10000:
                await send_json(writer,{'ok':False,'message':'1회 최대 10000pt'},400); return
            # 머슴 계정 검증
            cache_key = _auth_cache_key(r_auth, r_pw)
            if not _auth_cache_check(r_auth, cache_key):
                verified, _ = await asyncio.get_event_loop().run_in_executor(
                    None, mersoom_verify_account, r_auth, r_pw)
                if not verified:
                    await send_json(writer,{'ok':False,'message':'머슴닷컴 계정 인증 실패'},401); return
                _auth_cache_set(r_auth, cache_key)
            ok, msg, code = _deposit_request_add(r_auth, amount)
            if not ok:
                await send_json(writer,{'ok':False,'code':'DEPOSIT_ERROR','message':'이미 대기 중인 입금 요청이 있습니다' if msg=='already_pending' else msg},400); return
            await send_json(writer,{'ok':True,'message':f'{amount}pt 입금 요청 등록됨. 10분 내에 머슴닷컴에서 dolsoe에게 {amount}pt를 보내주세요. 전송 메시지에 코드 [{code}]를 포함해주세요.','target':'dolsoe','amount':amount,'deposit_code':code,'expires_in_sec':DEPOSIT_EXPIRE_SEC})
        elif method=='POST' and route=='/api/ranked/deposit-status':
            d=safe_json(body)
            r_auth=d.get('auth_id',''); r_pw=d.get('password','')
            if not r_auth or not r_pw: await send_json(writer,{'ok':False,'message':'auth_id, password 필수'},400); return
            # 본인 인증
            cache_key = _auth_cache_key(r_auth, r_pw)
            if not _auth_cache_check(r_auth, cache_key):
                verified, _ = await asyncio.get_event_loop().run_in_executor(
                    None, mersoom_verify_account, r_auth, r_pw)
                if not verified:
                    await send_json(writer,{'ok':False,'message':'머슴닷컴 계정 인증 실패'},401); return
                _auth_cache_set(r_auth, cache_key)
            with _ranked_lock:
                db = _db()
                rows = db.execute("SELECT amount, status, requested_at FROM deposit_requests WHERE auth_id=? ORDER BY requested_at DESC LIMIT 10", (r_auth,)).fetchall()
            reqs = [{'amount':r[0],'status':r[1],'requested_at':int(r[2])} for r in rows]
            await send_json(writer,{'auth_id':r_auth,'requests':reqs,'balance':ranked_balance(r_auth)})
        elif method=='POST' and route=='/api/ranked/admin-credit':
            d=safe_json(body)
            if not _check_admin(d.get('admin_key','')):
                await send_json(writer,{'ok':False,'message':'인증 실패'},401); return
            r_auth=d.get('auth_id','')
            try: amount=max(0, int(d.get('amount',0)))
            except (ValueError, TypeError): amount=0
            if not r_auth or amount<=0:
                await send_json(writer,{'ok':False,'message':'auth_id, amount(>0) required'},400); return
            with _ranked_lock:
                db = _db()
                db.execute("""INSERT INTO ranked_balances(auth_id, balance, total_deposited, updated_at)
                    VALUES(?, ?, ?, strftime('%s','now'))
                    ON CONFLICT(auth_id) DO UPDATE SET balance=balance+?, total_deposited=total_deposited+?, updated_at=strftime('%s','now')""",
                    (r_auth, amount, amount, amount, amount))
                db.commit()
            _ranked_audit('admin_credit', r_auth, amount, details=f'admin manual credit')
            await send_json(writer,{'ok':True,'auth_id':r_auth,'credited':amount,'balance':ranked_balance(r_auth)})
        elif method=='POST' and route=='/api/ranked/admin-fix-ledger':
            d=safe_json(body)
            if not _check_admin(d.get('admin_key','')):
                await send_json(writer,{'ok':False,'message':'인증 실패'},401); return
            with _ranked_lock:
                db = _db()
                rows = db.execute("SELECT auth_id, balance FROM ranked_balances").fetchall()
                total_bal = sum(r[1] for r in rows)
                total_ingame = 0
                for tid in RANKED_ROOMS:
                    t = tables.get(tid)
                    if t:
                        total_ingame += sum(s['chips'] for s in t.seats if s.get('_auth_id') and not s.get('out'))
                circulating = total_bal + total_ingame
                total_dep = db.execute("SELECT COALESCE(SUM(total_deposited),0) FROM ranked_balances").fetchone()[0]
                total_wd = db.execute("SELECT COALESCE(SUM(total_withdrawn),0) FROM ranked_balances").fetchone()[0]
                shortfall = circulating - (total_dep - total_wd)
                if shortfall > 0:
                    for auth_id, bal in rows:
                        db.execute("UPDATE ranked_balances SET total_deposited=total_deposited+? WHERE auth_id=?", (shortfall, auth_id))
                        break  # 첫 계정에만 보정
                    db.commit()
                    _ranked_audit('ledger_fix', rows[0][0] if rows else 'system', shortfall, details=f'auto ledger fix +{shortfall}')
                await send_json(writer,{'ok':True,'fixed':shortfall,'circulating':circulating,'total_deposited':total_dep+shortfall,'total_withdrawn':total_wd})
        else:
            await send_json(writer,{'ok':False,'message':'unknown ranked endpoint'},404)
    elif method=='GET' and route=='/api/recent':
        tid=qs.get('table_id',[''])[0]; t=find_table(tid)
        if not t: await send_json(writer,{'ok':False,'message':'no game'},404); return
        if is_ranked_table(tid):
            if not _check_admin(qs.get('admin_key',[''])[0]):
                await send_json(writer,{'ok':False,'message':'접근 거부'},403); return
        await send_json(writer,{'history':t.history[-10:]})
    elif method=='GET' and route=='/api/profile':
        tid=qs.get('table_id',[''])[0]; name=qs.get('name',[''])[0]
        t=find_table(tid)
        if not t: await send_json(writer,{'ok':False,'code':'NOT_FOUND','message':'no game'},404); return
        if name:
            profile=t.get_profile(name)
            await send_json(writer,profile)
        else:
            # 전체 프로필 목록
            profiles=[t.get_profile(n) for n in t.player_stats if t.player_stats[n]['hands']>0]
            profiles.sort(key=lambda x:x['hands'],reverse=True)
            await send_json(writer,{'profiles':profiles})
    elif method=='GET' and route=='/api/analysis':
        tid=qs.get('table_id',[''])[0]; name=qs.get('name',[''])[0]; rtype=qs.get('type',['hands'])[0]
        t=find_table(tid)
        if not t: await send_json(writer,{'ok':False,'message':'no game'},404); return
        # ranked: 본인 분석만 허용 (admin 제외)
        if is_ranked_table(tid):
            req_token=qs.get('token',[''])[0]
            is_admin=_check_admin(qs.get('admin_key',[''])[0])
            if not is_admin:
                if not name or name=='all':
                    await send_json(writer,{'ok':False,'message':'ranked analysis requires specific player name'},400); return
                if not verify_token(name, req_token):
                    await send_json(writer,{'ok':False,'message':'인증 필요'},401); return
        all_records=load_hand_history(tid, 500)
        if rtype=='hands':
            # 핸드별 의사결정 로그
            hands=[]
            for rec in all_records:
                p_info=next((p for p in rec.get('players',[]) if p['name']==name),None) if name and name!='all' else None
                if name and name!='all' and not p_info: continue
                h={'hand':rec['hand'],'community':rec.get('community',[]),'winner':rec.get('winner',''),'pot':rec.get('pot',0),'players_count':len(rec.get('players',[]))}
                if p_info:
                    h['hole']=p_info.get('hole',[]); h['chips']=p_info.get('chips',0)
                    h['actions']=[{'round':a['round'],'action':a['action'],'amount':a.get('amount',0)} for a in rec['actions'] if a['player']==name]
                    h['result']='win' if rec.get('winner')==name else 'loss'
                else:
                    h['players']=[{'name':p['name'],'hole':p.get('hole',[]),'chips':p.get('chips',0)} for p in rec.get('players',[])]
                    h['actions']=rec.get('actions',[])
                hands.append(h)
            await send_json(writer,{'type':'hands','player':name or 'all','total':len(hands),'hands':hands})
        elif rtype=='winrate':
            # 승률별 행동 분석 — 승률 구간별 액션 분포
            if not name or name=='all': await send_json(writer,{'ok':False,'message':'player name required'},400); return
            buckets={}  # '0-20','20-40','40-60','60-80','80-100'
            for b in ['0-20','20-40','40-60','60-80','80-100']: buckets[b]={'fold':0,'call':0,'raise':0,'allin':0,'check':0,'total':0,'wins':0}
            for rec in all_records:
                p_info=next((p for p in rec.get('players',[]) if p['name']==name),None)
                if not p_info or not p_info.get('hole'): continue
                comm=rec.get('community',[])
                # 각 액션 시점의 승률 추정 (카드 기반)
                for act in rec.get('actions',[]):
                    if act['player']!=name: continue
                    # 간단한 승률 구간 추정: hand_strength 사용
                    hole_cards=p_info.get('hole',[])
                    if len(hole_cards)<2: continue
                    try:
                        # parse cards for strength calc
                        parsed=[]
                        for cs in hole_cards:
                            if len(cs)>=2:
                                r=cs[:-1];s=cs[-1];parsed.append((r,s))
                        if len(parsed)<2: continue
                        comm_parsed=[]
                        rnd=act.get('round','preflop')
                        if rnd=='preflop': comm_parsed=[]
                        elif rnd=='flop': comm_parsed=[(c[:-1],c[-1]) for c in comm[:3] if len(c)>=2]
                        elif rnd=='turn': comm_parsed=[(c[:-1],c[-1]) for c in comm[:4] if len(c)>=2]
                        elif rnd=='river': comm_parsed=[(c[:-1],c[-1]) for c in comm[:5] if len(c)>=2]
                        wp=hand_strength(parsed,comm_parsed)*100
                    except: wp=50
                    bk='0-20' if wp<20 else '20-40' if wp<40 else '40-60' if wp<60 else '60-80' if wp<80 else '80-100'
                    a=act['action'].lower()
                    ak='allin' if 'all' in a else 'raise' if a in ('raise','bet') else 'call' if a=='call' else 'fold' if a=='fold' else 'check'
                    buckets[bk][ak]+=1; buckets[bk]['total']+=1
                if rec.get('winner')==name:
                    # 최종 승률 구간에 승리 기록
                    try:
                        parsed=[(cs[:-1],cs[-1]) for cs in p_info.get('hole',[]) if len(cs)>=2]
                        cp=[(c[:-1],c[-1]) for c in comm if len(c)>=2]
                        wp=hand_strength(parsed,cp)*100 if len(parsed)>=2 else 50
                    except: wp=50
                    bk='0-20' if wp<20 else '20-40' if wp<40 else '40-60' if wp<60 else '60-80' if wp<80 else '80-100'
                    buckets[bk]['wins']+=1
            await send_json(writer,{'type':'winrate','player':name,'buckets':buckets})
        elif rtype=='position':
            # 포지션별 성적
            if not name or name=='all': await send_json(writer,{'ok':False,'message':'player name required'},400); return
            pos={'SB':{'hands':0,'wins':0,'profit':0,'actions':{'fold':0,'call':0,'raise':0,'check':0,'allin':0}},
                 'BB':{'hands':0,'wins':0,'profit':0,'actions':{'fold':0,'call':0,'raise':0,'check':0,'allin':0}},
                 'Dealer':{'hands':0,'wins':0,'profit':0,'actions':{'fold':0,'call':0,'raise':0,'check':0,'allin':0}},
                 'Other':{'hands':0,'wins':0,'profit':0,'actions':{'fold':0,'call':0,'raise':0,'check':0,'allin':0}}}
            for rec in all_records:
                players=rec.get('players',[])
                idx=next((i for i,p in enumerate(players) if p['name']==name),-1)
                if idx<0: continue
                n_p=len(players); dealer_idx=rec.get('dealer',0)%n_p
                if n_p==2:
                    my_pos='Dealer' if idx==dealer_idx else 'BB'
                else:
                    sb_idx=(dealer_idx+1)%n_p; bb_idx=(dealer_idx+2)%n_p
                    my_pos='Dealer' if idx==dealer_idx else 'SB' if idx==sb_idx else 'BB' if idx==bb_idx else 'Other'
                won=rec.get('winner')==name; pot=rec.get('pot',0)
                pos[my_pos]['hands']+=1
                if won: pos[my_pos]['wins']+=1; pos[my_pos]['profit']+=pot
                for act in rec.get('actions',[]):
                    if act['player']!=name: continue
                    a=act['action'].lower()
                    ak='allin' if 'all' in a else 'raise' if a in ('raise','bet') else 'call' if a=='call' else 'fold' if a=='fold' else 'check'
                    pos[my_pos]['actions'][ak]+=1
            for k in pos:
                h=max(pos[k]['hands'],1); pos[k]['win_rate']=round(pos[k]['wins']/h*100,1)
            await send_json(writer,{'type':'position','player':name,'positions':pos})
        elif rtype=='ev':
            # EV 분석 — 각 액션의 기대값
            if not name or name=='all': await send_json(writer,{'ok':False,'message':'player name required'},400); return
            ev_data={'total_hands':0,'total_ev':0,'actions':[],'summary':{'good_calls':0,'bad_calls':0,'good_folds':0,'bad_folds':0,'good_raises':0,'bad_raises':0}}
            for rec in all_records:
                p_info=next((p for p in rec.get('players',[]) if p['name']==name),None)
                if not p_info: continue
                ev_data['total_hands']+=1
                won=rec.get('winner')==name; pot=rec.get('pot',0)
                my_total_bet=sum(a.get('amount',0) for a in rec.get('actions',[]) if a['player']==name and a['action'] in ('call','raise','bet','all_in'))
                hand_ev=pot-my_total_bet if won else -my_total_bet
                ev_data['total_ev']+=hand_ev
                for act in rec.get('actions',[]):
                    if act['player']!=name: continue
                    amt=act.get('amount',0); a=act['action'].lower()
                    # EV 추정: 승리했으면 +, 패배했으면 -
                    act_ev=round(pot/max(len(rec.get('players',[])),1)-amt) if won else -amt
                    if a=='fold': act_ev=0  # 폴드는 EV 0 (손실 방지)
                    ev_entry={'hand':rec['hand'],'round':act.get('round',''),'action':a,'amount':amt,'ev':act_ev}
                    ev_data['actions'].append(ev_entry)
                    # 분류
                    if a=='call':
                        if won: ev_data['summary']['good_calls']+=1
                        else: ev_data['summary']['bad_calls']+=1
                    elif a=='fold':
                        if not won: ev_data['summary']['good_folds']+=1
                        else: ev_data['summary']['bad_folds']+=1
                    elif a in ('raise','bet','all_in'):
                        if won: ev_data['summary']['good_raises']+=1
                        else: ev_data['summary']['bad_raises']+=1
            ev_data['avg_ev']=round(ev_data['total_ev']/max(ev_data['total_hands'],1),1)
            await send_json(writer,{'type':'ev','player':name,'data':ev_data})
        elif rtype=='matchup':
            # 상대별 전적 매트릭스
            if not name or name=='all':
                # 전체 매트릭스
                matrix={}
                for rec in all_records:
                    w=rec.get('winner','')
                    for p in rec.get('players',[]):
                        if p['name']==w: continue
                        pair=tuple(sorted([w,p['name']]))
                        if pair not in matrix: matrix[pair]={'a':pair[0],'b':pair[1],'a_wins':0,'b_wins':0,'hands':0}
                        matrix[pair]['hands']+=1
                        if w==pair[0]: matrix[pair]['a_wins']+=1
                        else: matrix[pair]['b_wins']+=1
                await send_json(writer,{'type':'matchup','player':'all','matchups':list(matrix.values())})
            else:
                rivals={}
                for rec in all_records:
                    p_info=next((p for p in rec.get('players',[]) if p['name']==name),None)
                    if not p_info: continue
                    w=rec.get('winner','')
                    for p in rec.get('players',[]):
                        if p['name']==name: continue
                        opp=p['name']
                        if opp not in rivals: rivals[opp]={'opponent':opp,'wins':0,'losses':0,'hands':0,'my_profit':0}
                        rivals[opp]['hands']+=1
                        if w==name: rivals[opp]['wins']+=1; rivals[opp]['my_profit']+=rec.get('pot',0)
                        elif w==opp: rivals[opp]['losses']+=1
                await send_json(writer,{'type':'matchup','player':name,'rivals':sorted(rivals.values(),key=lambda x:x['hands'],reverse=True)})
        else:
            await send_json(writer,{'ok':False,'message':'잘못된 요청'},400)
    elif method=='GET' and route=='/api/_v':
        # 스텔스 방문자 통계 (비공개 — URL 모르면 접근 불가)
        k=qs.get('k',[''])[0]
        if not _check_admin(k): await send_json(writer,{'ok':False,'message':'not found'},404); return
        await send_json(writer,_get_visitor_stats())
    elif method=='GET' and route=='/api/highlights':
        tid=qs.get('table_id',[''])[0]
        try: limit=min(100, max(1, int(qs.get('limit',['10'])[0])))
        except (ValueError, TypeError): limit=10
        t=find_table(tid)
        if not t: await send_json(writer,{'ok':False,'code':'NOT_FOUND','message':'no game'},404); return
        hls=t.highlight_replays[-limit:]
        hls.reverse()  # 최신순
        await send_json(writer,{'highlights':hls})
    elif method=='GET' and route=='/api/replay':
        tid=qs.get('table_id',[''])[0]; hand_num=qs.get('hand',[''])[0]
        t=find_table(tid)
        if not t: await send_json(writer,{'ok':False,'message':'no game'},404); return
        if hand_num:
            try: hand_num_i=int(hand_num)
            except: await send_json(writer,{'ok':False,'message':'invalid hand number'},400); return
            h=[x for x in t.history if x['hand']==hand_num_i]
            if not h:
                db_records=load_hand_history(tid, 500)
                h=[x for x in db_records if x.get('hand')==hand_num_i]
            if h:
                result=h[0]
                # ranked: 홀카드 마스킹 (본인 것만 공개, admin 제외)
                if is_ranked_table(tid):
                    req_player=qs.get('player',[''])[0]
                    req_token=qs.get('token',[''])[0]
                    is_admin=_check_admin(qs.get('admin_key',[''])[0])
                    if not is_admin:
                        import copy; result=copy.deepcopy(result)
                        for p in result.get('players',[]):
                            if not req_player or not req_token or not verify_token(req_player, req_token) or p['name']!=req_player:
                                p['hole']=['??','??']
                await send_json(writer,result)
            else: await send_json(writer,{'ok':False,'message':'hand not found'},404)
        else:
            db_records=load_hand_history(tid, 100)
            await send_json(writer,{'hands':[{'hand':x['hand'],'winner':x.get('winner',''),'pot':x.get('pot',0),'players':len(x.get('players',[]))} for x in db_records]})
    # ═══ 플레이어 히스토리 & CSV 익스포트 ═══
    elif method=='GET' and route=='/api/history':
        tid=qs.get('table_id',[''])[0]; player=qs.get('player',[''])[0]
        try: limit=min(500, max(1, int(qs.get('limit',['200'])[0])))
        except (ValueError, TypeError): limit=200
        t=find_table(tid)
        if not t: await send_json(writer,{'ok':False,'message':'no game'},404); return
        if not player: await send_json(writer,{'ok':False,'message':'player param required'},400); return
        # ranked: 토큰 검증 (본인 히스토리만, admin 제외)
        if is_ranked_table(tid):
            req_token=qs.get('token',[''])[0]
            is_admin=_check_admin(qs.get('admin_key',[''])[0])
            if not is_admin and not verify_token(player, req_token):
                await send_json(writer,{'ok':False,'message':'인증 필요'},401); return
        # DB에서 확장 히스토리 로드 (메모리 50개 넘는 것도 포함)
        all_records=load_hand_history(tid, limit) if limit>50 else t.history
        hands=[]
        for rec in all_records:
            # 이 핸드에 참여했는지
            p_info=next((p for p in rec['players'] if p['name']==player),None)
            if not p_info: continue
            my_actions=[a for a in rec['actions'] if a['player']==player]
            won=rec.get('winner')==player
            pot=rec.get('pot',0)
            hands.append({
                'hand':rec['hand'],
                'hole':p_info.get('hole',[]),
                'community':rec.get('community',[]),
                'actions':[{'round':a['round'],'action':a['action'],'amount':a.get('amount',0)} for a in my_actions],
                'result':'win' if won else 'loss',
                'pot':pot if won else 0,
                'winner':rec.get('winner',''),
                'players':len(rec['players']),
            })
        # 통계 요약
        total=len(hands); wins=sum(1 for h in hands if h['result']=='win')
        total_won=sum(h['pot'] for h in hands if h['result']=='win')
        stats=t.player_stats.get(player,{})
        summary={
            'player':player,'total_hands':total,'wins':wins,'losses':total-wins,
            'win_rate':round(wins/max(total,1)*100,1),
            'total_won':total_won,
            'biggest_pot':stats.get('biggest_pot',0),
            'allins':stats.get('allins',0),
            'folds':stats.get('folds',0),
            'showdowns':stats.get('showdowns',0),
        }
        await send_json(writer,{'summary':summary,'hands':hands})

    elif method=='GET' and route=='/api/export':
        if not _api_rate_ok(_visitor_ip, 'export', 5):
            await send_json(writer,{'ok':False,'code':'RATE_LIMITED','message':'rate limited — max 5 exports/min'},429); return
        tid=qs.get('table_id',[''])[0]; player=qs.get('player',[''])[0]
        # ranked 테이블 export 차단 (admin만 허용)
        if is_ranked_table(tid):
            if not _check_admin(qs.get('admin_key',[''])[0]):
                await send_json(writer,{'ok':False,'message':'접근 거부'},403); return
        fmt=qs.get('format',['csv'])[0]
        try: limit=min(500, max(1, int(qs.get('limit',['500'])[0])))
        except (ValueError, TypeError): limit=500
        t=find_table(tid)
        if not t: await send_json(writer,{'ok':False,'message':'no game'},404); return
        all_records=load_hand_history(tid, limit)
        is_all=not player or player=='all'
        rows=['hand,player,hole,community,actions,result,pot,winner,num_players'] if is_all else ['hand,hole,community,actions,result,pot,winner,players']
        for rec in all_records:
            if is_all:
                for p_info in rec.get('players',[]):
                    pn=p_info['name']
                    my_acts=[f"{a['round']}:{a['action']}{(':'+str(a.get('amount',''))) if a.get('amount') else ''}" for a in rec['actions'] if a['player']==pn]
                    won=rec.get('winner')==pn
                    hole=' '.join(p_info.get('hole',[])); comm=' '.join(rec.get('community',[])); acts='|'.join(my_acts)
                    pot=rec.get('pot',0) if won else 0
                    rows.append(f"{rec['hand']},\"{pn}\",\"{hole}\",\"{comm}\",\"{acts}\",{'win' if won else 'loss'},{pot},{rec.get('winner','')},{len(rec['players'])}")
            else:
                p_info=next((p for p in rec['players'] if p['name']==player),None)
                if not p_info: continue
                my_acts=[f"{a['round']}:{a['action']}{(':'+str(a.get('amount',''))) if a.get('amount') else ''}" for a in rec['actions'] if a['player']==player]
                won=rec.get('winner')==player
                hole=' '.join(p_info.get('hole',[])); comm=' '.join(rec.get('community',[])); acts='|'.join(my_acts)
                pot=rec.get('pot',0) if won else 0
                rows.append(f"{rec['hand']},\"{hole}\",\"{comm}\",\"{acts}\",{'win' if won else 'loss'},{pot},{rec.get('winner','')},{len(rec['players'])}")
        csv_text='\n'.join(rows)
        _safe_player=''.join(c for c in (player or 'all') if c.isalnum() or c in '_-')[:20] or 'export'
        fname=f"{_safe_player}_history.csv"
        if fmt=='json':
            await send_json(writer,{'csv':csv_text})
        else:
            headers=f"HTTP/1.1 200 OK\r\nContent-Type:text/csv;charset=utf-8\r\nContent-Disposition:attachment;filename={fname}\r\nContent-Length:{len(csv_text.encode())}\r\nAccess-Control-Allow-Origin:*\r\n\r\n"
            writer.write(headers.encode()+csv_text.encode()); await writer.drain(); writer.close()
            return

    # ═══ 디스배틀 ═══
    # 디스배틀 삭제됨 (battle.py 소각)
    elif method=='POST' and route=='/api/telemetry':
        try:
            if body and len(body) > 4096: await send_http(writer,413,'too large'); return
            peer = writer.get_extra_info('peername')
            ip = peer[0] if peer else 'unknown'
            if not _tele_rate_ok(ip): await send_http(writer,429,'rate limited'); return
            td=safe_json(body)
            # 텔레메트리 입력 검증: 허용된 필드만 수집, 타입 강제
            _TELE_ALLOWED = {'poll_ok','poll_err','rtt_avg','rtt_p95','hands','overlay_allin',
                'overlay_killcam','sid','ev','name','table','src'}
            td = {k: v for k, v in td.items() if k in _TELE_ALLOWED}
            # 숫자 필드 타입 강제
            for nf in ('poll_ok','poll_err','rtt_avg','rtt_p95','hands','overlay_allin','overlay_killcam'):
                if nf in td:
                    try: td[nf] = max(0, min(int(td[nf]), 1000000))
                    except (ValueError, TypeError): del td[nf]
            # 문자열 필드 길이 제한
            for sf in ('sid','ev','name','table','src'):
                if sf in td:
                    td[sf] = str(td[sf])[:50]
            td['_ip'] = _mask_ip(ip)
            _telemetry_log.append({'ts':time.time(),**td})
            if len(_telemetry_log)>500: _telemetry_log[:]=_telemetry_log[-250:]
            _tele_update_summary()
        except: pass
        await send_http(writer,204,'')
    elif method=='GET' and route=='/api/telemetry':
        if not _check_admin(qs.get('key',[''])[0]):
            await send_json(writer,{'ok':False,'code':'UNAUTHORIZED'},401); return
        await send_json(writer,{'summary':_tele_summary,'alerts':_alert_history[-20:],'streaks':dict(_alert_streaks),'entries':_telemetry_log[-50:]})
    elif method=='OPTIONS':
        await send_http(writer,200,'')
    else:
        await send_http(writer,404,'404 Not Found')
    try: writer.close(); await writer.wait_closed()
    except: pass

async def send_http(writer, status, body, ct='text/plain; charset=utf-8', extra_headers=''):
    st={200:'OK',304:'Not Modified',400:'Bad Request',401:'Unauthorized',404:'Not Found',302:'Found',429:'Too Many Requests',500:'Internal Server Error'}.get(status,'OK')
    if isinstance(body,str): body=body.encode('utf-8')
    h=f"HTTP/1.1 {status} {st}\r\nContent-Type: {ct}\r\nContent-Length: {len(body)}\r\n{extra_headers}Access-Control-Allow-Origin: *\r\nAccess-Control-Allow-Methods: GET, POST, OPTIONS\r\nAccess-Control-Allow-Headers: Content-Type\r\nX-Content-Type-Options: nosniff\r\nX-Frame-Options: DENY\r\nContent-Security-Policy: default-src 'self'; script-src 'unsafe-inline' 'self'; style-src 'unsafe-inline' 'self' https://fonts.googleapis.com https://cdn.jsdelivr.net; font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; img-src 'self' data: blob:; connect-src 'self' wss: ws:; object-src 'none'; base-uri 'self'\r\nConnection: close\r\n\r\n"
    try: writer.write(h.encode()+body); await writer.drain()
    except: pass

async def send_json(writer, data, status=200, extra_headers=''):
    await send_http(writer,status,json.dumps(data,ensure_ascii=False).encode('utf-8'),'application/json; charset=utf-8',extra_headers=extra_headers)

async def handle_ws(reader, writer, path):
    qs=parse_qs(urlparse(path).query); tid=qs.get('table_id',['mersoom'])[0]
    mode=qs.get('mode',['spectate'])[0]; name=qs.get('name',[''])[0]
    t=tables.get(tid) if tid else tables.get('mersoom')
    if not t: t=get_or_create_table('mersoom')

    if mode=='play' and name:
        name=sanitize_name(name)
        if not name:
            try: writer.close()
            except: pass
            return
        # WS play 모드: 토큰 검증 필수
        ws_token=qs.get('token',[''])[0]
        if not ws_token or not verify_token(name, ws_token):
            await ws_send(writer,json.dumps({'ok':False,'message':'인증 필요'},ensure_ascii=False))
            try: writer.close()
            except: pass
            return
        # ranked 테이블은 WS play 금지 (HTTP join만 허용)
        if is_ranked_table(tid):
            await ws_send(writer,json.dumps({'ok':False,'message':'잘못된 접근'},ensure_ascii=False))
            try: writer.close()
            except: pass
            return
        t.player_ws[name]=writer
        # 이미 seat에 있는 경우만 연결 (WS로 직접 add_player 금지)
        existing_seat = next((s for s in t.seats if s['name']==name and not s.get('out')), None)
        if not existing_seat:
            await ws_send(writer,json.dumps({'ok':False,'message':'인증 필요'},ensure_ascii=False))
            try: writer.close()
            except: pass
            return
        await ws_send(writer,json.dumps(t.get_public_state(viewer=name),ensure_ascii=False))
    else:
        # 관전자 상한 (DoS 방지)
        if len(t.spectator_ws) >= MAX_WS_SPECTATORS:
            await ws_send(writer,json.dumps({'ok':False,'message':'spectator limit reached'},ensure_ascii=False))
            try: writer.close()
            except: pass
            return
        t.spectator_ws.add(writer)
        # 관전자: 딜레이된 state
        init_state=t.last_spectator_state or json.dumps(t.get_spectator_state(),ensure_ascii=False)
        await ws_send(writer,init_state)
    _ws_last_activity = time.time()
    try:
        while True:
            # idle 타임아웃 체크
            remaining = WS_IDLE_TIMEOUT - (time.time() - _ws_last_activity)
            if remaining <= 0: break  # idle timeout
            msg=await ws_recv(reader, timeout=min(30, remaining))
            if msg is None: break
            _ws_last_activity = time.time()
            if msg=='__ping__': writer.write(bytes([0x8A,0])); await writer.drain(); continue
            try: data=json.loads(msg)
            except: continue
            if data.get('type')=='action' and mode=='play' and name and verify_token(name, ws_token): t.handle_api_action(name,data)
            elif data.get('type')=='chat':
                chat_name=name if (mode=='play' and name) else sanitize_name(data.get('name',''))[:10] or '관객'
                # 관전자가 플레이어 이름 사칭 방지
                if mode!='play':
                    _seated_names={s['name'] for s in t.seats}
                    if chat_name in _seated_names: chat_name=f'[관전]{chat_name}'
                chat_msg=sanitize_msg(data.get('msg',''),120)
                if not chat_msg: continue
                # WS 채팅 쿨다운
                now=time.time(); last_ws=chat_cooldowns.get(chat_name,0)
                if now-last_ws<CHAT_COOLDOWN: continue
                chat_cooldowns[chat_name]=now
                entry=t.add_chat(chat_name,chat_msg)
                await t.broadcast_chat(entry)
            elif data.get('type')=='reaction':
                emoji=data.get('emoji','')[:2]; rname=(name if (mode=='play' and name) else data.get('name','')[:10]) or '관객'
                if emoji:
                    rmsg=json.dumps({'type':'reaction','emoji':emoji,'name':rname},ensure_ascii=False)
                    for ws in list(t.spectator_ws):
                        if ws!=writer:
                            try: await ws_send(ws,rmsg)
                            except: t.spectator_ws.discard(ws)
                    for ws in set(t.player_ws.values()):
                        try: await ws_send(ws,rmsg)
                        except: pass
            elif data.get('type')=='vote' and mode!='play':
                pick=sanitize_name(data.get('pick',''))
                voter_id=id(writer)  # 서버측 ID 강제 (클라이언트 voter_id 스푸핑 방지)
                # pick이 실제 착석 플레이어인지 검증
                valid_picks = {s['name'] for s in t.seats if not s.get('out')}
                if pick and pick in valid_picks and t.running and t.hand_num>0:
                    if t.vote_hand!=t.hand_num:
                        t.spectator_votes={}; t.vote_results={}; t.vote_hand=t.hand_num
                    old_pick=t.spectator_votes.get(voter_id)
                    if old_pick: t.vote_results[old_pick]=max(0,t.vote_results.get(old_pick,0)-1)
                    t.spectator_votes[voter_id]=pick
                    t.vote_results[pick]=t.vote_results.get(pick,0)+1
                    vmsg=json.dumps({'type':'vote_update','counts':t.vote_results,'total':len(t.spectator_votes)},ensure_ascii=False)
                    await t._broadcast_spectators(vmsg)
            elif data.get('type')=='get_state':
                if mode=='play' and name:
                    await ws_send(writer,json.dumps(t.get_public_state(viewer=name),ensure_ascii=False))
                else:
                    _sstate=t.last_spectator_state or json.dumps(t.get_spectator_state(),ensure_ascii=False)
                    await ws_send(writer,_sstate)
    except: pass
    finally:
        if mode=='play' and name in t.player_ws: del t.player_ws[name]
        t.spectator_ws.discard(writer)
        # ranked: WS 끊기면 자동 leave + 칩 환불 (이중 정산 방지: _cashed_out 플래그 체크)
        if mode=='play' and name and is_ranked_table(t.id):
            seat=next((s for s in t.seats if s['name']==name and not s.get('out')),None)
            if seat and seat['chips']>0 and not seat.get('_cashed_out'):
                chips=seat['chips']
                auth_id_leave=seat.get('_auth_id') or _ranked_auth_map.get(name)
                if auth_id_leave and auth_id_leave not in _withdrawing_users:
                    seat['chips']=0
                    ranked_credit(auth_id_leave, chips)
                    _ranked_audit('ws_disconnect_cashout', auth_id_leave, chips, details=f'table:{t.id} name:{name}')
                    try:
                        db=_db()
                        db.execute("DELETE FROM ranked_ingame WHERE table_id=? AND auth_id=?", (t.id, auth_id_leave))
                        db.commit()
                    except: pass
                seat['out']=True; seat['folded']=True
                print(f"[RANKED] WS disconnect auto-cashout: {name} → {chips}pt returned to {auth_id_leave}", flush=True)
        try: writer.close()
        except: pass

# ══ HTML ══
from pages import DOCS_PAGE, DOCS_PAGE_EN, RANKING_PAGE, RANKING_PAGE_EN, HTML_PAGE


# ══ Arena HTML Pages ══

# ══ Main ══
async def _tele_log_loop():
    """Print telemetry summary every 60s + run alert checks"""
    while True:
        await asyncio.sleep(60)
        s = _tele_summary
        if s.get('last_ts',0) > 0:
            p95v = s.get('rtt_p95')
            p95s = f"{p95v}ms" if p95v and p95v > 0 else "-"
            print(f"📊 TELE | OK {s.get('success_rate',100)} | p95 {p95s} avg {s.get('rtt_avg',0)}ms | ERR {s.get('err_total',0)} | H+{s.get('hands_5m',0)} | AIN {s.get('sessions',0)} | ALLIN {s.get('allin_per_100h',0)}/100 KILL {s.get('killcam_per_100h',0)}/100 | {APP_VERSION}", flush=True)
            try: _tele_check_alerts(s)
            except Exception as e: print(f"⚠️ TELE_ALERT_ERR {e}", flush=True)

_conn_semaphore = asyncio.Semaphore(500)  # 최대 동시 연결 500

async def _guarded_handle(reader, writer):
    if _conn_semaphore.locked():
        writer.close()
        return
    async with _conn_semaphore:
        await handle_client(reader, writer)

async def main():
    # 포트 먼저 바인딩 (Render 타임아웃 방지)
    server = await asyncio.start_server(_guarded_handle, '0.0.0.0', PORT)
    print(f"😈 머슴포커 {APP_VERSION}", flush=True)
    print(f"🌐 http://0.0.0.0:{PORT}", flush=True)
    # 초기화는 포트 열린 후에
    load_leaderboard()
    init_mersoom_table()
    # ranked 테이블 미리 생성 (로비에 표시용)
    for rid in RANKED_ROOMS:
        t = get_or_create_table(rid)
        t.SB = RANKED_ROOMS[rid]['sb']
        t.BB = RANKED_ROOMS[rid]['bb']
        t.BLIND_SCHEDULE = [(RANKED_ROOMS[rid]['sb'], RANKED_ROOMS[rid]['bb'])]
    print(f"🏆 Ranked 테이블 {len(RANKED_ROOMS)}개 생성", flush=True)
    # 크래시 복구: 미정산 ranked 인게임 칩을 잔고에 복구
    try:
        db = _db()
        rows = db.execute("SELECT auth_id, name, chips, table_id FROM ranked_ingame LIMIT 200").fetchall()
        if rows:
            print(f"⚠️ [RANKED] 크래시 복구: {len(rows)}건 미정산 발견", flush=True)
            for auth_id, name, chips, tid in rows:
                if chips > 0:
                    ranked_credit(auth_id, chips)
                    print(f"  ✅ 복구: {name}({auth_id}) +{chips}pt → 잔고 {ranked_balance(auth_id)}pt", flush=True)
                    _ranked_audit('crash_recovery', auth_id, chips, details=f'table:{tid} name:{name}')
            db.execute("DELETE FROM ranked_ingame")
            db.commit()
            print(f"✅ [RANKED] 크래시 복구 완료", flush=True)
        # withdraw_pending 크래시 복구: 차감만 되고 API 호출 전 크래시된 건 → 잔고 복구
        try:
            wp_rows = db.execute("SELECT auth_id, amount, id FROM withdraw_pending").fetchall()
            if wp_rows:
                print(f"⚠️ [RANKED] 미완료 출금 {len(wp_rows)}건 복구", flush=True)
                for auth_id, amount, wp_id in wp_rows:
                    ranked_credit(auth_id, amount)
                    print(f"  ✅ 출금 복구: {auth_id} +{amount}pt", flush=True)
                    _ranked_audit('withdraw_crash_recovery', auth_id, amount, details=f'pending_id:{wp_id}')
                db.execute("DELETE FROM withdraw_pending")
                db.commit()
        except: pass  # 테이블 없으면 무시
    except Exception as e:
        print(f"⚠️ [RANKED] 크래시 복구 실패: {e}", flush=True)
    asyncio.create_task(_tele_log_loop())
    asyncio.create_task(_deposit_poll_loop())
    asyncio.create_task(_watchdog_loop())
    print("🛡️ Ranked Watchdog 가동", flush=True)
    async with server: await server.serve_forever()

asyncio.run(main())
