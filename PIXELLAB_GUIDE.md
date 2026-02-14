# PixelLab 그래픽 통일 가이드 (주인놈 직전)

## 핵심 원칙
- **팔레트 강제 + 같은 카메라** = 통일감의 전부

## PALETTE_16 (카지노 강제용)
```
#09080A #0B0D13 #130D0D #171212
#19110E #212621 #372418 #452C1A
#4C311C #593821 #8E6C34 #AD8C33
#D6AB3A #F1C243 #1F966E #29569E
```
옵션 네온 포인트: `#E33E75` (블루 `#29569E` 대체 가능)

## PixelLab 워크플로우
1. **Create map (pixflux)**: Camera view + Target palette 고정 → 배경/시설 기준
2. **Create walking character**: 같은 카메라/팔레트로 캐릭터
3. **Reduce colors**: 색 튀면 Target palette로 강제 통일 (최대 512×512)
4. **Image to pixel art**: 기존 이미지를 카지노 톤으로 재해석

## 슬라임 캐릭터 프롬프트 (32×32 or 32×40)
```
pixel art casino floor character, small slime creature redesigned to match
dark luxurious casino interior, top-down/3-4 view to match the map,
thicker outline, limited shading, warm brass highlights, subtle rim light
from chandeliers, 1-2px ground shadow under feet, readable silhouette at
32x40, no cute pastel tone
```

### Negative
```
no anti-aliasing, no smooth gradients, no 3D, no painterly, no soft airbrush,
no realistic texture, no high saturation outside palette, avoid chibi pastel
```

### Settings
- Outline: ON (두꺼운 외곽선)
- Shading: 2~3톤 (브라스 하이라이트 위주)
- Details: LOW~MID (32×40에서 과디테일 금지)

## 슬롯머신 애니메이션 프롬프트 (8프레임)
```
pixel art slot machine, top-down/3-4 view, matches dark casino palette,
brass trim, teal glow accents, lever pull animation then reels spin,
small blinking lights, 8 frames loop, readable silhouette, no gradients,
use only target palette
```
- 레버: 내려감(2f) → 튕김(1f)
- 릴: 회전 블러 금지 (패턴만 변경)
- 불빛: 깜빡(2f) + 쉬기(1f) 반복

## 바텐더 프롬프트 (6-8프레임 idle)
```
pixel art bartender character, casino uniform (vest, bow tie), top-down/3-4
view, warm brass highlights, teal accent, subtle idle animation: wiping
glass / pouring drink, 6-8 frames loop, 1-2px ground shadow, use only
target palette
```

## 따로 노는 느낌 줄이기 체크리스트
1. **카메라 시점 통일**: 맵(3/4 탑다운) = 캐릭터(3/4) 강제
2. **팔레트 강제**: 생성 → Reduce colors로 PALETTE_16 강제
3. **그림자 규칙**: 모든 캐릭터/오브젝트 1~2px 바닥 그림자
4. **외곽선 규격화**: 캐릭터 2px / 오브젝트 1~2px
5. **하이라이트 방향 통일**: 위쪽 샹들리에 → 림라이트 위-좌/위-중앙
6. **스케일 규격화**: 캐릭터 키 = 의자 좌판 높이 × 0.8 등
7. **골드 포인트 제한**: 엣지/프레임에만
8. **네온/청록**: 인터랙션 오브젝트에만 (슬롯/바/VP)
9. **텍스처 과밀 금지**: 캐릭터 주변 5~10타일은 패턴 약하게
10. **애니메이션**: 6~8프레임 루프, 과한 움직임 금지

## 코드 개선 시 필요한 최소 세트
1. 로비/맵 렌더 CSS (#casino-floor, .wrap, 비네트/블러/스케일/image-rendering)
2. 오브젝트 배치 데이터 (POI 좌표, z-index 규칙)
3. 슬라임 렌더 코드 (renderLobbyWalkers(), 스프라이트 로딩/스케일/그림자)
4. 애니메이션 루프 (requestAnimationFrame 타이밍, prefers-reduced-motion)
