# 🪑 의자 착석 구현 체크리스트

## 시점 (Perspective)
- [ ] 테이블 펠트에 5~10° 기울기 → `perspective: 800px` + `rotateX(5deg)` on `.felt`
- [ ] 기울기는 미세하게 — 카드/칩 가독성 유지하면서 의자 등받이만 살짝 보이는 정도
- [ ] 모바일에서는 기울기 제거 (flat) — 공간 부족

## 앵커 (Seat Anchor)
- [ ] 각 좌석에 `seatAnchor(x%, y%, angle°)` 정의
- [ ] angle: 테이블 중심을 바라보는 방향 (좌석 0=180°, 좌석 4=0° 등)
- [ ] chairSprite + slimeSprite + nameplate를 같은 앵커에 상대 배치
- [ ] 동적 좌석 배치 (플레이어 수 2~8) 기존 `seatPos` 배열 활용

## 레이어 (Z-Index)
```
Z:1  .chair-back     — 의자 등받이 (뒤)
Z:2  .slime-body     — 슬라임 (의자 위)
Z:3  table rail      — 테이블 레일 앞쪽 (CSS ::after로 처리)
Z:4  .cards, .chips  — 홀카드 + 칩 (레일 위)
Z:5  .badges, .label — 이름표 + 상태배지 + 액션라벨
```

## 그림자 (Shadow)
- [ ] 의자 아래: `radial-gradient ellipse, rgba(0,0,0,0.25)` — 6~8px 아래
- [ ] 슬라임 아래: 더 작은 타원 그림자 — 의자 쿠션 위에 있으니까 미세하게만
- [ ] 바닥 하이라이트: 골드 림라이트 반사 — `rgba(245,197,66,0.03)` 정도

## 동작 (Animation)
- [ ] 기본: 숨쉬기 바운스 `translateY(0~-2px)` + `scaleY(0.97~1.03)` — 3s ease
- [ ] 액션 시: 흔들림 `translateX(-2px~2px)` — 0.3s, 2~3프레임
- [ ] 올인: 격렬 떨림 — 기존 `slimeAllinTremble`
- [ ] 승리: 점프 — 기존 `slimeVictoryJump`
- [ ] 폴드: 축 처짐 — opacity 0.35 + scaleY(0.95)
- [ ] animation-delay 랜덤화 — 동기화 방지

## 구현 (Implementation)
- [ ] `renderSlimeToSeat()` 수정 → 의자+슬라임+그림자 레이어 HTML 반환
- [ ] NPC 슬라임: `/static/slimes/{name}.png` 매핑 (블러드팡→ruby 등)
- [ ] 제네릭 슬라임: 색상 해시 기반 자동 할당 (lavender/peach/mint/slate)
- [ ] 의자: 모든 좌석 동일 `/static/slimes/casino_chair.png`
- [ ] 이미지 프리로드 (로비 진입 시)
- [ ] 폴백: 이미지 로드 실패 시 기존 프로시저럴 슬라임으로
