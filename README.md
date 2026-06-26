# 서울과기대 공지사항 Q&A 웹 서비스

최근 1년 공지사항을 크롤링·검색해 질문에 답하는 웹앱입니다.
근거가 없으면 "모르겠습니다"라고 정직하게 답합니다.

## 구성
| 파일 | 역할 |
|------|------|
| `app.py` | 크롤링·검색 핵심 로직 (CLI 로도 사용 가능) |
| `server.py` | Flask 웹 서버 — `app.py` 함수를 재사용 |
| `templates/index.html` | 채팅형 질의응답 UI (다크 테마) |
| `requirements.txt` | 의존성 (flask, requests, beautifulsoup4, gunicorn) |
| `Procfile` / `render.yaml` | Render 배포 설정 |

## 로컬 실행
> Windows 에 Python 이 필요합니다. 없으면 https://www.python.org/downloads 에서 설치
> (설치 시 "Add Python to PATH" 체크).

```bash
pip install -r requirements.txt
python server.py
```
→ 브라우저에서 http://127.0.0.1:5000 접속
→ 처음 한 번 **[데이터 수집]** 버튼을 눌러 공지를 크롤링한 뒤 질문하세요.

CLI 로만 쓰려면:
```bash
python app.py --build
python app.py --ask "장학금 신청 언제까지야?"
```

## Render 배포
1. 이 폴더를 GitHub 저장소에 푸시 (`기본정보.txt` 참고)
2. Render → New → **Web Service** → 해당 저장소 선택
3. 설정값 (render.yaml 이 자동 인식되거나 수동 입력):
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn server:app`
4. 배포 후 사이트에서 **[데이터 수집]** 1회 실행

> ⚠️ Render 무료 플랜은 디스크가 휘발성이라, 재시작하면 `notice_cache.json` 이
> 사라집니다. 그때는 [데이터 수집]을 다시 누르면 됩니다.
