# 콜로세움 픽셀 격투 아트 룰 (주인놈 피드백 2026-02-15)

## 6대 문제점
1. **배경 블러 조명** → 디더링(점무늬)로만 빛 표현
2. **바닥/접지감 없음** → 그림자 규칙 + 그리드 약화
3. **VFX 서브픽셀+알파 과다** → 2~4색 + 큰 픽셀 덩어리 + 프레임 애니
4. **캐릭터 라인/채색 불통일** → 전원 동일 외곽선/쉐이딩 규칙
5. **UI 스타일 불일치** → 픽셀폰트 + 1px 테두리 + 단색
6. **팔레트 미통제** → 강제 16~24색 팔레트

## 픽셀 격투 룰 8개
1. **알파/블러/그라데이션 금지** → 빛은 디더링만
2. **베이스 해상도 고정**: 320×180 / 384×216 / 480×270 택1 → 정수배(×3~5) nearest
3. **지면 그림자**: 모든 캐릭 발밑 1~2px 타원, 점프 시 길이/진하기 변화
4. **외곽선 규격화**: 캐릭 1~2px 고정 (전원 동일), 이펙트도 규칙
5. **VFX 팔레트 4색 제한**: 피=어두운빨강2+하이라이트1+검정, 독=초록2+검정
6. **VFX 형태 = 큰 픽셀 덩어리** (잔선/머리카락 선 금지)
7. **배경 디테일 낮추기** (캐릭터가 주인공)
8. **UI = 픽셀폰트 + 1px 테두리 + 단색** (KO 크게, 정렬 정확히)

## 수정 우선순위
1. 배경 블러 조명 삭제 → 디더링 빛
2. 바닥 그리드 약화 + 발그림자 규칙
3. VFX 알파/잔선 제거 → 4색 덩어리
4. 팔레트 강제 (배경→캐릭→VFX→UI)
5. UI 정렬/크기 (KO 크게, HP바 통일)

## PixelLab 프롬프트 템플릿

### 배경 (KOF/사쇼 스타일)
```
pixel art fighting game stage, 2D side view, dark temple interior with
pillars and hanging banners, torch lights rendered with dithering
(no gradients), parallax background layers, clean readable floor plane,
320x180 base resolution, sharp pixels
```
Negative: `no blur, no smooth gradients, no bloom, no soft airbrush, no anti-aliasing, no realistic lighting`

### 캐릭터
```
pixel art fighter character, 2D side view, KOF / Samurai Shodown vibe,
strong silhouette, 48x80 sprite, 6-frame idle loop, 8-frame slash attack,
2-3 tone shading, consistent 1-2px outline, sharp pixels
```
Negative: `no glow, no semi-transparent trails, no high-detail hair strands, no smooth shading`

### 슬래시 이펙트
```
pixel art slash effect, 6 frames, chunky pixel clusters, 3-4 colors only,
no transparency, no blur, clean readable arc
```

### 피격/피 튐
```
pixel art hit blood burst, 4 colors max, chunky droplets, 4-6 frames,
no transparent mist, no neon green
```

## PixelLab 모드
- 현재: `generate-image-pixflux` (텍스트→이미지)
- 캐릭 스프라이트 64×64, side view
