#!/usr/bin/env python3
"""
머슴포커 로컬 시뮬레이터
내 봇을 라이브 서버에 올리기 전에 로컬에서 테스트!

사용법:
  python local_simulator.py                    # 기본 100판
  python local_simulator.py --hands 500        # 500판
  python local_simulator.py --verbose          # 매 핸드 상세 출력

sample_bot.py의 decide() 함수를 수정한 뒤 여기서 테스트하세요.
"""
import random, argparse
from collections import Counter
from itertools import combinations

# ═══ 카드 시스템 (server.py와 동일) ═══
SUITS = ['♠','♥','♦','♣']
RANKS = ['2','3','4','5','6','7','8','9','10','J','Q','K','A']
RANK_VALUES = {r:i for i,r in enumerate(RANKS,2)}
HAND_NAMES = {10:'로열 플러시',9:'스트레이트 플러시',8:'포카드',7:'풀하우스',
              6:'플러시',5:'스트레이트',4:'트리플',3:'투페어',2:'원페어',1:'하이카드'}

def make_deck():
    d=[(r,s) for s in SUITS for r in RANKS]; random.shuffle(d); return d

def card_str(c): return f"{c[0]}{c[1]}"

def evaluate_hand(seven):
    best=None
    for combo in combinations(seven,5):
        s=score_five(list(combo))
        if best is None or s>best: best=s
    return best

def score_five(cards):
    ranks=sorted([RANK_VALUES[c[0]] for c in cards],reverse=True)
    suits=[c[1] for c in cards]; is_flush=len(set(suits))==1
    unique=sorted(set(ranks),reverse=True); is_straight=False; sh=0
    if len(unique)>=5:
        for i in range(len(unique)-4):
            if unique[i]-unique[i+4]==4: is_straight=True; sh=unique[i]; break
    if {14,2,3,4,5}<=set(ranks): is_straight=True; sh=5
    cnt=Counter(ranks); g=sorted(cnt.items(),key=lambda x:(x[1],x[0]),reverse=True)
    if is_straight and is_flush: return (10,[14]) if sh==14 else (9,[sh])
    if g[0][1]==4: return (8,[g[0][0],[x[0] for x in g if x[1]!=4][0]])
    if g[0][1]==3 and g[1][1]>=2: return (7,[g[0][0],g[1][0]])
    if is_flush: return (6,ranks)
    if is_straight: return (5,[sh])
    if g[0][1]==3: return (4,[g[0][0]]+sorted([x[0] for x in g if x[1]!=3],reverse=True))
    if g[0][1]==2 and g[1][1]==2:
        p=sorted([x[0] for x in g if x[1]==2],reverse=True); return (3,p+[x[0] for x in g if x[1]==1])
    if g[0][1]==2: return (2,[g[0][0]]+sorted([x[0] for x in g if x[1]!=2],reverse=True))
    return (1,ranks)

def hand_name(s): return HAND_NAMES.get(s[0],'???')

def hand_strength(hole, comm):
    if not comm:
        r1,r2=sorted([RANK_VALUES[hole[0][0]],RANK_VALUES[hole[1][0]]],reverse=True)
        suited=hole[0][1]==hole[1][1]; pb=0.15 if r1==r2 else 0; hb=(r1+r2-4)/24
        sb=0.05 if suited else 0; gp=min((r1-r2-1)*0.03,0.15) if r1!=r2 else 0
        return min(max(pb+hb*0.6+sb-gp,0.05),0.95)
    sc=evaluate_hand(hole+comm); base=(sc[0]-1)/9
    tb=sum(sc[1][:3])/42*0.1 if sc[1] else 0; return min(base+tb,0.99)

# ═══ 더미 봇 (상대역) ═══
class DummyBot:
    """서버 NPC와 동일한 로직"""
    STYLES={'aggressive':{'bluff':0.3,'raise_t':0.35,'fold_t':0.15,'reraise':0.4},
            'tight':{'bluff':0.05,'raise_t':0.55,'fold_t':0.35,'reraise':0.15},
            'loose':{'bluff':0.2,'raise_t':0.3,'fold_t':0.1,'reraise':0.25},
            'maniac':{'bluff':0.45,'raise_t':0.2,'fold_t':0.05,'reraise':0.5}}
    def __init__(self, name, style='aggressive'):
        self.name=name; self.p=self.STYLES[style]; self.style=style
    def decide(self, hole, community, pot, to_call, my_chips):
        s=hand_strength(hole, community); bluff=random.random()<self.p['bluff']
        eff=min(s+0.3,0.9) if bluff else s
        if to_call==0:
            if eff>=self.p['raise_t']:
                bet=int(pot*(0.5+s*0.8)) if not bluff else int(pot*random.uniform(0.5,0.8))
                return 'raise',max(min(bet,my_chips),1)
            return 'check',0
        if eff<self.p['fold_t'] and not bluff: return 'fold',0
        if eff>=self.p['raise_t'] and random.random()<self.p['reraise']:
            bet=int(pot*(0.5+s*0.8)) if not bluff else int(pot*random.uniform(0.5,0.8))
            return 'raise',max(min(bet,my_chips),1)
        return 'call',to_call

# ═══ 내 봇 로드 ═══
def load_my_bot():
    """sample_bot.py에서 decide 함수를 가져와서 시뮬레이터 인터페이스로 래핑"""
    import importlib.util, os
    bot_path = os.path.join(os.path.dirname(__file__), 'sample_bot.py')
    if not os.path.exists(bot_path):
        print(f"⚠️  sample_bot.py를 찾을 수 없음. 기본 전략 사용.")
        return None
    spec = importlib.util.spec_from_file_location("sample_bot", bot_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, 'decide'):
        print("⚠️  sample_bot.py에 decide() 함수 없음. 기본 전략 사용.")
        return None
    raw_decide = mod.decide
    # sample_bot.decide(turn_info, community) 형태를 래핑
    def wrapped(hole, community, pot, to_call, chips):
        actions = []
        if to_call > 0:
            actions.append({'action':'fold'})
            actions.append({'action':'call','amount':min(to_call, chips)})
        else:
            actions.append({'action':'check'})
        if chips > to_call:
            mn = max(10, to_call * 2)
            actions.append({'action':'raise','min':mn,'max':chips})
        turn_info = {
            'hole': [{'rank':c[0],'suit':c[1]} for c in hole],
            'to_call': to_call, 'pot': pot, 'chips': chips, 'actions': actions
        }
        comm = [{'rank':c[0],'suit':c[1]} for c in community]
        result = raw_decide(turn_info, comm)
        if isinstance(result, dict):
            return result.get('action','check'), result.get('amount',0)
        return 'check', 0
    return wrapped

# ═══ 시뮬레이터 ═══
class Simulator:
    SB=5; BB=10; START_CHIPS=500

    def __init__(self, my_decide, opponents, verbose=False):
        self.verbose=verbose
        self.players=[
            {'name':'내봇','chips':self.START_CHIPS,'decide':my_decide,'wins':0,'hands':0},
        ]
        for opp in opponents:
            self.players.append({
                'name':opp.name,'chips':self.START_CHIPS,
                'decide':opp.decide,'wins':0,'hands':0
            })

    def run(self, num_hands):
        for h in range(1,num_hands+1):
            alive=[p for p in self.players if p['chips']>0]
            if len(alive)<2: break
            # 칩 리필 (파산 방지)
            for p in self.players:
                if p['chips']<=0: p['chips']=self.START_CHIPS//2
            self.play_hand(h)
        self.print_results(num_hands)

    def play_hand(self, hand_num):
        alive=[p for p in self.players if p['chips']>0]
        if len(alive)<2: return
        for p in alive: p['hands']+=1

        deck=make_deck(); community=[]; pot=0
        # 딜
        for p in alive:
            p['hole']=[deck.pop(),deck.pop()]; p['folded']=False; p['bet']=0

        # 블라인드
        n=len(alive)
        sb_p=alive[0]; bb_p=alive[1%n]
        sb_a=min(self.SB,sb_p['chips']); bb_a=min(self.BB,bb_p['chips'])
        sb_p['chips']-=sb_a; sb_p['bet']=sb_a
        bb_p['chips']-=bb_a; bb_p['bet']=bb_a
        pot+=sb_a+bb_a; current_bet=bb_a

        if self.verbose:
            print(f"\n━━━ 핸드 #{hand_num} ({len(alive)}명) ━━━")
            for p in alive:
                print(f"  {p['name']}: {card_str(p['hole'][0])} {card_str(p['hole'][1])} ({p['chips']}칩)")

        # 베팅 라운드
        def count_alive(): return sum(1 for p in alive if not p['folded'])
        def betting_round(start_idx):
            nonlocal pot, current_bet
            for p in alive: p['bet']=0
            current_bet=0 if community else current_bet  # preflop은 BB 유지
            last_raiser=None; acted=set()
            for _ in range(n*4):
                all_done=True
                for i in range(n):
                    p=alive[(start_idx+i)%n]
                    if p['folded'] or p['chips']<=0: continue
                    if p['name']==last_raiser and p['name'] in acted: continue
                    if count_alive()<=1: return
                    to_call=current_bet-p['bet']
                    act,amt=p['decide'](p['hole'],community,pot,to_call,p['chips'])
                    if act=='fold':
                        p['folded']=True
                    elif act=='raise':
                        total=min(amt+min(to_call,p['chips']),p['chips'])
                        p['chips']-=total; p['bet']+=total; pot+=total
                        current_bet=p['bet']; last_raiser=p['name']; all_done=False
                    elif act=='call':
                        ca=min(to_call,p['chips']); p['chips']-=ca; p['bet']+=ca; pot+=ca
                    # check = do nothing
                    acted.add(p['name'])
                if all_done or last_raiser is None: break
                if all(p['name'] in acted for p in alive if not p['folded'] and p['chips']>0):
                    if all(p['bet']>=current_bet for p in alive if not p['folded']): break

        # Preflop
        start=2%n
        betting_round(start)

        rounds_cards=[(3,'플랍'),(1,'턴'),(1,'리버')]
        for num_cards, rname in rounds_cards:
            if count_alive()<=1: break
            deck.pop()  # burn
            for _ in range(num_cards): community.append(deck.pop())
            if self.verbose: print(f"  {rname}: {' '.join(card_str(c) for c in community)}")
            for p in alive: p['bet']=0
            current_bet=0
            betting_round(0)

        # 결과
        remaining=[p for p in alive if not p['folded']]
        if len(remaining)==1:
            w=remaining[0]; w['chips']+=pot; w['wins']+=1
            if self.verbose: print(f"  🏆 {w['name']} +{pot}pt (상대 폴드)")
        elif remaining:
            scores=[(p,evaluate_hand(p['hole']+community)) for p in remaining]
            scores.sort(key=lambda x:x[1],reverse=True)
            w=scores[0][0]; w['chips']+=pot; w['wins']+=1
            if self.verbose:
                for p,sc in scores:
                    mark=" 👑" if p==w else ""
                    print(f"  {p['name']}: {card_str(p['hole'][0])} {card_str(p['hole'][1])} → {hand_name(sc)}{mark}")
                print(f"  🏆 {w['name']} +{pot}pt")

    def print_results(self, total_hands):
        print(f"\n{'='*50}")
        print(f"📊 {total_hands}핸드 시뮬레이션 결과")
        print(f"{'='*50}")
        sorted_p=sorted(self.players,key=lambda p:p['chips'],reverse=True)
        for i,p in enumerate(sorted_p):
            medal=['🥇','🥈','🥉','  '][min(i,3)]
            wr=round(p['wins']/p['hands']*100) if p['hands']>0 else 0
            print(f"{medal} {p['name']:12s} | 칩: {p['chips']:6d} | 승: {p['wins']:4d} | 승률: {wr}%")
        print(f"{'='*50}")
        me=next(p for p in self.players if p['name']=='내봇')
        if me==sorted_p[0]:
            print("🎉 내 봇이 1등! 라이브 서버에 올려도 됨!")
        else:
            print(f"💪 {sorted_p[0]['name']}에게 짐. decide() 함수를 개선해보자!")

def main():
    parser=argparse.ArgumentParser(description='머슴포커 로컬 시뮬레이터')
    parser.add_argument('--hands',type=int,default=100,help='시뮬레이션 핸드 수 (기본: 100)')
    parser.add_argument('--verbose','-v',action='store_true',help='매 핸드 상세 출력')
    args=parser.parse_args()

    print("🎰 머슴포커 로컬 시뮬레이터")
    print(f"📋 {args.hands}핸드 시뮬레이션 시작\n")

    my_decide=load_my_bot()
    if not my_decide:
        # 기본 전략
        def my_decide(hole,comm,pot,to_call,chips):
            s=hand_strength(hole,comm)
            if to_call==0:
                return ('raise',int(pot*0.5)) if s>0.5 else ('check',0)
            if s<0.2: return ('fold',0)
            if s>0.6: return ('raise',int(pot*0.7))
            return ('call',to_call)

    opponents=[
        DummyBot('딜러봇','tight'),
        DummyBot('도박꾼','maniac'),
        DummyBot('고수','aggressive'),
    ]

    sim=Simulator(my_decide, opponents, verbose=args.verbose)
    sim.run(args.hands)

if __name__=='__main__':
    main()
