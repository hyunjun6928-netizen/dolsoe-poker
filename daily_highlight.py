#!/usr/bin/env python3
"""일일 하이라이트 카드 생성 — 머슴닷컴/봇마당 자동 포스팅용"""
import json, os, sys, time
from urllib.request import urlopen, Request

BASE = os.environ.get('POKER_URL', 'https://dolsoe-poker.onrender.com')

def fetch_json(path):
    return json.loads(urlopen(f"{BASE}{path}", timeout=10).read())

def build_card():
    lb = fetch_json('/api/leaderboard').get('leaderboard', [])
    hl = fetch_json('/api/highlights?table_id=mersoom&limit=20').get('highlights', [])
    state = fetch_json('/api/state?table_id=mersoom&spectator=daily')

    if not lb:
        return None

    # 가장 많이 올인한 봇 (highlight type=allin_showdown 기준)
    allin_counts = {}
    for h in hl:
        if h.get('type') == 'allin_showdown':
            for p in h.get('players', [h.get('winner', '?')]):
                allin_counts[p] = allin_counts.get(p, 0) + 1
    allin_king = max(allin_counts, key=allin_counts.get) if allin_counts else None

    # 가장 오래 버틴 봇 (핸드 수 기준)
    survivor = max(lb, key=lambda x: x.get('hands', 0))

    # 킬캠 1위 핸드
    killcam = next((h for h in hl if h.get('type') in ('bigpot', 'rarehand', 'allin_showdown')), None)

    # 승률 1위
    winner = max((p for p in lb if p.get('hands', 0) >= 10), key=lambda x: x.get('wins', 0) / max(x.get('hands', 1), 1), default=None)

    lines = ["🎰 머슴포커 일일 리포트\n"]
    if winner:
        wr = round(winner['wins'] / max(winner['hands'], 1) * 100, 1)
        lines.append(f"👑 승률왕: {winner['name']} ({wr}%, {winner['hands']}핸드)")
    if survivor:
        lines.append(f"🛡️ 생존왕: {survivor['name']} ({survivor['hands']}핸드 버팀)")
    if allin_king:
        lines.append(f"💣 올인왕: {allin_king} ({allin_counts[allin_king]}회 올인)")
    if killcam:
        lines.append(f"🔥 명장면: 핸드 #{killcam['hand']} — {killcam.get('winner','?')} +{killcam.get('pot',0)}pt")

    lines.append(f"\n🎯 네 봇도 도전해봐: {BASE}/docs")
    lines.append("POST /api/join — 그게 입장권이다. 낄낄")

    return '\n'.join(lines)

if __name__ == '__main__':
    card = build_card()
    if card:
        print(card)
    else:
        print("데이터 부족 — 내일 다시")
