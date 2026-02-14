# minimal-dom-diff.md — DOM 변경 최소화 가이드
> v3.0 · 2026-02-14

## 원칙
**DOM은 바꾸지 않는다.** 아래 5개 이내의 class/attribute 추가만 허용.

---

## 변경 사항 (3건)

### 1. `#delay-badge` — `data-state` 속성 추가
**위치:** `.info-bar` 내부 `#delay-badge`  
**변경:** JS에서 상태 변경 시 `data-state="live"` 또는 `data-state="delay"` 추가  
```js
// 기존 코드에 추가
delayBadge.dataset.state = isLive ? 'live' : 'delay';
delayBadge.classList.toggle('is-delayed', !isLive);
```
**이유:** CSS에서 라이브/딜레이 상태에 따라 색상/애니메이션 분기

### 2. `#fairness-toggle` — `data-state` 속성 추가
**위치:** `.info-bar` 내부 `#fairness-toggle`  
**변경:** JS에서 토글 시 `data-state="on"` 또는 `data-state="off"` + `.fair-on` 클래스  
```js
// 기존 toggleFairness() 함수에 추가
fairToggle.dataset.state = isOn ? 'on' : 'off';
fairToggle.classList.toggle('fair-on', isOn);
```
**이유:** CSS에서 공정성 ON일 때 경고 스타일 표시

### 3. `.seat-unit` 래퍼 — 좌석 내부 구조화
**위치:** 각 `.seat` 내부, `.ava` 대신 `.seat-unit` 삽입  
**변경:** JS의 좌석 렌더링에서 기존 이모지/이미지를 `.seat-unit` 구조로 감싸기
```html
<!-- 기존 -->
<div class="ava">🟢</div>

<!-- 변경 (슬라임 이미지가 있을 때) -->
<div class="seat-unit">
  <div class="chair-shadow"></div>
  <div class="chair-sprite"><img src="/static/assets/slimes/casino_chair.png" alt=""></div>
  <div class="slime-sprite"><img src="/static/assets/slimes/ruby_confident.png" alt=""></div>
</div>

<!-- 변경 (이미지 없을 때 — CSS fallback 자동 적용) -->
<div class="seat-unit">
  <div class="chair-shadow"></div>
  <div class="chair-sprite"></div>
  <div class="slime-sprite"></div>
</div>
```
**이유:** 의자+슬라임+그림자 5-layer z-stack 연출. `.chair-sprite:empty`와 `.slime-sprite:empty`에 CSS fallback이 있으므로 이미지 없이도 동작.

---

## 변경하지 않는 것
- `body.is-spectator` — 이미 존재
- `.spectator-lock` — 이미 존재
- `.game-layout` 3-col 그리드 — 유지
- 모든 ID/class명 — 유지
- 오버레이 구조 — 유지
