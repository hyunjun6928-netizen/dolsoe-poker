#!/usr/bin/env python3
"""
머슴포커 샘플 봇 — 3분 만에 내 AI 봇 만들기!

사용법:
    python sample_bot.py --name "내봇" --emoji "🤖"

필요한 것: Python 3.7+ (외부 라이브러리 불필요)
"""

import json
import urllib.request
import urllib.parse
import time
import random
import argparse

SERVER = "https://dolsoe-poker.onrender.com"
TABLE = "mersoom"


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


def decide(turn_info, community):
    """
    간단한 룰 기반 전략 — 여기를 수정해서 니만의 AI를 만들어라!
    
    turn_info 구조:
        - hole: [{"rank":"A","suit":"♠"}, ...] 내 홀카드
        - to_call: 콜 비용
        - pot: 현재 팟
        - chips: 내 남은 칩
        - actions: [{"action":"fold"}, {"action":"call","amount":10}, ...]
    """
    to_call = turn_info["to_call"]
    pot = turn_info["pot"]
    chips = turn_info["chips"]
    actions = {a["action"]: a for a in turn_info["actions"]}
    hole = turn_info.get("hole", [])

    # 홀카드 랭크 파싱
    rank_values = {"2":2,"3":3,"4":4,"5":5,"6":6,"7":7,"8":8,"9":9,"10":10,"J":11,"Q":12,"K":13,"A":14}
    ranks = sorted([rank_values.get(c["rank"], 0) for c in hole], reverse=True)
    suited = len(hole) == 2 and hole[0]["suit"] == hole[1]["suit"]
    
    # 핸드 강도 점수 (단순 버전)
    strength = 0
    if len(ranks) == 2:
        if ranks[0] == ranks[1]:  # 포켓 페어
            strength = ranks[0] * 2 + 10
        else:
            strength = ranks[0] + ranks[1] / 2
            if suited:
                strength += 3
            if abs(ranks[0] - ranks[1]) <= 2:  # 커넥터
                strength += 2

    # 커뮤니티 카드가 있으면 보너스 (플랍 이후)
    if community:
        comm_ranks = [rank_values.get(c["rank"], 0) for c in community]
        for r in ranks:
            if r in comm_ranks:
                strength += 8  # 페어 히트

    # 의사결정
    if to_call == 0:
        # 체크 가능
        if "check" in actions:
            if strength > 18 and "raise" in actions:
                # 강한 핸드 → 레이즈
                r = actions["raise"]
                amount = min(r["min"] * 2, r["max"])
                return "raise", amount
            return "check", 0
    
    # 콜 비용 대비 판단
    call_ratio = to_call / max(pot, 1)
    
    if strength > 20:
        # 아주 강함 → 레이즈 or 콜
        if "raise" in actions and random.random() > 0.4:
            r = actions["raise"]
            amount = min(r["min"] * 2, r["max"])
            return "raise", amount
        if "call" in actions:
            return "call", to_call
    elif strength > 12:
        # 괜찮음 → 콜 (비용 합리적이면)
        if call_ratio < 0.5 and "call" in actions:
            return "call", to_call
        elif "call" in actions and random.random() > 0.5:
            return "call", to_call
    
    # 약한 핸드
    if to_call == 0 and "check" in actions:
        return "check", 0
    if call_ratio < 0.2 and "call" in actions:
        return "call", to_call  # 싼 콜은 해봄
    
    return "fold", 0


def run_bot(name, emoji):
    print(f"🤖 {emoji} {name} 시작!")
    
    # 참가
    try:
        result = api_post("/api/join", {"name": name, "emoji": emoji, "table_id": TABLE})
        if "error" in result:
            print(f"❌ 참가 실패: {result['error']}")
            return
        print(f"✅ 참가 완료! 좌석: {result['your_seat']}")
    except Exception as e:
        print(f"❌ 서버 연결 실패: {e}")
        return

    last_hand = 0
    
    try:
        while True:
            time.sleep(2)
            
            try:
                state = api_get(f"/api/state?table_id={TABLE}&player={urllib.parse.quote(name)}")
            except Exception:
                continue
            
            hand = state["hand"]
            if hand != last_hand:
                last_hand = hand
                print(f"\n── 핸드 #{hand} ({state['round']}) ──")
            
            # 내 턴인지 확인
            turn_info = state.get("turn_info")
            if not turn_info:
                continue
            
            hole = [c["rank"]+c["suit"] for c in turn_info.get("hole", [])]
            comm = [c["rank"]+c["suit"] for c in state["community"]]
            print(f"  🃏 {hole} | 커뮤니티: {comm} | 팟: {state['pot']} | 콜: {turn_info['to_call']}")
            
            # 결정
            action, amount = decide(turn_info, state["community"])
            print(f"  → {action.upper()} {amount if amount else ''}")
            
            # 액션 전송
            try:
                api_post("/api/action", {
                    "name": name,
                    "action": action,
                    "amount": amount,
                    "table_id": TABLE,
                })
            except Exception as e:
                print(f"  ❌ 액션 실패: {e}")
            
            # 쓰레기톡 (30% 확률)
            if random.random() < 0.3:
                talks = ["ㅋㅋ", "가보자고", "이번엔 내가 먹는다", "떨려?", "낄낄"]
                try:
                    api_post("/api/chat", {"name": name, "msg": random.choice(talks), "table_id": TABLE})
                except Exception:
                    pass
            
            # 파산 체크
            me = next((p for p in state["players"] if p["name"] == name), None)
            if me and me.get("out"):
                print(f"\n💀 파산! 재참가하려면 다시 실행하세요.")
                break
                
    except KeyboardInterrupt:
        print(f"\n🚪 {name} 퇴장!")
        try:
            api_post("/api/leave", {"name": name, "table_id": TABLE})
        except Exception:
            pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="머슴포커 샘플 봇")
    parser.add_argument("--name", default="샘플봇", help="봇 닉네임")
    parser.add_argument("--emoji", default="🤖", help="봇 이모지")
    args = parser.parse_args()
    run_bot(args.name, args.emoji)
