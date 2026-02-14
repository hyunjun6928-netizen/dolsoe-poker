#!/usr/bin/env python3
"""PixelLab Colosseum Character Generator — gore fighting game assets"""
import json, base64, time, sys, os, requests, struct, zlib

API_KEY = os.environ.get("PIXELLAB_API_KEY", "")
API_URL = "https://api.pixellab.ai/v1"
OUT_DIR = os.path.join(os.path.dirname(__file__), "colosseum", "assets")

# Dark gore palette — blood reds, bone whites, shadow blacks, steel grays
GORE_PALETTE = [
    (5,5,10),(20,8,8),(45,12,12),(80,15,15),       # blacks → dark blood
    (140,20,20),(180,30,30),(210,50,40),(240,80,60), # blood reds
    (60,55,50),(100,95,85),(140,135,125),(180,175,165), # bone/steel grays
    (200,180,140),(230,210,170),(50,70,90),(80,120,160), # bone white, steel blue
]

def make_palette_png(palette):
    w, h = 4, 4
    raw = b''
    for y in range(h):
        raw += b'\x00'
        for x in range(w):
            idx = y * w + x
            r, g, b = palette[idx]
            raw += struct.pack('BBB', r, g, b)
    def chunk(ctype, data):
        c = ctype + data
        return struct.pack('>I', len(data)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0))
    idat = chunk(b'IDAT', zlib.compress(raw))
    iend = chunk(b'IEND', b'')
    return base64.b64encode(sig + ihdr + idat + iend).decode()

PALETTE_B64 = make_palette_png(GORE_PALETTE)

BASE = {
    "outline": "single color black outline",
    "shading": "highly detailed shading",
    "detail": "highly detailed",
    "view": "side",
    "direction": "east",
    "no_background": True,
    "text_guidance_scale": 10,
    "color_image": {"type": "base64", "base64": PALETTE_B64},
}

# 8 fighters — each gets idle sprite, then we animate
FIGHTERS = [
    {
        "id": "bloodfang",
        "name": "블러드팡",
        "weapon": "giant battle axe",
        "desc": "A muscular fierce warrior slime with razor-sharp teeth dripping saliva and glowing blood-red eyes. Dark crimson body covered in deep battle scars and dried blood stains. Wearing spiked bone shoulder armor with enemy teeth trophies. Holding a massive double-headed battle axe with a chipped blade still dripping fresh blood. Veins pulsing visibly on body. Aggressive berserker fighting stance. Pixel art mature fighting game character.",
        "color": "#8C1414",
    },
    {
        "id": "ironclaw",
        "name": "아이언클로",
        "weapon": "heavy iron mace",
        "desc": "A hulking gray armored slime covered in bolted iron plates with dents and scratches from battle. Glowing menacing yellow eyes behind a cracked steel visor helmet with blood splatter. Massive spiked iron mace with chunks of flesh still stuck on spikes. Chains wrapped around one arm. Tank-like crushing stance. Pixel art mature fighting game character.",
        "color": "#646055",
    },
    {
        "id": "shadowblade",
        "name": "쉐도우",
        "weapon": "twin daggers",
        "desc": "A sleek dark purple-black slime assassin with piercing glowing cyan eyes in darkness. Wearing a blood-stained tattered dark cloak and hood with skull clasp. Holding twin curved serrated daggers dripping green venom and blood. Shadowy smoke tendrils emanating from body. Silent killer crouching stance. Pixel art mature fighting game character.",
        "color": "#321450",
    },
    {
        "id": "berserker",
        "name": "버서커",
        "weapon": "katana",
        "desc": "A wild blood-soaked crimson slime with flame-like hair tendrils and completely crazed spiral eyes with burst blood vessels. Shirtless body covered in self-inflicted ritual scars that glow with inner fire. Mouth open in eternal scream showing jagged teeth. Wielding a blood-grooved katana with a notched blade. Berserk rage stance with veins bulging. Pixel art mature fighting game character.",
        "color": "#B41E1E",
    },
    {
        "id": "bonecrusher",
        "name": "본크러셔",
        "weapon": "giant warhammer",
        "desc": "A massive pale bone-white slime with a skull face, hollow black eye sockets with tiny red pinpoint pupils. Wearing armor assembled from enemy bones — ribcage chestplate, skull pauldrons, spine gauntlets. Carrying an enormous warhammer with a head made from a giant skull filled with concrete, handle wrapped in skin leather. Gore-splattered. Heavy executioner stance. Pixel art mature fighting game character.",
        "color": "#C8B48C",
    },
    {
        "id": "venomqueen",
        "name": "베놈퀸",
        "weapon": "poison whip",
        "desc": "A sinister toxic green-purple slime with multiple spider-like red eyes and corrosive acid drool melting the ground. Wearing a crown of thorny vines with poisonous flowers and impaled tiny skulls. Body surface has bubbling toxic pustules. Wielding a barbed poison whip with hooks that tear flesh, acid dripping and sizzling. Seductive but deadly stance. Pixel art mature fighting game character.",
        "color": "#2D5A1E",
    },
    {
        "id": "hellfire",
        "name": "헬파이어",
        "weapon": "flaming sword",
        "desc": "A blazing infernal orange-red slime with actual hellfire erupting from cracks in body. Twisted demonic horns, ember eyes with flame pupils. Charred black patches on body revealing molten core underneath. Holding a massive greatsword completely engulfed in hellfire with a blade that glows white-hot. Surrounded by floating burning embers and ash. Ground beneath cracking from heat. Demonic battle stance. Pixel art mature fighting game character.",
        "color": "#D43218",
    },
    {
        "id": "frostbite",
        "name": "프로스트바이트",
        "weapon": "ice spear",
        "desc": "A crystalline ice-blue slime with jagged frozen spikes and icicles protruding violently from body. Cracked frozen skin texture with blue-black frostbitten patches. Breath visible as freezing cold mist that flash-freezes nearby air. Dead frozen eyes with ice crystal irises. Holding a massive jagged ice spear with frozen blood crystals embedded in it and a victim's frozen hand still gripping the shaft. Frigid death-bringer stance. Pixel art mature fighting game character.",
        "color": "#5078A0",
    },
]

# Animation types to generate per fighter
ANIMS = [
    {"id": "idle", "text": "character standing in idle fighting stance, breathing animation, slight bounce"},
    {"id": "walk", "text": "character walking forward aggressively, weapon ready"},
    {"id": "attack", "text": "character swinging weapon in powerful slash attack, motion blur on weapon"},
    {"id": "hit", "text": "character recoiling from being hit, pain expression, blood splatter"},
    {"id": "death", "text": "character collapsing and melting into a pool of blood, dramatic death"},
    {"id": "victory", "text": "character raising weapon triumphantly, roaring, blood dripping"},
]

# FATALITY gore animations
FATALITIES = [
    {"id": "head_off", "text": "character's head gets sliced clean off by a blade, massive blood fountain spraying upward from neck stump, head spinning in air with shocked expression, body standing for a moment with blood gushing before collapsing, pool of blood forming on ground"},
    {"id": "bisect", "text": "character gets sliced perfectly in half vertically from head to groin, the two halves slowly sliding apart revealing cross-section of organs and spine, intestines spilling out between the halves, massive blood waterfall, both halves twitching on the ground"},
    {"id": "explode", "text": "character's body swells and then violently explodes into bloody chunks of flesh, bone fragments, eyeballs, and organs flying in all directions, massive blood splatter painting the entire screen red, a spine lands standing upright"},
    {"id": "impale", "text": "a giant spear impales character through the chest from behind, tip bursting out through ribcage with heart still on it, character lifted off ground choking on blood, blood pouring down the spear shaft, legs dangling and twitching"},
    {"id": "spine_rip", "text": "victorious character reaches into defeated enemy's back and rips out their entire spine with skull still attached, holding it up as trophy while blood rains down, defeated body crumples into boneless heap"},
    {"id": "dissolve", "text": "acid melts character alive from feet up, skin dissolving to reveal muscle then bone then nothing, character screaming in agony reaching upward as body dissolves into a bubbling pool of gore and acid"},
]

def generate_image(desc, w, h, extra_params=None):
    params = {**BASE, "description": desc, "image_size": {"width": w, "height": h}}
    if extra_params:
        params.update(extra_params)
    resp = requests.post(f"{API_URL}/generate-image-pixflux",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json=params, timeout=120)
    if resp.status_code != 200:
        print(f"  ERR {resp.status_code}: {resp.text[:200]}")
        return None
    data = resp.json()
    return base64.b64decode(data["image"]["base64"])

def estimate_skeleton(img_b64, w, h):
    resp = requests.post(f"{API_URL}/estimate-skeleton",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"image": {"type": "base64", "base64": img_b64}, "image_size": {"width": w, "height": h}},
        timeout=60)
    if resp.status_code != 200:
        print(f"  SKELETON ERR {resp.status_code}: {resp.text[:200]}")
        return None
    return resp.json()

def animate_with_skeleton(img_b64, skeleton_data, desc, w, h):
    resp = requests.post(f"{API_URL}/animate-with-skeleton",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={
            "description": desc,
            "image": {"type": "base64", "base64": img_b64},
            "skeleton": skeleton_data,
            "image_size": {"width": w, "height": h},
            "no_background": True,
            "outline": "single color black outline",
            "shading": "highly detailed shading",
            "detail": "highly detailed",
        },
        timeout=120)
    if resp.status_code != 200:
        print(f"  ANIM ERR {resp.status_code}: {resp.text[:200]}")
        return None
    return resp.json()

def animate_with_text(ref_b64, char_desc, action_desc, w=64, h=64, n_frames=4):
    # animate-with-text max is 64x64
    body = {
        "description": char_desc,
        "action": action_desc,
        "image_size": {"width": min(w,64), "height": min(h,64)},
        "n_frames": n_frames,
        "view": "side",
        "direction": "east",
    }
    if ref_b64:
        body["reference_image"] = {"type": "base64", "base64": ref_b64}
    
    resp = requests.post(f"{API_URL}/animate-with-text",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json=body,
        timeout=120)
    if resp.status_code != 200:
        print(f"  TEXT-ANIM ERR {resp.status_code}: {resp.text[:200]}")
        return None
    return resp.json()

def rotate_character(img_b64, w, h, directions=None):
    """Generate 8-directional views"""
    if directions is None:
        directions = ["north","north-east","east","south-east","south","south-west","west","north-west"]
    results = {}
    for d in directions:
        resp = requests.post(f"{API_URL}/rotate",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json={
                "init_image": {"type": "base64", "base64": img_b64},
                "image_size": {"width": w, "height": h},
                "direction": d,
                "no_background": True,
                "outline": "single color black outline",
                "shading": "highly detailed shading",
                "detail": "highly detailed",
            },
            timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            results[d] = base64.b64decode(data["image"]["base64"])
            print(f"    ROT {d} OK")
        else:
            print(f"    ROT {d} ERR {resp.status_code}")
        time.sleep(0.3)
    return results

def save(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    SIZE = 128  # Character sprite size
    
    print(f"\n⚔️  COLOSSEUM CHARACTER GENERATOR")
    print(f"   Fighters: {len(FIGHTERS)}")
    print(f"   Anims per fighter: {len(ANIMS)}")
    print(f"   Fatalities: {len(FATALITIES)}")
    print(f"   Size: {SIZE}x{SIZE}\n")
    
    for fi, fighter in enumerate(FIGHTERS):
        fdir = os.path.join(OUT_DIR, fighter["id"])
        idle_path = os.path.join(fdir, "idle.png")
        
        print(f"\n[{fi+1}/{len(FIGHTERS)}] === {fighter['name']} ({fighter['id']}) ===")
        
        # 1. Generate idle sprite
        if not os.path.exists(idle_path):
            print(f"  Generating idle sprite...")
            img = generate_image(fighter["desc"], SIZE, SIZE)
            if img:
                save(idle_path, img)
                print(f"  ✅ idle.png [{len(img)} bytes]")
            else:
                print(f"  ❌ FAILED idle — skipping fighter")
                continue
            time.sleep(0.5)
        else:
            print(f"  SKIP idle.png (exists)")
        
        # Read idle for further processing
        with open(idle_path, "rb") as f:
            idle_b64 = base64.b64encode(f.read()).decode()
        
        # 1b. Generate 64x64 version for animations
        idle64_path = os.path.join(fdir, "idle_64.png")
        if not os.path.exists(idle64_path):
            print(f"  Generating 64x64 idle for animations...")
            img64 = generate_image(fighter["desc"], 64, 64)
            if img64:
                save(idle64_path, img64)
                print(f"  ✅ idle_64.png [{len(img64)} bytes]")
            time.sleep(0.3)
        
        # Read 64x64 idle for animations
        idle64_b64 = None
        if os.path.exists(idle64_path):
            with open(idle64_path, "rb") as f:
                idle64_b64 = base64.b64encode(f.read()).decode()
        
        # 2. Estimate skeleton
        skel_path = os.path.join(fdir, "skeleton.json")
        if not os.path.exists(skel_path):
            print(f"  Estimating skeleton...")
            skel = estimate_skeleton(idle_b64, SIZE, SIZE)
            if skel:
                with open(skel_path, "w") as f:
                    json.dump(skel, f)
                print(f"  ✅ skeleton.json")
            time.sleep(0.3)
        
        # 3. Generate animations via animate-with-text
        for anim in ANIMS:
            anim_path = os.path.join(fdir, f"{anim['id']}.png")
            if os.path.exists(anim_path):
                print(f"  SKIP {anim['id']}.png")
                continue
            print(f"  Animating: {anim['id']}...", end=" ", flush=True)
            result = animate_with_text(idle64_b64, fighter["desc"], anim["text"], 64, 64, n_frames=4)
            if result and "image" in result:
                img = base64.b64decode(result["image"]["base64"])
                save(anim_path, img)
                print(f"OK [{len(img)} bytes]")
            elif result and "images" in result:
                # Sprite sheet — save all frames
                for i, frame in enumerate(result["images"]):
                    frame_path = os.path.join(fdir, f"{anim['id']}_{i}.png")
                    img = base64.b64decode(frame["base64"])
                    save(frame_path, img)
                print(f"OK [{len(result['images'])} frames]")
            else:
                print("FAIL")
            time.sleep(0.5)
        
        # 4. Generate FATALITY animations (shared across fighters)
        for fatal in FATALITIES:
            fatal_path = os.path.join(fdir, f"fatal_{fatal['id']}.png")
            if os.path.exists(fatal_path):
                print(f"  SKIP fatal_{fatal['id']}.png")
                continue
            print(f"  FATALITY: {fatal['id']}...", end=" ", flush=True)
            result = animate_with_text(idle64_b64, fighter["desc"], fatal["text"], 64, 64, n_frames=4)
            if result and "image" in result:
                img = base64.b64decode(result["image"]["base64"])
                save(fatal_path, img)
                print(f"OK [{len(img)} bytes]")
            elif result and "images" in result:
                for i, frame in enumerate(result["images"]):
                    frame_path = os.path.join(fdir, f"fatal_{fatal['id']}_{i}.png")
                    img = base64.b64decode(frame["base64"])
                    save(frame_path, img)
                print(f"OK [{len(result['images'])} frames]")
            else:
                print("FAIL")
            time.sleep(0.5)
        
        # 5. 4-directional rotation (for movement)
        for d in ["east", "west", "south", "north"]:
            rot_path = os.path.join(fdir, f"dir_{d}.png")
            if os.path.exists(rot_path):
                continue
            print(f"  Rotating: {d}...", end=" ", flush=True)
            rots = rotate_character(idle_b64, SIZE, SIZE, [d])
            if d in rots:
                save(rot_path, rots[d])
                print(f"OK")
            time.sleep(0.3)
    
    # Count total assets
    total = sum(len(files) for _, _, files in os.walk(OUT_DIR))
    print(f"\n{'='*50}")
    print(f"⚔️  COLOSSEUM ASSETS COMPLETE")
    print(f"   Total files: {total}")
    print(f"   Output: {OUT_DIR}")

if __name__ == "__main__":
    main()
