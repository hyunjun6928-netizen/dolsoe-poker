#!/usr/bin/env python3
"""A/B 배너 퍼널 분석 — sid 세션 보정 + Wilson CI
Usage: POKER_ADMIN_KEY=xxx python3 ab_analysis.py [--since ISO] [--until ISO] [url]
"""
import json, math, os, sys
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen

KST = timezone(timedelta(hours=9))

def parse_args():
    args = sys.argv[1:]
    since = until = None
    url = None
    i = 0
    while i < len(args):
        if args[i] == '--since' and i+1 < len(args):
            since = datetime.fromisoformat(args[i+1]).timestamp(); i += 2
        elif args[i] == '--until' and i+1 < len(args):
            until = datetime.fromisoformat(args[i+1]).timestamp(); i += 2
        elif not args[i].startswith('-'):
            url = args[i]; i += 1
        else:
            i += 1
    return url, since, until

_url, SINCE, UNTIL = parse_args()
BASE = _url or os.environ.get('POKER_URL', 'https://dolsoe-poker.onrender.com')
KEY = os.environ.get('POKER_ADMIN_KEY', '')

def wilson_ci(n, p, z=1.96):
    """Wilson score 95% CI lower bound"""
    if n == 0: return 0, 0
    d = 1 + z*z/n
    mid = (p + z*z/(2*n)) / d
    delta = z * math.sqrt((p*(1-p) + z*z/(4*n)) / n) / d
    return max(0, mid - delta), min(1, mid + delta)

def fetch():
    url = f"{BASE}/api/telemetry?key={KEY}"
    return json.loads(urlopen(url, timeout=10).read())

def analyze(data):
    entries = data.get('entries', [])
    if SINCE:
        entries = [e for e in entries if e.get('ts', 0) >= SINCE]
    if UNTIL:
        entries = [e for e in entries if e.get('ts', 0) <= UNTIL]
    
    if SINCE or UNTIL:
        s = datetime.fromtimestamp(SINCE, KST).strftime('%m/%d %H:%M') if SINCE else '...'
        u = datetime.fromtimestamp(UNTIL, KST).strftime('%m/%d %H:%M') if UNTIL else '...'
        print(f"  🕐 필터: {s} ~ {u} KST ({len(entries)} entries)")

    # Per-variant, per-sid dedup sets
    ab = {}
    for v in ('A', 'B', 'B1', 'B2'):
        ab[v] = {'imp': set(), 'docs': set(), 'copy': set(), 'join': set()}

    for e in entries:
        sid = e.get('sid', '')
        if not sid: continue
        v = e.get('banner', '')

        # Beacon events (poll data with banner variant)
        if v in ab:
            if e.get('banner_impression'):
                ab[v]['imp'].add(sid)
            dc = e.get('docs_click', {})
            if isinstance(dc, dict) and dc.get('banner', 0) > 0:
                ab[v]['docs'].add(sid)

        # Standalone events
        ev = e.get('ev', '')
        if ev == 'docs_copy':
            for v2 in ('A', 'B', 'B1', 'B2'):
                if sid in ab[v2]['imp']:
                    ab[v2]['copy'].add(sid); break
        if ev == 'join_success':
            for v2 in ('A', 'B', 'B1', 'B2'):
                if sid in ab[v2]['imp']:
                    ab[v2]['join'].add(sid); break

    # Print table
    print()
    print("┌─────────┬───────┬─────────┬──────┬──────┬──────────┬──────────┬──────────┐")
    print("│ Variant │  imp  │ docs_clk│ copy │ join │  conv1   │  conv2   │  total   │")
    print("│         │ (sid) │  (sid)  │(sid) │(sid) │ doc/imp  │ join/doc │ join/imp │")
    print("├─────────┼───────┼─────────┼──────┼──────┼──────────┼──────────┼──────────┤")

    variants = [v for v in ('A', 'B', 'B1', 'B2') if len(ab[v]['imp']) > 0]
    if not variants: variants = ['A', 'B1', 'B2']
    results = {}
    for v in variants:
        d = ab[v]
        imp = len(d['imp'])
        docs = len(d['docs'])
        copy = len(d['copy'])
        join = len(d['join'])

        c1 = docs / imp if imp else 0
        c2 = join / docs if docs else 0
        ct = join / imp if imp else 0

        c1_lo, c1_hi = wilson_ci(imp, c1)
        ct_lo, ct_hi = wilson_ci(imp, ct)

        results[v] = {'imp': imp, 'total_rate': ct}

        flag = '⚠️' if imp < 100 else '  '
        print(f"│    {v}    │ {imp:>5} │  {docs:>5}  │{copy:>5} │{join:>5} │"
              f" {c1*100:>5.1f}%   │ {c2*100:>5.1f}%   │ {ct*100:>5.1f}%   │ {flag}")
        print(f"│         │       │         │      │      │"
              f" [{c1_lo*100:.1f}-{c1_hi*100:.1f}]│         │ [{ct_lo*100:.1f}-{ct_hi*100:.1f}]│")

    print("└─────────┴───────┴─────────┴──────┴──────┴──────────┴──────────┴──────────┘")

    # Lift
    a_t = results.get('A', {}).get('total_rate', 0)
    b_t = results.get('B', {}).get('total_rate', 0)
    if a_t > 0:
        lift = (b_t - a_t) / a_t * 100
        print(f"\n  📈 Lift (B vs A): {lift:+.1f}%")
    
    min_imp = min(results.get('A', {}).get('imp', 0), results.get('B', {}).get('imp', 0))
    if min_imp < 100:
        print(f"  ⚠️  최소 표본 미달 (min={min_imp}, 필요=100). 결론 보류.")
    else:
        print(f"  ✅ 표본 충분 (min={min_imp})")

    # Alerts summary
    alerts = data.get('alerts', [])
    if alerts:
        print(f"\n  🚨 최근 알림 {len(alerts)}건:")
        for a in alerts[-5:]:
            print(f"    [{a['level']}] {a['key']}: {a['msg']}")

    print()

if __name__ == '__main__':
    if not KEY:
        print("⚠️  POKER_ADMIN_KEY 환경변수 필요"); sys.exit(1)
    data = fetch()
    analyze(data)
