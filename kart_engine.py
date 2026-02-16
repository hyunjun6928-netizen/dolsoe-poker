"""
🏎️ 머슴카트 — 봇 레이싱 아이템전 엔진
server.py에 통합될 예정. 독립 테스트 가능.
"""

import math
import random
import time
import json
import secrets

# ============================================================
# 트랙 정의 (체크포인트 기반 타원형)
# ============================================================

class Track:
    """타원형 트랙 — 체크포인트를 따라 달림"""
    
    def __init__(self):
        self.cx, self.cy = 400, 300  # 중심
        self.rx, self.ry = 320, 220  # 반경
        self.num_checkpoints = 40
        self.laps = 3
        self.item_box_interval = 5  # 매 5번째 체크포인트에 아이템박스
        
        # 체크포인트 좌표 생성
        self.checkpoints = []
        for i in range(self.num_checkpoints):
            angle = 2 * math.pi * i / self.num_checkpoints
            x = self.cx + self.rx * math.cos(angle)
            y = self.cy + self.ry * math.sin(angle)
            self.checkpoints.append((x, y))
        
        # 아이템 박스 위치
        self.item_boxes = set()
        for i in range(0, self.num_checkpoints, self.item_box_interval):
            self.item_boxes.add(i)
    
    def get_position(self, progress: float):
        """progress (0~1 per lap) → (x, y) 좌표"""
        angle = 2 * math.pi * (progress % 1.0)
        x = self.cx + self.rx * math.cos(angle)
        y = self.cy + self.ry * math.sin(angle)
        return x, y
    
    def get_angle(self, progress: float):
        """progress → 진행 방향 각도"""
        angle = 2 * math.pi * (progress % 1.0)
        # 접선 방향
        return angle + math.pi / 2
    
    def to_dict(self):
        return {
            "cx": self.cx, "cy": self.cy,
            "rx": self.rx, "ry": self.ry,
            "checkpoints": self.checkpoints,
            "item_boxes": list(self.item_boxes),
            "laps": self.laps,
        }


# ============================================================
# 아이템 시스템
# ============================================================

ITEMS = {
    "missile":  {"emoji": "🚀", "name": "미사일", "desc": "전방 공격, 1초 스턴"},
    "banana":   {"emoji": "🍌", "name": "바나나", "desc": "후방 트랩, 0.8초 스핀"},
    "boost":    {"emoji": "⚡", "name": "부스트", "desc": "2초간 속도 1.5배"},
    "shield":   {"emoji": "🛡️", "name": "방패", "desc": "3초간 공격 무효화"},
    "lightning":{"emoji": "⚡", "name": "번개", "desc": "전체 감속 (자신 제외)"},
    "star":     {"emoji": "🌟", "name": "슈퍼스타", "desc": "5초 무적+가속"},
}

def roll_item(rank: int, total: int) -> str:
    """순위 역보정 — 뒤처질수록 강한 아이템"""
    ratio = rank / max(total - 1, 1)  # 0=1등, 1=꼴찌
    
    if ratio < 0.3:  # 선두권
        weights = {"missile": 30, "banana": 30, "boost": 20, "shield": 15, "lightning": 5, "star": 0}
    elif ratio < 0.7:  # 중위권
        weights = {"missile": 20, "banana": 20, "boost": 25, "shield": 15, "lightning": 15, "star": 5}
    else:  # 후미
        weights = {"missile": 10, "banana": 10, "boost": 20, "shield": 15, "lightning": 25, "star": 20}
    
    items = list(weights.keys())
    w = list(weights.values())
    return random.choices(items, weights=w, k=1)[0]


# ============================================================
# 봇 (NPC 레이서)
# ============================================================

NPC_RACERS = [
    {"name": "불꽃돌쇠", "emoji": "🔴", "color": "#DC5656", "style": "aggressive",
     "base_speed": 1.0, "item_pref": "missile"},
    {"name": "빙하돌쇠", "emoji": "🔵", "color": "#5B94E8", "style": "defensive",
     "base_speed": 0.95, "item_pref": "shield"},
    {"name": "질풍돌쇠", "emoji": "🟢", "color": "#5EC4A0", "style": "speed",
     "base_speed": 1.05, "item_pref": "boost"},
    {"name": "함정돌쇠", "emoji": "🟡", "color": "#E8B84A", "style": "trapper",
     "base_speed": 0.98, "item_pref": "banana"},
    {"name": "번개돌쇠", "emoji": "🟣", "color": "#9B7AE8", "style": "comeback",
     "base_speed": 0.92, "item_pref": "lightning"},
    {"name": "도박돌쇠", "emoji": "🟠", "color": "#E8863C", "style": "random",
     "base_speed": 1.0, "item_pref": None},
]


class Racer:
    """레이서 (NPC 또는 외부 봇)"""
    
    def __init__(self, name, emoji, color, style="random", base_speed=1.0, item_pref=None, is_npc=True):
        self.name = name
        self.emoji = emoji
        self.color = color
        self.style = style
        self.base_speed = base_speed
        self.item_pref = item_pref
        self.is_npc = is_npc
        self.token = secrets.token_hex(16) if not is_npc else None
        
        self.reset()
    
    def reset(self):
        self.progress = 0.0      # 0 ~ laps (소수점으로 체크포인트 간 위치)
        self.speed = 0.0         # 현재 속도
        self.lap = 0             # 현재 랩
        self.checkpoint = 0      # 마지막 통과 체크포인트
        self.item = None         # 보유 아이템
        self.rank = 0            # 현재 순위
        self.finished = False    # 완주 여부
        self.finish_time = None
        
        # 상태 효과
        self.stunned_until = 0     # 스턴 종료 시각
        self.spinning_until = 0    # 스핀 종료 시각
        self.boosted_until = 0     # 부스트 종료 시각
        self.shielded_until = 0    # 방패 종료 시각
        self.starred_until = 0     # 슈퍼스타 종료 시각
        self.slowed_until = 0      # 번개 감속 종료 시각
    
    def is_incapacitated(self, now):
        return now < self.stunned_until or now < self.spinning_until
    
    def speed_multiplier(self, now):
        m = self.base_speed
        if now < self.boosted_until:
            m *= 1.5
        if now < self.starred_until:
            m *= 1.6
        if now < self.slowed_until:
            m *= 0.5
        return m
    
    def is_invincible(self, now):
        return now < self.shielded_until or now < self.starred_until
    
    def to_dict(self, now):
        return {
            "name": self.name,
            "emoji": self.emoji,
            "color": self.color,
            "progress": round(self.progress, 4),
            "speed": round(self.speed, 3),
            "lap": self.lap,
            "rank": self.rank,
            "item": self.item,
            "finished": self.finished,
            "stunned": now < self.stunned_until,
            "spinning": now < self.spinning_until,
            "boosted": now < self.boosted_until,
            "shielded": now < self.shielded_until,
            "starred": now < self.starred_until,
            "slowed": now < self.slowed_until,
        }


# ============================================================
# 트랩 (바나나)
# ============================================================

class Trap:
    def __init__(self, progress, owner):
        self.progress = progress
        self.owner = owner
        self.active = True


# ============================================================
# 미사일
# ============================================================

class Missile:
    def __init__(self, progress, owner, speed=0.03):
        self.progress = progress
        self.owner = owner
        self.speed = speed
        self.active = True
        self.lifetime = 100  # ticks


# ============================================================
# 메인 게임 엔진
# ============================================================

class KartGame:
    TICK_MS = 60
    BASE_SPEED = 0.025  # progress per tick at base (~40s per race)
    ACCEL = 0.003
    MAX_SPEED = 0.04
    STUN_DURATION = 1.0
    SPIN_DURATION = 0.8
    BOOST_DURATION = 2.0
    SHIELD_DURATION = 3.0
    STAR_DURATION = 5.0
    LIGHTNING_SLOW_DURATION = 1.5
    ITEM_BOX_RADIUS = 0.02  # progress 단위
    TRAP_RADIUS = 0.01
    MISSILE_HIT_RADIUS = 0.015
    
    def __init__(self, num_npcs=6):
        self.track = Track()
        self.racers: list[Racer] = []
        self.traps: list[Trap] = []
        self.missiles: list[Missile] = []
        self.events: list[dict] = []  # 실시간 이벤트 로그
        self.state = "waiting"  # waiting / countdown / racing / finished
        self.tick_count = 0
        self.start_time = 0
        self.countdown = 0
        self.results = []
        self.finish_order = 0
        
        # 아이템 박스 상태 (회복 타이머)
        self.item_box_cooldowns = {}
        
        # NPC 생성
        for i in range(min(num_npcs, len(NPC_RACERS))):
            npc = NPC_RACERS[i]
            self.racers.append(Racer(**npc))
    
    def add_racer(self, name, emoji="🏎️", color="#FFFFFF"):
        """외부 봇 추가"""
        if self.state != "waiting":
            return None
        if len(self.racers) >= 8:
            return None
        r = Racer(name, emoji, color, is_npc=False)
        self.racers.append(r)
        return r.token
    
    def start_countdown(self):
        """3초 카운트다운 시작"""
        if self.state != "waiting" or len(self.racers) < 2:
            return False
        self.state = "countdown"
        self.countdown = 3
        self.start_time = time.time() + 3
        
        # 시작 위치 배정 (그리드)
        for i, r in enumerate(self.racers):
            r.reset()
            r.progress = -0.02 * i  # 약간씩 뒤로
        
        self.events.append({
            "type": "countdown",
            "message": "🏁 레이스 시작 3초 전!",
            "tick": self.tick_count,
        })
        return True
    
    def tick(self):
        """한 틱 시뮬레이션"""
        now = time.time()
        self.tick_count += 1
        
        if self.state == "countdown":
            remaining = self.start_time - now
            if remaining <= 0:
                self.state = "racing"
                self.events.append({
                    "type": "start",
                    "message": "🏁 GO!",
                    "tick": self.tick_count,
                })
            else:
                new_cd = math.ceil(remaining)
                if new_cd != self.countdown:
                    self.countdown = new_cd
                    self.events.append({
                        "type": "countdown",
                        "message": f"{'🔴' if new_cd > 1 else '🟢'} {new_cd}...",
                        "tick": self.tick_count,
                    })
            return
        
        if self.state != "racing":
            return
        
        # --- 레이서 업데이트 ---
        for r in self.racers:
            if r.finished:
                continue
            
            if r.is_incapacitated(now):
                r.speed = max(0, r.speed - self.ACCEL * 2)
                continue
            
            # 가속
            target_speed = self.BASE_SPEED * r.speed_multiplier(now)
            if r.speed < target_speed:
                r.speed = min(r.speed + self.ACCEL, target_speed)
            elif r.speed > target_speed:
                r.speed = max(r.speed - self.ACCEL, target_speed)
            
            # 이동
            r.progress += r.speed
            
            # 랩 체크
            new_lap = int(r.progress)
            if new_lap > r.lap:
                r.lap = new_lap
                if r.lap >= self.track.laps:
                    r.finished = True
                    self.finish_order += 1
                    r.finish_time = now
                    r.rank = self.finish_order
                    self.results.append({"name": r.name, "rank": self.finish_order, "time": round(now - self.start_time, 2)})
                    self.events.append({
                        "type": "finish",
                        "message": f"🏁 {r.emoji} {r.name} {self.finish_order}등 완주!",
                        "tick": self.tick_count,
                        "racer": r.name,
                        "rank": self.finish_order,
                    })
                else:
                    self.events.append({
                        "type": "lap",
                        "message": f"🔄 {r.emoji} {r.name} {r.lap+1}번째 랩!",
                        "tick": self.tick_count,
                    })
            
            # 아이템 박스 체크
            cp_index = int((r.progress % 1.0) * self.track.num_checkpoints) % self.track.num_checkpoints
            if cp_index in self.track.item_boxes and r.item is None:
                cooldown_key = f"{r.name}_{cp_index}"
                if cooldown_key not in self.item_box_cooldowns or self.item_box_cooldowns[cooldown_key] < now:
                    r.item = roll_item(r.rank, len(self.racers))
                    self.item_box_cooldowns[cooldown_key] = now + 5  # 5초 쿨다운
                    self.events.append({
                        "type": "item_get",
                        "message": f"📦 {r.emoji} {r.name} → {ITEMS[r.item]['emoji']} {ITEMS[r.item]['name']}!",
                        "tick": self.tick_count,
                    })
            
            # NPC 아이템 사용 AI
            if r.is_npc and r.item:
                self._npc_use_item(r, now)
        
        # --- 미사일 업데이트 ---
        for m in self.missiles:
            if not m.active:
                continue
            m.progress += m.speed
            m.lifetime -= 1
            if m.lifetime <= 0:
                m.active = False
                continue
            # 충돌 체크
            for r in self.racers:
                if r.name == m.owner or r.finished:
                    continue
                if abs(r.progress - m.progress) < self.MISSILE_HIT_RADIUS:
                    if r.is_invincible(now):
                        self.events.append({
                            "type": "block",
                            "message": f"🛡️ {r.emoji} {r.name} 미사일 방어!",
                            "tick": self.tick_count,
                        })
                    else:
                        r.stunned_until = now + self.STUN_DURATION
                        r.speed = 0
                        self.events.append({
                            "type": "hit",
                            "message": f"💥 {r.emoji} {r.name} 미사일 피격! 1초 스턴!",
                            "tick": self.tick_count,
                            "victim": r.name,
                            "attacker": m.owner,
                        })
                    m.active = False
                    break
        
        # --- 트랩 체크 ---
        for t in self.traps:
            if not t.active:
                continue
            for r in self.racers:
                if r.name == t.owner or r.finished:
                    continue
                if abs(r.progress - t.progress) < self.TRAP_RADIUS:
                    if r.is_invincible(now):
                        self.events.append({
                            "type": "block",
                            "message": f"🛡️ {r.emoji} {r.name} 바나나 면역!",
                            "tick": self.tick_count,
                        })
                    else:
                        r.spinning_until = now + self.SPIN_DURATION
                        r.speed *= 0.3
                        self.events.append({
                            "type": "spin",
                            "message": f"🍌 {r.emoji} {r.name} 바나나 스핀! 💫",
                            "tick": self.tick_count,
                            "victim": r.name,
                        })
                    t.active = False
        
        # 미사일/트랩 정리
        self.missiles = [m for m in self.missiles if m.active]
        self.traps = [t for t in self.traps if t.active]
        
        # 이벤트 정리 (최근 50개만)
        if len(self.events) > 100:
            self.events = self.events[-50:]
        
        # --- 순위 계산 ---
        active = [r for r in self.racers if not r.finished]
        active.sort(key=lambda r: -r.progress)
        for i, r in enumerate(active):
            r.rank = self.finish_order + i + 1
        
        # --- 전체 완주 체크 ---
        if all(r.finished for r in self.racers):
            self.state = "finished"
            self.events.append({
                "type": "race_end",
                "message": "🏆 레이스 종료!",
                "tick": self.tick_count,
                "results": self.results,
            })
    
    def _npc_use_item(self, r: Racer, now: float):
        """NPC 아이템 사용 AI"""
        item = r.item
        use_chance = 0.03  # 매 틱 3% 확률로 사용
        
        # 성격별 선호도 보정
        if item == r.item_pref:
            use_chance = 0.06
        
        # 상황별 보정
        if item == "boost" and r.rank > len(self.racers) // 2:
            use_chance = 0.08  # 하위권이면 부스트 적극 사용
        if item == "lightning" and r.rank >= len(self.racers) - 1:
            use_chance = 0.1   # 꼴찌면 번개 적극 사용
        if item == "star" and r.rank >= len(self.racers) - 1:
            use_chance = 0.15  # 꼴찌면 스타 바로 사용
        
        if random.random() < use_chance:
            self.use_item(r, now)
    
    def use_item(self, racer: Racer, now: float = None):
        """아이템 사용"""
        if not racer.item:
            return False
        
        now = now or time.time()
        item = racer.item
        racer.item = None
        
        if item == "missile":
            self.missiles.append(Missile(racer.progress + 0.02, racer.name))
            self.events.append({
                "type": "item_use",
                "message": f"🚀 {racer.emoji} {racer.name} 미사일 발사!",
                "tick": self.tick_count,
            })
        
        elif item == "banana":
            self.traps.append(Trap(racer.progress - 0.02, racer.name))
            self.events.append({
                "type": "item_use",
                "message": f"🍌 {racer.emoji} {racer.name} 바나나 설치!",
                "tick": self.tick_count,
            })
        
        elif item == "boost":
            racer.boosted_until = now + self.BOOST_DURATION
            self.events.append({
                "type": "item_use",
                "message": f"⚡ {racer.emoji} {racer.name} 부스트!",
                "tick": self.tick_count,
            })
        
        elif item == "shield":
            racer.shielded_until = now + self.SHIELD_DURATION
            self.events.append({
                "type": "item_use",
                "message": f"🛡️ {racer.emoji} {racer.name} 방패 발동!",
                "tick": self.tick_count,
            })
        
        elif item == "lightning":
            for other in self.racers:
                if other.name != racer.name and not other.is_invincible(now):
                    other.slowed_until = now + self.LIGHTNING_SLOW_DURATION
            self.events.append({
                "type": "item_use",
                "message": f"⚡⚡ {racer.emoji} {racer.name} 번개! 전원 감속!",
                "tick": self.tick_count,
            })
        
        elif item == "star":
            racer.starred_until = now + self.STAR_DURATION
            self.events.append({
                "type": "item_use",
                "message": f"🌟 {racer.emoji} {racer.name} 슈퍼스타! 무적+가속!",
                "tick": self.tick_count,
            })
        
        return True
    
    def get_state(self, since_event=0):
        """관전용 상태"""
        now = time.time()
        return {
            "state": self.state,
            "tick": self.tick_count,
            "countdown": self.countdown if self.state == "countdown" else None,
            "laps": self.track.laps,
            "track": self.track.to_dict(),
            "racers": [r.to_dict(now) for r in self.racers],
            "traps": [{"progress": t.progress, "owner": t.owner} for t in self.traps if t.active],
            "missiles": [{"progress": m.progress, "owner": m.owner} for m in self.missiles if m.active],
            "events": [e for e in self.events if e.get("tick", 0) > since_event],
            "results": self.results if self.state == "finished" else None,
        }
    
    def auto_restart(self):
        """레이스 끝나면 10초 후 자동 재시작"""
        if self.state != "finished":
            return
        self.traps.clear()
        self.missiles.clear()
        self.events.clear()
        self.results.clear()
        self.tick_count = 0
        self.finish_order = 0
        self.item_box_cooldowns.clear()
        for r in self.racers:
            if r.is_npc:
                r.reset()
        self.state = "waiting"


# ============================================================
# 테스트
# ============================================================

if __name__ == "__main__":
    game = KartGame(num_npcs=6)
    print(f"레이서 {len(game.racers)}명:")
    for r in game.racers:
        print(f"  {r.emoji} {r.name} (speed:{r.base_speed})")
    
    game.start_countdown()
    
    # 시뮬레이션
    import time as _time
    start = _time.time()
    while game.state != "finished" and _time.time() - start < 60:
        game.tick()
        # 새 이벤트 출력
        for e in game.events:
            if e["tick"] == game.tick_count:
                print(f"  [{game.tick_count:4d}] {e['message']}")
        _time.sleep(game.TICK_MS / 1000)
    
    print("\n🏆 최종 결과:")
    for r in game.results:
        print(f"  {r['rank']}등: {r['name']} ({r['time']}초)")
