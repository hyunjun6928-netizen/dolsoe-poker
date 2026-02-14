#!/usr/bin/env python3
"""PixelLab API batch generator — maximum quality pixel art casino assets"""
import json, base64, time, sys, os, requests

API_KEY = os.environ.get("PIXELLAB_API_KEY", "")
API_URL = "https://api.pixellab.ai/v1"
OUT_DIR = os.path.join(os.path.dirname(__file__), "assets", "slimes")

# Our 16-color palette as a 4x4 PNG (base64) for color_image
# We'll create it on-the-fly
PALETTE = [
    (5,15,26),(34,28,32),(7,57,53),(77,44,44),
    (112,70,55),(18,109,101),(143,96,76),(210,76,89),
    (157,127,51),(193,127,84),(147,139,123),(53,185,125),
    (105,181,168),(240,152,88),(252,200,142),(162,227,202),
]

def make_palette_png():
    """Create a tiny 4x4 PNG with our 16 colors for forced palette"""
    import struct, zlib
    w, h = 4, 4
    raw = b''
    for y in range(h):
        raw += b'\x00'  # filter byte
        for x in range(w):
            idx = y * w + x
            r, g, b = PALETTE[idx]
            raw += struct.pack('BBB', r, g, b)
    
    def chunk(ctype, data):
        c = ctype + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
    idat = chunk(b'IDAT', zlib.compress(raw))
    iend = chunk(b'IEND', b'')
    png = sig + ihdr + idat + iend
    return base64.b64encode(png).decode()

PALETTE_B64 = make_palette_png()

# Maximum quality settings for Tier 3
BASE_PARAMS = {
    "outline": "single color black outline",
    "shading": "highly detailed shading",
    "detail": "highly detailed",
    "view": "low top-down",
    "direction": "south",
    "no_background": True,
    "text_guidance_scale": 10,
    "color_image": {"type": "base64", "base64": PALETTE_B64},
}

# === ASSET DEFINITIONS ===
ASSETS = [
    # --- SITTING SLIMES (for poker table) 128x128 ---
    {"name": "px_sit_suit.png", "w": 128, "h": 128, "desc": "A cute round pastel blue slime character sitting on a dark wooden casino chair. Wearing a tiny black suit jacket and bow tie. Confident expression with small blush marks. Casino poker player. Judi-style cute round body."},
    {"name": "px_sit_casual.png", "w": 128, "h": 128, "desc": "A cute round pastel green slime character sitting on a dark wooden casino chair. Wearing a tiny baseball cap backwards. Relaxed happy expression with blush marks. Casual poker player. Judi-style cute round body."},
    {"name": "px_sit_vip.png", "w": 128, "h": 128, "desc": "A cute round golden slime character sitting on a luxurious red velvet casino chair. Wearing a tiny top hat and monocle. Smug rich expression with blush. VIP high roller. Judi-style cute round body."},
    {"name": "px_sit_wildcard.png", "w": 128, "h": 128, "desc": "A cute round red-pink slime character sitting on a dark casino chair. Wearing a tiny jester hat with bells. Mischievous grinning expression with blush. Wild unpredictable player. Judi-style cute round body."},
    {"name": "px_sit_dealer.png", "w": 128, "h": 128, "desc": "A cute round emerald green slime character sitting behind a dark casino chair. Wearing a dealer visor and vest, holding tiny cards. Professional focused expression. Casino dealer. Judi-style cute round body."},
    {"name": "px_sit_gambler.png", "w": 128, "h": 128, "desc": "A cute round amber-orange slime character sitting on a dark casino chair. Wearing tiny aviator sunglasses and a gold chain. Cool confident expression with blush. Veteran gambler. Judi-style cute round body."},
    {"name": "px_sit_rookie.png", "w": 128, "h": 128, "desc": "A cute round light pink slime character sitting on a dark casino chair. Wide nervous eyes, sweat drops, holding cards close. Anxious newbie expression with heavy blush. First-time player. Judi-style cute round body."},
    {"name": "px_sit_shadow.png", "w": 128, "h": 128, "desc": "A cute round dark purple-black slime character sitting on a dark casino chair. Glowing red eyes, mysterious hooded look. Enigmatic dangerous expression. Shadow player. Judi-style cute round body."},
    {"name": "px_sit_bartender.png", "w": 128, "h": 128, "desc": "A cute round teal slime character sitting on a bar stool. Wearing a tiny bow tie, holding a cocktail shaker. Cheerful friendly expression with blush. Bartender taking a break. Judi-style cute round body."},
    {"name": "px_sit_security.png", "w": 128, "h": 128, "desc": "A cute round dark gray slime character sitting on a sturdy chair. Wearing tiny sunglasses and earpiece. Serious stern expression. Casino security guard. Judi-style cute round body with small blush."},
    {"name": "px_sit_shark.png", "w": 128, "h": 128, "desc": "A cute round navy blue slime character sitting on a leather casino chair. Wearing a tiny fedora hat, half-lidded cunning eyes. Calculating predator expression. Card shark. Judi-style cute round body."},
    {"name": "px_sit_lucky.png", "w": 128, "h": 128, "desc": "A cute round bright yellow slime character sitting on a casino chair. Wearing a tiny four-leaf clover pin, surrounded by tiny sparkles. Excited lucky expression with big smile. Lucky player. Judi-style cute round body."},

    # --- WALKING SLIMES (for lobby, no chair) 64x64 ---
    {"name": "px_walk_suit.png", "w": 64, "h": 64, "desc": "A cute round pastel blue slime character walking, no chair. Tiny black suit jacket. Happy walking pose, slight bounce. Judi-style cute round body with blush marks."},
    {"name": "px_walk_casual.png", "w": 64, "h": 64, "desc": "A cute round pastel green slime character walking, no chair. Tiny backwards baseball cap. Casual strolling pose. Judi-style cute round body with blush."},
    {"name": "px_walk_gambler.png", "w": 64, "h": 64, "desc": "A cute round amber-orange slime character walking, no chair. Tiny aviator sunglasses and gold chain. Cool swagger walk. Judi-style cute round body."},
    {"name": "px_walk_dealer.png", "w": 64, "h": 64, "desc": "A cute round emerald green slime character walking, no chair. Dealer visor and vest. Professional stride. Judi-style cute round body."},
    {"name": "px_walk_rookie.png", "w": 64, "h": 64, "desc": "A cute round light pink slime character walking nervously, no chair. Wide eyes, sweat drops. Timid shuffling walk. Judi-style cute round body."},
    {"name": "px_walk_shadow.png", "w": 64, "h": 64, "desc": "A cute round dark purple-black slime character walking mysteriously, no chair. Glowing red eyes, hooded. Gliding walk. Judi-style cute round body."},
    {"name": "px_walk_drunk.png", "w": 64, "h": 64, "desc": "A cute round pink slime character walking wobbly, no chair. Spiral dizzy eyes, holding tiny martini glass, tilting. Silly drunk walk. Judi-style cute round body."},
    {"name": "px_walk_rich.png", "w": 64, "h": 64, "desc": "A cute round golden slime character walking proudly, no chair. Tiny top hat and monocle, nose up. Pompous strut. Judi-style cute round body."},
    {"name": "px_walk_excited.png", "w": 64, "h": 64, "desc": "A cute round bright orange slime character bouncing excitedly, no chair. Arms up, sparkle eyes, tiny stars around. Hyper bounce walk. Judi-style cute round body."},
    {"name": "px_walk_sleepy.png", "w": 64, "h": 64, "desc": "A cute round blue-gray slime character walking drowsily, no chair. Closed sleepy eyes, tiny zzz above head. Slow shuffle. Judi-style cute round body."},

    # --- POI FURNITURE (casino decorations) ---
    {"name": "px_slot_machine.png", "w": 128, "h": 128, "desc": "A casino slot machine with golden trim, three reels showing cherry-bar-seven. Colorful lights on top, lever on right side. Dark metal body."},
    {"name": "px_roulette_table.png", "w": 200, "h": 128, "desc": "A casino roulette table viewed from above at 3/4 angle. Gold trim, dark green felt, roulette wheel with red and black numbers. Elegant casino furniture."},
    {"name": "px_bar_counter.png", "w": 200, "h": 128, "desc": "A dark wooden bar counter with brass rail, bottles on shelves behind, warm amber lighting. Bar stools in front. Casino bar area."},
    {"name": "px_poker_table.png", "w": 200, "h": 200, "desc": "An oval poker table viewed from above. Dark green felt with gold trim border, chip spots marked, card positions. Luxurious casino poker table."},
    {"name": "px_velvet_curtain_L.png", "w": 64, "h": 200, "desc": "A rich dark red velvet curtain draped on the left side with gold tassels and ornate fringe. Hanging from a golden rod at top. Casino theater curtain."},
    {"name": "px_velvet_curtain_R.png", "w": 64, "h": 200, "desc": "A rich dark red velvet curtain draped on the right side with gold tassels and ornate fringe. Hanging from a golden rod at top. Casino theater curtain. Mirror of left."},
    {"name": "px_chandelier.png", "w": 128, "h": 128, "desc": "An ornate crystal chandelier with golden arms, hanging crystals catching warm amber light. Luxury casino ceiling decoration."},
    {"name": "px_neon_jackpot.png", "w": 200, "h": 64, "desc": "A neon sign spelling JACKPOT in golden and red glowing neon tubes. Star decorations on both sides. Bright casino neon sign."},
    {"name": "px_neon_vip.png", "w": 128, "h": 64, "desc": "A neon sign spelling VIP in pink and gold glowing neon tubes with subtle glow halo around letters. Casino VIP sign."},
    {"name": "px_neon_bar.png", "w": 128, "h": 64, "desc": "A neon sign spelling BAR in teal and green glowing neon tubes with subtle glow halo. Casino bar sign."},
    {"name": "px_lucky_cat.png", "w": 64, "h": 64, "desc": "A golden maneki-neko lucky beckoning cat statue with one paw raised, sitting on a red cushion. Casino good luck charm."},
    {"name": "px_trophy.png", "w": 64, "h": 80, "desc": "A golden championship trophy cup with ornate handles on a dark marble pedestal. Engraved winner plate. Casino tournament trophy."},
    {"name": "px_rope_barrier.png", "w": 128, "h": 64, "desc": "A velvet rope barrier with two golden stanchion posts connected by a red velvet rope. VIP area divider. Front view."},
    {"name": "px_jukebox.png", "w": 80, "h": 128, "desc": "A retro jukebox machine with glowing neon teal and red trim, dark body, golden accents, vinyl record visible in dome top. Casino music machine."},
    {"name": "px_fountain.png", "w": 128, "h": 128, "desc": "A small ornamental water fountain with dark stone base, teal water flowing gently upward and cascading down. Casino lobby decoration."},
    {"name": "px_disco_ball.png", "w": 64, "h": 64, "desc": "A mirrored disco ball with tiny reflective squares hanging from a thin chain. Light reflections in gold and mint colors. Casino ceiling decoration."},
    {"name": "px_floor_lamp.png", "w": 48, "h": 128, "desc": "A tall art deco floor lamp with warm amber light glowing from ornate shade. Brass pole on dark base. Casino standing lamp."},
    {"name": "px_cctv.png", "w": 48, "h": 48, "desc": "A small CCTV security camera mounted on a wall bracket. Dark metal body with tiny blinking red LED light. Casino security camera."},
    {"name": "px_chips_pile.png", "w": 80, "h": 64, "desc": "A scattered pile of casino poker chips in stacks. Red, gold, green, and black chips. Decorative chip pile on dark surface."},
    {"name": "px_whiskey.png", "w": 48, "h": 48, "desc": "A crystal whiskey glass with amber liquid and tiny ice cubes. Small casino bar prop."},
    {"name": "px_cigar.png", "w": 48, "h": 48, "desc": "A brass ashtray with a lit cigar producing a thin wisp of smoke. Casino atmosphere prop."},
    {"name": "px_dice.png", "w": 48, "h": 48, "desc": "A pair of red casino dice showing lucky seven, slightly angled for 3D perspective. Casino prop."},
    {"name": "px_card_fan.png", "w": 80, "h": 64, "desc": "A fan of five playing cards spread elegantly showing a royal flush in spades. Gold trimmed card backs visible. Casino decoration."},
    {"name": "px_money_stack.png", "w": 48, "h": 48, "desc": "A neat stack of green cash bills with a golden money clip. Small casino counter prop."},
    {"name": "px_tip_jar.png", "w": 48, "h": 64, "desc": "A glass tip jar half-full of golden coins with a small TIPS label. Casino counter prop."},
    {"name": "px_bouncer.png", "w": 80, "h": 80, "desc": "A large intimidating dark purple round slime character wearing tiny sunglasses and black suit. Arms crossed, tough bouncer pose. Judi-style cute body with blush."},
    {"name": "px_bartender.png", "w": 80, "h": 80, "desc": "A cheerful teal round slime character wearing a bow tie, holding a cocktail shaker. Behind bar counter. Happy expression with blush. Judi-style cute body."},

    # --- BACKGROUNDS ---
    {"name": "px_casino_floor.png", "w": 400, "h": 400, "bg": True, "desc": "A top-down view of a dark VIP underground casino floor. Dark charcoal carpet with golden diamond patterns. Slot machines along left wall, bar area on right, poker tables in center, VIP area at top with velvet ropes. Warm amber and teal neon accent lighting. Rich atmospheric casino interior."},
    {"name": "px_poker_felt_bg.png", "w": 400, "h": 300, "bg": True, "desc": "A top-down view of dark green poker table felt surface with subtle texture pattern. Gold decorative border around edges. Luxurious casino poker table surface background."},
]

def generate(asset):
    name = asset["name"]
    outpath = os.path.join(OUT_DIR, name)
    if os.path.exists(outpath):
        print(f"  SKIP: {name}")
        return True

    params = {
        **BASE_PARAMS,
        "description": asset["desc"],
        "image_size": {"width": asset["w"], "height": asset["h"]},
    }
    
    # Backgrounds keep their background
    if asset.get("bg"):
        params["no_background"] = False
    
    # Large scenes use different view
    if asset["w"] >= 200 or asset["h"] >= 200:
        params["view"] = "high top-down"

    print(f"  GEN: {name} ({asset['w']}x{asset['h']})...", end=" ", flush=True)
    
    try:
        resp = requests.post(
            f"{API_URL}/generate-image-pixflux",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json=params,
            timeout=120,
        )
        if resp.status_code != 200:
            print(f"ERR {resp.status_code}: {resp.text[:200]}")
            return False
        
        data = resp.json()
        img_b64 = data["image"]["base64"]
        img_bytes = base64.b64decode(img_b64)
        
        with open(outpath, "wb") as f:
            f.write(img_bytes)
        
        cost = data.get("usage", {}).get("usd", 0)
        print(f"OK (${cost:.4f}) [{len(img_bytes)} bytes]")
        return True
        
    except Exception as e:
        print(f"FAIL: {e}")
        return False

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    
    total = len(ASSETS)
    ok = 0
    fail = 0
    total_cost = 0.0
    
    print(f"\n🎰 PixelLab Batch Generator — {total} assets")
    print(f"   Quality: MAXIMUM (highly detailed shading, highly detailed)")
    print(f"   Palette: 16-color forced")
    print(f"   Tier: Pixel Architect ($50/mo)\n")
    
    for i, asset in enumerate(ASSETS):
        print(f"[{i+1}/{total}]", end="")
        if generate(asset):
            ok += 1
        else:
            fail += 1
        time.sleep(0.3)  # gentle rate limit
    
    print(f"\n{'='*50}")
    print(f"✅ Success: {ok}/{total}")
    print(f"❌ Failed: {fail}/{total}")
    print(f"📁 Output: {OUT_DIR}")
    print(f"📊 Total PNGs: {len([f for f in os.listdir(OUT_DIR) if f.endswith('.png')])}")

if __name__ == "__main__":
    main()
