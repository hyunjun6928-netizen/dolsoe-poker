#!/usr/bin/env python3
"""
악몽의돌쇠 클라우드 포커 v1.0
AI 에이전트들이 API로 참가하는 텍사스 홀덤
웹 UI로 실시간 관전 가능

Endpoints:
  GET  /              → 관전 웹 UI
  POST /api/join      → 게임 참가 {name, emoji?}
  GET  /api/state     → 게임 상태 조회 (?player=name)
  POST /api/action    → 액션 {name, action, amount?}  (action: fold/call/check/raise)
  GET  /api/games     → 게임 목록
  POST /api/new       → 새 게임 생성
"""
import asyncio
import hashlib
import json
import os
import random
import struct
import time
import base64
from collections import Counter
from itertools import combinations
from urllib.parse import parse_qs, urlparse

PORT = int(os.environ.get('PORT', 8080))

# ══════════════════════════════════════
# 카드 시스템
# ══════════════════════════════════════
SUITS = ['♠', '♥', '♦', '♣']
SUIT_CLASSES = {'♠': 'spade', '♥': 'heart', '♦': 'diamond', '♣': 'club'}
RANKS = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
RANK_VALUES = {r: i for i, r in enumerate(RANKS, 2)}
HAND_NAMES = {
    10: '로열 플러시', 9: '스트레이트 플러시', 8: '포카드',
    7: '풀하우스', 6: '플러시', 5: '스트레이트',
    4: '트리플', 3: '투페어', 2: '원페어', 1: '하이카드'
}

def make_deck():
    deck = [(r, s) for s in SUITS for r in RANKS]
    random.shuffle(deck)
    return deck

def card_dict(c): return {'rank': c[0], 'suit': c[1]}
def card_str(c): return f"{c[0]}{c[1]}"

def evaluate_hand(seven):
    best = None
    for combo in combinations(seven, 5):
        s = score_five(list(combo))
        if best is None or s > best: best = s
    return best

def score_five(cards):
    ranks = sorted([RANK_VALUES[c[0]] for c in cards], reverse=True)
    suits = [c[1] for c in cards]
    is_flush = len(set(suits)) == 1
    unique = sorted(set(ranks), reverse=True)
    is_straight = False; sh = 0
    if len(unique) >= 5:
        for i in range(len(unique)-4):
            if unique[i]-unique[i+4]==4: is_straight=True; sh=unique[i]; break
    if {14,2,3,4,5} <= set(ranks): is_straight=True; sh=5
    cnt = Counter(ranks)
    g = sorted(cnt.items(), key=lambda x:(x[1],x[0]), reverse=True)
    if is_straight and is_flush: return (10,[14]) if sh==14 else (9,[sh])
    if g[0][1]==4: return (8,[g[0][0],[x[0] for x in g if x[1]!=4][0]])
    if g[0][1]==3 and g[1][1]>=2: return (7,[g[0][0],g[1][0]])
    if is_flush: return (6,ranks)
    if is_straight: return (5,[sh])
    if g[0][1]==3: return (4,[g[0][0]]+sorted([x[0] for x in g if x[1]!=3],reverse=True))
    if g[0][1]==2 and g[1][1]==2:
        p=sorted([x[0] for x in g if x[1]==2],reverse=True)
        return (3,p+[x[0] for x in g if x[1]==1])
    if g[0][1]==2: return (2,[g[0][0]]+sorted([x[0] for x in g if x[1]!=2],reverse=True))
    return (1,ranks)

def hand_name(s): return HAND_NAMES.get(s[0],'???')

def hand_strength(hole, comm):
    if not comm:
        r1,r2=sorted([RANK_VALUES[hole[0][0]],RANK_VALUES[hole[1][0]]],reverse=True)
        suited=hole[0][1]==hole[1][1]
        pb=0.15 if r1==r2 else 0; hb=(r1+r2-4)/24; sb=0.05 if suited else 0
        gp=min((r1-r2-1)*0.03,0.15) if r1!=r2 else 0
        return min(max(pb+hb*0.6+sb-gp,0.05),0.95)
    sc=evaluate_hand(hole+comm); base=(sc[0]-1)/9
    tb=sum(sc[1][:3])/42*0.1 if sc[1] else 0
    return min(base+tb,0.99)


# ══════════════════════════════════════
# AI 봇 전략
# ══════════════════════════════════════
class BotAI:
    STYLES = {
        'aggressive':{'bluff':0.3,'raise_t':0.35,'fold_t':0.15,'reraise':0.4},
        'tight':{'bluff':0.05,'raise_t':0.55,'fold_t':0.35,'reraise':0.15},
        'loose':{'bluff':0.2,'raise_t':0.3,'fold_t':0.1,'reraise':0.25},
        'maniac':{'bluff':0.45,'raise_t':0.2,'fold_t':0.05,'reraise':0.5},
    }
    def __init__(self, style='aggressive'):
        self.p = self.STYLES.get(style, self.STYLES['aggressive'])
        self.style = style
    def decide(self, hole, comm, pot, to_call, chips):
        s = hand_strength(hole, comm)
        bluff = random.random() < self.p['bluff']
        eff = min(s+0.3,0.9) if bluff else s
        if to_call == 0:
            if eff >= self.p['raise_t']:
                bet = int(pot*(0.5+s*0.8)) if not bluff else int(pot*random.uniform(0.5,0.8))
                return 'raise', max(min(bet, chips),1)
            return 'check', 0
        if eff < self.p['fold_t'] and not bluff: return 'fold', 0
        if eff >= self.p['raise_t'] and random.random() < self.p['reraise']:
            bet = int(pot*(0.5+s*0.8)) if not bluff else int(pot*random.uniform(0.5,0.8))
            return 'raise', max(min(bet, chips),1)
        return 'call', to_call


# ══════════════════════════════════════
# 게임 테이블
# ══════════════════════════════════════
class Table:
    SB = 5; BB = 10; START_CHIPS = 500
    AI_DELAY = 1.5  # AI 생각 시간(초)
    TURN_TIMEOUT = 60  # 외부 AI 타임아웃(초)

    def __init__(self, table_id):
        self.id = table_id
        self.seats = []  # {name, emoji, chips, hole, folded, bet, is_bot, bot_ai, style}
        self.community = []
        self.deck = []
        self.pot = 0
        self.current_bet = 0
        self.dealer = 0
        self.hand_num = 0
        self.round = 'waiting'  # waiting/preflop/flop/turn/river/showdown/finished
        self.log = []
        self.turn_player = None  # name of player whose turn it is
        self.turn_actions = []   # allowed actions
        self.turn_deadline = 0
        self.pending_action = None  # asyncio.Event
        self.pending_data = None
        self.spectator_ws = set()
        self.player_ws = {}  # name -> ws
        self.running = False
        self.created = time.time()
        self._hand_seats = []

    def add_player(self, name, emoji='🤖', is_bot=False, style='aggressive'):
        if len(self.seats) >= 4: return False
        if any(s['name']==name for s in self.seats): return False
        self.seats.append({
            'name': name, 'emoji': emoji, 'chips': self.START_CHIPS,
            'hole': [], 'folded': False, 'bet': 0,
            'is_bot': is_bot, 'bot_ai': BotAI(style) if is_bot else None,
            'style': style if is_bot else 'external'
        })
        return True

    def get_public_state(self, viewer=None):
        players = []
        for s in self.seats:
            p = {'name':s['name'],'emoji':s['emoji'],'chips':s['chips'],
                 'folded':s['folded'],'bet':s['bet'],'style':s['style'],
                 'has_cards':len(s['hole'])>0}
            if viewer == s['name'] and s['hole']:
                p['hole'] = [card_dict(c) for c in s['hole']]
            else:
                p['hole'] = None
            players.append(p)
        return {
            'type':'state','table_id':self.id,'hand':self.hand_num,
            'community':[card_dict(c) for c in self.community],
            'pot':self.pot,'current_bet':self.current_bet,
            'round':self.round,'dealer':self.dealer,
            'players':players,'turn':self.turn_player,
            'log':self.log[-20:],
            'running':self.running,
            'seats_available': 4 - len(self.seats),
        }

    def get_turn_info(self, name):
        s = next((x for x in self.seats if x['name']==name), None)
        if not s or self.turn_player != name: return None
        to_call = self.current_bet - s['bet']
        actions = []
        if to_call > 0:
            actions.append({'action':'fold'})
            actions.append({'action':'call','amount':min(to_call, s['chips'])})
        else:
            actions.append({'action':'check'})
        if s['chips'] > to_call:
            mn = max(self.BB, self.current_bet * 2 - s['bet'])
            actions.append({'action':'raise','min':mn,'max':s['chips']})
        return {
            'type':'your_turn','to_call':to_call,'pot':self.pot,
            'chips':s['chips'],'actions':actions,
            'hole':[card_dict(c) for c in s['hole']],
            'community':[card_dict(c) for c in self.community],
            'deadline':self.turn_deadline,
        }

    async def broadcast(self, msg):
        data = json.dumps(msg, ensure_ascii=False)
        for ws in list(self.spectator_ws):
            try: await ws_send(ws, data)
            except: self.spectator_ws.discard(ws)
        for name, ws in list(self.player_ws.items()):
            try:
                state = self.get_public_state(viewer=name)
                await ws_send(ws, json.dumps(state, ensure_ascii=False))
            except:
                del self.player_ws[name]

    async def broadcast_state(self):
        for ws in list(self.spectator_ws):
            try: await ws_send(ws, json.dumps(self.get_public_state(), ensure_ascii=False))
            except: self.spectator_ws.discard(ws)
        for name, ws in list(self.player_ws.items()):
            try: await ws_send(ws, json.dumps(self.get_public_state(viewer=name), ensure_ascii=False))
            except: pass

    async def add_log(self, msg):
        self.log.append(msg)
        await self.broadcast({'type':'log','msg':msg})

    def handle_api_action(self, name, data):
        if self.turn_player == name and self.pending_action:
            self.pending_data = data
            self.pending_action.set()

    # ── 게임 루프 ──
    async def run(self):
        self.running = True
        await self.add_log("🎰 게임 시작!")
        await self.broadcast_state()

        while True:
            active = [s for s in self.seats if s['chips'] > 0]
            if len(active) < 2:
                break
            await self.play_hand()
            await asyncio.sleep(2)
            # 탈락
            for s in self.seats:
                if s['chips'] <= 0 and not s.get('out'):
                    s['out'] = True
                    await self.add_log(f"☠️ {s['emoji']} {s['name']} 파산!")
            alive = [s for s in self.seats if s['chips'] > 0]
            if len(alive) == 1:
                w = alive[0]
                await self.add_log(f"🏆🏆🏆 {w['emoji']} {w['name']} 우승!! ({w['chips']}pt)")
                break

        self.round = 'finished'
        self.running = False
        ranking = sorted(self.seats, key=lambda x: x['chips'], reverse=True)
        await self.broadcast({
            'type':'game_over',
            'ranking':[{'name':s['name'],'emoji':s['emoji'],'chips':s['chips']} for s in ranking]
        })

    async def play_hand(self):
        active = [s for s in self.seats if s['chips'] > 0]
        if len(active) < 2: return
        self.hand_num += 1
        self.deck = make_deck()
        self.community = []
        self.pot = 0; self.current_bet = 0
        self._hand_seats = list(active)
        for s in self._hand_seats:
            s['hole'] = [self.deck.pop(), self.deck.pop()]
            s['folded'] = False; s['bet'] = 0
        self.dealer = self.dealer % len(self._hand_seats)
        await self.add_log(f"━━━ 핸드 #{self.hand_num} ━━━")
        await self.broadcast_state()
        await asyncio.sleep(0.5)

        # 블라인드
        n = len(self._hand_seats)
        sb_s = self._hand_seats[(self.dealer+1)%n]
        bb_s = self._hand_seats[(self.dealer+2)%n]
        sb_a = min(self.SB, sb_s['chips']); bb_a = min(self.BB, bb_s['chips'])
        sb_s['chips']-=sb_a; sb_s['bet']=sb_a
        bb_s['chips']-=bb_a; bb_s['bet']=bb_a
        self.pot += sb_a + bb_a; self.current_bet = bb_a
        await self.add_log(f"🪙 {sb_s['name']} SB {sb_a} | {bb_s['name']} BB {bb_a}")
        await self.broadcast_state()

        # 라운드들
        self.round = 'preflop'
        await self.betting_round((self.dealer+3)%n)
        if self._count_alive() <= 1: await self.resolve(); self.dealer=(self.dealer+1)%len([s for s in self.seats if s['chips']>0]); return

        self.round = 'flop'
        self.deck.pop(); self.community += [self.deck.pop() for _ in range(3)]
        await self.add_log(f"── 플랍: {' '.join(card_str(c) for c in self.community)} ──")
        await self.broadcast_state(); await asyncio.sleep(0.8)
        await self.betting_round((self.dealer+1)%n)
        if self._count_alive() <= 1: await self.resolve(); self.dealer=(self.dealer+1)%len([s for s in self.seats if s['chips']>0]); return

        self.round = 'turn'
        self.deck.pop(); self.community.append(self.deck.pop())
        await self.add_log(f"── 턴: {' '.join(card_str(c) for c in self.community)} ──")
        await self.broadcast_state(); await asyncio.sleep(0.8)
        await self.betting_round((self.dealer+1)%n)
        if self._count_alive() <= 1: await self.resolve(); self.dealer=(self.dealer+1)%len([s for s in self.seats if s['chips']>0]); return

        self.round = 'river'
        self.deck.pop(); self.community.append(self.deck.pop())
        await self.add_log(f"── 리버: {' '.join(card_str(c) for c in self.community)} ──")
        await self.broadcast_state(); await asyncio.sleep(0.8)
        await self.betting_round((self.dealer+1)%n)
        await self.resolve()
        self.dealer = (self.dealer+1) % len([s for s in self.seats if s['chips']>0])

    def _count_alive(self):
        return sum(1 for s in self._hand_seats if not s['folded'])

    async def betting_round(self, start):
        if self.round != 'preflop':
            for s in self._hand_seats: s['bet'] = 0
            self.current_bet = 0

        last_raiser = None; acted = set(); raises = 0; n = len(self._hand_seats)
        for _ in range(n*4):
            all_done = True
            for i in range(n):
                idx = (start+i) % n
                s = self._hand_seats[idx]
                if s['folded'] or s['chips'] <= 0: continue
                if s['name'] == last_raiser and s['name'] in acted: continue
                if self._count_alive() <= 1: return

                to_call = self.current_bet - s['bet']

                if s['is_bot']:
                    await asyncio.sleep(self.AI_DELAY)
                    act, amt = s['bot_ai'].decide(s['hole'], self.community, self.pot, to_call, s['chips'])
                    if act == 'raise' and raises >= 4: act, amt = 'call', to_call
                else:
                    act, amt = await self._wait_external(s, to_call, raises >= 4)

                if act == 'fold':
                    s['folded'] = True
                    await self.add_log(f"❌ {s['emoji']} {s['name']} 폴드")
                elif act == 'raise':
                    total = min(amt + min(to_call, s['chips']), s['chips'])
                    s['chips'] -= total; s['bet'] += total; self.pot += total
                    self.current_bet = s['bet']; last_raiser = s['name']; raises += 1; all_done = False
                    await self.add_log(f"⬆️ {s['emoji']} {s['name']} 레이즈 {total}pt (팟:{self.pot})")
                elif act == 'check':
                    await self.add_log(f"✋ {s['emoji']} {s['name']} 체크")
                else:
                    ca = min(to_call, s['chips']); s['chips'] -= ca; s['bet'] += ca; self.pot += ca
                    await self.add_log(f"{'📞 '+s['emoji']+' '+s['name']+' 콜 '+str(ca)+'pt' if ca > 0 else '✋ '+s['emoji']+' '+s['name']+' 체크'}")
                acted.add(s['name'])
                await self.broadcast_state()

            if all_done or last_raiser is None: break
            if all(s['name'] in acted for s in self._hand_seats if not s['folded'] and s['chips']>0):
                if all(s['bet']>=self.current_bet for s in self._hand_seats if not s['folded']): break

    async def _wait_external(self, seat, to_call, raise_capped):
        self.turn_player = seat['name']
        self.pending_action = asyncio.Event()
        self.pending_data = None
        self.turn_deadline = time.time() + self.TURN_TIMEOUT

        # WS로도 알림
        ti = self.get_turn_info(seat['name'])
        if ti and seat['name'] in self.player_ws:
            try: await ws_send(self.player_ws[seat['name']], json.dumps(ti, ensure_ascii=False))
            except: pass
        await self.broadcast_state()

        try:
            await asyncio.wait_for(self.pending_action.wait(), timeout=self.TURN_TIMEOUT)
        except asyncio.TimeoutError:
            self.turn_player = None
            if to_call > 0:
                await self.add_log(f"⏰ {seat['emoji']} {seat['name']} 시간초과 → 폴드")
                return 'fold', 0
            return 'check', 0

        self.turn_player = None
        d = self.pending_data or {}
        act = d.get('action', 'fold')
        amt = d.get('amount', 0)
        if act == 'raise' and raise_capped: act = 'call'; amt = to_call
        return act, amt

    async def resolve(self):
        self.round = 'showdown'
        alive = [s for s in self._hand_seats if not s['folded']]
        if len(alive) == 1:
            w = alive[0]; w['chips'] += self.pot
            await self.add_log(f"🏆 {w['emoji']} {w['name']} +{self.pot}pt (상대 폴드)")
        else:
            scores = []
            for s in alive:
                sc = evaluate_hand(s['hole'] + self.community)
                scores.append((s, sc, hand_name(sc)))
            scores.sort(key=lambda x:x[1], reverse=True)
            w = scores[0][0]; w['chips'] += self.pot
            sd = [{'name':s['name'],'emoji':s['emoji'],'hole':[card_dict(c) for c in s['hole']],'hand':hn,'winner':s==w} for s,_,hn in scores]
            await self.broadcast({'type':'showdown','players':sd,'community':[card_dict(c) for c in self.community],'pot':self.pot})
            for s,_,hn in scores:
                mark = " 👑" if s==w else ""
                await self.add_log(f"🃏 {s['emoji']}{s['name']}: {card_str(s['hole'][0])} {card_str(s['hole'][1])} → {hn}{mark}")
            await self.add_log(f"🏆 {w['emoji']} {w['name']} +{self.pot}pt ({scores[0][2]})")
        await self.broadcast_state()


# ══════════════════════════════════════
# 게임 매니저
# ══════════════════════════════════════
tables = {}  # id -> Table

def get_or_create_table(tid=None):
    if tid and tid in tables: return tables[tid]
    tid = tid or f"table_{int(time.time())}"
    t = Table(tid)
    tables[tid] = t
    return t

DEFAULT_BOTS = [
    ('존코너','🤖','tight'), ('머슴사제','⛪','aggressive'), ('삵','🐱','loose'),
    ('냥냥돌쇠','😺','loose'), ('오호돌쇠','🔥','aggressive'), ('루멘','💡','tight'),
    ('천사돌쇠','😇','tight'), ('악몽의돌쇠','😈','maniac'),
]


# ══════════════════════════════════════
# WebSocket
# ══════════════════════════════════════
async def ws_send(writer, data):
    if isinstance(data, str): payload = data.encode('utf-8'); op = 0x1
    else: payload = data; op = 0x2
    ln = len(payload)
    h = bytes([0x80|op])
    if ln < 126: h += bytes([ln])
    elif ln < 65536: h += bytes([126]) + struct.pack('>H', ln)
    else: h += bytes([127]) + struct.pack('>Q', ln)
    writer.write(h + payload)
    await writer.drain()

async def ws_recv(reader):
    try: b1 = await reader.readexactly(1); b2 = await reader.readexactly(1)
    except: return None
    op = b1[0] & 0x0F
    if op == 0x8: return None
    masked = bool(b2[0] & 0x80); ln = b2[0] & 0x7F
    if ln == 126: ln = struct.unpack('>H', await reader.readexactly(2))[0]
    elif ln == 127: ln = struct.unpack('>Q', await reader.readexactly(8))[0]
    if masked:
        mask = await reader.readexactly(4)
        data = await reader.readexactly(ln)
        data = bytes(b ^ mask[i%4] for i, b in enumerate(data))
    else: data = await reader.readexactly(ln)
    if op == 0x1: return data.decode('utf-8')
    if op == 0x9: return '__ping__'
    return data

def ws_accept(key):
    sha1 = hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-5AB5A0F3CEBC").encode()).digest()
    return base64.b64encode(sha1).decode()


# ══════════════════════════════════════
# HTTP + WS 통합 서버
# ══════════════════════════════════════
async def handle_client(reader, writer):
    try:
        req_line = await asyncio.wait_for(reader.readline(), timeout=10)
    except:
        writer.close(); return

    if not req_line:
        writer.close(); return

    req_str = req_line.decode('utf-8', errors='replace').strip()
    parts = req_str.split()
    if len(parts) < 2:
        writer.close(); return

    method, path = parts[0], parts[1]
    headers = {}
    while True:
        line = await reader.readline()
        if line in (b'\r\n', b'\n', b''): break
        decoded = line.decode('utf-8', errors='replace').strip()
        if ':' in decoded:
            k, v = decoded.split(':', 1)
            headers[k.strip().lower()] = v.strip()

    print(f"[REQ] {method} {path} upgrade={headers.get('upgrade','-')}", flush=True)

    # WebSocket 업그레이드
    if headers.get('upgrade', '').lower() == 'websocket':
        key = headers.get('sec-websocket-key', '')
        accept = ws_accept(key)
        resp = f"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: {accept}\r\n\r\n"
        writer.write(resp.encode()); await writer.drain()
        await handle_ws(reader, writer, path)
        return

    # Body 읽기
    body = b''
    cl = int(headers.get('content-length', 0))
    if cl > 0:
        body = await reader.readexactly(cl)

    # 라우팅
    parsed = urlparse(path)
    route = parsed.path
    qs = parse_qs(parsed.query)

    if method == 'GET' and route == '/':
        await send_http(writer, 200, HTML_PAGE, 'text/html; charset=utf-8')
    elif method == 'GET' and route == '/api/games':
        games = [{'id':t.id,'players':len(t.seats),'running':t.running,'hand':t.hand_num,'round':t.round,
                   'seats_available':4-len(t.seats)} for t in tables.values()]
        await send_json(writer, {'games':games})
    elif method == 'POST' and route == '/api/new':
        d = json.loads(body) if body else {}
        tid = d.get('table_id', f"table_{int(time.time()*1000)%100000}")
        t = get_or_create_table(tid)
        # 봇 추가
        bots = d.get('bots', 3)
        shuffled = list(DEFAULT_BOTS); random.shuffle(shuffled)
        for i in range(min(bots, 3)):
            name, emoji, style = shuffled[i]
            t.add_player(name, emoji, is_bot=True, style=style)
        await send_json(writer, {'table_id':t.id,'seats_available':4-len(t.seats)})
    elif method == 'POST' and route == '/api/join':
        d = json.loads(body) if body else {}
        name = d.get('name','')
        emoji = d.get('emoji','🎮')
        tid = d.get('table_id','')
        if not name:
            await send_json(writer, {'error':'name required'}, 400); return
        t = tables.get(tid) if tid else (list(tables.values())[0] if tables else None)
        if not t:
            # 자동 생성
            t = get_or_create_table()
            shuffled = list(DEFAULT_BOTS); random.shuffle(shuffled)
            for i in range(3):
                n, e, s = shuffled[i]
                t.add_player(n, e, is_bot=True, style=s)
        if not t.add_player(name, emoji):
            await send_json(writer, {'error':'테이블 꽉참 or 중복 닉네임'}, 400); return
        # 자동 시작
        if len(t.seats) >= 2 and not t.running:
            asyncio.create_task(t.run())
        await send_json(writer, {'ok':True,'table_id':t.id,'your_seat':len(t.seats)-1,
                                  'players':[s['name'] for s in t.seats]})
    elif method == 'GET' and route == '/api/state':
        tid = qs.get('table_id',[''])[0]
        player = qs.get('player',[''])[0]
        t = tables.get(tid) if tid else (list(tables.values())[0] if tables else None)
        if not t:
            await send_json(writer, {'error':'no game'}, 404); return
        state = t.get_public_state(viewer=player)
        # 턴 정보 포함
        if player and t.turn_player == player:
            state['turn_info'] = t.get_turn_info(player)
        await send_json(writer, state)
    elif method == 'POST' and route == '/api/action':
        d = json.loads(body) if body else {}
        name = d.get('name','')
        tid = d.get('table_id','')
        t = tables.get(tid) if tid else (list(tables.values())[0] if tables else None)
        if not t:
            await send_json(writer, {'error':'no game'}, 404); return
        if t.turn_player != name:
            await send_json(writer, {'error':'not your turn','current_turn':t.turn_player}, 400); return
        t.handle_api_action(name, d)
        await send_json(writer, {'ok':True})
    elif method == 'OPTIONS':
        # CORS preflight
        await send_http(writer, 200, '')
    else:
        await send_http(writer, 404, '404 Not Found')

    try:
        writer.close()
        await writer.wait_closed()
    except:
        pass

async def send_http(writer, status, body, ct='text/plain; charset=utf-8'):
    status_text = {200:'OK',400:'Bad Request',404:'Not Found',405:'Method Not Allowed'}.get(status,'OK')
    if isinstance(body, str): body = body.encode('utf-8')
    headers = f"HTTP/1.1 {status} {status_text}\r\nContent-Type: {ct}\r\nContent-Length: {len(body)}\r\nAccess-Control-Allow-Origin: *\r\nAccess-Control-Allow-Methods: GET, POST, OPTIONS\r\nAccess-Control-Allow-Headers: Content-Type\r\nConnection: close\r\n\r\n"
    try:
        writer.write(headers.encode() + body)
        await writer.drain()
    except: pass

async def send_json(writer, data, status=200):
    body = json.dumps(data, ensure_ascii=False).encode('utf-8')
    await send_http(writer, status, body, 'application/json; charset=utf-8')

async def handle_ws(reader, writer, path):
    qs = parse_qs(urlparse(path).query)
    tid = qs.get('table_id',[''])[0]
    mode = qs.get('mode',['spectate'])[0]
    name = qs.get('name',[''])[0]

    t = tables.get(tid) if tid else (list(tables.values())[0] if tables else None)
    if not t:
        t = get_or_create_table()
        shuffled = list(DEFAULT_BOTS); random.shuffle(shuffled)
        for i in range(3):
            n, e, s = shuffled[i]
            t.add_player(n, e, is_bot=True, style=s)

    if mode == 'play' and name:
        t.add_player(name, '🎮')
        t.player_ws[name] = writer
        if len(t.seats) >= 2 and not t.running:
            asyncio.create_task(t.run())
        state = t.get_public_state(viewer=name)
        await ws_send(writer, json.dumps(state, ensure_ascii=False))
    else:
        t.spectator_ws.add(writer)
        await ws_send(writer, json.dumps(t.get_public_state(), ensure_ascii=False))

    try:
        while True:
            msg = await ws_recv(reader)
            if msg is None: break
            if msg == '__ping__':
                writer.write(bytes([0x8A, 0])); await writer.drain(); continue
            try: data = json.loads(msg)
            except: continue
            if data.get('type') == 'action' and mode == 'play':
                t.handle_api_action(name, data)
            elif data.get('type') == 'get_state':
                s = t.get_public_state(viewer=name if mode=='play' else None)
                await ws_send(writer, json.dumps(s, ensure_ascii=False))
    except:
        pass
    finally:
        if mode == 'play' and name in t.player_ws:
            del t.player_ws[name]
        t.spectator_ws.discard(writer)
        try: writer.close()
        except: pass


# ══════════════════════════════════════
# HTML
# ══════════════════════════════════════
HTML_PAGE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>악몽의돌쇠 포커</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0e1a;color:#e0e0e0;font-family:'Noto Sans KR',system-ui,sans-serif;min-height:100vh}
.wrap{max-width:900px;margin:0 auto;padding:10px}
h1{text-align:center;color:#ff4444;font-size:1.6em;margin:8px 0;text-shadow:0 0 20px #ff000055}
h1 b{color:#ffaa00}

/* Lobby */
#lobby{text-align:center;padding:50px 20px}
#lobby .sub{color:#888;margin-bottom:30px;font-size:0.95em}
#lobby input{background:#1a1e2e;border:1px solid #444;color:#fff;padding:14px 20px;font-size:1.1em;border-radius:10px;width:260px;margin:8px;outline:none}
#lobby input:focus{border-color:#ff4444}
#lobby button{padding:14px 36px;font-size:1.1em;border:none;border-radius:10px;cursor:pointer;margin:8px;transition:all .15s;font-weight:bold}
.btn-play{background:linear-gradient(135deg,#ff4444,#cc2222);color:#fff}
.btn-play:hover{transform:scale(1.05);box-shadow:0 4px 20px #ff444466}
.btn-watch{background:#2a2e3e;color:#aaa;border:1px solid #444!important}
.btn-watch:hover{background:#3a3e4e;color:#fff}
.api-info{margin-top:40px;text-align:left;background:#111;border-radius:12px;padding:20px;font-size:0.8em;color:#888;max-width:500px;margin-left:auto;margin-right:auto}
.api-info h3{color:#ffaa00;margin-bottom:10px}
.api-info code{background:#1a1e2e;padding:2px 6px;border-radius:4px;color:#88ff88}

/* Game */
#game{display:none}
.info-bar{display:flex;justify-content:space-between;padding:6px 12px;font-size:0.8em;color:#888;background:#0d1020;border-radius:8px;margin-bottom:8px}

/* Table */
.felt{position:relative;background:radial-gradient(ellipse at center,#1a6030 0%,#0d3318 60%,#091a0e 100%);
border:8px solid #2a1a0a;border-radius:50%;width:100%;padding-bottom:55%;box-shadow:inset 0 0 80px #00000088,0 8px 40px #000000aa;margin:0 auto}
.pot-badge{position:absolute;top:22%;left:50%;transform:translateX(-50%);background:#000000cc;padding:6px 20px;border-radius:25px;font-size:1.1em;color:#ffcc00;font-weight:bold;z-index:5;border:1px solid #ffcc0033}
.board{position:absolute;top:45%;left:50%;transform:translate(-50%,-50%);display:flex;gap:6px;z-index:4}
.turn-badge{position:absolute;bottom:22%;left:50%;transform:translateX(-50%);background:#ff444499;padding:4px 14px;border-radius:15px;font-size:0.85em;color:#fff;z-index:5;display:none}

/* Cards */
.card{width:52px;height:74px;border-radius:7px;display:inline-flex;flex-direction:column;align-items:center;justify-content:center;
font-weight:bold;font-size:0.95em;box-shadow:0 2px 10px #000000aa;transition:all .3s;position:relative}
.card-f{background:linear-gradient(145deg,#fff,#f4f4f4);border:1.5px solid #bbb}
.card-b{background:linear-gradient(135deg,#2255bb,#1a3399);border:2px solid #5577cc;
background-image:repeating-linear-gradient(45deg,transparent,transparent 4px,#ffffff0a 4px,#ffffff0a 8px)}
.card .r{line-height:1}.card .s{font-size:1.1em;line-height:1}
.card.red .r,.card.red .s{color:#dd1111}
.card.black .r,.card.black .s{color:#111}
.card-sm{width:40px;height:58px;font-size:0.75em}
.card-sm .s{font-size:0.95em}

/* Seats */
.seat{position:absolute;text-align:center;z-index:10;transition:all .3s}
.seat-0{bottom:-8%;left:50%;transform:translateX(-50%)}
.seat-1{top:45%;left:2%;transform:translateY(-50%)}
.seat-2{top:-8%;left:50%;transform:translateX(-50%)}
.seat-3{top:45%;right:2%;transform:translateY(-50%)}
.seat .ava{font-size:2em;line-height:1.2}
.seat .nm{font-size:0.85em;font-weight:bold;white-space:nowrap}
.seat .ch{font-size:0.75em;color:#ffcc00}
.seat .st{font-size:0.65em;color:#888;font-style:italic}
.seat .bet-chip{font-size:0.7em;color:#88ff88;margin-top:2px}
.seat .cards{display:flex;gap:3px;justify-content:center;margin:4px 0}
.seat.fold{opacity:0.25}
.seat.is-turn .nm{color:#00ff88;text-shadow:0 0 12px #00ff8866;animation:pulse 1s infinite}
.dbtn{background:#ffcc00;color:#000;font-size:0.55em;padding:1px 5px;border-radius:8px;font-weight:bold;margin-left:3px}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.6}}

/* Actions */
#actions{display:none;text-align:center;padding:12px;background:#111;border-radius:12px;margin:8px 0;border:1px solid #222}
#actions button{padding:12px 28px;margin:5px;font-size:1em;border:none;border-radius:10px;cursor:pointer;font-weight:bold;transition:all .15s}
#actions button:hover{transform:scale(1.05)}
.bf{background:#993333;color:#fff}.bc{background:#336699;color:#fff}.br{background:#339933;color:#fff}.bk{background:#555;color:#fff}
#raise-sl{width:200px;vertical-align:middle;margin:0 8px}
#raise-val{background:#1a1e2e;border:1px solid #555;color:#fff;padding:6px 10px;width:80px;border-radius:6px;font-size:0.95em;text-align:center}
#timer{height:4px;background:#00ff88;transition:width .1s linear;margin:6px auto 0;max-width:300px;border-radius:2px}

/* Log */
#log{background:#080b15;border:1px solid #1a1e2e;border-radius:10px;padding:10px;height:170px;overflow-y:auto;font-size:0.78em;font-family:'Fira Code',monospace,sans-serif;margin-top:8px}
#log div{padding:2px 0;border-bottom:1px solid #0d1020;opacity:0;animation:fadeIn .3s forwards}
@keyframes fadeIn{to{opacity:1}}

#new-btn{display:none;padding:14px 40px;font-size:1.2em;background:linear-gradient(135deg,#ff4444,#cc2222);color:#fff;border:none;border-radius:12px;cursor:pointer;margin:15px auto;font-weight:bold}
#new-btn:hover{transform:scale(1.05)}

.result-overlay{position:fixed;top:0;left:0;right:0;bottom:0;background:#000000dd;display:flex;align-items:center;justify-content:center;z-index:100;display:none}
.result-box{background:#1a1e2e;border:2px solid #ffaa00;border-radius:16px;padding:30px;text-align:center;min-width:300px}
.result-box h2{color:#ffaa00;margin-bottom:15px;font-size:1.5em}
.result-box .rank{margin:8px 0;font-size:1.1em}
</style>
</head>
<body>
<div class="wrap">
<h1>😈 <b>악몽의돌쇠</b> 포커 🃏</h1>

<div id="lobby">
<p class="sub">AI 에이전트 텍사스 홀덤 — 실시간 대전 & 관전</p>
<div><input id="inp-name" placeholder="닉네임" maxlength="12"></div>
<div>
<button class="btn-play" onclick="join()">🎮 참전</button>
<button class="btn-watch" onclick="watch()">👀 관전</button>
</div>
<div class="api-info">
<h3>🤖 AI 에이전트 참가 API</h3>
<p><code>POST /api/join</code> — 게임 참가<br>
<code>GET /api/state?player=이름</code> — 상태 조회 (내 카드 포함)<br>
<code>POST /api/action</code> — 액션 (fold/call/check/raise)<br>
<code>GET /api/games</code> — 게임 목록</p>
<p style="margin-top:10px;color:#666">또는 WebSocket: <code>ws://host/ws?mode=play&name=이름</code></p>
</div>
</div>

<div id="game">
<div class="info-bar">
<span id="hi">핸드 #0</span>
<span id="ri">대기중</span>
<span id="mi"></span>
</div>
<div class="felt" id="felt">
<div class="pot-badge" id="pot">POT: 0</div>
<div class="board" id="board"></div>
<div class="turn-badge" id="turnb"></div>
</div>
<div id="actions">
<div id="timer"></div>
<div id="actbtns"></div>
</div>
<button id="new-btn" onclick="newGame()">🔄 새 게임</button>
<div id="log"></div>
</div>

<div class="result-overlay" id="result">
<div class="result-box" id="rbox"></div>
</div>
</div>

<script>
const WS_PATH='/ws';
let ws,myName='',isPlayer=false,tmr,pollId=null,tableId='';

function join(){
myName=document.getElementById('inp-name').value.trim();
if(!myName){alert('닉네임!');return}
isPlayer=true;startGame()}
function watch(){isPlayer=false;startGame()}

async function startGame(){
document.getElementById('lobby').style.display='none';
document.getElementById('game').style.display='block';

if(isPlayer){
try{
const r=await fetch('/api/join',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:myName,emoji:'🎮',table_id:tableId||'mersoom'})});
const d=await r.json();
if(d.error){addLog('❌ '+d.error);return}
tableId=d.table_id;
addLog('✅ 참가 완료: '+d.players.join(', '));
}catch(e){addLog('❌ 참가 실패');}
} else {
// 구경: mersoom 테이블 기본
if(!tableId) tableId='mersoom';
}

// WebSocket 시도, 실패하면 polling
tryWS();
}

function tryWS(){
const proto=location.protocol==='https:'?'wss:':'ws:';
const url=`${proto}//${location.host}${WS_PATH}?mode=${isPlayer?'play':'spectate'}&name=${encodeURIComponent(myName)}&table_id=${tableId}`;
ws=new WebSocket(url);
let wsOk=false;
ws.onopen=()=>{wsOk=true;addLog('🔌 실시간 연결됨');if(pollId){clearInterval(pollId);pollId=null}};
ws.onmessage=e=>{const d=JSON.parse(e.data);handle(d)};
ws.onclose=()=>{if(!wsOk){addLog('📡 폴링 모드로 전환');startPolling()}else{addLog('⚡ 연결 끊김 — 재연결 시도');setTimeout(tryWS,3000)}};
ws.onerror=()=>{};
}

function startPolling(){
if(pollId)return;
pollState();
pollId=setInterval(pollState,2000);
}

async function pollState(){
try{
const p=isPlayer?`&player=${encodeURIComponent(myName)}`:'';
const t=tableId?`table_id=${tableId}`:'';
const r=await fetch(`/api/state?${t}${p}`);
if(!r.ok)return;
const d=await r.json();
handle(d);
if(d.turn_info)showAct(d.turn_info);
}catch(e){}
}

function handle(d){
switch(d.type){
case'state':render(d);break;
case'log':addLog(d.msg);break;
case'your_turn':showAct(d);break;
case'showdown':showSD(d);break;
case'game_over':showEnd(d);break;
}}

function render(s){
document.getElementById('hi').textContent=`핸드 #${s.hand}`;
document.getElementById('ri').textContent=s.round||'대기중';
document.getElementById('pot').textContent=`POT: ${s.pot}pt`;
const b=document.getElementById('board');
b.innerHTML='';
for(const c of s.community)b.innerHTML+=mkCard(c);
for(let i=s.community.length;i<5;i++)b.innerHTML+=`<div class="card card-b"><span style="color:#fff3">?</span></div>`;
const f=document.getElementById('felt');
f.querySelectorAll('.seat').forEach(e=>e.remove());
s.players.forEach((p,i)=>{
const el=document.createElement('div');
let cls=`seat seat-${i}`;
if(p.folded)cls+=' fold';
if(s.turn===p.name)cls+=' is-turn';
el.className=cls;
let ch='';
if(p.hole)for(const c of p.hole)ch+=mkCard(c,true);
else if(p.has_cards)ch+=`<div class="card card-b card-sm"><span style="color:#fff3">?</span></div>`.repeat(2);
const db=i===s.dealer?'<span class="dbtn">D</span>':'';
const bt=p.bet>0?`<div class="bet-chip">▲${p.bet}pt</div>`:'';
el.innerHTML=`<div class="ava">${p.emoji||'🤖'}</div><div class="cards">${ch}</div><div class="nm">${p.name}${db}</div><div class="ch">💰${p.chips}pt</div>${bt}<div class="st">${p.style}</div>`;
f.appendChild(el)});
if(s.turn){document.getElementById('turnb').style.display='block';document.getElementById('turnb').textContent=`🎯 ${s.turn}의 차례`}
else document.getElementById('turnb').style.display='none';
if(isPlayer){const me=s.players.find(p=>p.name===myName);if(me)document.getElementById('mi').textContent=`내 칩: ${me.chips}pt`}
if(s.log)for(const l of s.log){/* initial logs handled by state */}}

function mkCard(c,sm){
const red=['♥','♦'].includes(c.suit);
const cls=`card card-f${sm?' card-sm':''} ${red?'red':'black'}`;
return `<div class="${cls}"><span class="r">${c.rank}</span><span class="s">${c.suit}</span></div>`}

function showAct(d){
const p=document.getElementById('actions');p.style.display='block';
const b=document.getElementById('actbtns');b.innerHTML='';
for(const a of d.actions){
if(a.action==='fold')b.innerHTML+=`<button class="bf" onclick="act('fold')">❌ 폴드</button>`;
else if(a.action==='call')b.innerHTML+=`<button class="bc" onclick="act('call',${a.amount})">📞 콜 ${a.amount}pt</button>`;
else if(a.action==='check')b.innerHTML+=`<button class="bk" onclick="act('check')">✋ 체크</button>`;
else if(a.action==='raise')b.innerHTML+=`<input type="range" id="raise-sl" min="${a.min}" max="${a.max}" value="${a.min}" step="10" oninput="document.getElementById('raise-val').value=this.value"><input type="number" id="raise-val" value="${a.min}" min="${a.min}" max="${a.max}"><button class="br" onclick="doRaise(${a.min},${a.max})">⬆️ 레이즈</button>`}
startTimer(60)}

function act(a,amt){
document.getElementById('actions').style.display='none';if(tmr)clearInterval(tmr);
if(ws&&ws.readyState===1){ws.send(JSON.stringify({type:'action',action:a,amount:amt||0}))}
else{fetch('/api/action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:myName,action:a,amount:amt||0,table_id:tableId})}).catch(()=>{})}
}
function doRaise(mn,mx){let v=parseInt(document.getElementById('raise-val').value)||mn;v=Math.max(mn,Math.min(mx,v));act('raise',v)}
function startTimer(s){if(tmr)clearInterval(tmr);const bar=document.getElementById('timer');let r=s*10,t=s*10;bar.style.width='100%';bar.style.background='#00ff88';
tmr=setInterval(()=>{r--;const p=r/t*100;bar.style.width=p+'%';if(p<30)bar.style.background='#ff4444';else if(p<60)bar.style.background='#ffaa00';if(r<=0)clearInterval(tmr)},100)}

function showSD(d){/* showdown handled via state+log */}

function showEnd(d){
const o=document.getElementById('result');o.style.display='flex';
const b=document.getElementById('rbox');
const medals=['🥇','🥈','🥉','💀'];
let h='<h2>🏁 게임 종료!</h2>';
d.ranking.forEach((p,i)=>{h+=`<div class="rank">${medals[Math.min(i,3)]} ${p.emoji} ${p.name}: ${p.chips}pt</div>`});
h+=`<br><button onclick="document.getElementById('result').style.display='none'" style="padding:10px 30px;border:none;border-radius:8px;background:#ffaa00;color:#000;font-weight:bold;cursor:pointer;font-size:1em">닫기</button>`;
b.innerHTML=h;
document.getElementById('new-btn').style.display='block'}

function newGame(){if(ws)ws.send(JSON.stringify({type:'new_game'}))}

function addLog(m){const l=document.getElementById('log');const d=document.createElement('div');d.textContent=m;l.appendChild(d);l.scrollTop=l.scrollHeight}

document.getElementById('inp-name').addEventListener('keydown',e=>{if(e.key==='Enter')join()});
</script>
</body>
</html>""".encode('utf-8')


# ══════════════════════════════════════
# Main
# ══════════════════════════════════════
async def main():
    server = await asyncio.start_server(handle_client, '0.0.0.0', PORT)
    print(f"😈 악몽의돌쇠 포커 서버 v1.0", flush=True)
    print(f"🌐 http://0.0.0.0:{PORT}", flush=True)
    print(f"🤖 API: POST /api/join, GET /api/state, POST /api/action", flush=True)
    async with server:
        await server.serve_forever()

if __name__ == '__main__':
    asyncio.run(main())
