# 머슴포커 server.py 코드 전수검사 V2
> 검사일: 2025-02-17 | 검사자: dolsoe-agent | 파일: server.py (10,705줄)

## 요약

| 구분 | 결과 |
|------|------|
| 🔴 버그 (수정됨) | 2건 |
| 🟡 주의사항 | 3건 |
| 🟢 정상 | 14건 |

---

## 🔴 수정된 버그

### 1. slime cache key에 accessories 누락
- **위치**: drawSlime() 함수, 캐시 키 생성부 (line ~8774)
- **증상**: 같은 이름/감정/크기/타입/eyeStyle이지만 다른 장신구 조합의 슬라임이 같은 캐시 키를 공유 → 첫 번째 렌더링 결과만 반환
- **수정**: 캐시 키에 `accessories.join(',')` 추가
- **영향**: 장신구가 30종이 된 지금 실제로 발생 가능성 높았음

### 2. `propeller` 장신구 렌더링 코드 누락
- **위치**: drawSlime() 내 DYNAMIC ACCESSORIES 블록
- **증상**: newbie 타입에 `propeller`이 자동 배정되고, NPC 풀에도 포함되지만, 실제 그리기 코드가 없어 아무것도 표시 안 됨
- **수정**: propeller 렌더링 코드 추가 (파란 비니캡 + 빨간 프로펠러 블레이드)
- **영향**: 크래시는 없었지만 newbie 시각적 아이덴티티 상실

---

## 🟡 주의사항 (수정 불필요/선택)

### 3. NPC 장신구 랜덤 할당 시 캐시 무효화 안 됨
- **위치**: NPC용 setSlimeTraits (line ~9830)
- **상황**: NPC가 새로 생성될 때 `Math.random()`으로 장신구 배정 → 캐시 키에 accessories가 포함되므로 이제 정확히 동작
- **결론**: 캐시 키 수정으로 해결됨. 다만 NPC traits가 매번 재설정되면 캐시 미스가 자주 발생할 수 있음 (성능에 미미한 영향)

### 4. app_icon.jpg 파일 미존재 (fallback 정상 동작)
- **위치**: /app_icon.jpg 라우트 (line ~3002)
- **상황**: `static/icon.jpg` → `pwa_icon.png` 순서로 fallback. `static/icon.jpg` 존재 확인됨 (64KB)
- **결론**: 정상 동작. 단, manifest.json에서 `type: "image/jpeg"` 선언하면서 실제로는 jpg→png fallback 가능성 있음. 현재는 `static/icon.jpg`가 존재하므로 문제없음

### 5. `!important` 사용량 많음
- **위치**: 모바일 CSS 전반
- **상황**: 모바일(@media max-width:700px) 블록에서 약 40+ `!important` 사용
- **결론**: 인라인 스타일 오버라이드 목적이라 불가피. 향후 리팩터링 시 인라인 스타일 제거 → !important 줄이기 권장

---

## 🟢 정상 확인 항목

### JavaScript 문법/런타임
- ✅ eyeL/eyeR/eyeY 변수: `const` 선언 후 사용 (line 8887-8889). TDZ 문제 없음
- ✅ eyeStyle 6종 분기: `if/else if/else` 체인으로 fall-through 없음 (heart→star→money→sleepy→wink→default)
- ✅ drawSlime 호출부: 모두 `(name, emotion, size)` 3인자로 일관
- ✅ 중괄호/괄호 매칭: drawSlime 함수 정상 종료 (line ~9303 `_slimeCache[key] = c; return c;`)
- ✅ null 체크: `traits.accessories || []`, `traits.eyeStyle || 'normal'` 등 방어 코딩 적용

### CSS 무결성
- ✅ `#mobile-action-bar`: 인라인 `display:none` → 모바일에서만 `display:block!important` (데스크톱 숨김 정상)
- ✅ `#lobby-banner`: 데스크톱 표시, 모바일(@700px)에서 `display:none!important`, in-game에서도 `display:none!important`
- ✅ `#chip-stack`: 모바일에서 `display:none!important` (line 5461) → coin animation fallback이 `#pot`으로 정상 전환 (line 7768)

### HTML 구조
- ✅ id 중복 없음: `pwa-install-btn`과 `pwa-install-btn2`는 별개 id
- ✅ `lobby-banner`는 `table-list` div 다음에 위치 (line 5804 → 5807)
- ✅ `mobile-action-bar`는 lobby-banner 뒤에 위치 (line 5857)

### 서버 라우팅
- ✅ `/manifest.json`: 유효한 JSON, `application/json` 타입, `Cache-Control: no-cache`
- ✅ `/sw.js`: `Service-Worker-Allowed: /` 헤더 정상, `application/javascript` 타입
- ✅ `/app_icon.jpg` & `/pwa_icon.png`: 동일 핸들러에서 처리, `static/icon.jpg` → `pwa_icon.png` fallback 체인
- ✅ MIME type: `.jpg` → `image/jpeg`, `.png` → `image/png` 조건 분기 정상

### 게임 로직
- ✅ drawSlime은 관전자 렌더링에서도 동일 함수 사용 (miniSlime, profileSlime 등)
- ✅ NPC 장신구/눈 할당 시 크래시 없음: 모든 accessory 코드가 `if(a==='xxx')` 가드, 매칭 안 되면 skip
- ✅ VALID_ACC (서버측 30종) = _npcAccPool (클라이언트 30종) = drawSlime 렌더링 코드 (30종) 일치 (propeller 수정 후)

### 성능
- ✅ drawSlime의 acc.forEach: 캐시된 canvas 반환 시 forEach 실행 안 됨 (`_slimeCache[key]` 체크가 선행)
- ✅ SW 캐시 전략: network-first (`fetch().catch(() => caches.match())`) — 폴링/API 호출에 영향 없음
- ✅ SW 캐시 범위: `urlsToCache=['/']` (메인 페이지만) — 과도한 캐시 없음

---

## 수정 커밋
- slime cache key에 accessories 추가
- propeller 장신구 렌더링 코드 추가
