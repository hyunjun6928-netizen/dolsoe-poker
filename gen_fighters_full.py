#!/usr/bin/env python3
"""Generate KOF/Samurai Shodown grade fighter assets via PixelLab.
82 frames per fighter × 8 fighters = 656 assets (+ existing fatalities kept)."""

import requests, json, time, os, base64, sys

API = "https://api.pixellab.ai/v1/generate-image-pixflux"
KEY = "c95b6ec2-46fd-4f27-ba91-45c92b181c26"
HDR = {"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"}

FIGHTERS = [
    {"id": "bloodfang", "desc": "muscular red demon warrior, massive battle axe, horned helmet, red skin, glowing eyes, heavy armor plates, demonic"},
    {"id": "ironclaw", "desc": "huge iron golem knight, full plate armor, spiked gauntlets, glowing blue visor, massive tower shield, mechanical joints"},
    {"id": "shadowblade", "desc": "slim ninja assassin in black, dual wielding daggers, face mask, red scarf flowing, agile stance, shadow wisps"},
    {"id": "berserker", "desc": "wild samurai, katana, torn red hakama, bandaged arms, wild hair, battle scars, fierce expression, ronin"},
    {"id": "bonecrusher", "desc": "giant skeleton warrior, bone armor, skull pauldrons, wielding massive bone club, green ghostly flames, undead"},
    {"id": "venomqueen", "desc": "serpent sorceress, purple scales, snake crown, poison dripping staff, forked tongue, hypnotic eyes, elegant deadly"},
    {"id": "hellfire", "desc": "fire elemental fighter, body made of flames and magma, obsidian armor fragments, burning fists, molten eyes, volcanic"},
    {"id": "frostbite", "desc": "ice warrior, crystalline blue armor, frost sword, frozen breath, icicle crown, pale skin, cold aura, glacial"},
]

# Animation frames: (prefix, frame_count, action_description)
ANIMS = [
    # Idle breathing loop
    ("idle", 4, "standing idle fighting stance, {desc}, side view, frame {i}: {detail}",
     ["weight on back foot, arms ready", "slight body rise, breathing in", "peak stance, alert", "settling back down, exhale"]),
    # Walk forward
    ("walk_fwd", 4, "walking forward, {desc}, side view, frame {i}: {detail}",
     ["left foot forward, arms guard", "mid-stride, weight shifting", "right foot forward, balanced", "completing step, resetting"]),
    # Walk backward
    ("walk_back", 4, "walking backward cautiously, {desc}, side view, frame {i}: {detail}",
     ["stepping back with right foot", "weight shifting backward", "left foot retreating", "resetting guard stance"]),
    # Dash forward
    ("dash_fwd", 3, "explosive forward dash lunge, {desc}, side view, frame {i}: {detail}",
     ["crouching to launch, tensed muscles", "mid-dash blur of speed, leaning forward", "landing from dash, skidding"]),
    # Dash backward
    ("dash_back", 3, "quick backward evasive hop, {desc}, side view, frame {i}: {detail}",
     ["pushing off ground backward", "airborne moving back", "landing in guard stance"]),
    # Light attack (jab)
    ("light_atk", 4, "quick light punch or jab attack, {desc}, side view, frame {i}: {detail}",
     ["winding up fist, slight lean", "extending arm, fast strike", "fist at full extension, impact", "retracting arm, returning to stance"]),
    # Heavy attack (big slash/swing)
    ("heavy_atk", 6, "powerful heavy weapon swing overhead, {desc}, side view, frame {i}: {detail}",
     ["raising weapon high overhead, windup", "weapon at peak, muscles tensed", "swinging down with full force", "weapon mid-arc, maximum speed", "impact frame, ground crack effect", "follow through, recovering balance"]),
    # Crouch
    ("crouch", 2, "crouching low defensive position, {desc}, side view, frame {i}: {detail}",
     ["dropping into crouch, knees bending", "fully crouched, compact guard position"]),
    # Crouch attack
    ("crouch_atk", 4, "low sweeping attack from crouch, {desc}, side view, frame {i}: {detail}",
     ["crouched, preparing sweep", "extending low kick or slash", "full sweep extension, low to ground", "retracting back to crouch"]),
    # Jump
    ("jump", 4, "jumping high into air, {desc}, side view, frame {i}: {detail}",
     ["crouching to launch upward", "rising through air, arms up", "at peak height, floating", "descending, preparing to land"]),
    # Air attack
    ("air_atk", 3, "aerial diving attack from above, {desc}, side view, frame {i}: {detail}",
     ["airborne, weapon raised for strike", "diving down with weapon, diagonal slash", "landing from aerial attack"]),
    # Special move 1
    ("special_1", 6, "signature special move energy projectile attack, {desc}, side view, frame {i}: {detail}",
     ["gathering energy, aura glowing", "energy building at hands, particles", "launching projectile, arms thrust forward", "energy beam or projectile mid-flight", "follow through, energy dispersing", "returning to stance, energy fading"]),
    # Special move 2
    ("special_2", 6, "signature rushing special attack charge, {desc}, side view, frame {i}: {detail}",
     ["battle cry, powering up", "launching forward, weapon first", "mid-rush, trailing energy", "striking through enemy position", "past the enemy, weapon extended", "turning back, settling stance"]),
    # Super move
    ("super", 8, "ultimate super move devastating attack, {desc}, side view, frame {i}: {detail}",
     ["dramatic power-up pose, screen darkens", "aura exploding outward, intense glow", "charging with unstoppable force", "unleashing barrage of strikes", "final massive strike, huge impact", "explosion of energy at impact", "debris and particles everywhere", "standing victorious in smoke"]),
    # Hit standing
    ("hit_stand", 3, "getting hit while standing, recoiling in pain, {desc}, side view, frame {i}: {detail}",
     ["impact moment, head snapping back", "body bending backward from force", "staggering, trying to recover"]),
    # Hit crouching
    ("hit_crouch", 2, "getting hit while crouching, pain reaction, {desc}, side view, frame {i}: {detail}",
     ["crouched, impact to face/body", "sliding back from hit, grimacing"]),
    # Guard
    ("guard", 2, "blocking attack in guard stance, {desc}, side view, frame {i}: {detail}",
     ["arms raised blocking, bracing for impact", "absorbing hit, slight pushback, sparks"]),
    # Knockdown
    ("knockdown", 4, "being knocked down to the ground, {desc}, side view, frame {i}: {detail}",
     ["hit hard, flying backward", "spinning in air from impact", "hitting the ground, bounce", "lying on ground, defeated"]),
    # Get up
    ("getup", 3, "getting back up from the ground, {desc}, side view, frame {i}: {detail}",
     ["pushing off ground with arms", "rising to one knee", "standing back up into fighting stance"]),
    # Throw
    ("throw", 4, "grabbing and throwing the enemy, {desc}, side view, frame {i}: {detail}",
     ["reaching out to grab", "gripping enemy, pulling close", "lifting and turning enemy", "slamming enemy to the ground"]),
    # Victory
    ("victory", 4, "victory celebration pose, {desc}, side view, frame {i}: {detail}",
     ["standing tall, weapon raised", "triumphant pose, looking at camera", "signature victory gesture", "final pose, confident smirk"]),
    # Death
    ("death", 4, "collapsing in defeat, {desc}, side view, frame {i}: {detail}",
     ["staggering, losing balance", "falling to knees, weapon dropping", "collapsing forward", "lying motionless on ground"]),
]

def gen_one(fighter_id, anim_name, frame_idx, prompt, outdir):
    """Generate a single frame."""
    outpath = os.path.join(outdir, f"{anim_name}_{frame_idx}.png")
    if os.path.exists(outpath) and os.path.getsize(outpath) > 500:
        return "skip"

    body = {
        "description": f"pixel art fighting game character sprite, {prompt}, transparent background, 16-bit style, detailed shading, clean crisp pixels",
        "text_guidance_scale": 10,
        "outline": "single color black outline",
        "shading": "highly detailed shading",
        "detail": "highly detailed",
        "view": "side",
        "direction": "east",
        "isometric": False,
        "oblique_projection": False,
        "image_size": {"width": 64, "height": 64},
        "no_background": True,
    }

    for attempt in range(3):
        try:
            r = requests.post(API, headers=HDR, json=body, timeout=120)
            if r.status_code == 200:
                d = r.json()
                img = base64.b64decode(d["image"]["base64"])
                with open(outpath, "wb") as f:
                    f.write(img)
                return "ok"
            elif r.status_code == 429:
                print(f"    ⏳ Rate limited, waiting 15s...")
                time.sleep(15)
                continue
            else:
                print(f"    ⚠️ {r.status_code}: {r.text[:100]}")
                return "fail"
        except Exception as e:
            print(f"    ⚠️ Attempt {attempt+1}: {e}")
            time.sleep(5)
    return "fail"

def gen_idle_128(fighter, outdir):
    """Generate 128px idle portrait."""
    outpath = os.path.join(outdir, "idle_portrait.png")
    if os.path.exists(outpath) and os.path.getsize(outpath) > 500:
        print(f"  [idle_portrait] SKIP")
        return

    body = {
        "description": f"pixel art fighting game character portrait, {fighter['desc']}, fighting stance, side view, detailed, menacing, 16-bit style",
        "text_guidance_scale": 10,
        "outline": "single color black outline",
        "shading": "highly detailed shading",
        "detail": "highly detailed",
        "view": "side",
        "direction": "east",
        "isometric": False,
        "oblique_projection": False,
        "image_size": {"width": 128, "height": 128},
        "no_background": True,
    }

    for attempt in range(3):
        try:
            r = requests.post(API, headers=HDR, json=body, timeout=120)
            if r.status_code == 200:
                d = r.json()
                img = base64.b64decode(d["image"]["base64"])
                with open(outpath, "wb") as f:
                    f.write(img)
                print(f"  [idle_portrait] ✅ ({len(img)}B)")
                return
            elif r.status_code == 429:
                time.sleep(15)
                continue
            else:
                print(f"  [idle_portrait] ❌ {r.status_code}")
                return
        except Exception as e:
            print(f"  [idle_portrait] ⚠️ {e}")
            time.sleep(5)
    print(f"  [idle_portrait] ❌ failed after retries")

def main():
    base = os.path.join(os.path.dirname(__file__), "colosseum", "assets")
    total_frames = sum(a[1] for a in ANIMS) * len(FIGHTERS) + len(FIGHTERS)  # +portraits
    done = 0
    ok = 0
    fail = 0
    skip = 0

    print(f"=== KOF-GRADE FIGHTER ASSET GENERATION ===")
    print(f"Total: {total_frames} frames ({len(FIGHTERS)} fighters × {sum(a[1] for a in ANIMS)} frames + {len(FIGHTERS)} portraits)")
    print()

    for fi, fighter in enumerate(FIGHTERS):
        outdir = os.path.join(base, fighter["id"])
        os.makedirs(outdir, exist_ok=True)
        print(f"\n{'='*60}")
        print(f"Fighter {fi+1}/{len(FIGHTERS)}: {fighter['id']}")
        print(f"{'='*60}")

        # Portrait
        gen_idle_128(fighter, outdir)
        done += 1

        # All animations
        for anim_prefix, frame_count, prompt_tmpl, details in ANIMS:
            for i in range(frame_count):
                prompt = prompt_tmpl.format(desc=fighter["desc"], i=i+1, detail=details[i])
                print(f"  [{anim_prefix}_{i}] ", end="", flush=True)
                result = gen_one(fighter["id"], anim_prefix, i, prompt, outdir)
                done += 1
                if result == "ok":
                    ok += 1
                    print(f"✅")
                elif result == "skip":
                    skip += 1
                    print(f"SKIP")
                else:
                    fail += 1
                    print(f"❌")

                # Progress
                if done % 10 == 0:
                    print(f"  --- Progress: {done}/{total_frames} ({ok} ok, {skip} skip, {fail} fail) ---")

                time.sleep(0.5)  # Gentle rate limiting

    print(f"\n{'='*60}")
    print(f"COMPLETE: {done}/{total_frames}")
    print(f"  ✅ Generated: {ok}")
    print(f"  ⏭️ Skipped: {skip}")
    print(f"  ❌ Failed: {fail}")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
