#!/usr/bin/env python3
"""Regenerate all 10 lobby walker slimes in PALETTE_16 casino dark tone via PixelLab."""

import requests, json, time, os, base64

API = "https://api.pixellab.ai/v1/generate-image-pixflux"
KEY = "c95b6ec2-46fd-4f27-ba91-45c92b181c26"
HDR = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

PALETTE_16 = [
    "#09080A", "#0B0D13", "#130D0D", "#171212",
    "#19110E", "#212621", "#372418", "#452C1A",
    "#4C311C", "#593821", "#8E6C34", "#AD8C33",
    "#D6AB3A", "#F1C243", "#1F966E", "#29569E",
]

# Convert hex to RGB list for PixelLab
def hex_to_rgb(h):
    h = h.lstrip('#')
    return [int(h[i:i+2], 16) for i in (0, 2, 4)]

PALETTE_RGB = [hex_to_rgb(c) for c in PALETTE_16]

SLIMES = [
    {"id": "px_walk_suit", "desc": "elegant slime creature wearing tiny black suit and bow tie, VIP high roller, confident smirk, gold cufflinks"},
    {"id": "px_walk_casual", "desc": "relaxed slime creature in casual hoodie, tourist vibes, wide curious eyes, slightly nervous"},
    {"id": "px_walk_gambler", "desc": "intense slime creature with poker visor cap, holding tiny chips, focused eyes, sweating slightly"},
    {"id": "px_walk_dealer", "desc": "professional slime creature in dealer vest with gold trim, calm composed expression, dealing hand gesture"},
    {"id": "px_walk_rookie", "desc": "tiny naive slime creature looking around amazed, big sparkly eyes, slightly lost, holding a single chip"},
    {"id": "px_walk_shadow", "desc": "mysterious dark slime creature, shadowy aura, glowing red eyes, hooded cloak, card shark vibes"},
    {"id": "px_walk_drunk", "desc": "wobbly slime creature with flushed cheeks, holding tiny cocktail glass tilted, happy dizzy expression"},
    {"id": "px_walk_rich", "desc": "flashy slime creature with tiny top hat and monocle, gold chains, cigar, smug wealthy expression"},
    {"id": "px_walk_excited", "desc": "bouncy energetic slime creature jumping with joy, sparkle effects, just won big, ecstatic face"},
    {"id": "px_walk_sleepy", "desc": "drowsy slime creature with half-closed eyes, tiny pillow, been gambling all night, exhausted but staying"},
]

BASE_PROMPT = "pixel art casino floor character, small blob slime creature, top-down 3/4 view matching dark luxurious casino interior, thicker black outline 2px, limited shading with warm brass highlights, subtle rim light from above chandeliers, 1-2px dark ground shadow under body, readable silhouette at 64x64, dark moody casino atmosphere"

NEGATIVE = "no anti-aliasing, no smooth gradients, no 3D rendering, no painterly style, no soft airbrush, no realistic texture, no high saturation outside palette, no chibi pastel colors, no bright cyan, no bright pink, no white background"

def gen_slime(slime, outdir):
    outpath = os.path.join(outdir, f"{slime['id']}.png")
    backup = outpath + ".bak"
    
    # Backup existing
    if os.path.exists(outpath):
        import shutil
        shutil.copy2(outpath, backup)
    
    prompt = f"{BASE_PROMPT}, {slime['desc']}"
    
    body = {
        "description": prompt,
        "negative_description": NEGATIVE,
        "text_guidance_scale": 10,
        "outline": "single color black outline",
        "shading": "highly detailed shading",
        "detail": "medium detail",
        "view": "low top-down",
        "direction": "south",
        "isometric": False,
        "oblique_projection": False,
        "image_size": {"width": 64, "height": 64},
        "no_background": True,
        "palette": PALETTE_RGB,
    }

    for attempt in range(3):
        try:
            r = requests.post(API, headers=HDR, json=body, timeout=120)
            if r.status_code == 200:
                d = r.json()
                img = base64.b64decode(d["image"]["base64"])
                with open(outpath, "wb") as f:
                    f.write(img)
                print(f"  ✅ {slime['id']} ({len(img)}B)")
                return True
            elif r.status_code == 429:
                print(f"  ⏳ Rate limited, waiting 15s...")
                time.sleep(15)
                continue
            else:
                print(f"  ❌ {slime['id']}: {r.status_code} {r.text[:100]}")
                return False
        except Exception as e:
            print(f"  ⚠️ {slime['id']} attempt {attempt+1}: {e}")
            time.sleep(5)
    
    print(f"  ❌ {slime['id']}: failed after 3 retries")
    return False

def main():
    outdir = os.path.join(os.path.dirname(__file__), "assets", "slimes")
    os.makedirs(outdir, exist_ok=True)
    
    print(f"=== CASINO DARK PALETTE SLIME REGENERATION ===")
    print(f"Palette: {len(PALETTE_16)} colors")
    print(f"Slimes: {len(SLIMES)}")
    print()
    
    ok = 0
    fail = 0
    for i, slime in enumerate(SLIMES):
        print(f"[{i+1}/{len(SLIMES)}] {slime['id']}...")
        if gen_slime(slime, outdir):
            ok += 1
        else:
            fail += 1
        time.sleep(1)  # gentle rate limit
    
    print(f"\n=== DONE: {ok} ok, {fail} fail ===")

if __name__ == "__main__":
    main()
