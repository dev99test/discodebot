# Discord 음악 재생 봇 (Python + Lavalink v4)

한글 슬래시 커맨드 기반의 디스코드 음악 봇입니다.  
민감정보(토큰/IP/PORT/PASSWORD)는 **config.yaml**에서만 관리합니다.

## 1. 프로젝트 구조

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

## 2. 요구사항

- Python 3.11+
- Java 17+ (Lavalink v4)
- FFmpeg (필수)
- Discord Bot Token

---

## 3. Windows 설치 가이드

### 3-1) Python 설치
1. https://www.python.org/downloads/windows/ 에서 Python 3.11 이상 설치
2. 설치 시 `Add python.exe to PATH` 체크

### 3-2) Java 17+ 설치
1. https://adoptium.net/ (Temurin 17 권장) 설치
2. 확인:
   ```powershell
   java -version
   ```

### 3-3) FFmpeg 설치 (필수)
1. https://www.gyan.dev/ffmpeg/builds/ 에서 release full 빌드 다운로드
2. 압축 해제 후 `bin` 폴더 경로를 환경변수 PATH에 추가
3. 확인:
   ```powershell
   ffmpeg -version
   ```

---

## 4. Lavalink v4 준비

1. 예: `C:\lavalink` 폴더 생성
2. Lavalink v4 `Lavalink.jar` 다운로드
3. `application.yml` 생성:

```yaml
server:
  port: 2333

lavalink:
  server:
    password: "youshallnotpass"
    sources:
      youtube: false
      soundcloud: true
      bandcamp: true
      twitch: true
      vimeo: true
      http: true
      local: false

plugins:
  - dependency: "dev.lavalink.youtube:youtube-plugin:1.13.3"
```

4. 실행:
```powershell
cd C:\lavalink
java -jar Lavalink.jar
```

> `youtube-plugin` 버전을 바꾸려면 `dependency` 버전만 수정 후 Lavalink 재시작하면 됩니다.

---

## 5. 봇 설정 파일

### 5-1) 예제 복사
```powershell
cd music_bot
copy config.example.yaml config.yaml
```

### 5-2) config.yaml 수정

```yaml
discord:
  token: "디스코드_봇_토큰"
  test_guild_ids: [123456789012345678]

lavalink:
  host: "127.0.0.1"
  port: 2333
  password: "youshallnotpass"

bot:
  default_volume: 100
  progress_update_sec: 2
  search_results: 10
```

- `test_guild_ids`를 비우면 글로벌 커맨드로 동기화됩니다.

---

## 6. 실행 방법

```powershell
cd music_bot
python -m venv .venv
.\.venv\Scripts\activate
pip install -U pip
pip install -r requirements.txt
python src/main.py
```

실행 시 FFmpeg가 없으면 시작 전에 한글 오류로 종료됩니다.


> 이미 설치된 가상환경에서 `lavalink.integrations` 오류가 난다면 아래처럼 의존성을 다시 설치하세요.
> ```powershell
> pip uninstall -y lavalink
> pip install -r requirements.txt
> ```



## 7. 한글 슬래시 커맨드

- `/선수입장` : 내가 있는 음성 채널로 봇 입장
- `/나가` : 음성 채널 퇴장 + 큐 정리
- `/검색 키워드:<string>` : 유튜브 검색(상위 최대 10) + Select 메뉴
- `/재생 입력:<string>` : URL 재생 / 키워드면 검색 1곡 재생
- `/스킵` : 현재 트랙 건너뛰기
- `/정지` : 일시정지
- `/재개` : 재생 재개
- `/완전정지` : 정지 + 큐 비우기
- `/큐` : 큐 보기 (버튼 페이지 이동)
- `/현재` : 현재 재생곡 + 2초 단위 프로그레스바 갱신
- `/라디오 모드:<on|off>` : 자동 유사곡 큐잉 ON/OFF

---

## 8. 내부 동작 정책

- 길드당 플레이어/큐 1개 유지
- 큐/재생 전환은 비동기 락으로 보호
- 검색/라디오 자동재생 시 `live`, `cover`, 30초 미만 트랙 필터링
- `/현재` 진행 메시지는 길드당 1개만 갱신(스팸 방지)
- Lavalink 연결 끊김 이벤트를 감지하고 재연결 로그 출력

