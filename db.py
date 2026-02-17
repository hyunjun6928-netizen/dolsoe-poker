"""머슴포커 — SQLite DB 관리 (연결 + CRUD)"""
import os, sqlite3, json

DB_FILE = '/data/poker_data.db' if os.path.isdir('/data') else 'poker_data.db'
_db_conn = None

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

def save_hand_history(table_id, record):
    """핸드 기록을 DB에 영구 저장"""
    try:
        db=_db()
        db.execute("INSERT INTO hand_history(table_id,hand_num,data,winner,pot,players) VALUES(?,?,?,?,?,?)",
            (table_id, record.get('hand',0), json.dumps(record),
             record.get('winner',''), record.get('pot',0), len(record.get('players',[]))))
        db.commit()
    except Exception as e: print(f"⚠️ DB save_hh err: {e}",flush=True)

def load_hand_history(table_id, limit=50):
    """DB에서 핸드 기록 로드"""
    try:
        db=_db()
        rows=db.execute("SELECT data FROM hand_history WHERE table_id=? ORDER BY id DESC LIMIT ?",
            (table_id,limit)).fetchall()
        return [json.loads(r[0]) for r in reversed(rows)]
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

def save_leaderboard(leaderboard):
    """리더보드 DB 저장 (leaderboard dict를 인자로 받음)"""
    try:
        db=_db()
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
                 json.dumps(lb.get('achievements',[]))))
        db.commit()
    except Exception as e: print(f"⚠️ DB save_lb err: {e}",flush=True)

def load_leaderboard(leaderboard):
    """리더보드 DB 로드 (leaderboard dict를 인자로 받아 업데이트)"""
    try:
        if os.path.exists('leaderboard.json'):
            with open('leaderboard.json','r') as f: leaderboard.update(json.load(f))
            save_leaderboard(leaderboard)
            os.rename('leaderboard.json','leaderboard.json.bak')
            print("📦 Migrated leaderboard.json → SQLite",flush=True)
        db=_db()
        for row in db.execute("SELECT name,wins,losses,chips_won,hands,biggest_pot,streak,achievements FROM leaderboard"):
            leaderboard[row[0]]={'wins':row[1],'losses':row[2],'chips_won':row[3],
                'hands':row[4],'biggest_pot':row[5],'streak':row[6],
                'achievements':json.loads(row[7]) if row[7] else []}
        print(f"📊 Loaded {len(leaderboard)} players from DB",flush=True)
    except Exception as e: print(f"⚠️ DB load_lb err: {e}",flush=True)
