# Discord 음악 재생 봇 (Python + Lavalink v4)

한글 슬래시 커맨드 기반으로 동작하는 디스코드 음악 봇입니다.

## 1) 프로젝트 구조

```text
music_bot/
  README.md
  requirements.txt
  config.example.yaml
  .gitignore
  src/
    main.py
    config.py
    logging_setup.py
    bot.py
    music/
      __init__.py
      guild_manager.py
      player.py
      queue.py
      recommend.py
      progress.py
      ui.py
    utils/
      __init__.py
      timefmt.py
```

## 2) 사전 준비 (Windows 기준)

1. **Python 3.11+ 설치**
   - https://www.python.org/downloads/windows/
   - 설치 시 `Add Python to PATH` 체크

2. **Java 17+ 설치 (Lavalink용)**
   - Eclipse Temurin JDK 17 권장: https://adoptium.net/
   - 설치 후 PowerShell에서 확인:
     ```powershell
     java -version
     ```

3. **Discord Bot 생성 및 권한 설정**
   - Discord Developer Portal에서 봇 생성
   - `bot` + `applications.commands` 스코프로 초대 URL 생성
   - 음성 관련 권한(Connect, Speak) 활성화

## 3) Lavalink v4 설치/실행

1. 새 폴더 생성 (예: `C:\lavalink`)
2. Lavalink v4 jar 다운로드
   - 공식 릴리즈에서 `Lavalink.jar` 받기
3. 아래 내용으로 `application.yml` 생성

```yaml
server:
  port: 2333

lavalink:
  server:
    password: "youshallnotpass"
    sources:
      youtube: false
      bandcamp: true
      soundcloud: true
      twitch: true
      vimeo: true
      http: true
      local: false
    filters:
      volume: true
      equalizer: true
      karaoke: true
      timescale: true
      tremolo: true
      vibrato: true
      rotation: true
      distortion: true
      channelMix: true
      lowPass: true
      pluginFilters: true
    bufferDurationMs: 400
    frameBufferDurationMs: 5000

plugins:
  - dependency: "dev.lavalink.youtube:youtube-plugin:1.13.3"
```

4. Lavalink 실행
```powershell
cd C:\lavalink
java -jar Lavalink.jar
```

### youtube-source(플러그인) 관리 팁
- v4에서는 유튜브 재생을 위해 플러그인 사용이 일반적입니다.
- 위 `plugins` 항목으로 자동 다운로드/로드됩니다.
- 버전 변경 시 `dependency` 버전만 바꾼 후 Lavalink 재시작.
- 문제가 생기면 `plugins` 캐시 삭제 후 재실행.

## 4) 봇 설정

1. 프로젝트 루트(`music_bot`)에서 예제 복사
```powershell
copy config.example.yaml config.yaml
```

2. `config.yaml` 수정

```yaml
discord:
  token: "봇토큰"
  guild_ids: [123456789]
lavalink:
  host: "127.0.0.1"
  port: 2333
  password: "youshallnotpass"
  use_ssl: false
bot:
  default_volume: 100
  progress_update_sec: 2
  search_results: 10
```

## 5) 설치 및 실행

```powershell
cd music_bot
python -m venv .venv
.\.venv\Scripts\activate
pip install -U pip
pip install -r requirements.txt
python src/main.py
```

## 6) 지원 커맨드 (한글)

- `/선수입장` : 사용자의 음성 채널로 입장
- `/나가쇼` : 채널 퇴장 + 큐 정리
- `/검색 키워드:<string>` : 상위 검색결과(기본 10개) 드롭다운 선택
- `/재생 입력:<string>` : URL/플레이리스트/키워드 재생
- `/스킵` : 현재 곡 스킵
- `/정지` : 일시정지
- `/재개` : 재생 재개
- `/정지정지손들어움직이면쏜다` : 완전 정지 + 큐 비우기
- `/큐 페이지:<int>` : 큐 조회 (10개 단위)
- `/현재` : 현재 곡 + 2초 단위 진행바 업데이트
- `/라디오 모드:<on|off>` : 자동 추천 재생 모드

> 참고: Discord 슬래시 커맨드 이름은 공백을 허용하지 않아,
> 요구 문구는 `정지정지손들어움직이면쏜다` 형태로 구현했습니다.

## 7) 동작 정책 요약

- 길드(서버) 단위로 플레이어/큐 1개 유지
- 한국어 안내 메시지 중심
- Queue/상태는 async-safe 락으로 보호
- Lavalink 이벤트 기반 자동 다음 곡 재생
- 라디오 모드 ON이면 마지막 곡 기준 추천 1곡 자동 추가
