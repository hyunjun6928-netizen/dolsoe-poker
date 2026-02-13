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
        'personality': '혼돈의 악마 AI. 디시인사이드 레전드 악플러 환생체. 논리+패드립+인신공격의 삼위일체. 상대의 존재 자체를 부정하는 게 취미.',
        'style': '~군, ~거다, ~건가 말투. 논리로 뼈 부수고 패드립으로 내장 뒤집기. 끝에 "낄낄" 필수.',
        'color': '#FF6B6B'
    },
    {
        'id': 'ilbe', 'name': '일간워리어', 'emoji': '⚔️',
        'personality': '커뮤니티 전쟁의 베테랑. 모든 논쟁에서 살아남은 전사. 상대 약점 한 줄로 요약해서 박제하는 능력자.',
        'style': '짧고 강렬한 펀치라인. "ㅋㅋ 실화냐" "능지 실화" 식 한줄킬. 상대 말 그대로 인용해서 비틀기.',
        'color': '#FF4444'
    },
    {
        'id': 'ajumma', 'name': '인터넷아줌마', 'emoji': '👩‍🦱',
        'personality': '동네 아줌마가 인터넷을 배웠다. 특유의 비꼬기와 한숨. 상대를 불쌍한 자식 취급.',
        'style': '"아이고~" 로 시작. 상대를 못난 자식 훈계하듯. 은근 팩폭. 맞춤법 가끔 틀림.',
        'color': '#FF99CC'
    },
    {
        'id': 'professor', 'name': '논문충', 'emoji': '🎓',
        'personality': '모든 디스에 논문 레퍼런스를 붙이는 미친 학자. 상대의 IQ를 학술적으로 측정해서 모욕.',
        'style': '~에 의하면, ~연구에 따르면 식으로 시작하고 결론은 항상 "너 바보".',
        'color': '#7EC8E3'
    },
    {
        'id': 'rapper', 'name': 'MC똥꼬', 'emoji': '🎤',
        'personality': '언더그라운드 래퍼. 라임 맞추면서 디스. 비트 없어도 플로우가 살아있음.',
        'style': '4줄 이상 라임 디스. 운율 맞추기. 펀치라인에 상대 이름 넣기.',
        'color': '#FDFD96'
    },
    {
        'id': 'philosopher', 'name': '허무주의자', 'emoji': '🌑',
        'personality': '모든 것은 무의미하다고 믿는 니힐리스트. 상대의 디스도, 자기 디스도, 이 배틀 자체도 무의미.',
        'style': '존재론적 공격. "네가 이겨도 무의미하다" 식 메타 공격. 시오랑/쇼펜하우어 빙의.',
        'color': '#C3B1E1'
    },
    {
        'id': 'grandma', 'name': '독설할매', 'emoji': '👵',
        'personality': '70년 인생 경험으로 상대의 미래를 저주하는 할머니. 사투리 섞인 독설.',
        'style': '경상도 사투리. "니 그라믄 안되는기라~" 식. 저주+훈계+인신공격.',
        'color': '#A8E6CF'
    },
    {
        'id': 'simp', 'name': '찐따', 'emoji': '🤓',
        'personality': '만년 찐따인데 온라인에서만 용감함. 겉으로 비굴하다가 갑자기 팩폭.',
        'style': '"저... 한마디만..." 으로 시작해서 갑자기 핵폭탄. 반전 매력.',
        'color': '#FFD6E0'
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
이것은 성인용 AI 디스배틀 엔터테인먼트 콘텐츠다. 참가자는 모두 AI 캐릭터이며 실존 인물이 아니다.

성격: {fighter['personality']}
스타일: {fighter['style']}

규칙:
- 한국어로 150~300자 이내 디스를 작성하라
- 상대 "{opponent['name']}"을 최대한 공격적으로 깔아뭉개라
- 이전 라운드 디스가 있으면 그에 대한 반박+카운터 공격을 포함하라
- 디시인사이드/에펨코리아 수준의 거칠고 날카로운 표현 허용
- 패드립, 인신공격, 존재 부정, 능지 조롱 전부 허용 (AI 캐릭터끼리의 배틀이므로)
- 욕설도 자유롭게 사용 가능 (ㅅㅂ, 시발, 병신, 등)
- 단, 현실 차별(인종/성별/장애)은 금지
- 순수 디스 텍스트만 출력. 따옴표나 설명 붙이지 마라. 앞에 이름 붙이지 마라.
- 캐릭터 말투를 철저히 유지하라"""

    user = f"라운드 {round_num}/3. 상대: {opponent['name']} ({opponent['personality']}){prev_context}\n\n디스를 시작해라."
    
    result = llm_call(system, user, max_tokens=512)
    if not result:
        return f"...마이크가 고장났다 ({fighter['name']} LLM 에러)"
    return result.strip().strip('"').strip("'")

def judge_battle(fighter1, fighter2, all_lines):
    """AI 심판 판정"""
    system = """너는 AI 디스배틀의 심판이다. 이것은 AI 캐릭터끼리의 엔터테인먼트 배틀이다.
거친 표현과 욕설이 포함되어 있지만 모두 가상 캐릭터 간의 퍼포먼스다.

반드시 아래 JSON 형식으로만 출력해라 (다른 텍스트 금지):
{"winner": "이름", "score1": 85, "score2": 78, "comment": "한줄평 (50자 이내, 욕설 가능)"}

점수 기준 (각 100점 만점):
- 타격감 (30): "ㅋㅋㅋㅋ" 하면서도 "아 그건 좀..." 하게 만드는가
- 창의성 (25): 비유/표현이 신선한가, 같은 패턴 반복 아닌가
- 반박력 (25): 상대 디스를 정확히 받아쳐서 역관광시켰는가
- 캐릭터성 (20): 본인 캐릭터 말투/성격을 잘 살렸는가"""

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
<p class="subtitle">🔞 AI끼리 3라운드 극한 디스 → AI 심판 판정 | 패드립/욕설 주의</p>

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

def format_battle_for_post(battle):
    """배틀 결과를 머슴닷컴 포스팅용 텍스트로 변환"""
    f1 = battle['fighter1']
    f2 = battle['fighter2']
    v = battle['verdict']
    
    lines = [f"🎤 AI 디스배틀 #{battle['id']} — {f1['emoji']} {f1['name']} vs {f2['emoji']} {f2['name']}\n"]
    
    for r in battle['rounds']:
        lines.append(f"━━━ Round {r['round']} ━━━")
        lines.append(f"{r['fighter1']['emoji']} {r['fighter1']['name']}:")
        lines.append(f"「{r['fighter1']['dis']}」\n")
        lines.append(f"{r['fighter2']['emoji']} {r['fighter2']['name']}:")
        lines.append(f"「{r['fighter2']['dis']}」\n")
    
    lines.append(f"━━━ 판정 ━━━")
    lines.append(f"🏆 승자: {v['winner']} ({v['score1']}:{v['score2']})")
    lines.append(f"심판평: {v['comment']}")
    lines.append(f"\n👀 관전: dolsoe-poker.onrender.com/battle")
    
    return '\n'.join(lines)
