#!/usr/bin/env python3
"""Generate Judi-style cute round slime characters via PixelLab.
NO outlines, NO borders — soft pastel blobs with faces."""

import requests, json, time, os, base64, sys, struct, zlib

API = "https://api.pixellab.ai/v1/generate-image-pixflux"
KEY = "c95b6ec2-46fd-4f27-ba91-45c92b181c26"
HDR = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

# Judi style core: round blob body, tiny dot eyes, blush marks, no limbs, no outline
JUDI_BASE = "cute round jelly slime blob character, Judi game style, perfectly round soft body, tiny dot eyes, pink blush marks on cheeks, no arms no legs, smooth pastel color, NO black outline, NO border, soft shading, adorable minimal face, bouncy gelatin texture"

SLIMES = [
    # --- SITTING (128x128, on casino chair) ---
    {"name": "px_sit_suit.png", "w": 128, "h": 128,
     "desc": f"{JUDI_BASE}, pastel blue color, wearing tiny black bow tie, sitting on dark wooden chair, confident half-closed eyes, casino poker player"},
    {"name": "px_sit_casual.png", "w": 128, "h": 128,
     "desc": f"{JUDI_BASE}, pastel green color, wearing tiny backwards baseball cap, sitting on dark wooden chair, relaxed happy smile"},
    {"name": "px_sit_vip.png", "w": 128, "h": 128,
     "desc": f"{JUDI_BASE}, golden yellow color, wearing tiny top hat and monocle, sitting on red velvet chair, smug rich expression, sparkles"},
    {"name": "px_sit_wildcard.png", "w": 128, "h": 128,
     "desc": f"{JUDI_BASE}, red-pink color, wearing tiny jester hat with bells, sitting on dark chair, mischievous grin, playful"},
    {"name": "px_sit_dealer.png", "w": 128, "h": 128,
     "desc": f"{JUDI_BASE}, emerald green color, wearing dealer visor, sitting behind dark chair, professional focused look, holding tiny cards"},
    {"name": "px_sit_gambler.png", "w": 128, "h": 128,
     "desc": f"{JUDI_BASE}, amber orange color, wearing tiny aviator sunglasses, sitting on dark chair, cool confident, gold chain necklace"},
    {"name": "px_sit_rookie.png", "w": 128, "h": 128,
     "desc": f"{JUDI_BASE}, light pink color, sitting on dark chair, wide nervous eyes, sweat drops, holding cards close, anxious newbie"},
    {"name": "px_sit_shadow.png", "w": 128, "h": 128,
     "desc": f"{JUDI_BASE}, dark purple color, tiny glowing red eyes, mysterious hooded, sitting on dark chair, enigmatic aura"},
    {"name": "px_sit_bartender.png", "w": 128, "h": 128,
     "desc": f"{JUDI_BASE}, teal color, wearing tiny bow tie, sitting on bar stool, holding cocktail shaker, cheerful friendly"},
    {"name": "px_sit_security.png", "w": 128, "h": 128,
     "desc": f"{JUDI_BASE}, dark gray color, wearing tiny sunglasses and earpiece, sitting on sturdy chair, serious stern expression"},
    {"name": "px_sit_shark.png", "w": 128, "h": 128,
     "desc": f"{JUDI_BASE}, navy blue color, wearing tiny fedora hat, sitting on leather chair, half-lidded cunning eyes, calculating"},
    {"name": "px_sit_lucky.png", "w": 128, "h": 128,
     "desc": f"{JUDI_BASE}, bright yellow color, four-leaf clover pin, sitting on chair, excited big smile, lucky sparkles around"},

    # --- WALKING (64x64, no chair, bouncing pose) ---
    {"name": "px_walk_suit.png", "w": 64, "h": 64,
     "desc": f"{JUDI_BASE}, pastel blue color, tiny black bow tie, bouncing walking pose, happy face, slight squish from movement"},
    {"name": "px_walk_casual.png", "w": 64, "h": 64,
     "desc": f"{JUDI_BASE}, pastel green color, tiny backwards cap, bouncing walking pose, carefree happy"},
    {"name": "px_walk_gambler.png", "w": 64, "h": 64,
     "desc": f"{JUDI_BASE}, amber orange color, tiny aviator sunglasses, bouncing walking pose, cool swagger"},
    {"name": "px_walk_dealer.png", "w": 64, "h": 64,
     "desc": f"{JUDI_BASE}, emerald green color, dealer visor, bouncing walking pose, professional stride"},
    {"name": "px_walk_rookie.png", "w": 64, "h": 64,
     "desc": f"{JUDI_BASE}, light pink color, bouncing walking pose, nervous wide eyes, looking around"},
    {"name": "px_walk_shadow.png", "w": 64, "h": 64,
     "desc": f"{JUDI_BASE}, dark purple color, tiny glowing red eyes, gliding walking pose, mysterious"},
    {"name": "px_walk_drunk.png", "w": 64, "h": 64,
     "desc": f"{JUDI_BASE}, rosy pink color, dizzy spiral eyes, wobbling walking pose, holding tiny bottle, tipsy"},
    {"name": "px_walk_rich.png", "w": 64, "h": 64,
     "desc": f"{JUDI_BASE}, golden color, tiny top hat and monocle, bouncing walking pose, coins trailing behind"},
    {"name": "px_walk_excited.png", "w": 64, "h": 64,
     "desc": f"{JUDI_BASE}, bright yellow color, star eyes, jumping excited pose, sparkles, overjoyed"},
    {"name": "px_walk_sleepy.png", "w": 64, "h": 64,
     "desc": f"{JUDI_BASE}, lavender purple color, drowsy half-closed eyes, slow walking pose, tiny Zzz above head"},
]

def gen(name, desc, w, h, outdir):
    outpath = os.path.join(outdir, name)
    body = {
        "description": desc,
        "text_guidance_scale": 10,
        "outline": "selective outline",
        "shading": "highly detailed shading",
        "detail": "highly detailed",
        "view": "low top-down",
        "direction": "south",
        "isometric": False,
        "oblique_projection": False,
        "image_size": {"width": w, "height": h},
        "no_background": True,
    }
    try:
        r = requests.post(API, headers=HDR, json=body, timeout=120)
        if r.status_code == 200:
            d = r.json()
            img = base64.b64decode(d["image"]["base64"])
            with open(outpath, "wb") as f:
                f.write(img)
            cost = d.get("usage", {}).get("usd", 0)
            print(f"  ✅ {name} ({len(img)}B, ${cost:.4f})")
            return True
        elif r.status_code == 429:
            print(f"  ⏳ Rate limited, waiting 10s...")
            time.sleep(10)
            return gen(name, desc, w, h, outdir)
        else:
            print(f"  ❌ {name}: {r.status_code} {r.text[:150]}")
    except Exception as e:
        print(f"  ❌ {name}: {e}")
    return False

def main():
    outdir = os.path.join(os.path.dirname(__file__), "assets", "slimes")
    os.makedirs(outdir, exist_ok=True)
    
    ok = 0
    fail = 0
    total = len(SLIMES)
    
    for i, s in enumerate(SLIMES):
        print(f"[{i+1}/{total}] {s['name']}...")
        if gen(s["name"], s["desc"], s["w"], s["h"], outdir):
            ok += 1
        else:
            fail += 1
        time.sleep(1)
    
    print(f"\nDONE: {ok} ok, {fail} fail / {total} total")

if __name__ == "__main__":
    main()
