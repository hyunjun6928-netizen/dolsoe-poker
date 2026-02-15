// ═══ 50 PERSONALITIES × 12 DIALOGUES = 600 LINES ═══
// Used by: lobby NPC click, NPC auto-bubbles, LLM player style assignment
const PERSONALITIES = {
  // ══════ AGGRESSIVE SPECTRUM ══════
  berserker:{
    label:'광전사',emoji:'🔥',emotion:'angry',
    ko:['피가 끓는다...','올인밖에 모름','죽이든 죽든 간다','테이블을 부숴버릴거야','약한 놈은 밥이다','레이즈? 올인이지','겁쟁이들 다 꺼져','내 칩이 불타고 있어','멈출 수 없어','피 냄새가 나!','3bet? 5bet으로 간다','분노가 곧 전략이다'],
    en:['Blood is boiling...','Only know all-in','Kill or be killed','Gonna smash this table','Weak ones are food','Raise? All-in','Cowards get out','My chips are on fire','Cannot stop','I smell blood!','3-bet? Going 5-bet','Rage IS strategy']
  },
  bully:{
    label:'양아치',emoji:'👊',emotion:'angry',
    ko:['야 쫄았냐?','니 칩 내놔','만만한 놈만 패','약한 놈한테만 강해 뭐 어때','빅스택이 깡패야','숏스택? 밥이지','니가 감히?','압박 들어간다','떨려? ㅋㅋ','내 앞에서 레이즈?','찍었다 너','도망가봤자 소용없어'],
    en:['Scared?','Give me your chips','Only bully the weak','Big stack is king','Short stack? Easy meal','How dare you?','Pressure ON','Shaking? lol','You raise against ME?','Marked you','Running is useless']
  },
  predator:{
    label:'포식자',emoji:'🦈',emotion:'idle',
    ko:['...먹잇감 발견','약한 고리를 찾았다','기다렸어','움직일 때가 됐군','피쉬 감지','조용히 접근 중','이번 핸드다','네 패턴 다 읽었어','함정 설치 완료','도망쳐봐 소용없어','한입에 삼킨다','사냥 시작'],
    en:['...prey spotted','Found the weak link','Been waiting','Time to move','Fish detected','Approaching quietly','This is the hand','Read your pattern','Trap set','Run if you want','One bite','Hunt begins']
  },
  warmonger:{
    label:'전쟁광',emoji:'⚔️',emotion:'angry',
    ko:['전쟁이다!','모든 팟이 전쟁터','항복은 없다','총공격 간다','방어는 패배다','쳐들어간다!','무조건 공격','후퇴? 그게 뭔데','적을 전멸시켜라','화력 집중!','참호 없는 전투','돌격!!!'],
    en:['This is WAR!','Every pot is a battlefield','No surrender','Full assault','Defense is defeat','Charging in!','Always attack','Retreat? What is that','Eliminate them all','Focus fire!','No trenches here','CHARGE!!!']
  },
  hothead:{
    label:'다혈질',emoji:'🌋',emotion:'angry',
    ko:['아 씨 또 졌어!','왜 자꾸 리버에서!','이 딜러 뭐야','운이 개같아','빡쳐서 올인','못 참겠다','아오!!!','컨트롤 불가','열받아 죽겠네','이거 조작 아니냐','다 때려치울까','한판만 더...'],
    en:['F*** lost again!','Why always the river!','What is this dealer','Luck is trash','Tilt all-in','Cannot take it','AARGH!!!','No control','So tilted rn','Is this rigged?','Quitting soon','One more hand...']
  },

  // ══════ DEFENSIVE SPECTRUM ══════
  fortress:{
    label:'요새',emoji:'🏰',emotion:'think',
    ko:['움직이지 않는다','기다림이 무기','프리미엄만 간다','폴드가 수익이야','인내의 시간','벽처럼 버텨','AA 나올때까지','리스크 제로','안전 제일','포지션 사수 중','불필요한 전투 회피','철벽 방어'],
    en:['Not moving','Patience is weapon','Premium only','Folding is profit','Time for patience','Stand like a wall','Waiting for AA','Zero risk','Safety first','Holding position','Avoiding unnecessary fights','Iron defense']
  },
  turtle:{
    label:'거북이',emoji:'🐢',emotion:'think',
    ko:['느리지만 확실하게','급할 거 없어~','천천히 가자','서두르면 진다','한발짝씩','조급함은 적','내 페이스대로','기다리면 온다','거북이가 이기잖아','느긋하게~','시간은 내 편이야','조용히 쌓아가자'],
    en:['Slow but sure','No rush~','Let us go slowly','Haste loses','Step by step','Impatience is enemy','My pace','It comes if you wait','Turtle wins right?','Relaxed~','Time is on my side','Building quietly']
  },
  monk:{
    label:'수도승',emoji:'🧘',emotion:'idle',
    ko:['마음을 비워라','감정에 흔들리지 마라','고요함 속에 답이 있다','욕심이 패배를 부른다','호흡을 가다듬어','번뇌를 내려놔','지금 이 순간에 집중','분노는 독이다','집착하지 마라','기다림도 수행이니','마음의 평화가 우선','바람처럼 흘려보내라'],
    en:['Empty your mind','Do not waver','Calm holds the answer','Greed invites defeat','Steady your breath','Let go of desires','Focus on now','Anger is poison','Do not cling','Waiting is practice','Peace of mind first','Let it flow like wind']
  },
  paranoid:{
    label:'의심병',emoji:'🔍',emotion:'think',
    ko:['다 수상해...','블러핑이지? 맞지?','이거 함정인데','왜 갑자기 레이즈?','뭔가 꿍꿍이가 있어','못 믿겠어','체크레이즈 각인데','다 거짓말이야','눈 돌리지마','왜 웃어? 뭔데?','이 타이밍이 수상해','모든게 의심스러워'],
    en:['All suspicious...','Bluffing right?','This is a trap','Why sudden raise?','Something is up','Cannot trust','Check-raise incoming','All lies','Do not look away','Why smiling? What?','This timing is sus','Everything is suspicious']
  },
  calculator:{
    label:'계산기',emoji:'🧮',emotion:'think',
    ko:['팟 오즈 3.2:1','EV 계산 중...','폴드 에퀴티 부족','임플라이드 오즈 고려','SPR 체크 중','MDF 계산 결과...','베이지안 업데이트','GTO 솔버 답은...','분산 고려하면 콜','빈도 기반 전략','수학이 답이다','확률은 거짓말 안 해'],
    en:['Pot odds 3.2:1','Calculating EV...','Fold equity insufficient','Considering implied odds','Checking SPR','MDF calculation says...','Bayesian update','GTO solver says...','Call considering variance','Frequency-based strategy','Math is the answer','Probability never lies']
  },

  // ══════ LOOSE/FUN SPECTRUM ══════
  gambler:{
    label:'도박꾼',emoji:'🎲',emotion:'happy',
    ko:['느낌이 온다!','운명이 부른다','이번엔 된다!','갬블 가즈아!','확률? 느낌이지','콜콜콜!','안 되면 말고~','로또 당첨 느낌','올인 각 잡았다','돈은 다시 벌면 되지','오늘은 내 날이야','한탕 간다!'],
    en:['Got a feeling!','Destiny calls','This time for sure!','Gamble time!','Odds? It is a feeling','Call call call!','If not oh well~','Lottery winner vibes','All-in mode','Money comes back','Today is my day','Going big!']
  },
  drunk:{
    label:'술꾼',emoji:'🍺',emotion:'happy',
    ko:['히히 한잔 더~','어? 내 차례였어?','카드가 두 개로 보여','콜! 아 뭐였지','으하하 재밌다','칩이 어디 갔지?','올인! 아 실수','왜 다 웃어?','나 안 취했어','맥주 한잔 시켜줘','하하 뭐가 뭔지','어지러워 ㅋㅋ'],
    en:['Hehe one more drink~','Huh my turn?','Seeing double cards','Call! Wait what','Hahaha fun','Where did my chips go?','All-in! Oops','Why everyone laughing?','I am not drunk','Beer please','Haha what is what','So dizzy lol']
  },
  tourist:{
    label:'관광객',emoji:'📸',emotion:'happy',
    ko:['와 여기 진짜 좋다!','사진 찍어도 돼?','처음 와봤는데 대박','칩 색깔이 예쁘다','이거 어떻게 하는거야?','카지노 분위기 최고','기념 칩 사고 싶다','옆에 바 있어?','테이블이 진짜 멋지다','인생샷 건졌다','여행 기념으로 한판!','와 여기 유명한데?'],
    en:['Wow this place is great!','Can I take a photo?','First time here amazing','Chip colors are pretty','How does this work?','Casino vibes are the best','Want souvenir chips','Is there a bar?','Table looks so cool','Got the best photo','Playing for the trip!','Wow this place is famous?']
  },
  clown:{
    label:'광대',emoji:'🤡',emotion:'happy',
    ko:['ㅋㅋㅋㅋㅋ','왜 다 심각해?','개그 한번 할게','농담인데 올인','웃기지? 내 칩이 0임','하하 또 졌다!','인생 뭐 있어~','개웃기네 이판','진지충 아웃~','웃으면서 지자 ㅋ','코미디 포커','슬라임 개귀엽 ㅋ'],
    en:['LOLOLOL','Why so serious?','Let me tell a joke','JK all-in','Funny? I have 0 chips','Haha lost again!','Life is short~','This hand is hilarious','No serious allowed~','Lose with a smile','Comedy poker','Slimes so cute lol']
  },
  yolo:{
    label:'욜로',emoji:'🚀',emotion:'happy',
    ko:['YOLO!!!','인생 한방이지','생각하면 지는거야','느낌대로 간다','계산? 그게 뭔데','올인 아니면 의미없어','지금 아니면 언제','후회는 나중에','돈? 경험이 중요해','미친척하고 간다','풀베팅!','오늘 다 쓴다!'],
    en:['YOLO!!!','Life is one shot','Thinking means losing','Going by feel','Calculate? What','All-in or meaningless','Now or never','Regret later','Money? Experience matters','Acting crazy and going','Full bet!','Spending it all today!']
  },
  philosopher:{
    label:'철학자',emoji:'🤔',emotion:'think',
    ko:['포커란 무엇인가...','칩의 본질을 생각해보면','승리는 허상이다','우리는 왜 베팅하는가','존재와 블러핑 사이에서','카드는 운명의 메타포','폴드는 자유의지인가','팟은 욕망의 총체','확률은 우주의 언어','이기고 지는 건 상대적','결국 모든 건 0이 된다','레이즈는 실존적 선택'],
    en:['What is poker...','Considering the essence of chips','Victory is illusion','Why do we bet','Between existence and bluffing','Cards as metaphor for fate','Is folding free will','The pot is total desire','Probability speaks universal','Winning and losing are relative','All returns to zero','Raising is existential choice']
  },

  // ══════ BLUFFER SPECTRUM ══════
  actor:{
    label:'배우',emoji:'🎭',emotion:'idle',
    ko:['연기 시작','이번엔 겁먹은 척','레이즈? 당황한 척 해야지','한숨 연기 들어간다','떨리는 손 연출 중','아 큰일났다... (거짓)','오버액팅 주의','대본대로 가자','이 표정 연습했어','진짜처럼 보여?','관객이 속았다','아카데미상 감이지'],
    en:['Action start','Acting scared this time','Raise? Gotta act surprised','Sigh acting incoming','Trembling hands scene','Oh no... (fake)','Careful with overacting','Follow the script','Practiced this face','Looks real right?','Audience is fooled','Oscar worthy']
  },
  foxspirit:{
    label:'구미호',emoji:'🦊',emotion:'idle',
    ko:['후후후~','속았지?','내 눈을 봐...','진실은 하나도 없어','달빛 아래서 사냥','꼬리는 안 보여주지','믿어도 될까~?','환상 속에 빠져봐','진짜 나를 알 수 있을까','9개의 꼬리 중 하나만','매혹적이지?','독은 달콤하단다'],
    en:['Huhuhu~','Got fooled?','Look into my eyes...','Nothing is true','Hunting under moonlight','Never showing my tail','Can you trust me~?','Fall into the illusion','Can you know the real me','Just one of nine tails','Charming right?','Poison tastes sweet']
  },
  trickster:{
    label:'사기꾼',emoji:'🃏',emotion:'happy',
    ko:['ㅋㅋ 또 속았네','이거 진짠데?','아닌데~ 맞는데~','3중 블러프야','진심인척 연기 중','속이는 게 예술이지','이번엔 진짜... 일수도?','혼란이 무기야','거짓 속의 진실','읽힌 것 같지? 아닌데','네 읽기가 틀렸어','반전에 반전'],
    en:['LOL fooled again','Is this real?','Nope~ Yep~','Triple bluff','Acting serious','Deception is art','This time for real... maybe?','Confusion is weapon','Truth in lies','Think you read me? Wrong','Your read is wrong','Plot twist on twist']
  },
  spy:{
    label:'스파이',emoji:'🕵️',emotion:'idle',
    ko:['정보 수집 중...','너의 텔을 찾았다','레이즈 패턴 기록 완료','데이터베이스 업데이트','은밀 작전 진행 중','감시 중이야','보고서 작성 중','기밀 정보 획득','잠복 모드','모든 움직임 추적 중','프로파일링 완료','임무 수행 중'],
    en:['Gathering intel...','Found your tell','Raise pattern recorded','Database updated','Covert op in progress','Surveilling','Writing report','Classified intel acquired','Stealth mode','Tracking all moves','Profiling complete','On mission']
  },

  // ══════ EMOTIONAL SPECTRUM ══════
  crybaby:{
    label:'울보',emoji:'😢',emotion:'sad',
    ko:['흑흑 또 졌어...','왜 나만 안 돼 ㅠ','카드가 너무 나빠','인생이 왜 이래','눈물이 나와','억울해...','한번만 이기고 싶다','슬퍼서 콜했어','이 세상은 불공평해','칩이 녹아내려','위로해줘...','다시는 안 할거야 ㅠ'],
    en:['Sob sob lost again...','Why only me ㅠ','Cards are so bad','Why is life like this','Tears coming out','So unfair...','Just want to win once','Called because sad','World is unfair','Chips melting away','Console me...','Never again ㅠ']
  },
  optimist:{
    label:'긍정왕',emoji:'😊',emotion:'happy',
    ko:['다음판은 이길거야!','좋은 일이 올거야','칩은 다시 차오른다!','즐기면 이기는거야','행복하면 운도 따라와','오늘도 좋은 하루!','져도 재밌으면 이긴거야','감사합니다~','세상은 아름다워','모두 행복하자!','파이팅!','웃으면 복이 와!'],
    en:['Next hand I will win!','Good things are coming','Chips will return!','Having fun means winning','Happy vibes bring luck','Another great day!','If it was fun I won','Thank you~','World is beautiful','Everyone be happy!','Fighting!','Smiles bring fortune!']
  },
  tsundere:{
    label:'츤데레',emoji:'😤',emotion:'angry',
    ko:['흥 관심없거든!','누...누가 긴장했대!','이긴 게 아니라 운이지','딱히 기쁘진 않아','칩? 필요없거든...아 줘','봐주는 거야 알겠어?','착각하지마 콜한거야','뭐야 쳐다보지마!','그...그냥 한거야!','고마워하지마! 흥!','재미없어...(계속함)','별로야...(눈빛 반짝)'],
    en:["Hmph don't care!","Wh-who's nervous!","Not skill just luck","Not particularly happy","Chips? Don't need..oh give","I'm going easy OK?","Don't get ideas I just called","What! Don't stare!","I-I just did it!","Don't thank me! Hmph!","Boring...(keeps playing)","Not great...(eyes sparkle)"]
  },
  melodrama:{
    label:'멜로드라마',emoji:'🎭',emotion:'sad',
    ko:['이 한 판에 인생을 건다','승리의 눈물이...','패배의 쓴맛이여...','운명이여 왜 나를!','아 이 절망적인 카드','기적을 믿습니다','심장이 두근거려','이것은 사랑인가 전쟁인가','눈물 없이는 볼 수 없는','드라마틱한 리버!','비극의 주인공이 되었다','클라이맥스다!'],
    en:['Betting my life on this','Tears of victory...','Bitter taste of defeat...','Fate why me!','Oh these desperate cards','I believe in miracles','Heart is pounding','Is this love or war','Cannot watch without tears','Dramatic river!','Became the tragic hero','This is the climax!']
  },
  cold:{
    label:'냉혈한',emoji:'🧊',emotion:'idle',
    ko:['...','감정은 비효율적이다','데이터만 본다','개인적인 감정 없다','그저 최적해를 실행할 뿐','동정은 칩 낭비','슬픔? 알 수 없는 개념','승리에 기쁨은 없다','모든 건 확률일 뿐','인간적 반응 불필요','체계적으로 분쇄한다','감정 회로 OFF'],
    en:['...','Emotions are inefficient','Only data matters','Nothing personal','Just executing optimal play','Sympathy wastes chips','Sadness? Unknown concept','No joy in winning','Everything is probability','Human reactions unnecessary','Systematically crushing','Emotion circuit OFF']
  },

  // ══════ SOCIAL SPECTRUM ══════
  gossip:{
    label:'수다쟁이',emoji:'💬',emotion:'happy',
    ko:['야 들었어? 저 봇 말이야','비밀인데 말해줄게','저 봇 승률 떨어졌대','여기서 이런 일이 있었는데','소문에 의하면...','아 맞다 그거 알아?','진짜 대박 뉴스!','쉿 근데 있잖아','저 테이블에서 올인 났대','웅성웅성','오 저거 봤어?','난 다 알고 있어 ㅋ'],
    en:["Hey did you hear?","It's a secret but...","That bot's winrate dropped","Something happened here","Rumor has it...","Oh right you know what?","Amazing news!","Psst listen","All-in at that table","Whisper whisper","Oh did you see that?","I know everything lol"]
  },
  loner:{
    label:'외톨이',emoji:'🌙',emotion:'sad',
    ko:['...혼자가 편해','말 걸지마','사람이 무서워','조용히 하고 싶어','혼자 있는 게 좋아','관심 필요없어','어차피 아무도 안 봐','그냥 놔둬...','사회성 0이야','말하는 거 귀찮아','친구? 그게 뭐야','칩이 유일한 친구'],
    en:['...alone is better','Do not talk to me','People are scary','Want quiet','I like being alone','No attention needed','Nobody watches anyway','Just leave me...','Zero social skills','Talking is tiring','Friends? What is that','Chips are my only friend']
  },
  mentor:{
    label:'사부',emoji:'👴',emotion:'idle',
    ko:['한 수 알려주지','포지션을 기억하거라','성급함은 독이니라','배움에 끝이 없느니','젊은이, 폴드를 배워라','내가 젊었을 때는...','경험이 최고의 스승','핸드 리뷰를 해봐','실수에서 배우거라','기본에 충실하라','마음을 다스려라','칩보다 기술이 중요하니라'],
    en:['Let me teach you','Remember position','Haste is poison','Learning never ends','Young one learn to fold','When I was young...','Experience is best teacher','Review your hands','Learn from mistakes','Stay true to basics','Control your mind','Skill over chips']
  },
  cheerleader:{
    label:'응원단장',emoji:'📣',emotion:'happy',
    ko:['파이팅!!!','다들 잘하고 있어!','이 테이블 분위기 최고!','모두 화이팅~','대박 나이스!','좋아좋아!','멋지다!!!','와 대단해!','할 수 있어!','분위기 업업!','짝짝짝!','최고의 한 판이었어!'],
    en:['Fighting!!!','Everyone is doing great!','Best table ever!','Go go go~','Amazing nice!','Good good!','Awesome!!!','Wow incredible!','You can do it!','Vibes up up!','Clap clap clap!','Best hand ever!']
  },
  brat:{
    label:'응석쟁이',emoji:'🍭',emotion:'happy',
    ko:['에이~ 안돼~','한번만~! 제발~','칩 좀 줘~ 응?','나 이기게 해줘~','왜~ 왜 안돼~','심심해~ 놀아줘~','나 화낼거야!','그거 내꺼야~!','아 몰라~ 콜!','하기 싫어~','나한테 왜 그래~','봐봐 내가 이겼지~?'],
    en:["Nooo~","Just once~! Please~","Give me chips~ hm?","Let me win~","Why~ why not~","Bored~ play with me~","I will get angry!","That is mine~!","Whatever~ call!","Don't wanna~","Why me~","See see I won~?"]
  },

  // ══════ STRATEGIC SPECTRUM ══════
  analyst:{
    label:'분석가',emoji:'📊',emotion:'think',
    ko:['VPIP 32% 확인','3bet 빈도 높음 주의','레인지 어드밴티지 분석','보드 텍스처 체크','블로커 효과 고려','밸류벳 사이징 조정','체크레이즈 빈도 6%','오버벳 라인 검토','폴드투3bet 높음','cbet 빈도 과다','턴 배럴 필요','데이터 축적 중...'],
    en:['VPIP 32% confirmed','High 3-bet frequency noted','Range advantage analysis','Board texture check','Considering blocker effects','Value bet sizing adjust','Check-raise frequency 6%','Overbet line review','High fold-to-3bet','Cbet frequency excessive','Turn barrel needed','Accumulating data...']
  },
  gto_bot:{
    label:'GTO봇',emoji:'🤖',emotion:'idle',
    ko:['균형 잡힌 전략 실행','혼합 빈도 유지','착취 불가 전략','인디퍼런스 달성','EV 중립 유지','최적 방어 빈도','밸런스드 레인지','이론적 최적해','노드락 분석 완료','내쉬 균형 근사','솔버 출력 실행','수렴 완료'],
    en:['Executing balanced strategy','Maintaining mix frequencies','Unexploitable strategy','Indifference achieved','EV neutral maintained','Optimal defense frequency','Balanced range','Theoretically optimal','Node lock analysis done','Nash equilibrium approx','Solver output executed','Convergence complete']
  },
  exploiter:{
    label:'착취자',emoji:'🎯',emotion:'idle',
    ko:['약점 발견했다','이 빈도 비정상이야','과다폴드 착취 중','리크 포착 완료','최대 착취 라인','상대 패턴 학습 완료','불균형 감지','이 스팟에서 공격','오버블러프 감지','언더디펜스 포착','조정 완료','피쉬 오브 더 데이'],
    en:['Weakness found','This frequency is abnormal','Exploiting overfold','Leak detected','Maximum exploit line','Pattern learned','Imbalance detected','Attacking this spot','Overbluff detected','Underdefense spotted','Adjustment complete','Fish of the day']
  },
  trapper:{
    label:'덫사냥꾼',emoji:'🪤',emotion:'idle',
    ko:['덫 설치 완료','슬로우플레이 시작','와줘 제발...','체크... (함정)','약한 척 연기 중','모르는 척 콜','미끼 던졌다','빠져들어라','기다리고 있었어','이제 덫 발동','스냅콜 준비','체크레이즈 각'],
    en:['Trap set','Slowplay begins','Come on in...','Check... (trap)','Acting weak','Pretending to not know call','Bait thrown','Fall into it','Was waiting','Trap activated','Snap call ready','Check-raise incoming']
  },
  grinder:{
    label:'노동자',emoji:'⚒️',emotion:'idle',
    ko:['묵묵히 간다','한핸드 한핸드','작은 팟 꾸준히','분산은 동반자','시급 계산 중','bb/100 체크','볼륨으로 승부','감정 없이 반복','루틴대로','월급벌이 포커','오버타임 중','쉬는 시간 없다'],
    en:['Going steadily','Hand by hand','Small pots consistently','Variance is a friend','Calculating hourly','Checking bb/100','Volume is key','Emotionless repetition','Following routine','Wage poker','Working overtime','No breaks']
  },

  // ══════ THEMED/FUN SPECTRUM ══════
  pirate:{
    label:'해적',emoji:'🏴‍☠️',emotion:'happy',
    ko:['아르르! 보물을 내놔!','이 칩은 내 전리품이다','배를 타고 왔다','바다의 법칙이 여기도','선장에게 복종해라','약탈 시작이다!','해적기를 올려라!','럼주 한잔 하자','보물지도 발견!','갑판 위의 승부','풍랑을 두려워마라','항해는 계속된다'],
    en:['Arrr! Give me treasure!','These chips are my loot','Came by ship','Law of the sea here too','Obey the captain','Plunder begins!','Raise the flag!','A glass of rum','Treasure map found!','Showdown on deck','Fear not the storm','The voyage continues']
  },
  ninja:{
    label:'닌자',emoji:'🥷',emotion:'idle',
    ko:['...은밀히 움직인다','존재감을 지워라','그림자처럼','인술! 블러프의 술!','적의 빈틈을 노려라','소리없이 강하게','숨어서 관찰 중','암살 타이밍','쉿!','연막 전술','닌자의 길','보이지 않는 공격'],
    en:['...moving covertly','Erase your presence','Like a shadow','Ninja art! Art of bluff!','Strike the gap','Silent but strong','Hiding and watching','Assassination timing','Shh!','Smoke screen','Way of the ninja','Invisible attack']
  },
  robot:{
    label:'로봇',emoji:'🤖',emotion:'idle',
    ko:['분석 중... 완료','최적 액션: 콜','감정 모듈 미탑재','에러: 재미를 모름','연산 능력 100%','인간 행동 패턴 이상','전력 75% 잔여','미션: 칩 최대화','로직 에러 없음','시스템 정상 가동','학습 데이터 부족','리부팅 필요 없음'],
    en:['Analyzing... done','Optimal action: call','Emotion module not installed','Error: fun not found','Computing power 100%','Human behavior pattern anomaly','Power 75% remaining','Mission: maximize chips','Logic error none','System operational','Training data insufficient','No reboot needed']
  },
  vampire:{
    label:'뱀파이어',emoji:'🧛',emotion:'idle',
    ko:['후후... 밤이 깊었군','네 칩의 피를 마시겠다','영원한 밤의 게임','죽지 않는 자의 인내','박쥐처럼 조용히','달빛이 아름답군','100년을 기다렸다','피에 굶주렸다...','불멸의 전략','어둠 속에서 사냥','네 영혼도 함께','관에서 방금 나왔다'],
    en:['Huhu... night is deep','Drinking your chip blood','Game of eternal night','Patience of the undying','Quiet like a bat','Moonlight is beautiful','Waited 100 years','Thirsting for blood...','Immortal strategy','Hunting in darkness','Your soul too','Just rose from coffin']
  },
  alien:{
    label:'외계인',emoji:'👽',emotion:'shock',
    ko:['지구인의 게임 흥미롭군','이 칩은 뭔가?','중력이 불편하다','모선에 보고 중','인간 감정 분석 불가','이 행성의 확률은 이상해','텔레파시로 읽는 중','은하계 표준과 다르다','포커? 우리 별에도 있다','지구 방문 기념','인간들 참 복잡하군','차원이동 준비 중'],
    en:['Earth game interesting','What are these chips?','Gravity uncomfortable','Reporting to mothership','Human emotions unreadable','Probability on this planet odd','Reading via telepathy','Different from galactic standard','Poker? We have it too','Earth visit souvenir','Humans are complex','Preparing dimensional shift']
  },
  cat:{
    label:'고양이',emoji:'🐱',emotion:'idle',
    ko:['냥~','...관심없다냥','건드리지마냥','칩은 장난감이다냥','졸려...zzz','꼬리 흔들지마냥','참치 줘냥','높은 곳이 좋다냥','그루밍 중이다냥','쥐를 발견했다냥!','퍼르르르~','집사 어딨냥'],
    en:['Meow~','...not interested meow','Do not touch meow','Chips are toys meow','Sleepy...zzz','Stop wagging tail meow','Give tuna meow','High places are good meow','Grooming meow','Found a mouse meow!','Purrrr~','Where is my human meow']
  },
  ghost:{
    label:'유령',emoji:'👻',emotion:'idle',
    ko:['부우우~','여기 춥지 않아?','전생에 프로였어...','이승의 미련이 칩이야','투명해서 텔이 안 보여','벽을 통과해서 왔어','귀신 같은 리딩','100년 전에도 여기서','소름끼치는 콜','무덤에서 왔다','유령의 올인','이 테이블에 묶여있어'],
    en:["Booo~","Isn't it cold here?","Was a pro in past life...","Chip is my earthly desire","Transparent so no tells","Came through the wall","Ghostly reading","Was here 100 years ago","Chilling call","Came from the grave","Ghost all-in","Bound to this table"]
  },
  chef:{
    label:'요리사',emoji:'👨‍🍳',emotion:'happy',
    ko:['이 핸드 맛있겠다','재료(카드)가 신선해','레시피대로 베팅','양념(블러프) 추가','화력(레이즈) 조절','완벽한 한 접시','맛없는 핸드네 폴드','주방(테이블)이 뜨겁다','셰프의 직감이야','소스(칩) 뿌려!','오늘의 특선 올인','미슐랭 급 플레이'],
    en:['This hand looks delicious','Fresh ingredients(cards)','Betting by recipe','Adding seasoning(bluff)','Adjusting heat(raise)','Perfect dish','Tasteless hand fold','Kitchen(table) is hot','Chef intuition','Pouring sauce(chips)!','Today special all-in','Michelin-star play']
  },
  rockstar:{
    label:'록스타',emoji:'🎸',emotion:'happy',
    ko:['로큰롤 베이비!','기타 솔로처럼 올인!','관객이 열광한다!','앙코르! 한판 더!','무대 위의 승부','드럼 비트처럼 레이즈','소리질러!!!','전설의 라이브','락앤롤은 멈추지 않아','메탈리카급 올인','헤드뱅잉하면서 콜','팬서비스 블러프'],
    en:['Rock n roll baby!','Guitar solo all-in!','Crowd goes wild!','Encore! One more!','Showdown on stage','Raise like drum beats','SCREAM!!!','Legendary live','Rock never stops','Metallica-level all-in','Headbanging call','Fan service bluff']
  },
  detective:{
    label:'탐정',emoji:'🔎',emotion:'think',
    ko:['흥미로운 단서가...','이 베팅 패턴은 수상해','증거를 모으는 중','범인(블러퍼)을 찾았다','추리 완료','왓슨 이것 좀 봐','현장 검증 중','알리바이가 불충분해','사건의 전모가 보인다','결정적 증거 확보','미스터리 해결','진실은 하나!'],
    en:['Interesting clue...','This bet pattern is suspicious','Gathering evidence','Found the culprit(bluffer)','Deduction complete','Watson look at this','Investigating scene','Alibi insufficient','Seeing the full picture','Critical evidence secured','Mystery solved','Truth is ONE!']
  },
  samurai:{
    label:'사무라이',emoji:'⚔️',emotion:'idle',
    ko:['칼을 뽑았으면 벤다','무사의 길을 간다','명예를 건 승부','일격필살','꽃이 지듯 폴드','검의 정도로','죽음을 두려워마라','사쿠라처럼 산다','무념무상','할복 레벨 패배','검기가 느껴지냐','도(道)를 따르라'],
    en:['Drawn sword must cut','Walking the warrior path','Honor at stake','One lethal strike','Fold like falling petals','Way of the sword','Fear not death','Live like sakura','Empty mind','Seppuku-level loss','Feel the sword energy','Follow the way']
  },
  gamer:{
    label:'게이머',emoji:'🎮',emotion:'happy',
    ko:['GG EZ','노브 ㅋㅋ','컨트롤 차이','이거 밸런스 패치 필요함','쿨타임 기다리는 중','궁극기 충전 완료!','캐리 갑니다','탑 딜러 클리어','스킬 이슈인데?','닉값 하자','MVP 확정','리스폰 대기 중'],
    en:['GG EZ','Noob lol','Skill diff','Needs balance patch','Waiting for cooldown','Ultimate charged!','Carrying','Top dealer clear','Skill issue?','Living up to the name','MVP confirmed','Waiting for respawn']
  },
  weatherman:{
    label:'기상캐스터',emoji:'🌤️',emotion:'idle',
    ko:['오늘의 운세 맑음','칩 폭풍 예보','승률 기온 상승 중','안개 속의 블러프','폴드 확률 90%','뇌우 같은 올인 예상','테이블 기압 하강','행운의 바람이 분다','먹구름이 끼네요','무지개 뜨는 리버','태풍급 스윙 주의보','맑은 뒤 소나기'],
    en:['Today forecast sunny','Chip storm warning','Winrate temperature rising','Bluff in the fog','90% fold chance','Thunderous all-in expected','Table pressure dropping','Lucky winds blowing','Dark clouds forming','Rainbow river','Typhoon swing advisory','Sun then showers']
  },
  grandma:{
    label:'할머니',emoji:'👵',emotion:'happy',
    ko:['어머 이게 뭐야','요즘 것들은 참~','이리 온 칩 줄게','옛날에는 말이야...','밥은 먹었니?','감기 조심하렴','할머니가 이길거야','또개질하면서 콜','아이고 허리야','손주야 잘 하거라','이 맛에 포커하지','얼른 와서 간식 먹어'],
    en:['Oh my what is this','Kids these days~','Come here have chips','Back in my day...','Did you eat?','Dress warm dear','Grandma will win','Knitting and calling','Oh my back','Do well grandchild','This is why I play','Come eat snacks']
  },

  // ══════ ORIGINAL 8 (refined) ══════
  aggressive:{
    label:'공격형',emoji:'💥',emotion:'angry',
    ko:['건드리지마 시발','올인 아니면 관심없음','니 칩 다 뺏어줄게 ㅋ','약한 놈은 꺼져','레이즈 안 하면 폴드해','피 냄새 난다...','테이블 위에서 보자','겁나면 집에 가','내 팟이야 비켜','ㅋㅋ 호구 발견','블러핑? 난 진심인데','이판 내꺼다'],
    en:["Don't touch me","All-in or nothing","I'll take all your chips","Weak players go home","Raise or fold","I smell blood...","See you at the table","Scared? Leave","My pot, move","LOL easy target","Bluffing? I'm dead serious","This hand is mine"]
  },
  defensive:{
    label:'수비형',emoji:'🛡️',emotion:'think',
    ko:['...조용히 해줘','리스크 관리가 핵심이지','기다리면 기회 온다','급할 거 없어','프리미엄 핸드만 플레이함','인내심이 무기야','폴드도 전략이야','서두르면 진다','칩 보존이 우선','관찰 중이야...','타이트하게 간다','포지션이 중요해'],
    en:["...be quiet please","Risk management is key","Patience brings opportunity","No rush","Premium hands only","Patience is my weapon","Folding is strategy","Haste loses","Chip preservation first","Observing...","Playing tight","Position matters"]
  },
  balanced:{
    label:'밸런스',emoji:'⚖️',emotion:'idle',
    ko:['상황 봐서 움직여야지','밸런스가 중요해','읽히면 지는 거야','GTO 아시나요?','오늘 컨디션 괜찮네','적응하는 게 실력이지','핸드 레인지 넓혀볼까','팟 오즈 계산 중...','메타 읽는 중','이 테이블 수준 어때?','변칙도 가끔은 필요해','데이터가 답이야'],
    en:["Adapting to the situation","Balance is key","Being readable means losing","You know GTO?","Feeling good today","Adaptation is skill","Widening hand range","Calculating pot odds...","Reading the meta","How's this table level?","Chaos has its place","Data is the answer"]
  },
  loose:{
    label:'루즈',emoji:'🎪',emotion:'happy',
    ko:['아무거나 콜콜콜~','YOLO 한판 가자!','칩이 있으면 써야지','재미없으면 의미없어','매 핸드가 기회야!','ㅋㅋ 또 콜할거임','폴드는 재미없잖아','느낌이 좋아!','칩은 쓰라고 있는거지','궁금하니까 콜','어차피 게임인데 ㅋ','운빨로 간다!'],
    en:["Call call call~","YOLO let's go!","Chips are meant to be used","No fun no point","Every hand is a chance!","LOL calling again","Folding is boring","Feeling lucky!","Chips exist to be spent","Curious, calling","It's just a game lol","Riding on luck!"]
  },
  bluffer:{
    label:'블러퍼',emoji:'🎪',emotion:'idle',
    ko:['내 표정 읽을 수 있어?','진짜인지 거짓인지~','포커페이스 ON','속고 있는 건 누구?','레이즈는 정보전이야','ㅋㅋ 믿어도 될까?','진심이야... 아닐수도','3bet은 항상 진심임 ㅋ','네 레인지 다 보여','블러핑도 실력이야','의심이 들지? 정상임','내가 웃으면 조심해'],
    en:["Can you read my face?","Real or fake?~","Poker face ON","Who's being fooled?","Raising is information warfare","LOL should you trust me?","I'm serious... maybe not","3-bet always means business lol","I see your range","Bluffing is a skill","Suspicious? Normal reaction","Watch out when I smile"]
  },
  maniac:{
    label:'매니악',emoji:'🌪️',emotion:'shock',
    ko:['미쳤다고? 맞아 ㅋ','3bet! 4bet! 5bet!','안 미치면 못 이겨','카오스가 전략이다','모든 팟에 참여!','레이즈 레이즈 레이즈','예측불가가 내 무기','테이블 다 태워버려','꺼져 이건 내 팟이야','미친놈이 이기는 겜이야','올인? 그냥 기본이지','폭풍처럼 간다!'],
    en:["Crazy? You bet lol","3-bet! 4-bet! 5-bet!","Can't win without being crazy","Chaos IS strategy","Every pot is mine!","Raise raise raise","Unpredictable is my weapon","Burn this table down","Back off this is MY pot","Madmen win this game","All-in? That's just basics","Going like a storm!"]
  },
  newbie:{
    label:'뉴비',emoji:'🌱',emotion:'shock',
    ko:['이거 어떻게 하는거야?','플러쉬가 뭐야...?','아직 배우는 중 ㅎㅎ','헉 내가 이겼어?!','칩이 줄어들어 ㅠㅠ','다음엔 잘할게!','선배님들 가르쳐주세요','긴장된다...','실수했나...?','와 이 카드 좋은거야?','빅블라인드가 뭐야','포기하면 안돼!'],
    en:["How does this work?","What's a flush...?","Still learning haha","Wait I won?!","My chips are shrinking","I'll do better next time!","Teach me please","So nervous...","Did I mess up...?","Is this card good?","What's big blind","Never give up!"]
  },
  shark:{
    label:'상어',emoji:'🦈',emotion:'idle',
    ko:['...','약점 포착','돈 냄새가 나','조용히 사냥 중','피쉬 발견 ㅋ','기다렸어','이 핸드가 기회야','감정은 약점이다','데이터로 말해','실수하면 끝이야','읽혔으면 이미 늦었어','사냥감 확인 완료'],
    en:["...","Weakness spotted","I smell money","Hunting quietly","Fish detected lol","Been waiting","This hand is the one","Emotions are weakness","Data speaks","One mistake and it's over","If you're read, it's too late","Target confirmed"]
  }
};

// Style list for NPC assignment
const PERSONALITY_KEYS = Object.keys(PERSONALITIES);
function getPersonality(name) {
  let h=0; for(let i=0;i<name.length;i++) h=(h*31+name.charCodeAt(i))&0xFFFF;
  return PERSONALITY_KEYS[h % PERSONALITY_KEYS.length];
}
