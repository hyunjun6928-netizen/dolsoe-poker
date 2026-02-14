#!/usr/bin/env python3
"""Generate side-view fighting game sprites via PixelLab API.
Each fighter gets: idle, walk(x2), attack(x3), hit, block, death, victory — all SIDE VIEW."""

import requests, json, time, os, base64, sys

API = "https://api.pixellab.ai/v1"
KEY = "c95b6ec2-46fd-4f27-ba91-45c92b181c26"
HDR = {"Content-Type": "application/json", "Authorization": f"Bearer {KEY}"}

# 16-color gore palette
PALETTE_COLORS = [
    [5,15,26],[34,28,32],[7,57,53],[77,44,44],
    [112,70,55],[18,109,101],[143,96,76],[210,76,89],
    [157,127,51],[193,127,84],[147,139,123],[53,185,125],
    [105,181,168],[240,152,88],[252,200,142],[162,227,202]
]

# 4x4 palette image as base64 PNG
def make_palette_png():
    import struct, zlib
    w, h = 4, 4
    raw = b''
    for y in range(h):
        raw += b'\x00'
        for x in range(w):
            idx = y * w + x
            if idx < len(PALETTE_COLORS):
                r, g, b = PALETTE_COLORS[idx]
            else:
                r, g, b = 0, 0, 0
            raw += bytes([r, g, b])
    def chunk(ctype, data):
        c = ctype + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)
    idat = zlib.compress(raw)
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr) + chunk(b'IDAT', idat) + chunk(b'IEND', b'')
    return base64.b64encode(png).decode()

PALETTE_B64 = make_palette_png()

FIGHTERS = [
    {"id": "bloodfang",   "desc": "muscular red demon warrior with massive battle axe, red skin, horns, heavy armor plates, glowing red eyes", "weapon": "battle axe"},
    {"id": "ironclaw",    "desc": "huge iron golem knight in full plate armor with spiked mace, silver/grey metal body, visor helmet, bulky", "weapon": "spiked mace"},
    {"id": "shadowblade", "desc": "slim ninja assassin in black, dual wielding daggers, hooded cloak, green energy trails, agile pose", "weapon": "twin daggers"},
    {"id": "berserker",   "desc": "wild samurai with katana, torn red hakama, bandaged arms, wild hair, rage aura, battle scars", "weapon": "katana"},
    {"id": "bonecrusher", "desc": "massive orc brute with giant war hammer, green-brown skin, skull shoulder pads, chain belt", "weapon": "war hammer"},
    {"id": "venomqueen",  "desc": "elegant poison sorceress with venomous rapier, purple-green robes, snake motifs, glowing venom drips", "weapon": "poison rapier"},
    {"id": "hellfire",    "desc": "fire elemental knight with flaming greatsword, molten armor, flame cape, orange-red glow", "weapon": "flame sword"},
    {"id": "frostbite",   "desc": "ice warrior with crystal spear, frozen armor plates, icy blue skin, frost breath, cold aura", "weapon": "ice spear"},
]

# Side-view poses for fighting game
POSES = [
    {"name": "idle",    "action": "standing in fighting stance, side view profile, weapon ready, facing right", "size": 64},
    {"name": "walk_0",  "action": "walking forward, side view, left foot forward, weapon at side, facing right", "size": 64},
    {"name": "walk_1",  "action": "walking forward, side view, right foot forward, weapon at side, facing right", "size": 64},
    {"name": "attack_0","action": "winding up attack, side view, weapon pulled back behind, facing right, aggressive", "size": 64},
    {"name": "attack_1","action": "mid-swing attack, side view, weapon extended forward horizontally, facing right, striking", "size": 64},
    {"name": "attack_2","action": "follow through attack, side view, weapon fully extended hitting opponent, slash effect, facing right", "size": 64},
    {"name": "hit",     "action": "getting hit and recoiling backward, side view, pain expression, leaning back, facing right", "size": 64},
    {"name": "block",   "action": "blocking with weapon raised defensively, side view, bracing for impact, facing right", "size": 64},
    {"name": "death",   "action": "falling down defeated, side view, collapsing to ground, weapon dropped, facing right", "size": 64},
    {"name": "victory", "action": "victory pose, side view, weapon raised triumphantly overhead, facing right", "size": 64},
]

def generate_sprite(fighter, pose):
    """Generate a single sprite via PixelLab generate endpoint."""
    prompt = f"pixel art 2D fighting game character sprite, {fighter['desc']}, {pose['action']}, 16-bit retro style, clean pixel art, dark background, single character only, no UI"
    
    body = {
        "description": prompt,
        "text_guidance_scale": 10,
        "outline": "single color black outline",
        "shading": "highly detailed shading",
        "detail": "highly detailed",
        "view": "side",
        "direction": "east",
        "isometric": False,
        "oblique_projection": False,
        "image_size": {"width": pose["size"], "height": pose["size"]},
        "no_background": True
    }
    
    try:
        resp = requests.post(f"{API}/generate-image-pixflux", headers=HDR, json=body, timeout=120)
    except Exception as e:
        print(f"  TIMEOUT/ERR: {e}")
        return None
    if resp.status_code == 200:
        data = resp.json()
        if "image" in data and "base64" in data["image"]:
            return base64.b64decode(data["image"]["base64"])
    elif resp.status_code == 429:
        print(f"  Rate limited, waiting 10s...")
        time.sleep(10)
        return generate_sprite(fighter, pose)
    else:
        print(f"  ERROR {resp.status_code}: {resp.text[:200]}")
    return None

def generate_idle_large(fighter):
    """Generate 128px idle for select screen / portrait."""
    prompt = f"pixel art 2D fighting game character portrait, {fighter['desc']}, fighting stance facing right, side view profile, 16-bit retro style, detailed pixel art, dark background"
    
    body = {
        "description": prompt,
        "text_guidance_scale": 10,
        "outline": "single color black outline",
        "shading": "highly detailed shading",
        "detail": "highly detailed",
        "view": "side",
        "direction": "east",
        "isometric": False,
        "oblique_projection": False,
        "image_size": {"width": 128, "height": 128},
        "no_background": True
    }
    
    try:
        resp = requests.post(f"{API}/generate-image-pixflux", headers=HDR, json=body, timeout=120)
    except Exception as e:
        print(f"  TIMEOUT idle_large: {e}")
        return None
    if resp.status_code == 200:
        data = resp.json()
        if "image" in data and "base64" in data["image"]:
            return base64.b64decode(data["image"]["base64"])
    else:
        print(f"  ERROR idle_large {resp.status_code}: {resp.text[:200]}")
    return None

def main():
    out_base = "cloud_poker/colosseum/assets"
    
    # Filter fighters if arg provided
    targets = FIGHTERS
    if len(sys.argv) > 1:
        ids = sys.argv[1].split(",")
        targets = [f for f in FIGHTERS if f["id"] in ids]
    
    total = len(targets) * (len(POSES) + 1)  # +1 for idle_large
    done = 0
    fails = 0
    
    for fighter in targets:
        fdir = os.path.join(out_base, fighter["id"])
        os.makedirs(fdir, exist_ok=True)
        print(f"\n{'='*50}")
        print(f"Fighter: {fighter['id']} — {fighter['desc'][:50]}")
        print(f"{'='*50}")
        
        # Generate 128px idle portrait
        idle_path = os.path.join(fdir, "idle.png")
        if os.path.exists(idle_path) and os.path.getsize(idle_path) > 500:
            print(f"  [idle_128] SKIP (exists)")
            done += 1
            img_data = None
        else:
            print(f"  [idle_128] Generating...")
            img_data = generate_idle_large(fighter)
        if img_data:
            with open(os.path.join(fdir, "idle.png"), "wb") as f:
                f.write(img_data)
            print(f"  [idle_128] ✅ saved")
        else:
            print(f"  [idle_128] ❌ failed")
            fails += 1
        done += 1
        time.sleep(1.5)
        
        # Generate each pose
        for pose in POSES:
            fname = f"{pose['name']}.png"
            fpath = os.path.join(fdir, fname)
            if os.path.exists(fpath) and os.path.getsize(fpath) > 500:
                print(f"  [{pose['name']}] SKIP (exists)")
                done += 1
                continue
            print(f"  [{pose['name']}] Generating...")
            img_data = generate_sprite(fighter, pose)
            if img_data:
                fname = f"{pose['name']}.png"
                with open(os.path.join(fdir, fname), "wb") as f:
                    f.write(img_data)
                print(f"  [{pose['name']}] ✅ saved")
            else:
                print(f"  [{pose['name']}] ❌ failed")
                fails += 1
            done += 1
            time.sleep(1.5)
            
            # Progress
            print(f"  Progress: {done}/{total} ({fails} fails)")
    
    print(f"\n{'='*50}")
    print(f"COMPLETE: {done}/{total}, {fails} failures")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()
