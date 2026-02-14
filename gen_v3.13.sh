#!/bin/bash
set -e
export OPENAI_API_KEY="${OPENAI_API_KEY}"
SCRIPT="/home/jeet/.nvm/versions/node/v24.13.0/lib/node_modules/openclaw/skills/openai-image-gen/scripts/gen.py"
OUT="/home/jeet/.openclaw/workspace/cloud_poker/assets/slimes"
PAL="Use ONLY these 16 colors: #050F1A #221C20 #073935 #4D2C2C #704637 #126D65 #8F604C #D24C59 #9D7F33 #C17F54 #938B7B #35B97D #69B5A8 #F09858 #FCC88E #A2E3CA"
STY="16-bit pixel art, crisp pixels, no anti-aliasing, no blur, dithering only, 1px dark outline using #050F1A, transparent background, 3/4 top-down perspective"

gen() {
  local name="$1"; local prompt="$2"
  if [ -f "$OUT/$name" ]; then echo "SKIP: $name"; return; fi
  echo ">>> GEN: $name"
  local tmp="/tmp/pxgen_${name%.*}_$$"
  python3 "$SCRIPT" --model gpt-image-1 --quality high --size 1024x1024 --background transparent --output-format png --count 1 --out-dir "$tmp" --prompt "$prompt"
  cp "$tmp"/image_*.png "$OUT/$name" 2>/dev/null || cp "$tmp"/*.png "$OUT/$name"
  rm -rf "$tmp"
  echo "<<< DONE: $name"
}

# === NEW CHARACTER SLIMES (for lobby & crowd) ===
gen "bouncer_slime.png" "$STY. A large intimidating dark purple (#221C20, #4D2C2C) round slime character wearing tiny pixel sunglasses and a black suit jacket. Arms crossed pose, tough bouncer/security guard. Cute Judi-style round body with blush marks. $PAL"

gen "bartender_slime.png" "$STY. A cheerful teal (#126D65, #69B5A8) round slime character wearing a small bow tie, holding a pixel cocktail shaker. Behind a tiny bar counter. Cute round body with happy expression and blush. $PAL"

gen "dealer_slime_standing.png" "$STY. A professional emerald green (#073935, #35B97D) round slime character wearing a dealer visor and vest, holding a tiny deck of cards. Standing pose. Cute Judi-style with focused expression. $PAL"

gen "drunk_slime.png" "$STY. A wobbly pink (#D24C59, #FCC88E) round slime character with spiral dizzy eyes and rosy cheeks, holding a tiny martini glass, slightly tilting to one side. Cute and silly pixel art. $PAL"

gen "rich_slime.png" "$STY. A golden (#9D7F33, #FCC88E) round slime character wearing a tiny top hat and monocle, sitting on a small pile of gold coins. VIP wealthy look. Cute Judi-style with smug expression. $PAL"

gen "sleepy_slime.png" "$STY. A blue-gray (#938B7B, #69B5A8) round slime character with closed sleepy eyes and a tiny 'zzz' above head, slightly slumped. Cute Judi-style drowsy expression. $PAL"

gen "excited_slime.png" "$STY. A bright orange (#F09858, #FCC88E) round slime character with wide sparkling eyes, tiny arms raised up in excitement, small star effects around. Cute hyper-excited pixel art. $PAL"

gen "nervous_slime.png" "$STY. A pale mint (#A2E3CA, #69B5A8) round slime character with sweat drops, biting lip expression, tiny hands fidgeting. Anxious/nervous cute pixel art slime. $PAL"

# === NEW POI FURNITURE/DECORATIONS ===
gen "roulette_table.png" "$STY. A small pixel art roulette table with gold (#9D7F33) trim, dark green (#073935) felt, roulette wheel visible from top-down 3/4 angle. Casino furniture piece. $PAL"

gen "poker_chips_pile.png" "$STY. A scattered pile of casino poker chips in stacks, colors: red (#D24C59), gold (#9D7F33), green (#35B97D), black (#221C20). Small decorative pile. $PAL"

gen "whiskey_glass.png" "$STY. A crystal whiskey glass with amber (#F09858) liquid and tiny ice cubes on a dark surface. Small pixel art casino prop. $PAL"

gen "cigar_ashtray.png" "$STY. A brass (#C17F54) ashtray with a lit cigar producing a thin smoke wisp. Small pixel art casino atmosphere prop. $PAL"

gen "dice_pair.png" "$STY. A pair of casino dice showing lucky 7, red (#D24C59) with white dots, slightly angled for 3D feel. Small pixel art prop. $PAL"

gen "trophy_cup.png" "$STY. A golden (#9D7F33, #FCC88E) championship trophy cup with ornate handles on a small dark pedestal. Pixel art casino trophy. $PAL"

gen "lucky_cat.png" "$STY. A pixel art maneki-neko golden (#FCC88E, #9D7F33) lucky beckoning cat statue with one paw raised, sitting on a red (#D24C59) cushion. Casino good luck charm. $PAL"

gen "velvet_curtain_left.png" "$STY. A rich dark red (#4D2C2C, #D24C59) velvet curtain draped on the left side, with gold (#9D7F33) tassels and fringe. Casino theater decoration, hanging from top. $PAL"

gen "velvet_curtain_right.png" "$STY. A rich dark red (#4D2C2C, #D24C59) velvet curtain draped on the right side, with gold (#9D7F33) tassels and fringe. Casino theater decoration, hanging from top. Mirror of left curtain. $PAL"

gen "neon_sign_vip.png" "$STY. A glowing neon sign spelling 'VIP' in pink (#D24C59) and gold (#9D7F33) neon tubes, with subtle glow halo effect around letters. Pixel art sign. $PAL"

gen "neon_sign_bar.png" "$STY. A glowing neon sign spelling 'BAR' in teal (#126D65) and green (#35B97D) neon tubes, with subtle glow halo. Pixel art neon sign. $PAL"

gen "neon_sign_jackpot.png" "$STY. A flashing neon sign spelling 'JACKPOT' with gold (#FCC88E) and red (#D24C59) neon tubes, star decorations on sides. Pixel art neon sign. $PAL"

gen "floor_lamp.png" "$STY. A tall art deco floor lamp with warm amber (#F09858) light glow from shade, brass (#C17F54) pole on dark base. Pixel art casino standing lamp. $PAL"

gen "card_fan.png" "$STY. A fan of 5 playing cards (royal flush, spades) spread elegantly, pixel art style with gold (#9D7F33) trimmed card backs partially visible. $PAL"

gen "gold_rope_barrier.png" "$STY. A velvet rope barrier with gold (#9D7F33) stanchion posts connected by a red (#D24C59) velvet rope. Pixel art VIP area divider, front view. $PAL"

gen "cctv_camera.png" "$STY. A small CCTV security camera mounted on a bracket, dark metal (#221C20, #938B7B) body with a tiny red (#D24C59) LED light. Pixel art casino security prop. $PAL"

gen "tip_jar.png" "$STY. A glass tip jar half-full of coins (#9D7F33, #FCC88E), with a small 'TIPS' label. Pixel art casino counter prop. $PAL"

gen "money_stack.png" "$STY. A neat stack of cash bills in green (#073935, #35B97D) with a gold (#9D7F33) money clip. Small pixel art decoration. $PAL"

gen "disco_ball.png" "$STY. A small mirrored disco ball with tiny reflective squares, hanging from a thin chain. Light reflections in gold (#FCC88E) and mint (#A2E3CA). Pixel art. $PAL"

gen "jukebox.png" "$STY. A retro pixel art jukebox machine with glowing neon (#35B97D, #D24C59) trim, dark body (#221C20), gold (#9D7F33) accents, and a vinyl record visible. $PAL"

gen "fountain_small.png" "$STY. A small ornamental water fountain with dark stone (#221C20) base, water in teal (#69B5A8, #A2E3CA) flowing gently. Pixel art casino lobby decoration. $PAL"

echo ""
echo "=== ALL ASSETS GENERATED ==="
ls -la "$OUT"/*.png | wc -l
