# 🎨 Casino Pixel Art Palette & Asset Spec

## 16-Color Palette (Dark → Light)

| # | HEX | Name | Usage |
|---|---------|------|-------|
| 0 | `#050F1A` | Deep Navy | 바닥/그림자 바탕, 최암부 |
| 1 | `#221C20` | Dark Purple-Gray | 벽/음영, 패널 배경 |
| 2 | `#073935` | Deep Teal | 네온/유리 음영, 어두운 포인트 |
| 3 | `#4D2C2C` | Dark Maroon | 가죽/목재 그림자 |
| 4 | `#704637` | Brown | 가구 본체, 바 카운터 |
| 5 | `#126D65` | Teal | 네온 라인/포인트 |
| 6 | `#8F604C` | Tan Brown | 목재 하이라이트 |
| 7 | `#D24C59` | Red | 경고/사인/포인트 |
| 8 | `#9D7F33` | Gold | 테두리/장식/프리미엄 |
| 9 | `#C17F54` | Orange Bronze | 조명 반사 |
| 10 | `#938B7B` | Dusty Gray | 금속/먼지톤 |
| 11 | `#35B97D` | Neon Green | 버튼/사인/활성 |
| 12 | `#69B5A8` | Mint Teal | 유리/빛 번짐 |
| 13 | `#F09858` | Amber | 조명 강조 |
| 14 | `#FCC88E` | Light Peach | 피부톤/하이라이트 |
| 15 | `#A2E3CA` | Pale Mint | 광원/글로우 끝 |

---

## 공통 프롬프트 프리픽스 (모든 에셋에 필수 삽입)

```
16-bit pixel art, crisp pixels, no anti-aliasing, no blur.
Use ONLY these 16 colors: #050F1A #221C20 #073935 #4D2C2C #704637 #126D65 #8F604C #D24C59 #9D7F33 #C17F54 #938B7B #35B97D #69B5A8 #F09858 #FCC88E #A2E3CA
No additional colors, no gradients. Shading via dithering only.
Single light source from upper-left. Subtle rim-light on upper-right edges.
1px dark outline (#050F1A) on all objects.
Transparent PNG background.
```

---

## 에셋 규격표

### 1. 슬라임 캐릭터 (Slimes)

| Asset | Size | Frames | Notes |
|-------|------|--------|-------|
| `sit_*.png` | 64×64 | 1 | 의자 통합, 정면 3/4뷰 |
| `walk_*.png` | 64×64 ×4 | 4 (horizontal strip) | 로비 워커용 (idle/step1/step2/bounce) |
| `expression_*.png` | 32×32 | 1 | 감정 오버레이 (위에 얹힘) |
| `slime_set_unified.png` | 64×64 ×12 | 12 (4×3 grid) | 전체 슬라임 종류 한 장 |

**슬라임 종류 (12종):**
suit, casual, hoodie, bartender, gambler, dealer, security, vip, rookie, veteran, wildcard, shadow

**프롬프트:**
```
[공통 프리픽스]
Cute round pastel slime character sitting on a small dark wooden chair with gold trim.
The slime has dot eyes, rosy cheeks, and a [OUTFIT] outfit.
3/4 top-down perspective. 64x64 pixels.
```

### 2. 슬롯머신 (Slot Machine)

| Asset | Size | Frames | Notes |
|-------|------|--------|-------|
| `slot_machine.png` | 96×96 | 1 | 정적 아이콘 (로비 POI) |
| `slot_anim.png` | 96×96 ×6 | 6 (3×2 grid) | 레버→릴→잭팟 시퀀스 |

**프롬프트 (정적):**
```
[공통 프리픽스]
Pixel art slot machine. Gold-trimmed dark body (#221C20 base, #9D7F33 trim),
neon green (#35B97D) accents, small pixel screen showing "777",
lever on right side (#938B7B metal with #D24C59 ball top).
96x96 pixels.
```

**프롬프트 (애니메이션 6프레임):**
```
[공통 프리픽스]
6-frame pixel art sprite sheet, 96x96 per frame, arranged in 3x2 grid.
Slot machine animation sequence:
F1: idle with subtle neon glow pulse
F2: lever pulled down (lever rotates 45°)
F3: reels spinning (dithered motion blur on screen)
F4: reels slowing (partial symbols visible)
F5: reels stopped + small flash (#A2E3CA)
F6: jackpot sparkle + 3 coins popping out (#9D7F33 coins)
96x96 per frame. Total sheet: 288x192.
```

### 3. 바 카운터 (Bar)

| Asset | Size | Frames | Notes |
|-------|------|--------|-------|
| `bar_counter.png` | 128×96 | 1 | 바 전체 (병, 잔, 네온사인) |
| `bartender_slime.png` | 64×64 | 1 | 바텐더 슬라임 단독 |
| `bartender_anim.png` | 64×64 ×4 | 4 (horizontal) | 칵테일 셰이킹 시퀀스 |
| `drink_glass.png` | 16×16 | 1 | 개별 잔 (로비 이펙트용) |

**프롬프트 (바 카운터):**
```
[공통 프리픽스]
Pixel art casino bar counter scene. Wooden counter (#704637 base, #8F604C highlight, #9D7F33 gold edge trim).
Behind: 3 bottle shelves with colorful bottles (#D24C59 red, #126D65 teal, #F09858 amber).
Above: small neon sign reading "BAR" in #35B97D glow.
One cocktail glass on counter with subtle #A2E3CA glow.
3/4 top-down perspective. 128x96 pixels.
```

**프롬프트 (바텐더 애니메이션):**
```
[공통 프리픽스]
4-frame pixel art sprite sheet, 64x64 per frame, arranged horizontally (total: 256x64).
Bartender slime wearing vest (#221C20) and bow tie (#D24C59):
F1: idle with blink
F2: shaking cocktail shaker (arms up)
F3: pouring drink (tilt motion)
F4: presenting drink with sparkle (#A2E3CA)
```

### 4. 가구/인테리어 (Furniture)

| Asset | Size | Frames | Notes |
|-------|------|--------|-------|
| `vip_door.png` | 64×96 | 1 | VIP 입구 (금장 + 벨벳 로프) |
| `cashier_booth.png` | 96×64 | 1 | 캐셔 창구 |
| `chandelier.png` | 96×64 | 1 | 샹들리에 (천장 장식) |
| `chandelier_glow.png` | 96×64 ×3 | 3 (horizontal) | 반짝임 애니 |
| `carpet_tile.png` | 32×32 | 1 | 타일러블 카펫 패턴 |
| `wall_tile.png` | 32×32 | 1 | 타일러블 벽 패턴 |
| `poker_table_top.png` | 256×160 | 1 | 포커 테이블 탑뷰 |
| `velvet_rope.png` | 48×32 | 1 | VIP 구역 로프 |
| `neon_sign_*.png` | 128×32 | 1 | 각종 네온 사인 |

**프롬프트 (VIP 문):**
```
[공통 프리픽스]
Pixel art VIP entrance door. Dark wooden double door (#221C20) with
gold (#9D7F33) frame and handle. Red (#D24C59) velvet rope on brass (#C17F54) stands.
Small neon "VIP" text (#35B97D) above door.
3/4 perspective. 64x96 pixels.
```

**프롬프트 (샹들리에):**
```
[공통 프리픽스]
Pixel art ornate chandelier. Brass (#C17F54) frame with gold (#9D7F33) accents.
5 candle-style lights with amber (#F09858) flames and pale mint (#A2E3CA) glow halos.
Crystal drops in dusty gray (#938B7B). Hung from dark ceiling.
96x64 pixels.
```

**프롬프트 (카펫 타일 — 시맨틀리 타일러블):**
```
[공통 프리픽스]
Seamlessly tileable pixel art carpet pattern. Dark maroon (#4D2C2C) base with
gold (#9D7F33) diamond/fleur-de-lis repeating motif.
Edges must tile perfectly in all directions.
32x32 pixels.
```

**프롬프트 (포커 테이블):**
```
[공통 프리픽스]
Pixel art poker table top-down view. Oval shape.
Dark felt surface (#050F1A center, #221C20 edge).
Gold (#9D7F33) brass rail border. Subtle card positions marked.
Dealer chip area. 3/4 slight angle.
256x160 pixels.
```

### 5. 이펙트/파티클 (Effects)

| Asset | Size | Frames | Notes |
|-------|------|--------|-------|
| `coin_spin.png` | 16×16 ×6 | 6 (horizontal) | 칩/코인 회전 |
| `sparkle.png` | 16×16 ×4 | 4 (horizontal) | 범용 반짝임 |
| `smoke_puff.png` | 32×32 ×4 | 4 (horizontal) | 등장/퇴장 연기 |
| `card_flip.png` | 24×32 ×4 | 4 (horizontal) | 카드 뒤집기 |
| `neon_flicker.png` | 8×8 ×3 | 3 | 네온 깜빡임 오버레이 |

**프롬프트 (코인 스핀):**
```
[공통 프리픽스]
6-frame pixel art sprite sheet, 16x16 per frame, horizontal strip (96x16 total).
Gold coin spinning animation: F1 front face, F2-F5 rotation with foreshortening,
F6 back face. Coin color: #9D7F33 body, #FCC88E highlight, #704637 shadow.
```

---

## CSS 변수 매핑 (design-tokens.css 업데이트용)

```css
:root {
  /* Palette — 16 casino colors */
  --px-deep-navy:    #050F1A;
  --px-dark-purple:  #221C20;
  --px-deep-teal:    #073935;
  --px-dark-maroon:  #4D2C2C;
  --px-brown:        #704637;
  --px-teal:         #126D65;
  --px-tan:          #8F604C;
  --px-red:          #D24C59;
  --px-gold:         #9D7F33;
  --px-bronze:       #C17F54;
  --px-dusty-gray:   #938B7B;
  --px-neon-green:   #35B97D;
  --px-mint:         #69B5A8;
  --px-amber:        #F09858;
  --px-peach:        #FCC88E;
  --px-pale-mint:    #A2E3CA;
}
```

---

## 에셋 생성 우선순위

| Priority | Asset | Why |
|----------|-------|-----|
| P0 | `slime_set_unified.png` (12종) | 기존 슬라임 교체 — 팔레트 통일 |
| P0 | `poker_table_top.png` | 펠트 교체 — 그린볼 문제 해결 가능 |
| P1 | `slot_machine.png` + `slot_anim.png` | 로비 POI 비주얼 |
| P1 | `bar_counter.png` + `bartender_slime.png` | 로비 POI 비주얼 |
| P1 | `vip_door.png` | 로비 POI 비주얼 |
| P2 | `chandelier.png` | 분위기 장식 |
| P2 | `carpet_tile.png` + `wall_tile.png` | 로비 배경 타일 |
| P2 | `velvet_rope.png` + `cashier_booth.png` | 디테일 |
| P3 | 이펙트 스프라이트 전부 | 애니메이션 폴리시 |
| P3 | `neon_sign_*.png` | 장식 |

---

## 스프라이트 시트 CSS 애니메이션 패턴

```css
/* 6-frame 96x96 slot machine (3x2 grid) */
.slot-anim {
  width: 96px; height: 96px;
  background: url('/static/slimes/slot_anim.png') no-repeat;
  image-rendering: pixelated;
  animation: slot-spin 1.2s steps(1) infinite;
}
@keyframes slot-spin {
  0%      { background-position: 0 0; }
  16.67%  { background-position: -96px 0; }
  33.33%  { background-position: -192px 0; }
  50%     { background-position: 0 -96px; }
  66.67%  { background-position: -96px -96px; }
  83.33%  { background-position: -192px -96px; }
}

/* 4-frame horizontal strip (e.g. bartender 256x64) */
.bartender-anim {
  width: 64px; height: 64px;
  background: url('/static/slimes/bartender_anim.png') no-repeat;
  image-rendering: pixelated;
  animation: bartender-shake 2s steps(1) infinite;
}
@keyframes bartender-shake {
  0%   { background-position: 0 0; }
  25%  { background-position: -64px 0; }
  50%  { background-position: -128px 0; }
  75%  { background-position: -192px 0; }
}
```

---

## 주의사항

- **gpt-image-1은 팔레트 강제를 100% 지키지 않음** — 생성 후 반드시 색상 검수, 필요시 포토샵/스크립트로 nearest-color 매핑
- **투명 배경 지정해도 배경 나올 수 있음** — `background:transparent` 명시 + 후처리 제거
- **스프라이트 시트 정렬이 안 맞을 수 있음** — 프레임별 개별 생성 후 `montage`로 합치는 게 안전
- **image-rendering: pixelated 필수** — 안 하면 브라우저가 bilinear 보간해서 뭉개짐
