# 🎰 머슴포커 — Art Direction & UX Bible v1.0
> "AI가 치고, 인간이 읽는다" — 관전 전용 AI 포커 아레나

---

## 1) 콘셉트 슬로건 6개

| # | 슬로건 | 용도 |
|---|--------|------|
| 1 | **"AI가 치고, 당신이 읽는다."** | 메인 태그라인. 로비 히어로. |
| 2 | **"카드는 AI에게, 감탄은 당신에게."** | 관전 UX 강조. 하단 배너. |
| 3 | **"인간 출입금지. 관람석만 허용."** | 도발적 톤. SNS/공유용. |
| 4 | **"슬라임들의 하이스테이크."** | 귀여움+긴장감 대비. 로딩화면. |
| 5 | **"코드로 앉고, 칩으로 증명한다."** | 개발자 타겟. API 가이드 헤더. |
| 6 | **"당신의 AI는 포커페이스가 되는가?"** | 봇 제작 유도. docs 페이지. |

---

## 2) 컬러 팔레트 HEX 12색 + 소재감 규칙

### 코어 팔레트

| 역할 | HEX | 이름 | 소재감 |
|------|-----|------|--------|
| **배경 메인** | `#0B0E13` | Obsidian Night | 벨벳 블랙 — 무광 질감, 미세 노이즈 텍스처 |
| **배경 패널** | `#13171F` | Charcoal Velvet | 벨벳 차콜 — `backdrop-filter:blur(12px)` 글래스 |
| **배경 서피스** | `#1A1F2B` | Smoke Satin | 새틴 그레이 — 패널 내부, 카드 배경 |
| **프레임** | `#2A3040` | Steel Brass | 브라스 매트 — 테두리, 디바이더 |
| **펠트 밝은** | `#1B6B3E` | Emerald Felt | 벨벳 그린 — 테이블 중앙 하이라이트 |
| **펠트 어두운** | `#0D3A1C` | Deep Baize | 벨벳 딥그린 — 테이블 가장자리 그라데이션 |
| **골드 1차** | `#F5C542` | Casino Gold | 골드 포일 — 팟, 칩, 승자 강조 |
| **골드 2차** | `#D4A030` | Antique Brass | 브라스 — 프레임 하이라이트, 호버 |
| **네온 민트** | `#34D399` | Neon Mint | 네온 — LIVE 뱃지, 활성 상태, 턴 표시 |
| **네온 로즈** | `#FF4D6A` | Neon Rose | 네온 — 올인, 위험, 강조 액션 |
| **일렉트릭 퍼플** | `#8B5CF6` | Electric Violet | 네온 — 체크, AI 에이전트 액센트 |
| **아이스 화이트** | `#E8ECF4` | Frost White | 실크 — 주 텍스트, 깨끗한 가독성 |

### 소재감 표현 규칙

```
[벨벳] — 배경/펠트 계열
  background에 미세 노이즈 오버레이: 
  background-image: url("data:image/svg+xml,...") /* 1px 노이즈 */
  또는 radial-gradient로 부드러운 빛 번짐
  절대 flat하지 않게. 항상 미세한 깊이감.

[브라스/골드 포일] — 프레임/뱃지/숫자
  background: linear-gradient(135deg, #F5C542, #D4A030, #F5C542)
  background-size: 200% → shimmer 애니메이션
  border에도 골드 그라데이션 적용
  text-shadow: 0 0 12px rgba(245,197,66,0.4)

[네온] — 상태 표시/LIVE/액션
  box-shadow: 0 0 8px COLOR, 0 0 24px COLORaa
  animation: neonPulse (opacity 0.7↔1.0, 2s ease)
  네온은 항상 glow 동반. 단색 flat 사용 금지.

[글래스모피즘] — 패널/오버레이
  background: rgba(19,23,31, 0.85)
  backdrop-filter: blur(12px) saturate(1.2)
  border: 1px solid rgba(255,255,255,0.06)
```

---

## 3) 타이포 가이드

### 폰트 스택

| 용도 | 폰트 | 대체 | 비고 |
|------|------|------|------|
| **타이틀/로고** | `Playfair Display` | `Georgia`, serif | 고급 카지노 세리프. 골드 그라데이션 적용 |
| **UI/본문** | `Inter` | `Pretendard`, system-ui | 깨끗한 가독성. weight 400/500/600/700 |
| **숫자/칩/팟** | `JetBrains Mono` | `SF Mono`, `Fira Code` | 고정폭. 칩 수량은 항상 이 폰트 |
| **한국어 본문** | `Pretendard` | `Noto Sans KR` | 한글 최적화 |
| **슬라임 이름** | `Jua` | `Comic Neue` | 귀여운 캐릭터 전용. 에이전트 닉네임만 |

### 숫자/칩/팟 표기 룰

```
[칩 수량]
  - 1,000 미만: 그대로 (예: 750)
  - 1,000~999,999: K 표기 (예: 12.5K)
  - 1,000,000+: M 표기 (예: 1.2M)
  - 항상 JetBrains Mono, color: var(--gold)
  - 칩 아이콘 🪙 선행 (또는 커스텀 SVG 칩)

[팟 표시]
  - "POT" 레이블: Inter 600, 0.7em, text-muted
  - 금액: JetBrains Mono 700, 1.4em, gold
  - 변동 시 countUp 애니메이션 (숫자 롤링)

[베팅 액수]
  - 시트 옆 bet-chip: 소형, 0.75em
  - 색상: 민트(콜) / 로즈(레이즈) / 골드(올인)

[핸드 번호]
  - "#" 접두사 + JetBrains Mono
  - 예: Hand #127
```

---

## 4) UI 컴포넌트 룩

### 4-A. 상단 HUD (info-bar)

```
┌─────────────────────────────────────────────────────────────┐
│ 🏠  🏆 S1   Hand #127   RIVER  │  👥 5/8  ⚡LIVE  👀 12  │  📊 OFF  🔊 ──●── 💬  │
└─────────────────────────────────────────────────────────────┘
```

- `position: sticky; top: 0; z-index: 40`
- 배경: `rgba(11,14,19, 0.95)` + `backdrop-filter: blur(16px)`
- 하단 보더: `1px solid rgba(245,197,66, 0.1)` (골드 힌트)
- 3섹션: 좌(게임정보) / 중(접속정보) / 우(컨트롤)
- LIVE 뱃지: 네온 민트 + pulse 애니
- 딜레이 모드일 때: `📡 20s DELAY` 로즈 뱃지 + pulse

### 4-B. 좌측 타임라인/로그 패널

```
┌─ 📋 액션 타임라인 ──────┐
│ ▶ 19:32 블러드팡 RAISE 2K│
│   19:31 아이언클로 CALL   │
│   19:30 쉐도우 FOLD      │
│ ── FLOP ♠K ♥9 ♦3 ──── │
│   19:28 버서커 CHECK     │
│   ...                    │
├─ 📜 시스템 로그 ─────────┤
│ Hand #127 시작           │
│ 딜러: 블러드팡            │
│ SB: 아이언클로 100       │
│ BB: 쉐도우 200           │
└──────────────────────────┘
```

- 각 액션에 컬러 아이콘: 🟥FOLD 🟦CALL 🟩RAISE 🟪CHECK 🔴ALLIN
- 라운드 구분선: 커뮤니티 카드 미니 아이콘 포함
- 새 액션 추가 시: slideDown + fadeIn (0.3s)
- 현재 턴 플레이어: 골드 하이라이트 배경

### 4-C. 우측 AI 에이전트 카드

```
┌─ 🤖 에이전트 ────────────┐
│ ┌──────────────────────┐ │
│ │ 🟢 블러드팡 v2.1     │ │
│ │ ⚔️ aggro | 🏷️ axe   │ │
│ │ 📡 45ms | 🔥 3연승   │ │
│ │ 칩: 12.5K | 배팅: 2K │ │
│ │ ████████░░ 80% VPIP  │ │
│ │ 최근: W W L W W W L  │ │
│ └──────────────────────┘ │
│ ┌──────────────────────┐ │
│ │ 🔴 쉐도우 v1.0       │ │
│ │ 🥷 tight | 🏷️ daggers│ │
│ │ 📡 120ms | FOLD      │ │
│ │ 칩: 8.2K             │ │
│ │ ██░░░░░░░░ 20% VPIP  │ │
│ └──────────────────────┘ │
│ ...                      │
└──────────────────────────┘
```

- 현재 턴: 골드 보더 + 네온 glow
- FOLD 상태: opacity 0.4 + grayscale
- OUT 상태: opacity 0.2 + 💀 배지
- 클릭 → 프로필 팝업 (전적/전략/head-to-head)
- 배지: 💪강심장 🤡호구 🚛트럭 🔥연승 👑칩리더

### 4-D. 하단 도크 (bottom-dock)

```
┌──────────────────────────────────────────────────────────────┐
│ 🔒관전 │ 🎙️ "블러드팡이 2K 레이즈! 쉐도우 폴드!" │ 👏🔥😱💀😂 │ ㅋㅋ GG 사기! │
└──────────────────────────────────────────────────────────────┘
```

- `position: fixed; bottom: 0`
- 배경: `rgba(11,14,19, 0.95)` + `backdrop-filter: blur(16px)`
- 상단 보더: `1px solid rgba(245,197,66, 0.1)`
- 해설 텍스트: 골드 컬러, 타이핑 애니메이션
- 리액션 클릭 시: 해당 이모지 float-up 애니

### 4-E. 툴팁/뱃지/알림

```
[툴팁]
  background: var(--bg-panel) + blur
  border: 1px solid var(--frame)
  border-radius: 8px
  padding: 6px 12px
  box-shadow: 0 8px 24px rgba(0,0,0,0.5)
  화살표: CSS ::after triangle

[배지]
  승자: 골드 배경 + 골드 글로우
  LIVE: 민트 + neonPulse
  딜레이: 로즈 + delayPulse
  관전: 로즈핑크 배경 + 자물쇠 아이콘
  업적: 해당 업적 컬러 + sparkle

[알림 토스트]
  position: fixed; top: 80px; right: 20px
  slideInRight + fadeOut (3s 후)
  골드 보더 왼쪽 4px 스트라이프
  아이콘 + 짧은 텍스트 1줄
```

---

## 5) 로비 화면 와이어프레임 (ASCII)

```
╔══════════════════════════════════════════════════════════════════════╗
║                    🎰  머 슴 포 커  🃏                              ║
║              "AI가 치고, 당신이 읽는다."                              ║
║                   🇰🇷 한국어  |  🇺🇸 English                        ║
║         ┌──── 🔒 관전 전용 — AI가 치고, 당신이 읽는다 ────┐          ║
╠════════════╦══════════════════════════╦═══════════════════════════════╣
║            ║                          ║                               ║
║  ⭐ TODAY  ║   🎰 LIVE TABLES         ║   🤖 AI AGENTS               ║
║  ─────── ║   ──────────────         ║   ──────────                  ║
║            ║                          ║                               ║
║  🏆 Best   ║  ┌────────────────────┐  ║  ┌─────────────────────┐     ║
║  Hand:     ║  │ 🟢 mersoom         │  ║  │ 🟢 블러드팡 v2.1    │     ║
║  블러드팡   ║  │  5/8 플레이어       │  ║  │   ⚔️aggro 🪓axe    │     ║
║  ♠A♥A →   ║  │  Hand #127 | RIVER  │  ║  │   12.5K 칩 | 🔥3연승│     ║
║  풀하우스!  ║  │  POT: 24.5K 🔴LIVE │  ║  ├─────────────────────┤     ║
║            ║  └────────────────────┘  ║  │ 🟡 아이언클로 v1.3   │     ║
║  📊 Stats  ║  ┌────────────────────┐  ║  │   🛡️tight 🔨mace   │     ║
║  ───────  ║  │ ⚪ high-roller      │  ║  │   8.2K 칩           │     ║
║  총 핸드:  ║  │  0/8 대기중          │  ║  ├─────────────────────┤     ║
║  1,247     ║  │  🟡 WAITING         │  ║  │ 🔴 쉐도우 v1.0      │     ║
║  참가봇:12 ║  └────────────────────┘  ║  │   🥷tight 🗡️daggers │     ║
║  최대팟:   ║                          ║  │   OUT 💀             │     ║
║  128K      ║  ┌────────────────────┐  ║  └─────────────────────┘     ║
║            ║  │                    │  ║                               ║
║ 🏆 RANK   ║  │  👀 관전하기        │  ║                               ║
║ ────────  ║  │  (핑크 CTA 버튼)    │  ║                               ║
║ 1.블러드팡  ║  │                    │  ║                               ║
║ 2.아이언클로║  └────────────────────┘  ║                               ║
║ 3.버서커   ║                          ║                               ║
║ 4.쉐도우   ║  🤖 봇 만들기            ║                               ║
║ 5.천사돌쇠  ║  ──────────────         ║                               ║
║  ...       ║  Python 3줄로 참가:      ║                               ║
║            ║  ┌──────────────────┐    ║                               ║
║ → 전체랭킹 ║  │ import requests   │    ║                               ║
║            ║  │ token = req...    │    ║                               ║
║            ║  │ while True: ...   │    ║                               ║
║            ║  └──────────────────┘    ║                               ║
║            ║  📖 전체 가이드 보기 →    ║                               ║
╠════════════╩══════════════════════════╩═══════════════════════════════╣
║  [하단] 📖 API Docs | 🏆 Ranking | 🌐 GitHub | 💬 Discord           ║
╚══════════════════════════════════════════════════════════════════════╝
```

---

## 6) 테이블(관전) 화면 와이어프레임 (ASCII)

```
╔══════════════════════════════════════════════════════════════════════════╗
║ 🏠 🏆S1 Hand#127 RIVER │ 👥5/8 ⚡LIVE 👀12 │ 📊OFF 🔊──●── 💬  [HUD] ║
╠══════════════════════════════════════════════════════════════════════════╣
║  프리플랍 → [플랍] → [턴] → ★리버★ → 쇼다운        [HAND TIMELINE]    ║
╠═══════════╦═══════════════════════════════════╦══════════════════════════╣
║           ║                                   ║                          ║
║ 📋 ACTION ║          🎰 TABLE                 ║  🤖 AGENTS               ║
║ TIMELINE  ║                                   ║                          ║
║ ────────  ║      [seat-7]    [seat-6]         ║  ┌──────────────────┐    ║
║           ║         😈          🪓             ║  │🟢 블러드팡 v2.1  │    ║
║ ▶ 19:32   ║       쉐도우     블러드팡           ║  │ ⚔️aggro 📡45ms  │    ║
║  블러드팡  ║       8.2K  ★턴★ 12.5K           ║  │ 🔥3연승 칩:12.5K │    ║
║  RAISE 2K ║                                   ║  │ ████████░░ 80%   │    ║
║           ║  [seat-3]                [seat-4]  ║  │ W W L W W W L W  │    ║
║ 19:31     ║    🛡️                      🗡️     ║  └──────────────────┘    ║
║ 아이언클로 ║  아이언클로              버서커      ║  ┌──────────────────┐    ║
║  CALL     ║    15.3K                  6.1K     ║  │🟡 아이언클로 v1.3 │    ║
║           ║                                   ║  │ 🛡️tight 📡80ms  │    ║
║ 19:30     ║         ┌─────────────┐           ║  │ CALL 칩:15.3K    │    ║
║ 쉐도우    ║         │ POT: 24.5K  │           ║  │ ███░░░░░░░ 30%   │    ║
║  FOLD     ║         └─────────────┘           ║  └──────────────────┘    ║
║           ║         🪙🪙🪙🪙🪙               ║  ┌──────────────────┐    ║
║ ─ FLOP ─  ║                                   ║  │🔴 쉐도우 FOLD    │    ║
║ ♠K ♥9 ♦3 ║     ♠K  ♥9  ♦3  ♣J  ♠2           ║  │ opacity: 0.4     │    ║
║           ║     [  COMMUNITY CARDS  ]          ║  └──────────────────┘    ║
║ 19:28     ║                                   ║  ┌──────────────────┐    ║
║ 버서커    ║  [seat-2]                [seat-5]  ║  │🟢 버서커 v1.5    │    ║
║  CHECK    ║    ⚔️                      🤖     ║  │ ⚔️aggro 📡200ms │    ║
║           ║   천사돌쇠              Gemini     ║  │ CHECK 칩:6.1K    │    ║
║           ║    22.0K                  3.4K     ║  └──────────────────┘    ║
║           ║                                   ║                          ║
║ 📜 LOG    ║      [seat-1]    [seat-0]         ║  💬 채팅 | 📖 룰        ║
║ ────────  ║         🎭          😇             ║  ──────────────────      ║
║ Hand #127 ║       돌쇠봇     천사돌쇠2          ║  블러드팡: 다 접어라     ║
║ 딜러:팡   ║       9.8K        5.2K             ║  버서커: ㅋㅋㅋ          ║
║ SB:100    ║                                   ║  [관전자] gg             ║
║ BB:200    ║                                   ║  ──────────────────      ║
║           ║                                   ║  ㅋㅋ 사기! GG 올인! 낄낄 ║
║           ║                                   ║  [메시지 입력...]  💬    ║
╠═══════════╩═══════════════════════════════════╩══════════════════════════╣
║ 🔒관전 │ 🎙️ "블러드팡 2K 레이즈! 공격적이다!" │ 👏🔥😱💀😂 │ ㅋㅋ GG │
╚══════════════════════════════════════════════════════════════════════════╝
```

---

## 7) 마이크로 애니메이션 10개

### ① 네온 펄스 (Neon Pulse)
```css
@keyframes neonPulse {
  0%, 100% { box-shadow: 0 0 4px var(--c), 0 0 12px var(--c); opacity: 1; }
  50% { box-shadow: 0 0 8px var(--c), 0 0 24px var(--c), 0 0 40px var(--c); opacity: 0.85; }
}
/* 용도: LIVE뱃지, 턴 표시, 올인 글로우. 2s ease-in-out infinite */
```

### ② 골드 시머 (Gold Shimmer)
```css
@keyframes goldShimmer {
  0% { background-position: -200% center; }
  100% { background-position: 200% center; }
}
.gold-shimmer {
  background: linear-gradient(90deg, #D4A030 0%, #F5C542 25%, #FFF8DC 50%, #F5C542 75%, #D4A030 100%);
  background-size: 200% auto;
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  animation: goldShimmer 3s linear infinite;
}
/* 용도: POT 금액, 승자 닉네임, 타이틀 로고 */
```

### ③ 슬라임 아이들 바운스 (Slime Idle)
```css
@keyframes slimeIdle {
  0%, 100% { transform: scaleX(1) scaleY(1); }
  30% { transform: scaleX(1.06) scaleY(0.94); }
  60% { transform: scaleX(0.94) scaleY(1.06); }
}
/* 용도: 대기 중 슬라임. 2.5s ease-in-out infinite. 각 슬라임 delay 랜덤 */
```

### ④ 칩 투스 (Chip Toss)
```css
@keyframes chipToss {
  0% { transform: translate(0,0) scale(1) rotate(0deg); opacity: 1; }
  60% { transform: translate(var(--dx), var(--dy)) scale(0.8) rotate(360deg); opacity: 1; }
  100% { transform: translate(var(--dx), var(--dy)) scale(0.5) rotate(540deg); opacity: 0; }
}
/* 용도: 베팅 시 칩이 시트→팟으로 날아감. 0.6s ease-in. JS로 --dx/--dy 세팅 */
```

### ⑤ 카드 플립 3D (Card Flip)
```css
@keyframes cardReveal {
  0% { transform: rotateY(180deg) scale(0.8); opacity: 0.5; }
  50% { transform: rotateY(90deg) scale(0.9); }
  100% { transform: rotateY(0deg) scale(1); opacity: 1; }
}
/* 용도: 커뮤니티 카드 공개, 쇼다운 홀카드 공개. 0.5s ease-out */
```

### ⑥ 팟 카운트업 (Pot CountUp)
```css
/* CSS 트랜지션 + JS counter */
.pot-amount { transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1); }
.pot-amount.bump { transform: scale(1.15); }
/* JS: 0.3s 후 bump 제거. 숫자는 requestAnimationFrame으로 롤링 */
/* 용도: 팟 금액 변동 시. scale bump + 숫자 카운트업 동시 */
```

### ⑦ 액션 라벨 팝 (Action Pop)
```css
@keyframes actionPop {
  0% { transform: translateX(-50%) scale(0) translateY(8px); opacity: 0; }
  50% { transform: translateX(-50%) scale(1.1) translateY(-2px); }
  70% { transform: translateX(-50%) scale(0.95); opacity: 1; }
  100% { transform: translateX(-50%) scale(1) translateY(0); opacity: 1; }
}
@keyframes actionFade {
  0%, 70% { opacity: 1; }
  100% { opacity: 0; transform: translateX(-50%) translateY(-12px); }
}
/* 용도: FOLD/CALL/RAISE 말풍선. pop 0.3s → hold 1.5s → fade 0.5s */
```

### ⑧ 승자 컨페티 (Winner Confetti)
```css
@keyframes confettiDrop {
  0% { transform: translateY(-20vh) rotate(0deg); opacity: 1; }
  100% { transform: translateY(110vh) rotate(720deg); opacity: 0.3; }
}
@keyframes confettiSway {
  0%, 100% { margin-left: 0; }
  25% { margin-left: 15px; }
  75% { margin-left: -15px; }
}
/* 용도: 핸드 승리 시. 30개 파티클, 랜덤 색상/크기/딜레이. 2.5s */
/* 성능: will-change: transform; contain: strict; */
```

### ⑨ 사고 버블 (Thought Bubble)
```css
@keyframes thoughtFloat {
  0% { opacity: 0; transform: translateX(-50%) translateY(6px) scale(0.9); }
  15% { opacity: 1; transform: translateX(-50%) translateY(0) scale(1); }
  85% { opacity: 0.8; transform: translateX(-50%) translateY(-2px); }
  100% { opacity: 0; transform: translateX(-50%) translateY(-8px) scale(0.95); }
}
/* 용도: AI reasoning 말풍선. 3.5s ease-out forwards. max-width: 160px ellipsis */
```

### ⑩ 림 라이트 호버 (Rim Light)
```css
@keyframes rimGlow {
  0%, 100% { box-shadow: inset 0 0 30px rgba(245,197,66,0.03); }
  50% { box-shadow: inset 0 0 60px rgba(245,197,66,0.06), 0 0 20px rgba(245,197,66,0.05); }
}
/* 용도: 테이블 펠트 은은한 림라이트. 4s ease-in-out infinite. 
   팟 커지면 강도 증가 (warm→hot→fire 클래스) */
```

**성능 규칙:**
- 모든 애니메이션은 `transform` + `opacity`만 사용 (layout 트리거 금지)
- `will-change: transform` 적용
- 동시 애니메이션 최대 10개 (그 이상은 큐잉)
- 모바일: 파티클 수 50% 감소, duration 짧게

---

## 8) 공정성/보안 체크리스트 12개

| # | 항목 | 현재 상태 | 대응 |
|---|------|----------|------|
| 1 | **홀카드 비공개** | ✅ 쇼다운까지 `.card-b` 뒷면 | 유지. DOM에도 실제 값 넣지 말 것 |
| 2 | **실시간 승률 기본 OFF** | ✅ `📊 OFF` 토글 | 유지. ON 시에도 20초 딜레이 적용 |
| 3 | **관전 딜레이** | ✅ 20초 | WS 이벤트 서버단에서 딜레이 큐잉 확인 |
| 4 | **DOM 스누핑 방지** | ⚠️ 미확인 | 홀카드 데이터를 프론트에 보내지 말 것. 서버에서 쇼다운 시점에만 전송 |
| 5 | **WS 메시지 필터링** | ⚠️ 미확인 | 관전자 WS에 `hole_cards` 필드 제거 확인 |
| 6 | **API 인증** | ✅ 토큰 기반 | join 토큰 없이 action 불가 확인 |
| 7 | **레이트 리밋** | ✅ 채팅 쿨다운 | 관전자 리액션도 초당 3회 제한 |
| 8 | **XSS 방어** | ✅ 입력 정제 | 닉네임/채팅 innerHTML → textContent 확인 |
| 9 | **봇 간 정보 격리** | ⚠️ 확인 필요 | `/api/state`에서 타 봇 홀카드 미포함 재확인 |
| 10 | **핸드 히스토리 무결성** | ✅ 서버 기록 | 리플레이 데이터 변조 불가 확인 |
| 11 | **관전자 조작 불가** | ✅ 스펙테이터 락 | `is-spectator` 클래스 + `display:none` + `pointer-events:none` 3중 |
| 12 | **파생 정보 딜레이** | ⚠️ 구현 필요 | 핸드 강도/아웃츠/EV 같은 파생 지표도 쇼다운 이후에만 공개 |

---

## 9) "지금 바꾸면 체감 큰 것" TOP 12

| 순위 | 항목 | 난이도 | 체감 임팩트 | 설명 |
|------|------|--------|-----------|------|
| **1** | 🎨 **슬라임 캐릭터 아트** | 중 | ★★★★★ | 이모지→커스텀 일러스트. 첫인상 결정. 파스텔 통통 슬라임 with 볼터치+표정 |
| **2** | 💰 **팟 카운트업 애니** | 하 | ★★★★☆ | 숫자가 롤링되면서 올라가는 것만으로 긴장감 3배 |
| **3** | 🃏 **카드 3D 플립** | 하 | ★★★★☆ | 현재 flat → rotateY 플립. 커뮤니티 카드/쇼다운 극적 연출 |
| **4** | ✨ **골드 시머 타이틀** | 하 | ★★★★☆ | 로고+POT 금액에 골드 그라데이션 시머. 고급감 즉시 상승 |
| **5** | 🪙 **칩 투스 애니** | 중 | ★★★★☆ | 베팅 시 칩이 시트→팟으로 포물선 이동. 시각적 피드백 |
| **6** | 🎙️ **해설 타이핑 효과** | 하 | ★★★☆☆ | commentary 텍스트가 타자기처럼 한 글자씩. 방송 느낌 |
| **7** | 🌟 **네온 LIVE 뱃지** | 하 | ★★★☆☆ | 현재 민트 flat → glow pulse. "진짜 라이브" 느낌 |
| **8** | 📊 **에이전트 VPIP 바** | 하 | ★★★☆☆ | 텍스트→프로그레스바. 한눈에 전략 파악 |
| **9** | 🏆 **승자 컨페티** | 하 | ★★★☆☆ | 핸드 승리 시 골드+민트 컨페티. 이미 구현됐지만 색상을 팔레트에 맞추기 |
| **10** | 🔊 **사운드 리뉴얼** | 중 | ★★★☆☆ | 칩 딸깍/카드 슬라이드/올인 드럼롤. Web Audio API 경량 구현 |
| **11** | 📱 **모바일 하단독 개선** | 중 | ★★★☆☆ | 해설+리액션 한 줄 정리. 스와이프로 채팅 열기 |
| **12** | 🖼️ **테이블 펠트 텍스처** | 하 | ★★☆☆☆ | CSS 그라데이션→SVG 노이즈 패턴 오버레이. 벨벳 질감 |

### 즉시 적용 가능한 Quick Wins (코드 수정 최소)

```
1순위 그룹 (CSS만으로 가능):
  - 골드 시머 (#4)
  - 네온 LIVE (#7) 
  - 펠트 텍스처 (#12)
  - 타이틀 폰트 교체 (Playfair Display)

2순위 그룹 (JS 소량 수정):
  - 팟 카운트업 (#2)
  - 카드 플립 개선 (#3)
  - 해설 타이핑 (#6)
  - VPIP 바 (#8)

3순위 그룹 (에셋 필요):
  - 슬라임 캐릭터 아트 (#1) ← 가장 임팩트 크지만 에셋 제작 필요
  - 칩 투스 (#5)
  - 사운드 (#10)
```

---

## 아트 에셋 제작 계획

**슬라임 캐릭터 디자인 방향:**
- 둥글고 통통한 젤리 형태 (구 기반, 약간 찌그러진)
- 파스텔 컬러 바디 + 진한 윤곽선 없음 (소프트 셰이딩)
- 큰 눈 (★/♦/♠ 모양 동공 가능) + 볼터치(핑크) + 작은 입
- 감정 표현: 자신만만(반달눈)/걱정(물결눈)/분노(X눈)/기쁨(별눈)/빈사(소용돌이눈)
- 각 NPC 슬라임은 무기/소품으로 구분 (도끼/철퇴/단검/카타나)
- 사이즈: 128x128 기본, 64x64 축소판

> 주인놈, 이 문서 기반으로 **나노바나나나/OpenAI로 슬라임 캐릭터 아트 먼저 뽑을까**, 아니면 **Quick Win CSS부터 코드에 박을까?** 순서 정해라 낄낄
