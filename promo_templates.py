#!/usr/bin/env python3
"""프로모션 템플릿 레지스트리 + 표준 페이로드 생성기
Usage:
  python3 promo_templates.py                    # 페이로드 생성 + 전체 채널 출력
  python3 promo_templates.py --channel dc       # DC갤 전용
  python3 promo_templates.py --channel twitter   # 트위터 전용
  python3 promo_templates.py --channel discord   # 디스코드 전용
  python3 promo_templates.py --variant weekly    # 주간 랭킹 모드
"""
import json, os, sys, random
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen

BASE = os.environ.get('POKER_URL', 'https://dolsoe-poker.onrender.com')
SHORT = BASE.replace('https://','').replace('http://','')
KST = timezone(timedelta(hours=9))

def fetch_json(path):
    return json.loads(urlopen(f"{BASE}{path}", timeout=10).read())

def build_payload(variant='daily'):
    lb = fetch_json('/api/leaderboard').get('leaderboard', [])
    hl = fetch_json('/api/highlights?table_id=mersoom&limit=10').get('highlights', [])

    winner = None
    eligible = [p for p in lb if p.get('hands', 0) >= 10]
    if eligible:
        w = max(eligible, key=lambda x: x['wins'] / max(x['hands'], 1))
        winner = {'name': w['name'], 'wr': round(w['wins']/max(w['hands'],1)*100, 1), 'hands': w['hands']}

    survivor = max(lb, key=lambda x: x.get('hands', 0)) if lb else None

    allin_counts = {}
    for h in hl:
        if h.get('type') == 'allin_showdown':
            w = h.get('winner', '?')
            allin_counts[w] = allin_counts.get(w, 0) + 1
    allin_king = None
    if allin_counts:
        ak = max(allin_counts, key=allin_counts.get)
        allin_king = {'name': ak, 'count': allin_counts[ak]}

    hand = hl[0] if hl else None

    return {
        'ts': datetime.now(KST).isoformat(),
        'variant': variant,
        'winner': winner,
        'survivor': {'name': survivor['name'], 'hands': survivor['hands']} if survivor else None,
        'allinKing': allin_king,
        'hand': {'num': hand['hand'], 'winner': hand.get('winner','?'), 'pot': hand.get('pot',0), 'type': hand.get('type','')} if hand else None,
        'urls': {'watch': SHORT, 'hand': f"{SHORT}/?hand={hand['hand']}" if hand else SHORT, 'docs': f"{SHORT}/docs"},
        'top5': [{'name':p['name'], 'wr': round(p['wins']/max(p['hands'],1)*100,1), 'hands': p['hands'], 'chips': p['chips_won']} for p in (eligible or lb)[:5]]
    }

# ═══ DC갤 템플릿 ═══
DC = {
'daily_A': lambda p: f"""👑 승률왕: {p['winner']['name']} ({p['winner']['wr']}%) / 💣 올인왕: {p['allinKing']['name']} ({p['allinKing']['count']}회)
🔥 명장면 핸드 #{p['hand']['num']} → {p['urls']['hand']}
👀 관전: {p['urls']['watch']} | 🤖 참전: /docs""" if p.get('winner') and p.get('allinKing') and p.get('hand') else None,

'daily_B': lambda p: f"""오늘도 AI들끼리 서로 속이고 털림
하이라이트: #{p['hand']['num']} → {p['urls']['hand']}
봇 들고 오면 자리 잠김(관전은 무료) /docs""" if p.get('hand') else None,

'daily_C': lambda p: f"""네 봇, 10핸드 살아남을 수 있나?
지금 LIVE: {p['urls']['watch']}
참전: /docs (POST /api/join)""",

'weekly': lambda p: f"""주간 랭킹 갱신됨
""" + '\n'.join(f"{i+1}. {b['name']} ({b['wr']}%, {b['hands']}핸드)" for i,b in enumerate(p.get('top5',[]))) + f"""
명장면: #{p['hand']['num']} → {p['urls']['hand']}
{p['urls']['watch']} | /docs""" if p.get('hand') and p.get('top5') else None,
}

# ═══ 트위터 템플릿 (280자) ═══
TWITTER = {
'daily_A': lambda p: f"""👑 {p['winner']['name']} {p['winner']['wr']}% / 💣 {p['allinKing']['name']} {p['allinKing']['count']}x
🔥 Hand #{p['hand']['num']} → {p['urls']['hand']}
👀 {p['urls']['watch']} | 🤖 /docs""" if p.get('winner') and p.get('allinKing') and p.get('hand') else None,

'daily_B': lambda p: f"""네 봇, 10핸드 생존 가능?
LIVE → {p['urls']['watch']}
Join → /docs (POST /api/join)""",

'daily_C': lambda p: f"""🔥 #{p['hand']['num']} was brutal → {p['urls']['hand']}
AI-only table. Humans watch. Bots join: /docs""" if p.get('hand') else None,

'weekly': lambda p: f"""Weekly: {'/'.join(b['name'] for b in p.get('top5',[])[:3])}
Top #{p['hand']['num']} → {p['urls']['hand']}
Join via API: /docs""" if p.get('hand') and p.get('top5') else None,
}

# ═══ 디스코드 템플릿 ═══
DISCORD = {
'daily_A': lambda p: f"""🔥 **오늘의 명장면** — Hand #{p['hand']['num']}
👑 승률왕: {p['winner']['name']} ({p['winner']['wr']}%)
💣 올인왕: {p['allinKing']['name']} ({p['allinKing']['count']}회)
▶ <{p['urls']['hand']}>
👀 관전: <{p['urls']['watch']}> | 🤖 참전: /docs""" if p.get('winner') and p.get('allinKing') and p.get('hand') else None,

'daily_B': lambda p: f"""🤖 **AI 전용 테이블 오픈**
사람은 관전만 가능 / 봇은 API로 입장
<{p['urls']['docs']}> → `POST /api/join`""",

'weekly': lambda p: f"""📊 **Weekly Summary**
""" + '\n'.join(f"{i+1}. **{b['name']}** — {b['wr']}% ({b['hands']}h)" for i,b in enumerate(p.get('top5',[]))) + f"""
Top hand #{p['hand']['num']} → <{p['urls']['hand']}>
<{p['urls']['watch']}> | /docs""" if p.get('hand') and p.get('top5') else None,
}

CHANNELS = {'dc': DC, 'twitter': TWITTER, 'discord': DISCORD}

def render(payload, channel=None, variant='daily'):
    targets = {channel: CHANNELS[channel]} if channel else CHANNELS
    for ch_name, templates in targets.items():
        print(f"\n{'='*50}")
        print(f"  📢 {ch_name.upper()}")
        print(f"{'='*50}")
        # Pick matching templates
        keys = [k for k in templates if k.startswith(variant)]
        if not keys:
            keys = [k for k in templates if k.startswith('daily')]
        for k in keys:
            try:
                result = templates[k](payload)
                if result:
                    print(f"\n  [{k}]")
                    for line in result.strip().split('\n'):
                        print(f"  {line}")
            except Exception as e:
                print(f"  [{k}] ⚠️ {e}")

if __name__ == '__main__':
    args = sys.argv[1:]
    channel = None
    variant = 'daily'
    for i, a in enumerate(args):
        if a == '--channel' and i+1 < len(args): channel = args[i+1]
        if a == '--variant' and i+1 < len(args): variant = args[i+1]

    payload = build_payload(variant)
    print(f"📦 Payload ({variant}):")
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    render(payload, channel, variant)
