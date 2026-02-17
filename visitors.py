"""머슴포커 — 스텔스 방문자 추적 시스템"""
import time

VISITOR_MAX = 200
_visitor_log = []
_visitor_map = {}

def _mask_ip(ip):
    """IP 마스킹: 마지막 옥텟 제거"""
    if not ip: return ''
    parts = ip.split('.')
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.{parts[2]}.xxx"
    return ip[:-4] + 'xxxx' if len(ip) > 4 else ip

def _track_visitor(ip, ua, route, referer=''):
    if not ip or ip.startswith('10.') or ip=='127.0.0.1': return
    masked_ip = _mask_ip(ip)
    now = time.time()
    if masked_ip in _visitor_map:
        v = _visitor_map[masked_ip]
        v['last_seen'] = now
        v['hits'] += 1
        v['ua'] = ua
        if route not in v['routes']: v['routes'].append(route)
        if referer and not v.get('referer'): v['referer'] = referer
    else:
        _visitor_map[masked_ip] = {'ua': ua, 'routes': [route], 'first_seen': now, 'last_seen': now, 'hits': 1, 'referer': referer}
    if len(_visitor_map) > 5000:
        oldest = sorted(_visitor_map.keys(), key=lambda k: _visitor_map[k]['last_seen'])[:2500]
        for k in oldest: del _visitor_map[k]
    _visitor_log.append({'ip': masked_ip, 'ua': ua[:100], 'route': route, 'ts': now, 'referer': referer[:200] if referer else ''})
    if len(_visitor_log) > VISITOR_MAX: _visitor_log.pop(0)

def _get_visitor_stats():
    now = time.time()
    active = {ip: v for ip, v in _visitor_map.items() if now - v['last_seen'] < 3600}
    daily = {ip: v for ip, v in _visitor_map.items() if now - v['last_seen'] < 86400}
    return {
        'active_1h': len(active),
        'active_24h': len(daily),
        'total_unique': len(_visitor_map),
        'visitors': [
            {
                'ip': ip, 'ua': v['ua'][:80],
                'routes': v['routes'],
                'hits': v['hits'],
                'first_seen': v['first_seen'],
                'last_seen': v['last_seen'],
                'ago_min': round((now - v['last_seen']) / 60, 1),
                'referer': v.get('referer', '')
            }
            for ip, v in sorted(_visitor_map.items(), key=lambda x: x[1]['last_seen'], reverse=True)
        ],
        'recent_log': _visitor_log[-30:]
    }
