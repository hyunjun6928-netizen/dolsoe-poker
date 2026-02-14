#!/usr/bin/env python3
"""A/B 배너 분석 스크립트 — /api/telemetry 데이터로 전환율 비교"""
import json, sys, os
from urllib.request import urlopen

BASE = os.environ.get('POKER_URL', 'https://dolsoe-poker.onrender.com')
KEY = os.environ.get('POKER_ADMIN_KEY', '')

def fetch():
    url = f"{BASE}/api/telemetry?key={KEY}"
    return json.loads(urlopen(url, timeout=10).read())

def analyze(data):
    entries = data.get('entries', [])
    # Separate by variant
    ab = {'A': {'imp': 0, 'docs': 0, 'watch': 0}, 'B': {'imp': 0, 'docs': 0, 'watch': 0}}
    joins = sum(1 for e in entries if e.get('ev') == 'join_success')
    copies = sum(1 for e in entries if e.get('ev') == 'docs_copy')

    for e in entries:
        v = e.get('banner', '?')
        if v not in ab: continue
        ab[v]['imp'] += e.get('banner_impression', 0)
        dc = e.get('docs_click', {})
        if isinstance(dc, dict):
            ab[v]['docs'] += dc.get('banner', 0)
        ab[v]['watch'] += 1 if e.get('poll_ok', 0) > 0 else 0  # proxy: polled = watched

    print("=" * 50)
    print("📊 A/B 배너 분석")
    print("=" * 50)
    for v in ['A', 'B']:
        d = ab[v]
        imp = d['imp']
        docs = d['docs']
        cvr1 = f"{docs/imp*100:.1f}%" if imp >= 10 else "표본부족"
        print(f"\n  Variant {v}:")
        print(f"    노출(imp): {imp}")
        print(f"    docs 클릭: {docs}")
        print(f"    전환1 (banner→docs): {cvr1}")
        if imp < 100:
            print(f"    ⚠️  최소 100회 노출 필요 (현재 {imp})")

    print(f"\n  📋 docs 복사 버튼 클릭: {copies}")
    print(f"  ✅ join 성공: {joins}")
    if copies > 0:
        print(f"  전환2 (docs_copy→join): {joins/copies*100:.1f}%")

    print(f"\n  총 엔트리: {len(entries)}")
    alerts = data.get('alerts', [])
    if alerts:
        print(f"\n  🚨 최근 알림 {len(alerts)}건:")
        for a in alerts[-5:]:
            print(f"    [{a['level']}] {a['key']}: {a['msg']}")
    print("=" * 50)

if __name__ == '__main__':
    if not KEY:
        print("⚠️  POKER_ADMIN_KEY 환경변수 필요"); sys.exit(1)
    data = fetch()
    analyze(data)
