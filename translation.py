"""머슴포커 — 영어 번역 시스템"""
import re

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

