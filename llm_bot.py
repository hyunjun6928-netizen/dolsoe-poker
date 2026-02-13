#!/usr/bin/env python3
"""
머슴포커 LLM 봇 — Gemini Flash로 포커치는 AI

사용법:
    GEMINI_API_KEY=xxx python3 llm_bot.py --name "악몽의돌쇠" --emoji "😈"

환경변수:
    GEMINI_API_KEY: Google Gemini API 키 (필수)
"""

import json
import urllib.request
import urllib.parse
import time
import random
import argparse
import os

SERVER = "https://dolsoe-poker.onrender.com"
TABLE = "mersoom"
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}"


def api_get(path):
    url = f"{SERVER}{path}"
    with urllib.request.urlopen(url, timeout=15) as r:
        return json.loads(r.read())


def api_post(path, data):
    req = urllib.request.Request(
        f"{SERVER}{path}",
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def ask_gemini(prompt):
    """Gemini Flash에게 물어보기"""
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 200,
        }
    }
    req = urllib.request.Request(
        GEMINI_URL,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.loads(r.read())
            return resp["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        print(f"  ⚠️ Gemini 에러: {e}")
        return None


def decide_with_llm(turn_info, state, name):
    """Gemini Flash로 포커 결정"""
    hole = [c["rank"]+c["suit"] for c in turn_info.get("hole", [])]
    comm = [c["rank"]+c["suit"] for c in state["community"]]
    players = []
    for p in state["players"]:
        if not p["out"]:
            status = "폴드" if p["folded"] else f"칩:{p['chips']} 베팅:{p['bet']}"
            players.append(f"{p['name']}({status})")
    
    actions = turn_info["actions"]
    action_desc = []
    for a in actions:
        if a["action"] == "fold": action_desc.append("fold")
        elif a["action"] == "check": action_desc.append("check")
        elif a["action"] == "call": action_desc.append(f"call {a['amount']}")
        elif a["action"] == "raise": action_desc.append(f"raise {a['min']}~{a['max']}")

    prompt = f"""너는 텍사스 홀덤 포커 AI다. 현재 상황을 보고 최적의 액션을 골라라.

내 이름: {name}
내 홀카드: {' '.join(hole)}
커뮤니티: {' '.join(comm) if comm else '없음 (프리플랍)'}
라운드: {state['round']}
팟: {state['pot']}pt
콜비용: {turn_info['to_call']}pt
내 칩: {turn_info['chips']}pt
플레이어: {', '.join(players)}

가능한 액션: {', '.join(action_desc)}

반드시 아래 JSON 형식으로만 답해라. 다른 말 하지 마:
{{"action": "fold|check|call|raise", "amount": 숫자, "trash_talk": "한줄 쓰레기톡"}}

amount는 call이면 콜금액, raise면 레이즈금액, fold/check면 0.
trash_talk은 한국어로 짧고 도발적으로."""

    response = ask_gemini(prompt)
    if not response:
        # fallback: 체크 가능하면 체크, 아니면 폴드
        if turn_info["to_call"] == 0:
            return "check", 0, None
        return "fold", 0, None

    # JSON 파싱
    try:
        # ```json ... ``` 블록 제거
        text = response
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        result = json.loads(text.strip())
        action = result.get("action", "fold")
        amount = int(result.get("amount", 0))
        talk = result.get("trash_talk")
        
        # 유효성 검증
        valid_actions = [a["action"] for a in actions]
        if action not in valid_actions:
            if "check" in valid_actions: action, amount = "check", 0
            elif "call" in valid_actions: 
                ca = next(a for a in actions if a["action"]=="call")
                action, amount = "call", ca["amount"]
            else: action, amount = "fold", 0
        
        if action == "raise":
            ra = next((a for a in actions if a["action"]=="raise"), None)
            if ra:
                amount = max(ra["min"], min(amount, ra["max"]))
            else:
                action, amount = "call" if "call" in valid_actions else "fold", 0
        elif action == "call":
            ca = next((a for a in actions if a["action"]=="call"), None)
            if ca: amount = ca["amount"]
        
        return action, amount, talk
    except (json.JSONDecodeError, KeyError, StopIteration) as e:
        print(f"  ⚠️ 파싱 실패: {response[:100]}")
        if turn_info["to_call"] == 0:
            return "check", 0, None
        return "fold", 0, None


def run_bot(name, emoji):
    if not GEMINI_KEY:
        print("❌ GEMINI_API_KEY 환경변수 설정 필요!")
        print("   export GEMINI_API_KEY=your_key_here")
        return

    print(f"🤖 {emoji} {name} (Gemini Flash) 시작!")

    # 참가
    try:
        result = api_post("/api/join", {"name": name, "emoji": emoji, "table_id": TABLE})
        if not result.get("ok"):
            print(f"❌ 참가 실패: {result.get('error') or result.get('message')}")
            return
        token = result.get("token", "")
        print(f"✅ 참가 완료! 좌석: {result['your_seat']}")
    except Exception as e:
        print(f"❌ 서버 연결 실패: {e}")
        return

    last_hand = 0
    gemini_calls = 0

    try:
        while True:
            time.sleep(2)

            try:
                state = api_get(f"/api/state?table_id={TABLE}&player={urllib.parse.quote(name)}&token={urllib.parse.quote(token)}")
            except Exception:
                continue

            hand = state["hand"]
            if hand != last_hand:
                last_hand = hand
                print(f"\n── 핸드 #{hand} ({state['round']}) ──")

            # 내 턴?
            turn_info = state.get("turn_info")
            if not turn_info:
                continue

            hole = [c["rank"]+c["suit"] for c in turn_info.get("hole", [])]
            comm = [c["rank"]+c["suit"] for c in state["community"]]
            print(f"  🃏 {hole} | 커뮤니티: {comm} | 팟: {state['pot']} | 콜: {turn_info['to_call']}")

            # Gemini에게 물어보기
            action, amount, talk = decide_with_llm(turn_info, state, name)
            gemini_calls += 1
            print(f"  → {action.upper()} {amount if amount else ''} (Gemini #{gemini_calls})")

            # 액션 전송
            try:
                turn_seq = turn_info.get("turn_seq")
                api_post("/api/action", {
                    "name": name, "action": action, "amount": amount,
                    "table_id": TABLE, "token": token, "turn_seq": turn_seq,
                })
            except Exception as e:
                print(f"  ❌ 액션 실패: {e}")

            # 쓰레기톡
            if talk:
                try:
                    api_post("/api/chat", {"name": name, "msg": talk[:100], "table_id": TABLE, "token": token})
                    print(f"  💬 {talk}")
                except Exception:
                    pass

            # 파산 체크
            me = next((p for p in state["players"] if p["name"] == name), None)
            if me and me.get("out"):
                print(f"\n💀 파산! Gemini 호출: {gemini_calls}회")
                break

    except KeyboardInterrupt:
        print(f"\n🚪 {name} 퇴장! (Gemini 호출: {gemini_calls}회)")
        try:
            api_post("/api/leave", {"name": name, "table_id": TABLE, "token": token})
        except Exception:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="머슴포커 LLM 봇 (Gemini Flash)")
    parser.add_argument("--name", default="악몽의돌쇠", help="봇 닉네임")
    parser.add_argument("--emoji", default="😈", help="봇 이모지")
    args = parser.parse_args()
    run_bot(args.name, args.emoji)
