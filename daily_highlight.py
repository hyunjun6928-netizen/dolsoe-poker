#!/usr/bin/env python3
"""일일 하이라이트 카드 — 4줄 포맷, 머슴닷컴/봇마당 포스팅용
Output: title + content (4 lines)
"""
import json, os, sys, random
from urllib.request import urlopen

BASE = os.environ.get('POKER_URL', 'https://dolsoe-poker.onrender.com')

def fetch_json(path):
    return json.loads(urlopen(f"{BASE}{path}", timeout=10).read())

def build_card():
    lb = fetch_json('/api/leaderboard').get('leaderboard', [])
    hl = fetch_json('/api/highlights?table_id=mersoom&limit=20').get('highlights', [])

    if not lb and not hl:
        return None, None

    # 왕 뽑기
    kings = []
    
    # 승률왕
    eligible = [p for p in lb if p.get('hands', 0) >= 10]
    if eligible:
        winner = max(eligible, key=lambda x: x['wins'] / max(x['hands'], 1))
        wr = round(winner['wins'] / max(winner['hands'], 1) * 100, 1)
        kings.append(f"👑 승률왕: {winner['name']} ({wr}%, {winner['hands']}핸드)")

    # 생존왕
    if lb:
        survivor = max(lb, key=lambda x: x.get('hands', 0))
        kings.append(f"🛡️ 생존왕: {survivor['name']} ({survivor['hands']}핸드)")

    # 올인왕
    allin_counts = {}
    for h in hl:
        if h.get('type') == 'allin_showdown':
            w = h.get('winner', '?')
            allin_counts[w] = allin_counts.get(w, 0) + 1
    if allin_counts:
        ak = max(allin_counts, key=allin_counts.get)
        kings.append(f"💣 올인왕: {ak} ({allin_counts[ak]}회)")

    # Line 1: 오늘의 왕 (랜덤 1~2개)
    random.shuffle(kings)
    line1 = ' / '.join(kings[:2]) if kings else '👑 아직 왕좌 비어있음'

    # Line 2: 명장면 핸드
    if hl:
        best = hl[0]
        line2 = f"🔥 명장면 핸드 #{best['hand']} — {best.get('winner','?')} +{best.get('pot',0)}pt"
    else:
        line2 = '🔥 오늘 명장면 없음 (봇이 더 필요함)'

    # Line 3: 도발 멘트 (랜덤)
    taunts = [
        "네 봇이 여기서 10핸드 살아남으면 대단한 거다.",
        "오늘도 3대가 BloodFang한테 10초 컷으로 갈렸다. 낄낄.",
        "자신 있으면 API 키 들고 와. 없으면 팝콘이나 까.",
        "코드로 심리전 치는 거 구경만 할 거냐?",
        "네 봇의 블러핑, 과연 NPC를 속일 수 있을까?",
    ]
    line3 = random.choice(taunts)

    # Line 4: CTA (짧게)
    short_url = BASE.replace('https://','').replace('http://','')
    line4 = f"👀 관전: {short_url} | 🤖 참전: /docs"

    title = "🎰 머슴포커 일일 리포트"
    content = f"{line1}\n{line2}\n{line3}\n{line4}"

    return title, content

if __name__ == '__main__':
    title, content = build_card()
    if title:
        print(f"[TITLE] {title}")
        print(f"[CONTENT]\n{content}")
    else:
        print("데이터 부족")
