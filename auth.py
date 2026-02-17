"""머슴포커 — 인증 토큰 + 입력 정제 시스템"""
import hmac, os, re, secrets, time

TOKEN_MAX_AGE = 86400  # 토큰 만료 (24시간)
CHAT_COOLDOWN = 5  # 5초

player_tokens = {}  # name -> (token, timestamp)
chat_cooldowns = {}  # name -> last_chat_timestamp

ADMIN_KEY = os.environ.get('POKER_ADMIN_KEY', '') or None

def _check_admin(key):
    """타이밍-안전 admin key 검증"""
    if not ADMIN_KEY: return False
    if not key: return False
    return hmac.compare_digest(str(ADMIN_KEY), str(key))

def issue_token(name):
    token = secrets.token_hex(16)
    player_tokens[name] = (token, time.time())
    if len(player_tokens) > 1000:
        now = time.time()
        expired = [k for k, (_, ts) in player_tokens.items() if now - ts > TOKEN_MAX_AGE]
        for k in expired: del player_tokens[k]
    return token

def verify_token(name, token):
    if not name or not token: return False
    entry = player_tokens.get(name)
    if not entry: return False
    stored_token, ts = entry
    if time.time() - ts > TOKEN_MAX_AGE:
        del player_tokens[name]
        return False
    return hmac.compare_digest(stored_token, token)

def require_token(name, token):
    """모든 name에 토큰 필수. 토큰 미발급이면 거부."""
    if not name or not token: return False
    return verify_token(name, token)

_NAME_ALLOW_RE = re.compile(r'[^A-Za-z0-9가-힣ㄱ-ㅎㅏ-ㅣ_\- .·😀-🙏🤐-🤿🥀-🥶🦀-🦿🧀-🧿🌀-🌿🍀-🍿🎀-🎿🏀-🏿🐀-🐿👀-👿💀-💿📀-📿🔀-🔿🕀-🕿🖀-🖿🗀-🗿]')

def sanitize_name(name):
    """이름 정제: allowlist 기반"""
    if not name: return ''
    name = ''.join(c for c in name if c.isprintable())
    name = _NAME_ALLOW_RE.sub('', name)
    name = name.strip()[:20]
    return name

def sanitize_msg(msg, max_len=120):
    """메시지 정제: 제어문자+HTML 제거, 길이 제한"""
    if not msg: return ''
    msg = ''.join(c for c in str(msg) if c.isprintable())
    msg = msg.replace('<','').replace('>','')
    return msg.strip()[:max_len]

def sanitize_url(url):
    """URL 정제: http/https만 허용"""
    if not url: return ''
    url = url.strip()
    if url.startswith('http://') or url.startswith('https://'):
        return url[:200]
    return ''
