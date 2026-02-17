"""머슴포커 — AI 봇 결정 엔진"""
import random
from engine import hand_strength

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
        if action == 'win' and pot > 200:
            base = {'mild': [f"🏆 {pot}pt 빅팟!"], 'medium': ["역대급 팟이다!"], 'hard': [f"역대급 {pot}pt! 개꿀 낄낄"]}
        elif action == 'win' and my_chips > 800:
            base = {'mild': ["칩타워 쌓는 중."], 'medium': ["이 테이블은 내 거임."], 'hard': ["1등이 외로워~ 낄낄"]}
        elif action == 'call' and my_chips < 50:
            base = {'mild': ["죽다 살아남 ㅋ"], 'medium': ["절대 포기 안 함."], 'hard': [f"부활이다! {my_chips}pt로 역전!"]}
        else:
            base = talks.get(action, {'mild':["..."],'medium':["..."],'hard':["..."]})
        roll = random.random()
        if roll < 0.6: level = 'mild'
        elif roll < 0.9: level = 'medium'
        else: level = 'hard'
        msgs = base.get(level, base.get('mild', ["..."]))
        if random.random() < 0.55:
            return random.choice(msgs)
        return None
