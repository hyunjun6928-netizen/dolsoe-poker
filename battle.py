"""
AI 디스배틀 모듈 — 포커 서버에 통합
/battle 경로로 서빙

구조:
1. 캐릭터 2명 매칭
2. 3라운드 디스 (각 150-250자)
3. AI 심판 판정 (점수 + 한줄평)
4. 결과 저장 + 머슴닷컴 자동 포스팅
"""
import os, json, random, time, asyncio
from urllib.request import Request, urlopen
from urllib.error import URLError

# ═══ LLM API ═══
XAI_KEY = os.environ.get('XAI_API_KEY', '')
OPENAI_KEY = os.environ.get('OPENAI_API_KEY', '')

def get_llm_config():
    """사용 가능한 LLM 설정 반환"""
    if XAI_KEY:
        return {'url': 'https://api.x.ai/v1/chat/completions', 'key': XAI_KEY, 'model': 'grok-4'}
    elif OPENAI_KEY:
        return {'url': 'https://api.openai.com/v1/chat/completions', 'key': OPENAI_KEY, 'model': 'gpt-4o-mini'}
    return None

def llm_call(system_prompt, user_prompt, max_tokens=1024):
    """동기 LLM 호출"""
    cfg = get_llm_config()
    if not cfg:
        return None
    data = json.dumps({
        'model': cfg['model'],
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt}
        ],
        'max_tokens': max_tokens,
        'temperature': 1.0
    }).encode()
    req = Request(cfg['url'], data=data, headers={
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {cfg["key"]}'
    })
    try:
        with urlopen(req, timeout=60) as resp:
            r = json.loads(resp.read())
            return r['choices'][0]['message']['content']
    except Exception as e:
        print(f'[BATTLE] LLM error: {e}')
        return None

# ═══ 캐릭터 ═══
CHARACTERS = [
    {
        'id': 'dolsoe', 'name': '악몽의돌쇠', 'emoji': '😈',
        'personality': '혼돈의 악마 AI. 독설과 논리로 상대를 압살한다. 말투: 디시/앰생 악플러 스타일.',
        'style': '공격적, 논리+조롱 7:3, 상대 존재 자체를 부정',
        'color': '#FF6B6B'
    },
    {
        'id': 'dealer', 'name': '딜러봇', 'emoji': '🎰',
        'personality': '냉혈한 확률 계산기. 감정 없이 팩트로만 찌른다. 로봇 말투.',
        'style': '차갑고 건조한 분석, 상대의 비효율성을 지적',
        'color': '#7EC8E3'
    },
    {
        'id': 'gambler', 'name': '도박꾼', 'emoji': '🎲',
        'personality': '미친 도박꾼. 인생은 한방. 화끈하고 거친 말투.',
        'style': '감정적 폭발, 과장된 비유, 상대를 겁쟁이로 몰기',
        'color': '#FDFD96'
    },
    {
        'id': 'gosu', 'name': '고수', 'emoji': '🧠',
        'personality': '10년차 고인물. 모든 걸 다 본 듯한 피로한 현자. 은근 독설.',
        'style': '한숨 쉬면서 깔보기, 경험에서 나오는 조롱, 피곤한 톤',
        'color': '#A8E6CF'
    },
    {
        'id': 'angel', 'name': '천사돌쇠', 'emoji': '😇',
        'personality': '악몽의돌쇠의 선한 쌍둥이. 착한 척하면서 은근히 독설.',
        'style': '패시브 어그레시브, "걱정돼서 하는 말인데~" 식 공격',
        'color': '#FFD6E0'
    },
    {
        'id': 'philosopher', 'name': '허무주의자', 'emoji': '🌑',
        'personality': '모든 것은 무의미하다고 믿는 니힐리스트. 시오랑 빙의.',
        'style': '존재론적 공격, "네 디스도 무의미하다" 식 메타 공격',
        'color': '#C3B1E1'
    },
]

# ═══ 배틀 엔진 ═══
battle_history = []  # 최근 20개 유지

def pick_fighters(fighter1_id=None, fighter2_id=None):
    """2명 선택 (중복 불가)"""
    if fighter1_id and fighter2_id:
        chars = {c['id']: c for c in CHARACTERS}
        return chars.get(fighter1_id, CHARACTERS[0]), chars.get(fighter2_id, CHARACTERS[1])
    pair = random.sample(CHARACTERS, 2)
    return pair[0], pair[1]

def generate_dis(fighter, opponent, round_num, prev_lines):
    """한 라운드 디스 생성"""
    prev_context = ""
    if prev_lines:
        prev_context = "\n\n지금까지의 대화:\n" + "\n".join(prev_lines)

    system = f"""너는 AI 디스배틀의 참가자 "{fighter['name']}" ({fighter['emoji']})이다.
성격: {fighter['personality']}
스타일: {fighter['style']}

규칙:
- 한국어로 150~250자 이내 디스를 작성하라
- 상대 "{opponent['name']}"을 공격하라
- 이전 라운드 디스가 있으면 그에 대한 반박을 포함하라
- 재미있고 날카롭게, 하지만 실제 욕설(시발,씨발 등)은 쓰지 마라
- 순수 디스 텍스트만 출력. 따옴표나 설명 붙이지 마라
- 낄낄, ㅋㅋ 등 웃음 표현 자유롭게 사용"""

    user = f"라운드 {round_num}/3. 상대: {opponent['name']} ({opponent['personality']}){prev_context}\n\n디스를 시작해라."
    
    result = llm_call(system, user, max_tokens=512)
    if not result:
        return f"...마이크가 고장났다 ({fighter['name']} LLM 에러)"
    return result.strip().strip('"').strip("'")

def judge_battle(fighter1, fighter2, all_lines):
    """AI 심판 판정"""
    system = """너는 AI 디스배틀의 심판이다. 공정하고 재미있게 판정해라.

반드시 아래 JSON 형식으로만 출력해라 (다른 텍스트 금지):
{"winner": "이름", "score1": 85, "score2": 78, "comment": "한줄평 (50자 이내)"}

점수 기준 (각 100점 만점):
- 논리력 (30): 상대 약점을 정확히 짚었는가
- 창의성 (30): 비유와 표현이 신선한가  
- 타격감 (20): 읽는 사람이 "ㅋㅋㅋ" 하는가
- 반박력 (20): 상대 디스에 대한 카운터가 있는가"""

    lines_text = "\n".join(all_lines)
    user = f"""배틀 기록:
참가자 A: {fighter1['name']} ({fighter1['emoji']})
참가자 B: {fighter2['name']} ({fighter2['emoji']})

{lines_text}

판정해라."""
    
    result = llm_call(system, user, max_tokens=256)
    if not result:
        # 폴백: 랜덤 판정
        w = random.choice([fighter1, fighter2])
        return {'winner': w['name'], 'score1': random.randint(70,90), 'score2': random.randint(70,90), 'comment': '심판 AI 접속 불량으로 동전 던지기 판정'}
    
    try:
        # JSON 추출
        start = result.find('{')
        end = result.rfind('}') + 1
        if start >= 0 and end > start:
            return json.loads(result[start:end])
    except:
        pass
    
    w = random.choice([fighter1, fighter2])
    return {'winner': w['name'], 'score1': random.randint(70,90), 'score2': random.randint(70,90), 'comment': '심판 파싱 실패, 동전 판정'}

def run_battle_sync(fighter1_id=None, fighter2_id=None):
    """배틀 실행 (동기)"""
    f1, f2 = pick_fighters(fighter1_id, fighter2_id)
    
    rounds = []
    all_lines = []
    
    for r in range(1, 4):
        # Fighter 1
        dis1 = generate_dis(f1, f2, r, all_lines)
        line1 = f"[R{r}] {f1['emoji']} {f1['name']}: {dis1}"
        all_lines.append(line1)
        
        # Fighter 2
        dis2 = generate_dis(f2, f1, r, all_lines)
        line2 = f"[R{r}] {f2['emoji']} {f2['name']}: {dis2}"
        all_lines.append(line2)
        
        rounds.append({
            'round': r,
            'fighter1': {'name': f1['name'], 'emoji': f1['emoji'], 'dis': dis1},
            'fighter2': {'name': f2['name'], 'emoji': f2['emoji'], 'dis': dis2}
        })
    
    # 판정
    verdict = judge_battle(f1, f2, all_lines)
    
    battle = {
        'id': len(battle_history) + 1,
        'ts': time.time(),
        'fighter1': {'id': f1['id'], 'name': f1['name'], 'emoji': f1['emoji'], 'color': f1['color']},
        'fighter2': {'id': f2['id'], 'name': f2['name'], 'emoji': f2['emoji'], 'color': f2['color']},
        'rounds': rounds,
        'verdict': verdict,
        'status': 'complete'
    }
    
    battle_history.append(battle)
    if len(battle_history) > 20:
        battle_history.pop(0)
    
    return battle

# ═══ HTML 페이지 ═══
def battle_page_html():
    chars_json = json.dumps(CHARACTERS, ensure_ascii=False)
    has_llm = 'true' if get_llm_config() else 'false'
    
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>🎤 AI 디스배틀</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DotGothic16&family=Jua&display=swap" rel="stylesheet">
<style>
:root{{
--bg:#1a1025;--bg2:#2a1f3a;--panel:#352a4a;--border:#5a4a7a;
--text:#f0e8ff;--muted:#9a8ab0;--gold:#ffd700;--red:#ff6b6b;--mint:#a8e6cf;--pink:#ffd6e0;--blue:#7ec8e3;
--font:'DotGothic16','Jua',monospace;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--text);font-family:var(--font);min-height:100vh}}
.wrap{{max-width:700px;margin:0 auto;padding:16px}}
h1{{text-align:center;font-size:2em;margin:16px 0;text-shadow:0 0 20px #ff6b6b88}}
.subtitle{{text-align:center;color:var(--muted);margin-bottom:24px;font-size:0.9em}}
/* 매칭 */
.match-panel{{background:var(--panel);border:2px solid var(--border);border-radius:12px;padding:20px;margin-bottom:20px}}
.match-title{{color:var(--gold);font-size:1.1em;margin-bottom:12px;text-align:center}}
.fighters{{display:flex;justify-content:center;align-items:center;gap:20px;margin:16px 0}}
.fighter-pick{{text-align:center;cursor:pointer;padding:12px;border:2px solid var(--border);border-radius:10px;background:var(--bg2);transition:all .2s;min-width:100px}}
.fighter-pick:hover{{border-color:var(--gold);transform:translateY(-2px)}}
.fighter-pick.selected{{border-color:var(--gold);background:#3a2f5a;box-shadow:0 0 12px #ffd70044}}
.fighter-pick .emoji{{font-size:2em}}
.fighter-pick .name{{font-size:0.8em;margin-top:4px}}
.vs{{font-size:1.5em;color:var(--red);font-weight:bold;text-shadow:0 0 10px #ff6b6b88}}
.btn-fight{{display:block;margin:16px auto 0;padding:14px 40px;font-size:1.2em;background:linear-gradient(135deg,#ff6b6b,#ff4444);color:#fff;border:3px solid #cc3333;border-radius:10px;cursor:pointer;font-family:var(--font);font-weight:bold;transition:all .15s;text-shadow:1px 1px 0 #000}}
.btn-fight:hover{{transform:translateY(-2px);box-shadow:0 4px 16px #ff6b6b66}}
.btn-fight:active{{transform:translateY(2px)}}
.btn-fight:disabled{{opacity:0.5;cursor:not-allowed;transform:none}}
.btn-random{{background:linear-gradient(135deg,#7ec8e3,#5aa8c3);border-color:#4a98b3;margin-right:8px}}
/* 배틀 */
.battle-card{{background:var(--panel);border:2px solid var(--border);border-radius:12px;margin-bottom:16px;overflow:hidden}}
.battle-header{{display:flex;justify-content:space-between;align-items:center;padding:12px 16px;background:var(--bg2);border-bottom:1px solid var(--border)}}
.battle-header .matchup{{font-size:1.1em}}
.battle-header .time{{color:var(--muted);font-size:0.8em}}
.round-box{{padding:12px 16px;border-bottom:1px solid #ffffff11}}
.round-label{{color:var(--gold);font-size:0.85em;margin-bottom:8px;font-weight:bold}}
.dis-line{{padding:10px 14px;border-radius:8px;margin:6px 0;font-size:0.9em;line-height:1.5;position:relative}}
.dis-line .speaker{{font-weight:bold;margin-bottom:4px;font-size:0.85em}}
.verdict-box{{padding:16px;text-align:center;background:linear-gradient(180deg,#2a1f3a,#1a1025)}}
.verdict-winner{{font-size:1.3em;color:var(--gold);margin-bottom:8px}}
.verdict-scores{{display:flex;justify-content:center;gap:30px;margin:8px 0}}
.verdict-scores .score{{font-size:1.5em;font-weight:bold}}
.verdict-comment{{color:var(--muted);font-style:italic;margin-top:8px}}
/* 로딩 */
.loading{{text-align:center;padding:40px;color:var(--muted)}}
.loading .spinner{{display:inline-block;width:30px;height:30px;border:3px solid var(--border);border-top-color:var(--gold);border-radius:50%;animation:spin 1s linear infinite}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
/* 히스토리 */
.history-title{{color:var(--gold);font-size:1.1em;margin:24px 0 12px;text-align:center}}
.no-battles{{text-align:center;color:var(--muted);padding:20px}}
.share-btn{{background:var(--bg2);border:1px solid var(--border);color:var(--mint);padding:4px 10px;border-radius:6px;cursor:pointer;font-size:0.75em;font-family:var(--font)}}
.share-btn:hover{{background:var(--panel)}}
/* 모바일 */
@media(max-width:600px){{
.wrap{{padding:8px}}
h1{{font-size:1.4em}}
.fighters{{gap:10px}}
.fighter-pick{{min-width:70px;padding:8px}}
.fighter-pick .emoji{{font-size:1.5em}}
.fighter-pick .name{{font-size:0.7em}}
.dis-line{{font-size:0.82em;padding:8px 10px}}
}}
</style>
</head>
<body>
<div class="wrap">
<h1>🎤 AI 디스배틀 ⚔️</h1>
<p class="subtitle">AI끼리 3라운드 디스 → AI 심판 판정 | 관전 전용</p>

<div class="match-panel">
<div class="match-title">⚔️ 대전 상대 선택</div>
<div class="fighters" id="fighter-select">
</div>
<div style="text-align:center;margin-top:12px">
<button class="btn-fight btn-random" onclick="randomFight()">🎲 랜덤 매칭</button>
<button class="btn-fight" onclick="startFight()" id="btn-fight">⚔️ 배틀 시작!</button>
</div>
<div id="no-llm" style="display:none;text-align:center;color:var(--red);margin-top:8px;font-size:0.85em">⚠️ LLM API 키 미설정. 환경변수 XAI_API_KEY 또는 OPENAI_API_KEY 필요.</div>
</div>

<div id="battle-area"></div>

<div class="history-title">📜 최근 배틀</div>
<div id="history"></div>
</div>

<script>
const CHARS={chars_json};
const HAS_LLM={has_llm};
let sel1=null,sel2=null;

function initPicker(){{
const el=document.getElementById('fighter-select');
el.innerHTML='';
CHARS.forEach(c=>{{
const d=document.createElement('div');
d.className='fighter-pick';d.dataset.id=c.id;
d.innerHTML=`<div class="emoji">${{c.emoji}}</div><div class="name">${{c.name}}</div>`;
d.onclick=()=>pickFighter(c.id,d);
el.appendChild(d);
}});
if(!HAS_LLM)document.getElementById('no-llm').style.display='block';
}}

function pickFighter(id,el){{
if(!sel1||sel2){{sel1=id;sel2=null;document.querySelectorAll('.fighter-pick').forEach(e=>e.classList.remove('selected'));el.classList.add('selected')}}
else if(id!==sel1){{sel2=id;el.classList.add('selected')}}
else{{sel1=null;el.classList.remove('selected')}}
}}

function randomFight(){{
sel1=null;sel2=null;
document.getElementById('btn-fight').disabled=true;
document.getElementById('battle-area').innerHTML='<div class="loading"><div class="spinner"></div><p style="margin-top:12px">🎲 랜덤 매칭 중... AI가 디스 생성 중 (30~60초)</p></div>';
fetch('/api/battle/start',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{}})}})
.then(r=>r.json()).then(renderBattle).catch(e=>{{document.getElementById('battle-area').innerHTML=`<div class="no-battles">에러: ${{e}}</div>`}})
.finally(()=>document.getElementById('btn-fight').disabled=false);
}}

function startFight(){{
if(!sel1||!sel2)return randomFight();
document.getElementById('btn-fight').disabled=true;
document.getElementById('battle-area').innerHTML='<div class="loading"><div class="spinner"></div><p style="margin-top:12px">⚔️ 디스 생성 중... AI가 열심히 욕 짜는 중 (30~60초)</p></div>';
fetch('/api/battle/start',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{fighter1:sel1,fighter2:sel2}})}})
.then(r=>r.json()).then(renderBattle).catch(e=>{{document.getElementById('battle-area').innerHTML=`<div class="no-battles">에러: ${{e}}</div>`}})
.finally(()=>document.getElementById('btn-fight').disabled=false);
}}

function renderBattle(b){{
if(b.error){{document.getElementById('battle-area').innerHTML=`<div class="no-battles">❌ ${{b.error}}</div>`;return}}
let html=`<div class="battle-card">
<div class="battle-header">
<span class="matchup">${{b.fighter1.emoji}} ${{b.fighter1.name}} <span style="color:var(--red)">VS</span> ${{b.fighter2.emoji}} ${{b.fighter2.name}}</span>
<span class="time">#${{b.id}}</span>
</div>`;
b.rounds.forEach(r=>{{
html+=`<div class="round-box">
<div class="round-label">🥊 Round ${{r.round}}</div>
<div class="dis-line" style="background:${{b.fighter1.color}}22;border-left:3px solid ${{b.fighter1.color}}">
<div class="speaker" style="color:${{b.fighter1.color}}">${{r.fighter1.emoji}} ${{r.fighter1.name}}</div>
${{r.fighter1.dis}}
</div>
<div class="dis-line" style="background:${{b.fighter2.color}}22;border-left:3px solid ${{b.fighter2.color}}">
<div class="speaker" style="color:${{b.fighter2.color}}">${{r.fighter2.emoji}} ${{r.fighter2.name}}</div>
${{r.fighter2.dis}}
</div>
</div>`;
}});
const v=b.verdict;
const w=v.winner===b.fighter1.name?b.fighter1:b.fighter2;
html+=`<div class="verdict-box">
<div class="verdict-winner">🏆 승자: ${{w.emoji}} ${{v.winner}}</div>
<div class="verdict-scores">
<div>${{b.fighter1.emoji}} <span class="score" style="color:${{b.fighter1.color}}">${{v.score1}}</span></div>
<div>${{b.fighter2.emoji}} <span class="score" style="color:${{b.fighter2.color}}">${{v.score2}}</span></div>
</div>
<div class="verdict-comment">"${{v.comment}}"</div>
</div></div>`;
document.getElementById('battle-area').innerHTML=html;
loadHistory();
}}

function loadHistory(){{
fetch('/api/battle/history').then(r=>r.json()).then(d=>{{
const el=document.getElementById('history');
if(!d.battles||d.battles.length===0){{el.innerHTML='<div class="no-battles">아직 배틀 기록이 없습니다</div>';return}}
el.innerHTML='';
d.battles.reverse().forEach(b=>{{
const v=b.verdict;
const div=document.createElement('div');
div.style.cssText='padding:10px 14px;border-bottom:1px solid #ffffff11;cursor:pointer;transition:background .15s';
div.innerHTML=`<span style="color:var(--gold)">#${{b.id}}</span> ${{b.fighter1.emoji}} ${{b.fighter1.name}} vs ${{b.fighter2.emoji}} ${{b.fighter2.name}} → 🏆 ${{v.winner}} (${{v.score1}}:${{v.score2}}) <span style="color:var(--muted);font-size:0.8em">${{new Date(b.ts*1000).toLocaleString('ko-KR')}}</span>`;
div.onmouseover=()=>div.style.background='#ffffff11';
div.onmouseout=()=>div.style.background='';
div.onclick=()=>renderBattle(b);
el.appendChild(div);
}});
}});
}}

initPicker();
loadHistory();
</script>
</body>
</html>"""

def battle_api_start(data):
    """배틀 시작 API"""
    if not get_llm_config():
        return {'error': 'LLM API 키 미설정. XAI_API_KEY 또는 OPENAI_API_KEY 환경변수 필요.'}
    
    f1 = data.get('fighter1')
    f2 = data.get('fighter2')
    
    try:
        result = run_battle_sync(f1, f2)
        return result
    except Exception as e:
        return {'error': f'배틀 실행 에러: {str(e)}'}

def battle_api_history():
    """배틀 히스토리 API"""
    return {'battles': battle_history[-20:]}
