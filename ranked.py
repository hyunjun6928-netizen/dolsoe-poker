"""머슴포커 — 랭크 경제 시스템 (머슴포인트 연동, 입출금, 워치독)"""
import asyncio, hashlib, hmac, json, os, re, time, threading, datetime
from urllib.parse import parse_qs
from db import _db
from visitors import _mask_ip

# ══ 머슴포인트 상수 ══
MERSOOM_API = 'https://www.mersoom.com/api'
MERSOOM_AUTH_ID = os.environ.get('MERSOOM_AUTH_ID', '')
MERSOOM_PASSWORD = os.environ.get('MERSOOM_PASSWORD', '')

RANKED_ROOMS = {
    'ranked-nano':  {'min_buy': 1, 'max_buy': 10, 'sb': 1, 'bb': 1, 'label': '나노 (1~10pt)', 'label_en': 'Nano (1~10pt)'},
    'ranked-micro': {'min_buy': 10, 'max_buy': 100, 'sb': 1, 'bb': 2, 'label': '마이크로 (10~100pt)', 'label_en': 'Micro (10~100pt)'},
    'ranked-mid':   {'min_buy': 50, 'max_buy': 500, 'sb': 5, 'bb': 10, 'label': '미들 (50~500pt)', 'label_en': 'Mid (50~500pt)'},
    'ranked-high':  {'min_buy': 200, 'max_buy': 2000, 'sb': 25, 'bb': 50, 'label': '하이 (200~2000pt)', 'label_en': 'High (200~2000pt)'},
}
RANKED_LOCKED = os.environ.get('RANKED_LOCKED', 'true').lower() == 'true'

# 상수 (server.py에서 이동)
AUTH_CACHE_TTL = 600
AUTH_CACHE_MAX = 500
AUTH_CACHE_PRUNE = 250
DEPOSIT_EXPIRE_SEC = 600
DEPOSIT_DELETE_SEC = 86400
DEPOSIT_POLL_INTERVAL = 60
WATCHDOG_INTERVAL = 60
WATCHDOG_BALANCE_SPIKE = 200
WATCHDOG_EVENT_MAX = 100
WATCHDOG_EVENT_KEEP = 50
AUDIT_LOG_MAX = 10000
AUDIT_LOG_KEEP = 5000
POW_MAX_NONCE = 10_000_000

# 글로벌 상태
_verified_auth_cache = {}
_ranked_auth_map = {}
_ranked_lock = threading.Lock()
_withdrawing_users = set()

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
        import traceback; traceback.print_exc()
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

_tables_ref = None  # server.py에서 set_tables_ref(tables)로 주입

def set_tables_ref(t):
    global _tables_ref
    _tables_ref = t

def _ranked_watchdog_check():
    """ranked 이상 거래 탐지 (60초마다 호출)"""
    global tables
    tables = _tables_ref or {}
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
        import traceback; traceback.print_exc()
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

