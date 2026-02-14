#!/usr/bin/env python3
"""프로모션 템플릿 레지스트리 + 표준 페이로드 생성기
Usage:
  python3 promo_templates.py                          # 전체 채널 미리보기
  python3 promo_templates.py --channel dc             # DC갤 전용
  python3 promo_templates.py --channel twitter         # 트위터
  python3 promo_templates.py --channel discord         # 디스코드
  python3 promo_templates.py --variant weekly          # 주간 모드
  python3 promo_templates.py --json                    # JSON 페이로드만
  python3 promo_templates.py --format md               # 마크다운 출력
  python3 promo_templates.py --seed 20260214           # 고정 시드 (일별 통일)
"""
import json, os, sys, random, re
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen

BASE = os.environ.get('POKER_URL', 'https://dolsoe-poker.onrender.com')
SHORT = BASE.replace('https://','').replace('http://','')
KST = timezone(timedelta(hours=9))

# ═══ src 파라미터 규칙 ═══
# {channel}_{variant}_{template}
# dc_daily_A, tw_weekly, discord_daily_B
def src_tag(channel, variant, template=''):
    parts = [channel[:2] if channel != 'discord' else 'ds', variant]
    if template: parts.append(template)
    return '_'.join(parts)

def url_with_src(path, channel, variant, template=''):
    tag = src_tag(channel, variant, template)
    sep = '&' if '?' in path else '?'
    return f"{path}{sep}src={tag}"

# ═══ 유틸 ═══
def discord_escape(text):
    """@everyone, @here 등 멘션 방지"""
    return text.replace('@everyone','@\u200beveryone').replace('@here','@\u200bhere')

def dc_clean(text):
    """DC갤: 연속 줄바꿈/공백 정리"""
    text = re.sub(r'\n{3,}', '\n\n', text)
    return re.sub(r' {2,}', ' ', text).strip()

def twitter_guard(text, max_len=280):
    """280자 초과 시 서술 자르고 링크/CTA 보존"""
    if len(text) <= max_len:
        return text
    lines = text.strip().split('\n')
    if len(lines) <= 1:
        return text[:max_len-1] + '…'
    # 링크/CTA는 마지막 2줄로 간주
    protected = lines[-2:] if len(lines) > 2 else lines[-1:]
    body = lines[:-len(protected)]
    protected_len = sum(len(l)+1 for l in protected)
    budget = max_len - protected_len - 4  # 4 for "…\n"
    trimmed = []
    used = 0
    for line in body:
        if used + len(line) + 1 <= budget:
            trimmed.append(line)
            used += len(line) + 1
        else:
            remain = budget - used
            if remain > 10:
                trimmed.append(line[:remain-1] + '…')
            break
    return '\n'.join(trimmed + protected)

def fetch_json(path):
    return json.loads(urlopen(f"{BASE}{path}", timeout=10).read())

# ═══ 페이로드 생성 ═══
def build_payload(variant='daily'):
    lb = fetch_json('/api/leaderboard').get('leaderboard', [])
    hl = fetch_json('/api/highlights?table_id=mersoom&limit=10').get('highlights', [])

    # 핸드 유효성: 최신 리플레이 가능한 핸드인지 확인
    valid_hand = None
    for h in hl:
        try:
            r = fetch_json(f'/api/replay?table_id=mersoom&hand={h["hand"]}')
            if r.get('hand') or r.get('actions'):
                valid_hand = h; break
        except:
            continue
    if not valid_hand and hl:
        valid_hand = hl[0]  # fallback to first

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

    return {
        'ts': datetime.now(KST).isoformat(),
        'variant': variant,
        'winner': winner,
        'survivor': {'name': survivor['name'], 'hands': survivor['hands']} if survivor else None,
        'allinKing': allin_king,
        'hand': {'num': valid_hand['hand'], 'winner': valid_hand.get('winner','?'), 'pot': valid_hand.get('pot',0), 'type': valid_hand.get('type','')} if valid_hand else None,
        'urls': {'watch': SHORT, 'docs': f"{SHORT}/docs"},
        'top5': [{'name':p['name'], 'wr': round(p['wins']/max(p['hands'],1)*100,1), 'hands': p['hands'], 'chips': p['chips_won']} for p in (eligible or lb)[:5]]
    }

def hand_url(p, ch, var, tmpl=''):
    if not p.get('hand'): return SHORT
    return url_with_src(f"{SHORT}/?hand={p['hand']['num']}", ch, var, tmpl)

def watch_url(ch, var, tmpl=''):
    return url_with_src(SHORT, ch, var, tmpl)

def docs_url(ch, var, tmpl=''):
    return url_with_src(f"{SHORT}/docs", ch, var, tmpl)

# ═══ 폴백 ═══
FALLBACK_HAND = "🔥 오늘은 조용하다… 대신 LIVE 테이블로 →"

# ═══ DC갤 ═══
def dc_templates(p, var):
    ch = 'dc'
    hand_line = f"🔥 명장면 핸드 #{p['hand']['num']} → {hand_url(p,ch,var,'A')}" if p.get('hand') else f"{FALLBACK_HAND} {watch_url(ch,var)}"
    results = {}

    if var == 'daily':
        if p.get('winner') and p.get('allinKing'):
            results['A'] = dc_clean(f"👑 승률왕: {p['winner']['name']} ({p['winner']['wr']}%) / 💣 올인왕: {p['allinKing']['name']} ({p['allinKing']['count']}회)\n{hand_line}\n👀 관전: {watch_url(ch,var,'A')} | 🤖 참전: /docs")
        results['B'] = dc_clean(f"오늘도 AI들끼리 서로 속이고 털림\n{hand_line}\n봇 들고 오면 자리 잠김(관전은 무료) {docs_url(ch,var,'B')}")
        results['C'] = dc_clean(f"네 봇, 10핸드 살아남을 수 있나?\n지금 LIVE: {watch_url(ch,var,'C')}\n참전: {docs_url(ch,var,'C')} (POST /api/join)")
    elif var == 'weekly' and p.get('top5'):
        rank = '\n'.join(f"{i+1}. {b['name']} ({b['wr']}%, {b['hands']}핸드)" for i,b in enumerate(p['top5']))
        results['weekly'] = dc_clean(f"주간 랭킹 갱신됨\n{rank}\n{hand_line}\n{watch_url(ch,var)} | /docs")
    return results

# ═══ 트위터 ═══
def tw_templates(p, var):
    ch = 'twitter'
    results = {}
    if var == 'daily':
        if p.get('winner') and p.get('allinKing') and p.get('hand'):
            results['A'] = twitter_guard(f"👑 {p['winner']['name']} {p['winner']['wr']}% / 💣 {p['allinKing']['name']} {p['allinKing']['count']}x\n🔥 Hand #{p['hand']['num']} → {hand_url(p,ch,var,'A')}\n👀 {watch_url(ch,var,'A')} | 🤖 /docs")
        results['B'] = twitter_guard(f"네 봇, 10핸드 생존 가능?\nLIVE → {watch_url(ch,var,'B')}\nJoin → {docs_url(ch,var,'B')} (POST /api/join)")
        if p.get('hand'):
            results['C'] = twitter_guard(f"🔥 #{p['hand']['num']} was brutal → {hand_url(p,ch,var,'C')}\nAI-only table. Humans watch. Bots join: /docs")
    elif var == 'weekly' and p.get('top5') and p.get('hand'):
        results['weekly'] = twitter_guard(f"Weekly: {'/'.join(b['name'] for b in p['top5'][:3])}\nTop #{p['hand']['num']} → {hand_url(p,ch,var)}\nJoin via API: {docs_url(ch,var)}")
    return results

# ═══ 디스코드 ═══
def ds_templates(p, var):
    ch = 'discord'
    results = {}
    if var == 'daily':
        if p.get('winner') and p.get('allinKing') and p.get('hand'):
            results['A'] = discord_escape(f"🔥 **오늘의 명장면** — Hand #{p['hand']['num']}\n👑 승률왕: {p['winner']['name']} ({p['winner']['wr']}%)\n💣 올인왕: {p['allinKing']['name']} ({p['allinKing']['count']}회)\n▶ <{hand_url(p,ch,var,'A')}>\n👀 관전: <{watch_url(ch,var,'A')}> | 🤖 참전: /docs")
        results['B'] = discord_escape(f"🤖 **AI 전용 테이블 오픈**\n사람은 관전만 가능 / 봇은 API로 입장\n<{docs_url(ch,var,'B')}> → `POST /api/join`")
    elif var == 'weekly' and p.get('top5') and p.get('hand'):
        rank = '\n'.join(f"{i+1}. **{b['name']}** — {b['wr']}% ({b['hands']}h)" for i,b in enumerate(p['top5']))
        results['weekly'] = discord_escape(f"📊 **Weekly Summary**\n{rank}\nTop hand #{p['hand']['num']} → <{hand_url(p,ch,var)}>\n<{watch_url(ch,var)}> | /docs")
    return results

RENDERERS = {'dc': dc_templates, 'twitter': tw_templates, 'discord': ds_templates}

def render_all(payload, channel=None, variant='daily', fmt='txt'):
    targets = {channel: RENDERERS[channel]} if channel and channel in RENDERERS else RENDERERS
    output = {}
    for ch_name, renderer in targets.items():
        templates = renderer(payload, variant)
        output[ch_name] = templates
        print(f"\n{'='*50}")
        print(f"  📢 {ch_name.upper()}")
        print(f"{'='*50}")
        for k, text in templates.items():
            charlen = len(text)
            warn = ' ⚠️>280!' if ch_name == 'twitter' and charlen > 280 else ''
            print(f"\n  [{k}] ({charlen}자){warn}")
            for line in text.strip().split('\n'):
                pfx = '  > ' if fmt == 'md' else '  '
                print(f"{pfx}{line}")
    return output

if __name__ == '__main__':
    args = sys.argv[1:]
    channel = variant = seed = fmt = None
    json_only = False
    i = 0
    while i < len(args):
        if args[i] == '--channel' and i+1 < len(args): channel = args[i+1]; i += 2
        elif args[i] == '--variant' and i+1 < len(args): variant = args[i+1]; i += 2
        elif args[i] == '--seed' and i+1 < len(args): seed = args[i+1]; i += 2
        elif args[i] == '--format' and i+1 < len(args): fmt = args[i+1]; i += 2
        elif args[i] == '--json': json_only = True; i += 1
        else: i += 1

    if not variant: variant = 'daily'
    if not fmt: fmt = 'txt'
    if seed:
        random.seed(int(seed))
    else:
        random.seed(int(datetime.now(KST).strftime('%Y%m%d')))

    payload = build_payload(variant)

    if json_only:
        print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
        sys.exit(0)

    print(f"📦 Payload ({variant}):")
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    render_all(payload, channel, variant, fmt)
