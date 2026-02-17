"""머슴포커 — 관전자 베팅 시스템"""
import time

SPECTATOR_START_COINS = 1000
spectator_bets = {}   # table_id -> {hand_num -> {spectator_name -> {'pick','amount'}}}
spectator_coins = {}  # spectator_name -> coins
_spectator_last_seen = {}  # name -> timestamp

def get_spectator_coins(name):
    if name not in spectator_coins:
        if len(spectator_coins) > 5000:
            now = time.time()
            inactive = [k for k, ts in _spectator_last_seen.items() if now - ts > 86400]
            for k in inactive:
                spectator_coins.pop(k, None)
                _spectator_last_seen.pop(k, None)
            if len(spectator_coins) > 5000:
                oldest = sorted(spectator_coins.keys(), key=lambda k: spectator_coins.get(k,0))[:2500]
                for k in oldest:
                    del spectator_coins[k]
                    _spectator_last_seen.pop(k, None)
        spectator_coins[name]=SPECTATOR_START_COINS
    _spectator_last_seen[name] = time.time()
    return spectator_coins[name]

def place_spectator_bet(table_id, hand_num, spectator, pick, amount):
    coins=get_spectator_coins(spectator)
    if amount>coins or amount<=0: return False,'코인 부족'
    if table_id not in spectator_bets: spectator_bets[table_id]={}
    hb=spectator_bets[table_id]
    if hand_num not in hb: hb[hand_num]={}
    if spectator in hb[hand_num]: return False,'이미 베팅함'
    hb[hand_num][spectator]={'pick':pick,'amount':amount}
    spectator_coins[spectator]-=amount
    return True,'베팅 완료'

def resolve_spectator_bets(table_id, hand_num, winner):
    if table_id not in spectator_bets: return []
    if table_id in spectator_bets:
        old_hands = [h for h in spectator_bets[table_id] if h < hand_num - 5]
        for h in old_hands: del spectator_bets[table_id][h]
    hb=spectator_bets[table_id].get(hand_num,{})
    results=[]
    total_pool=sum(b['amount'] for b in hb.values())
    winners=[k for k,v in hb.items() if v['pick']==winner]
    winner_pool=sum(hb[k]['amount'] for k in winners)
    for name,bet in hb.items():
        if bet['pick']==winner and winner_pool>0:
            payout=int(bet['amount']/winner_pool*total_pool)
            spectator_coins[name]=get_spectator_coins(name)+payout
            results.append({'name':name,'pick':bet['pick'],'bet':bet['amount'],'payout':payout,'win':True})
        else:
            results.append({'name':name,'pick':bet['pick'],'bet':bet['amount'],'payout':0,'win':False})
    return results
