#!/bin/bash
# Generate all missing casino pixel art assets
set -e
SCRIPT="/home/jeet/.nvm/versions/node/v24.13.0/lib/node_modules/openclaw/skills/openai-image-gen/scripts/gen.py"
OUT="/home/jeet/.openclaw/workspace/cloud_poker/assets/slimes"
PALETTE="16-color palette: #050F1A #221C20 #073935 #4D2C2C #704637 #126D65 #8F604C #D24C59 #9D7F33 #C17F54 #938B7B #35B97D #69B5A8 #F09858 #FCC88E #A2E3CA"
STYLE="16-bit pixel art, crisp pixels, no blur, dithering only, 1px dark outline #050F1A, transparent background, top-down 3/4 perspective"

gen() {
  local name="$1"
  local prompt="$2"
  if [ -f "$OUT/$name" ]; then
    echo "SKIP: $name (exists)"
    return
  fi
  echo "GEN: $name"
  python3 "$SCRIPT" --model gpt-image-1 --quality high --size 1024x1024 --background transparent --output-format png --count 1 --out-dir "/tmp/pixgen_$$" --prompt "$prompt"
  cp /tmp/pixgen_$$/image_*.png "$OUT/$name" 2>/dev/null || cp /tmp/pixgen_$$/*.png "$OUT/$name"
  rm -rf /tmp/pixgen_$$
  echo "DONE: $name"
}

# === NEW POI ASSETS ===
gen "roulette_table.png" "$STYLE. A small pixel art roulette table with gold trim, dark green felt, seen from above at 3/4 angle. Casino furniture. $PALETTE"
gen "poker_chips_pile.png" "$STYLE. A scattered pile of casino poker chips in red, gold, green, and black colors. Pixel art, small decorative element. $PALETTE"
gen "whiskey_glass.png" "$STYLE. A crystal whiskey glass with amber liquid and ice cubes, pixel art, small object on dark surface. $PALETTE"
gen "cigar_ashtray.png" "$STYLE. A brass ashtray with a lit cigar producing a thin smoke trail, pixel art casino prop. $PALETTE"
gen "dice_pair.png" "$STYLE. A pair of casino dice showing lucky 7, red with white dots, pixel art small prop. $PALETTE"
gen "trophy_cup.png" "$STYLE. A golden trophy cup with pixel art style, ornate handles, sitting on a small pedestal. Casino championship trophy. $PALETTE"
gen "bouncer_slime.png" "$STYLE. A large intimidating dark purple slime character wearing sunglasses and a black suit, arms crossed, bouncer/security guard pose. Cute but tough pixel art. $PALETTE"
gen "bartender_slime.png" "$STYLE. A cheerful teal slime character behind a bar counter, wearing a bow tie, mixing a cocktail with a shaker. Pixel art, cute round body. $PALETTE"
gen "dealer_slime_standing.png" "$STYLE. A professional-looking emerald green slime character in a dealer vest and visor, holding a deck of cards. Standing pose, pixel art. $PALETTE"
gen "drunk_slime.png" "$STYLE. A wobbly pink slime character with spiral eyes and rosy cheeks, holding a martini glass, slightly tilting. Drunk and happy pixel art. $PALETTE"
gen "rich_slime.png" "$STYLE. A gold-colored slime character wearing a top hat and monocle, sitting on a pile of coins. VIP wealthy pixel art character. $PALETTE"
gen "lucky_cat.png" "$STYLE. A pixel art maneki-neko (lucky beckoning cat) statue in gold, with one paw raised, sitting on a red cushion. Casino good luck charm. $PALETTE"
gen "velvet_curtain.png" "$STYLE. A rich dark red velvet curtain draped elegantly, pixel art, with gold tassels and fringe. Casino theater decoration. $PALETTE"
gen "neon_sign_vip.png" "$STYLE. A glowing neon sign spelling 'VIP' in pink and gold neon tubes, pixel art, dark background glow effect. $PALETTE"
gen "neon_sign_bar.png" "$STYLE. A glowing neon sign spelling 'BAR' in teal and green neon tubes, pixel art, subtle glow. $PALETTE"
gen "neon_sign_jackpot.png" "$STYLE. A flashing neon sign spelling 'JACKPOT' in gold and red neon tubes with star decorations, pixel art. $PALETTE"
gen "floor_lamp.png" "$STYLE. A tall art deco floor lamp with warm amber light glow, brass pole, pixel art casino decoration. $PALETTE"
gen "card_fan.png" "$STYLE. A fan of 5 playing cards (royal flush) spread out elegantly, pixel art, gold-trimmed card backs visible. $PALETTE"
gen "gold_rope_barrier.png" "$STYLE. A velvet rope barrier with gold stanchion posts, pixel art, VIP area divider. $PALETTE"
gen "confetti_burst.png" "$STYLE. A burst of colorful confetti and streamers exploding outward, pixel art celebration effect, transparent background. $PALETTE"
gen "gold_coin_rain.png" "$STYLE. Gold coins falling/raining down, various sizes and angles, pixel art celebration effect, transparent background. $PALETTE"
gen "screen_crack.png" "$STYLE. A dramatic screen crack/shatter effect radiating from center, pixel art, white and light blue crack lines on transparent background. $PALETTE"
gen "god_ray.png" "$STYLE. Diagonal light rays/god rays streaming down from upper left, soft warm gold light beams, pixel art atmospheric effect, transparent background. $PALETTE"
gen "smoke_ambient.png" "$STYLE. Soft ambient smoke/haze wisps floating horizontally, very subtle and thin, pixel art atmospheric effect, transparent background. $PALETTE"

echo "=== ALL DONE ==="
