#!/usr/bin/env python3
"""머슴포커 보안 자동 테스트 — 배포 후 실행"""
import urllib.request, urllib.error, json, sys

BASE = sys.argv[1] if len(sys.argv) > 1 else 'https://dolsoe-poker.onrender.com'
PASS = 0; FAIL = 0; WARN = 0

def req(path, method='GET', body=None, headers=None):
    url = f'{BASE}{path}'
    r = urllib.request.Request(url, method=method)
    if headers:
        for k,v in headers.items(): r.add_header(k,v)
    data = json.dumps(body).encode() if body else None
    if data: r.add_header('Content-Type','application/json')
    try:
        with urllib.request.urlopen(r, data=data, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode())
        except: return e.code, {}
    except Exception as e:
        return 0, str(e)

def check(name, condition, critical=False):
    global PASS, FAIL, WARN
    icon = '✅' if condition else ('🔴' if critical else '🟡')
    if condition: PASS += 1
    elif critical: FAIL += 1
    else: WARN += 1
    print(f"  {icon} {name}")

print(f"\n🔒 머슴포커 보안 테스트 — {BASE}\n{'='*50}")

# 1. Admin API 인증
print("\n[1] Admin API 인증")
s, d = req('/api/telemetry?key=wrong')
check('텔레메트리 잘못된 키 거부', s == 401, critical=True)

s, d = req('/api/telemetry')
check('텔레메트리 키 없이 거부', s == 401, critical=True)

# 2. Ranked 잠금
print("\n[2] Ranked 잠금")
s, d = req('/api/ranked/house')
check('ranked house 잠금', s in (401,403), critical=True)

s, d = req('/api/ranked/rooms')
check('ranked rooms 잠금', s in (401,403))

# 3. XSS 방어 헤더
print("\n[3] 보안 헤더")
try:
    r = urllib.request.urlopen(f'{BASE}/', timeout=10)
    hdrs = dict(r.headers)
    check('X-Content-Type-Options', 'nosniff' in hdrs.get('X-Content-Type-Options',''))
    check('X-Frame-Options', hdrs.get('X-Frame-Options','') in ('DENY','SAMEORIGIN'))
    check('Content-Security-Policy', 'Content-Security-Policy' in hdrs)
except Exception as e:
    check(f'헤더 확인 실패: {e}', False)

# 4. 액션 검증
print("\n[4] 액션 검증")
s, d = req('/api/action', 'POST', {'name':'test','action':'raise','amount':-999})
check('음수 amount 거부/무시', s in (400,401,409), critical=True)

s, d = req('/api/action', 'POST', {'name':'test','action':'HACK','amount':0})
check('잘못된 action 타입 거부/무시', s in (400,401,409))

# 5. 레이트리밋
print("\n[5] 레이트리밋")
for _ in range(12):
    s, d = req('/api/join', 'POST', {'name':'ratelimit_test'})
s, d = req('/api/join', 'POST', {'name':'ratelimit_test'})
check('join 레이트리밋 작동', s == 429)

# 6. 백도어 키
print("\n[6] 백도어/은닉 경로")
s, d = req('/api/_v?k=dolsoe_peek_2026')
check('백도어 키 제거됨', s == 404, critical=True)

# 7. 데이터 유출
print("\n[7] 데이터 유출")
s, d = req('/api/recent?table_id=ranked-micro')
check('ranked recent 인증 필요', s in (401,403,404))

s, d = req('/api/export?table_id=ranked-micro&player=all')
check('ranked export 인증 필요', s in (401,403,404))

# 8. 닉네임 새니타이즈
print("\n[8] 입력 검증")
s, d = req('/api/join', 'POST', {'name':'<script>alert(1)</script>'})
check('XSS 닉네임 새니타이즈', 'script' not in json.dumps(d))

# 9. Body 크기 제한
print("\n[9] Body 크기 제한")
big = 'A' * 70000
try:
    s, d = req('/api/join', 'POST', {'name': big})
    check('대용량 body 거부', s == 413, critical=True)
except: check('대용량 body 거부 (연결 끊김)', True)

print(f"\n{'='*50}")
print(f"결과: ✅ {PASS} 통과 | 🔴 {FAIL} 실패 | 🟡 {WARN} 경고")
if FAIL: print("⚠️ CRITICAL 실패 있음! 배포 전 수정 필요")
else: print("🎉 모든 CRITICAL 통과!")
