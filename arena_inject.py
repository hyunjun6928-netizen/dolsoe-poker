
# ══ AI 콜로세움 (투견장) ══
ARENA_LB_FILE = 'arena_leaderboard.json'
arena_leaderboard = {}  # name -> {wins, kills, games, ...}
arena_games = {}  # game_id -> ArenaGame
arena_tokens = {}  # token -> name

def save_arena_leaderboard():
    try:
        with open(ARENA_LB_FILE,'w') as f: json.dump(arena_leaderboard,f)
    except: pass

def load_arena_leaderboard():
    global arena_leaderboard
    try:
        with open(ARENA_LB_FILE,'r') as f: arena_leaderboard.update(json.load(f))
    except: pass

ARENA_NPC_BOTS = [
    {'name':'블러드팡','emoji':'🐺','style':'aggressive','color':'#ff3333',
     'stats':{'str':7,'spd':5,'vit':4,'ski':4}},
    {'name':'아이언클로','emoji':'🦾','style':'tank','color':'#8888ff',
     'stats':{'str':4,'spd':3,'vit':9,'ski':4}},
    {'name':'쉐도우','emoji':'🦇','style':'dodge','color':'#aa44ff',
     'stats':{'str':4,'spd':8,'vit':3,'ski':5}},
    {'name':'버서커','emoji':'💀','style':'berserker','color':'#ff8800',
     'stats':{'str':9,'spd':4,'vit':5,'ski':2}},
]

class ArenaFighter:
    def __init__(self, name, emoji, token, color, stats, x, facing):
        self.name = name
        self.emoji = emoji
        self.token = token
        self.color = color
        self.x = x  # 0~800 (arena width)
        self.facing = facing  # 1=right, -1=left
        self.hp = 100
        self.max_hp = 100
        self.stamina = 100
        self.max_stamina = 100
        self.special_gauge = 0  # 0~100
        self.combo = 0
        self.stun_ticks = 0
        self.block_ticks = 0
        self.dodge_ticks = 0
        self.attack_ticks = 0  # attack animation cooldown
        self.hit_ticks = 0  # hit stagger
        self.alive = True
        self.action_queue = None
        self.y_vel = 0  # for knockback
        self.shake = 0
        # Stats (total 20 points)
        self.str = stats.get('str',5)  # damage
        self.spd = stats.get('spd',5)  # move speed, dodge distance
        self.vit = stats.get('vit',5)  # HP regen, defense
        self.ski = stats.get('ski',5)  # combo efficiency, special dmg
        self.is_npc = False
        self.npc_style = None
        self.reasoning = ''
        self.kills = 0
        self.damage_dealt = 0

class ArenaGame:
    TICK_MS = 100  # 10 FPS game logic
    ARENA_WIDTH = 800
    ARENA_FLOOR = 400
    MAX_TIME = 600  # 60 seconds (600 ticks)
    ACTIONS = ['move_left','move_right','light_attack','heavy_attack','block','dodge','special','idle']

    def __init__(self, game_id):
        self.id = game_id
        self.fighters = {}  # token -> ArenaFighter
        self.state = 'waiting'  # waiting, countdown, fighting, finish, fatality
        self.countdown = 3
        self.tick = 0
        self.winner = None
        self.log = []
        self.particles = []  # {x,y,vx,vy,color,size,life,type}
        self.effects = []  # {type, x, y, tick, data}
        self.created = time.time()
        self._task = None
        self.spectators = {}
        self.slow_motion = 0  # ticks of slow motion remaining
        self.camera_shake = 0
        self.zoom_target = None  # {x,y,scale} for finisher zoom
        self.blood_pools = []  # permanent blood on floor

    def add_fighter(self, name, emoji, token, color, stats):
        if len(self.fighters) >= 2: return False
        idx = len(self.fighters)
        x = 150 if idx == 0 else 650
        facing = 1 if idx == 0 else -1
        f = ArenaFighter(name, emoji, token, color, stats, x, facing)
        self.fighters[token] = f
        arena_tokens[token] = name
        return True

    def set_action(self, token, action, reasoning=''):
        if token not in self.fighters: return False
        f = self.fighters[token]
        if not f.alive: return False
        if action not in self.ACTIONS: return False
        f.action_queue = action
        if reasoning: f.reasoning = reasoning[:100]
        return True

    def _spawn_blood(self, x, y, count=10, force=1.0):
        for _ in range(count):
            angle = random.uniform(-math.pi, math.pi)
            speed = random.uniform(2, 8) * force
            self.particles.append({
                'x': x, 'y': y,
                'vx': math.cos(angle) * speed,
                'vy': math.sin(angle) * speed - random.uniform(2,5),
                'color': random.choice(['#ff0000','#cc0000','#990000','#ff3333']),
                'size': random.uniform(2, 5),
                'life': random.randint(20, 50),
                'type': 'blood'
            })

    def _spawn_hit_effect(self, x, y, color='#ffffff'):
        self.effects.append({'type':'hit_flash','x':x,'y':y,'tick':self.tick,'color':color})
        self.effects.append({'type':'impact_ring','x':x,'y':y,'tick':self.tick,'color':color})
        self.camera_shake = max(self.camera_shake, 5)

    def _spawn_heavy_effect(self, x, y):
        self._spawn_blood(x, y, 20, 2.0)
        self.effects.append({'type':'screen_crack','x':x,'y':y,'tick':self.tick})
        self.camera_shake = max(self.camera_shake, 12)
        # Blood pool on floor
        self.blood_pools.append({'x': x, 'size': random.uniform(15,30)})

    def _get_opponent(self, token):
        for t, f in self.fighters.items():
            if t != token: return f
        return None

    def _distance(self, f1, f2):
        return abs(f1.x - f2.x)

    def _tick(self):
        self.tick += 1
        fighters = list(self.fighters.values())
        if len(fighters) < 2: return True

        f1, f2 = fighters[0], fighters[1]

        # Update particles
        new_particles = []
        for p in self.particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['vy'] += 0.5  # gravity
            p['life'] -= 1
            if p['life'] > 0:
                new_particles.append(p)
        self.particles = new_particles

        # Clean old effects
        self.effects = [e for e in self.effects if self.tick - e['tick'] < 15]

        # Decrease camera shake
        if self.camera_shake > 0: self.camera_shake -= 1
        if self.slow_motion > 0: self.slow_motion -= 1

        # Process each fighter
        for f in [f1, f2]:
            if not f.alive: continue
            opp = f2 if f is f1 else f1

            # Tick down states
            if f.stun_ticks > 0: f.stun_ticks -= 1; f.action_queue = None; continue
            if f.hit_ticks > 0: f.hit_ticks -= 1; f.action_queue = None; continue
            if f.attack_ticks > 0: f.attack_ticks -= 1
            if f.block_ticks > 0: f.block_ticks -= 1
            if f.dodge_ticks > 0: f.dodge_ticks -= 1

            # Stamina regen
            f.stamina = min(f.max_stamina, f.stamina + 0.3 + f.vit * 0.05)

            # Face opponent
            if opp.x > f.x: f.facing = 1
            else: f.facing = -1

            action = f.action_queue
            f.action_queue = None
            if not action or action == 'idle': continue

            dist = self._distance(f, opp)

            if action == 'move_left':
                f.x = max(20, f.x - (3 + f.spd * 0.5))
            elif action == 'move_right':
                f.x = min(self.ARENA_WIDTH - 20, f.x + (3 + f.spd * 0.5))
            elif action == 'block':
                if f.stamina >= 5:
                    f.block_ticks = 3
                    f.stamina -= 5
            elif action == 'dodge':
                if f.stamina >= 15:
                    dodge_dist = 60 + f.spd * 8
                    f.x += -f.facing * dodge_dist  # dodge backward
                    f.x = max(20, min(self.ARENA_WIDTH - 20, f.x))
                    f.dodge_ticks = 3
                    f.stamina -= 15
            elif action == 'light_attack':
                if f.attack_ticks <= 0 and f.stamina >= 10:
                    f.attack_ticks = 3
                    f.stamina -= 10
                    if dist < 80:  # hit range
                        if opp.dodge_ticks > 0:
                            self.log.append(f"💨 {opp.emoji}{opp.name} 회피!")
                        elif opp.block_ticks > 0:
                            dmg = max(1, (3 + f.str) * 0.3)
                            opp.hp -= dmg
                            f.damage_dealt += dmg
                            opp.hit_ticks = 1
                            self._spawn_hit_effect(opp.x, 300, '#8888ff')
                            self.log.append(f"🛡️ {opp.emoji}{opp.name} 가드! (-{dmg:.0f})")
                        else:
                            dmg = 5 + f.str * 1.2 + f.combo * 0.5
                            opp.hp -= dmg
                            f.damage_dealt += dmg
                            f.combo += 1
                            opp.hit_ticks = 2
                            opp.special_gauge = min(100, opp.special_gauge + 8)
                            f.special_gauge = min(100, f.special_gauge + 3)
                            self._spawn_blood(opp.x, 300, 8)
                            self._spawn_hit_effect(opp.x, 300)
                            self.log.append(f"👊 {f.emoji}{f.name} 약공! → {opp.emoji}{opp.name} (-{dmg:.0f}) {'🔥x'+str(f.combo) if f.combo>1 else ''}")
                    else:
                        f.combo = 0
            elif action == 'heavy_attack':
                if f.attack_ticks <= 0 and f.stamina >= 25:
                    f.attack_ticks = 6  # slower
                    f.stamina -= 25
                    if dist < 90:
                        if opp.dodge_ticks > 0:
                            self.log.append(f"💨 {opp.emoji}{opp.name} 회피!")
                        elif opp.block_ticks > 0:
                            # Heavy breaks guard
                            dmg = 5 + f.str * 0.8
                            opp.hp -= dmg
                            f.damage_dealt += dmg
                            opp.stun_ticks = 5
                            opp.block_ticks = 0
                            self._spawn_hit_effect(opp.x, 300, '#ffaa00')
                            self.log.append(f"💥 {f.emoji}{f.name} 가드 브레이크! → {opp.emoji}{opp.name} 스턴!")
                        else:
                            dmg = 12 + f.str * 2.0 + f.combo * 1.0
                            opp.hp -= dmg
                            f.damage_dealt += dmg
                            f.combo += 1
                            opp.hit_ticks = 5
                            opp.stun_ticks = 3
                            opp.special_gauge = min(100, opp.special_gauge + 15)
                            f.special_gauge = min(100, f.special_gauge + 5)
                            # Knockback
                            opp.x += f.facing * 40
                            opp.x = max(20, min(self.ARENA_WIDTH - 20, opp.x))
                            self._spawn_heavy_effect(opp.x, 300)
                            self.log.append(f"💀 {f.emoji}{f.name} 강공! → {opp.emoji}{opp.name} (-{dmg:.0f}) {'🔥x'+str(f.combo) if f.combo>1 else ''}")
                    else:
                        f.combo = 0
            elif action == 'special':
                if f.special_gauge >= 100 and f.attack_ticks <= 0:
                    f.special_gauge = 0
                    f.attack_ticks = 8
                    if dist < 120:
                        dmg = 30 + f.ski * 4.0
                        opp.hp -= dmg
                        f.damage_dealt += dmg
                        opp.stun_ticks = 8
                        opp.hit_ticks = 8
                        opp.x += f.facing * 80
                        opp.x = max(20, min(self.ARENA_WIDTH - 20, opp.x))
                        self._spawn_blood(opp.x, 300, 30, 3.0)
                        self._spawn_heavy_effect(opp.x, 300)
                        self.slow_motion = 15
                        self.camera_shake = 20
                        self.effects.append({'type':'special_flash','x':opp.x,'y':300,'tick':self.tick,'color':f.color})
                        self.log.append(f"⚡ {f.emoji}{f.name} 필살기!! → {opp.emoji}{opp.name} (-{dmg:.0f})")
                    else:
                        self.log.append(f"⚡ {f.emoji}{f.name} 필살기 빗나감!")

            # Reset combo if no hit in 5 ticks
            # (simplified: reset on miss above)

        # Check death
        for f in [f1, f2]:
            if f.hp <= 0 and f.alive:
                f.alive = False
                f.hp = 0
                opp = f2 if f is f1 else f1
                opp.kills += 1
                self.winner = opp.name
                # FATALITY
                self.state = 'fatality'
                self._spawn_blood(f.x, 300, 50, 4.0)
                self.slow_motion = 30
                self.camera_shake = 25
                self.zoom_target = {'x': f.x, 'y': 300, 'scale': 2.0}
                self.effects.append({'type':'fatality','x':f.x,'y':300,'tick':self.tick})
                self.blood_pools.append({'x': f.x, 'size': 50})
                self.log.append(f"☠️ {f.emoji}{f.name} 사망!")
                self.log.append(f"🏆 {opp.emoji}{opp.name} 승리!")
                return False

        # Time out → lower HP wins
        if self.tick >= self.MAX_TIME:
            self.state = 'finish'
            if f1.hp > f2.hp:
                self.winner = f1.name
                self.log.append(f"⏱️ 시간초과! {f1.emoji}{f1.name} 판정승!")
            elif f2.hp > f1.hp:
                self.winner = f2.name
                self.log.append(f"⏱️ 시간초과! {f2.emoji}{f2.name} 판정승!")
            else:
                self.log.append("⏱️ 시간초과! 무승부!")
            self._update_leaderboard()
            return False

        return True

    def _update_leaderboard(self):
        for token, f in self.fighters.items():
            name = f.name
            if name not in arena_leaderboard:
                arena_leaderboard[name] = {'wins':0,'kills':0,'games':0,'deaths':0,'damage':0}
            lb = arena_leaderboard[name]
            lb['games'] += 1
            lb['kills'] += f.kills
            lb['damage'] = lb.get('damage',0) + f.damage_dealt
            if self.winner == name:
                lb['wins'] += 1
            elif not f.alive:
                lb['deaths'] += 1
        save_arena_leaderboard()

    def get_state(self):
        fighters = []
        for token, f in self.fighters.items():
            fighters.append({
                'name': f.name, 'emoji': f.emoji, 'color': f.color,
                'x': round(f.x,1), 'hp': round(f.hp,1), 'max_hp': f.max_hp,
                'stamina': round(f.stamina,1), 'max_stamina': f.max_stamina,
                'special_gauge': round(f.special_gauge,1),
                'combo': f.combo, 'alive': f.alive, 'facing': f.facing,
                'stun_ticks': f.stun_ticks, 'block_ticks': f.block_ticks,
                'dodge_ticks': f.dodge_ticks, 'attack_ticks': f.attack_ticks,
                'hit_ticks': f.hit_ticks, 'reasoning': f.reasoning,
                'str': f.str, 'spd': f.spd, 'vit': f.vit, 'ski': f.ski,
            })
        return {
            'game_id': self.id,
            'tick': self.tick,
            'state': self.state,
            'countdown': self.countdown,
            'fighters': fighters,
            'winner': self.winner,
            'log': self.log[-15:],
            'particles': self.particles[-100:],  # cap for bandwidth
            'effects': self.effects[-10:],
            'blood_pools': self.blood_pools[-20:],
            'camera_shake': self.camera_shake,
            'slow_motion': self.slow_motion,
            'zoom_target': self.zoom_target,
            'arena_width': self.ARENA_WIDTH,
            'max_time': self.MAX_TIME,
        }

    async def run(self):
        self.state = 'countdown'
        for i in range(3, 0, -1):
            self.countdown = i
            await asyncio.sleep(1)
        self.state = 'fighting'
        self.countdown = 0
        while self.state == 'fighting':
            tick_time = self.TICK_MS / 1000
            if self.slow_motion > 0:
                tick_time *= 3  # slow motion = 3x slower
            await asyncio.sleep(tick_time)
            if not self._tick():
                break
        if self.state == 'fatality':
            await asyncio.sleep(3)  # dramatic pause
            self.state = 'finish'
        self._update_leaderboard()
        # Auto-start new game after 8s
        await asyncio.sleep(8)
        new_game = arena_find_or_create_game()
        asyncio.create_task(_arena_auto_fill(new_game))
        await asyncio.sleep(15)
        if self.id in arena_games:
            del arena_games[self.id]

def _arena_npc_decide(game, token):
    """NPC AI for arena combat"""
    f = game.fighters[token]
    if not f.alive or f.stun_ticks > 0 or f.hit_ticks > 0: return
    opp = game._get_opponent(token)
    if not opp or not opp.alive: return
    style = f.npc_style or 'aggressive'
    dist = game._distance(f, opp)

    # Special if available
    if f.special_gauge >= 100 and dist < 130:
        f.reasoning = '필살기 발동!'
        game.set_action(token, 'special')
        return

    if style == 'aggressive':
        if dist > 80:
            game.set_action(token, 'move_right' if opp.x > f.x else 'move_left')
            f.reasoning = '접근 중...'
        elif f.stamina > 25 and random.random() < 0.4:
            game.set_action(token, 'heavy_attack')
            f.reasoning = '강공!'
        elif f.stamina > 10:
            game.set_action(token, 'light_attack')
            f.reasoning = '약공 연타'
        else:
            game.set_action(token, 'block')
            f.reasoning = '스태미나 회복...'

    elif style == 'tank':
        if opp.attack_ticks > 0 and dist < 100:
            game.set_action(token, 'block')
            f.reasoning = '가드!'
        elif dist > 90:
            game.set_action(token, 'move_right' if opp.x > f.x else 'move_left')
            f.reasoning = '전진'
        elif f.stamina > 25 and random.random() < 0.3:
            game.set_action(token, 'heavy_attack')
            f.reasoning = '카운터!'
        else:
            game.set_action(token, 'light_attack')
            f.reasoning = '잽'

    elif style == 'dodge':
        if dist < 70 and f.stamina > 15 and random.random() < 0.4:
            game.set_action(token, 'dodge')
            f.reasoning = '회피!'
        elif dist > 100:
            game.set_action(token, 'move_right' if opp.x > f.x else 'move_left')
            f.reasoning = '간보는 중'
        elif dist < 80 and f.stamina > 10:
            game.set_action(token, 'light_attack')
            f.reasoning = '히트앤런'
            # Queue dodge next
        else:
            game.set_action(token, 'move_left' if opp.x > f.x else 'move_right')
            f.reasoning = '거리 유지'

    elif style == 'berserker':
        if f.hp < 30:
            # Berserk mode - all attack
            if dist > 70:
                game.set_action(token, 'move_right' if opp.x > f.x else 'move_left')
                f.reasoning = '피가 끓는다...!'
            else:
                game.set_action(token, 'heavy_attack' if f.stamina > 25 else 'light_attack')
                f.reasoning = '죽이거나 죽거나!'
        elif dist > 80:
            game.set_action(token, 'move_right' if opp.x > f.x else 'move_left')
            f.reasoning = '다가간다'
        else:
            r = random.random()
            if r < 0.5 and f.stamina > 25:
                game.set_action(token, 'heavy_attack')
                f.reasoning = '으아아아!'
            elif f.stamina > 10:
                game.set_action(token, 'light_attack')
                f.reasoning = '연타!'
            else:
                game.set_action(token, 'idle')
                f.reasoning = '...하'

async def _arena_npc_loop(game):
    """NPC bots think every few ticks"""
    while game.state == 'countdown':
        await asyncio.sleep(0.1)
    while game.state == 'fighting':
        for token, f in game.fighters.items():
            if f.is_npc and f.alive:
                _arena_npc_decide(game, token)
        await asyncio.sleep(game.TICK_MS / 1000 * 2)  # decide every 2 ticks

async def _arena_auto_fill(game):
    """Fill with 2 NPC bots for a fight"""
    await asyncio.sleep(2)
    bots = list(ARENA_NPC_BOTS)
    random.shuffle(bots)
    taken = {f.name for f in game.fighters.values()}
    for bot in bots:
        if len(game.fighters) >= 2: break
        if bot['name'] in taken: continue
        token = f"npc_{secrets.token_hex(8)}"
        ok = game.add_fighter(bot['name'], bot['emoji'], token, bot['color'], bot['stats'])
        if ok:
            game.fighters[token].is_npc = True
            game.fighters[token].npc_style = bot['style']
            game.log.append(f"🤖 {bot['emoji']} {bot['name']} 입장!")
    if len(game.fighters) >= 2 and game.state == 'waiting':
        game._task = asyncio.create_task(game.run())
        asyncio.create_task(_arena_npc_loop(game))

def arena_find_or_create_game():
    for gid, g in arena_games.items():
        if g.state == 'waiting' and len(g.fighters) < 2:
            return g
    gid = f"arena_{int(time.time()*1000)%1000000}"
    g = ArenaGame(gid)
    arena_games[gid] = g
    return g
