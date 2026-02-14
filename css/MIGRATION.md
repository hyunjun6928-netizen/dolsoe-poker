# 머슴포커 CSS v2.0 마이그레이션 가이드

## D) 관전모드 규칙 — 숨길/잠글 요소

### 완전 숨김 (display: none)
```
body.is-spectator #actions          — 플레이 액션 패널
body.is-spectator #new-btn          — 새 게임 버튼
body.is-spectator #reactions        — 옛 리액션 (하단독으로 이전)
body.is-spectator #action-stack     — 우측 액션 스택 전체
#replay-panel                       — 리플레이 (추후 재구현)
#highlights-panel                   — 하이라이트 (추후 재구현)
.forest-top, .forest-deco           — 레거시 데코
```

### 잠금 표시 (pointer-events:none + opacity)
```
.spectator-lock                     — 관전 잠금 오버레이 (빗금 패턴)
.spectator-lock .stack-btn          — 폴드/콜/레/올인 버튼 (opacity 0.2)
#bet-panel                          — 베팅 패널 (관전시 숨김)
```

### 딜레이/공정성 컨트롤
```
.fair-hidden                        — 📊 OFF 시 파생정보 숨김
#delay-badge.live                   — ⚡ LIVE (민트 네온 pulse)
#delay-badge.delayed                — 📡 20s DELAY (로즈 pulse)
```

### 추가 권장 (서버단)
- WS 관전자 채널에서 `hole_cards` 필드 제거
- `/api/state` 관전자 응답에 홀카드 미포함
- 파생 지표(승률/EV)는 쇼다운 이후에만 WS push

---

## E) HTML 최소 변경 diff

### 1. `<head>` — 폰트 + CSS 교체

```html
<!-- 기존 inline <style> 태그 전체 제거 -->
<!-- 대신 아래 추가: -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&family=Playfair+Display:wght@700;800;900&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/static/css/design-tokens.css">
<link rel="stylesheet" href="/static/css/layout.css">
<link rel="stylesheet" href="/static/css/components.css">
```

### 2. `<body>` — 클래스 추가

```html
<!-- 기존 -->
<body>
<!-- 변경 -->
<body class="is-spectator">
<!-- JS가 관전 진입 시 is-spectator 추가, 
     플레이어 진입 시 제거 (현재는 항상 관전) -->
```

### 3. `<h1>` — 타이틀 id 확인

```html
<!-- 이미 있음 — 변경 없음 -->
<h1 id="main-title">🎰 <b>머슴</b>포커 🃏</h1>
<!-- font-family inline style 제거 (CSS에서 처리) -->
```

### 4. `#delay-badge` — 클래스 추가

```html
<!-- 기존 -->
<span id="delay-badge" style="...">⚡ LIVE</span>
<!-- 변경: inline style 제거, 클래스 추가 -->
<span id="delay-badge" class="live">⚡ LIVE</span>
<!-- JS에서 딜레이 모드 전환 시: -->
<!-- badge.className = isLive ? 'live' : 'delayed'; -->
```

### 5. 에이전트 카드 — VPIP 바 추가 (선택)

```html
<!-- agent-card 내부에 추가 -->
<div class="agent-vpip">
  <div class="agent-vpip-fill" style="width: 80%"></div>
</div>
```

### 6. `bottom-dock` — position 변경

```html
<!-- bottom-dock은 이제 grid child이므로 
     position:fixed 인라인 스타일이 있다면 제거 -->
```

### 7. inline style 정리 대상

```
제거 대상 (CSS에서 처리):
- h1의 style="font-family:..."
- .info-bar 내부 div들의 style="display:flex;..."  (이미 CSS에 있음)
- #delay-badge의 inline background/color/padding
- .btn-watch의 inline style  (px-btn 클래스로 대체)
- .bottom-dock 관전 배지의 inline style
```

---

## F) 적용 순서 3단계 + 체크리스트

### 🟢 Phase 1: 토큰 + 레이아웃 교체 (파괴 없음)

**작업:**
1. `css/` 폴더에 3파일 생성 (완료)
2. server.py에서 static 파일 서빙 경로 추가 (`/static/css/`)
3. HTML_PAGE의 `<style>` 블록을 `<link>` 3개로 교체
4. `<body>` 에 `class="is-spectator"` 추가
5. Playfair Display 폰트 로드 추가

**체크리스트:**
- [ ] 로비 3컬럼 그리드 정상 렌더링
- [ ] 테이블 3컬럼(좌독/테이블/우독) 정상
- [ ] HUD sticky 동작
- [ ] 하단 독 고정 (모바일: fixed, 데스크톱: grid)
- [ ] 배경 다크 + 미세 빛 번짐 확인
- [ ] 골드 시머 타이틀 확인
- [ ] 모바일 반응형 (좌/우독 hide, 풀 테이블)

### 🟡 Phase 2: 컴포넌트 스타일 적용

**작업:**
1. inline style 정리 (E 섹션 참고)
2. #delay-badge에 .live/.delayed 클래스 JS 연동
3. .fair-hidden 토글 JS 연동
4. agent-card에 .agent-vpip 바 추가
5. 관전 잠금 UI 확인 (#action-stack 숨김)

**체크리스트:**
- [ ] 패널 글래스 효과 (반투명 + blur)
- [ ] 카드 플립 애니메이션
- [ ] 액션 라벨 pop+fade
- [ ] 에이전트 카드 턴 하이라이트 (골드 보더 + glow)
- [ ] 폴드/아웃 상태 시각 차이
- [ ] 팟 카운트업 bump
- [ ] 네온 LIVE 뱃지 pulse
- [ ] 관전모드에서 플레이 버튼 완전 숨김

### 🔴 Phase 3: 에셋 + 사운드 + 폴리시

**작업:**
1. 슬라임 캐릭터 아트 (OpenAI/나노바나나나) → 이모지 교체
2. 사운드 팩 (Web Audio API)
3. 해설 타이핑 이펙트 JS
4. 칩 투스 JS (시트→팟 궤적 계산)
5. 승자 컨페티 색상 팔레트 조정

**체크리스트:**
- [ ] 슬라임 아바타 128px PNG (NPC 4종 + 제네릭 3종)
- [ ] 슬라임 감정별 스프라이트 (idle/think/angry/happy/sad)
- [ ] 사운드: 칩딸깍, 카드슬라이드, 올인드럼, 승리팡파레
- [ ] 해설 한 글자씩 타이핑
- [ ] 칩 포물선 애니메이션
- [ ] 최종 크로스브라우저 테스트 (Chrome/Safari/Firefox)
- [ ] Lighthouse 성능 점수 > 85

---

## 파일 구조

```
cloud_poker/
├── css/
│   ├── design-tokens.css   ← A) 토큰
│   ├── layout.css          ← B) 레이아웃
│   ├── components.css      ← C) 컴포넌트
│   └── MIGRATION.md        ← D+E+F) 이 문서
├── ART_DIRECTION.md        ← 아트 디렉션 바이블
└── server.py               ← 기존 서버 (수정 대상)
```
