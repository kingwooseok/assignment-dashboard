# 마감노트

과제와 캘린더 일정을 모아 마감 현황을 확인하는 로컬 웹앱입니다.
FastAPI와 HTML/CSS/JavaScript, SQLite를 사용합니다.
GitHub Actions에서 테스트와 Docker 이미지 배포를 자동으로 실행합니다.

## 실행

Windows에 Python 3.11 이상을 설치한 뒤 프로젝트 폴더에서 실행합니다.

```powershell
.\start.bat
```

처음 실행할 때 `.venv` 환경과 필요한 패키지를 준비합니다. 최초 설치에는 인터넷이 필요합니다.
서버가 시작되면 **http://127.0.0.1:8000** 을 브라우저에서 엽니다.
서버 종료는 실행한 터미널에서 **Ctrl+C**를 누릅니다.

직접 설치하고 실행할 수도 있습니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

8000번 포트를 다른 프로그램이 사용한다면 `run.py --port 8001`로 실행하고
http://127.0.0.1:8001 에 접속합니다.

## 주요 기능

- 과제 등록·수정·삭제, 메모와 과제 링크 저장
- 날짜 또는 날짜·시각을 지정하고 한국 시간 기준으로 D-day 표시
- 오늘 마감, 이번 주 마감, 기한 지난 미완료, 완료 과제 수 표시
- 과목 필터, 과제명 검색, 전체·미완료·완료 상태 필터
- 완료 처리와 취소, 전체 과제 완료율 표시
- `.ics` 캘린더 파일 미리보기, 선택한 일정 가져오기, 과목 지정
- 같은 일정의 중복 등록 방지
- SQLite 자동 저장 및 재실행 시 복원
- 창 너비에 맞춰 배치가 바뀌는 화면과 한국어 오류 안내

### 집계 기준

마감 현황과 진행률은 전체 저장 목록을 기준으로 계산합니다. 검색과 필터는 목록에 적용됩니다.
‘이번 주’는 오늘부터 이번 주 일요일까지이며, 완료한 과제는 미완료 마감 집계에서 빠집니다.
시각을 지정한 과제는 해당 시각이 지나면 ‘기한 지남’으로 표시됩니다.
날짜만 지정한 과제는 당일 내내 ‘오늘 마감’으로 표시됩니다.

## 캘린더 파일 사용

`.ics`는 일정 제목과 날짜 등을 담는 표준 캘린더 파일입니다.

1. **캘린더 가져오기**를 누르고 `.ics` 파일을 선택합니다.
2. 가져올 일정을 선택합니다. 과목명이 비어 있으면 입력합니다.
3. **선택한 일정 가져오기**를 눌러 저장합니다.

**예시 파일로 체험** 버튼은 프로젝트의 `sample_assignments.ics`를 미리보기로 엽니다.
직접 선택해서 테스트할 수 있도록 다운로드 링크도 제공합니다.
이 파일에는 2026년 11월의 시연용 과제 6개가 들어 있습니다.

### 읽는 필드

| ICS 필드 | 사용 방식 |
| --- | --- |
| `SUMMARY` | 과제명 |
| `DTSTART` | 마감 날짜·시각. 날짜만 있으면 날짜 그대로 유지 |
| `CATEGORIES` | 첫 번째 항목을 과목명으로 사용. 없으면 직접 지정 |
| `DESCRIPTION` | 메모 |
| `URL` | 과제 페이지 링크 |
| `UID`, `RECURRENCE-ID` | 중복 식별 |

UTC와 지정된 시간대의 시각은 한국 시간으로 변환합니다. 시간대 없는 시각은 한국 시간으로 해석합니다.
UID가 없으면 제목·시작일·메모·링크로 식별합니다.
이미 등록한 UID는 다시 가져올 때 건너뛰며, 변경된 내용은 과제 수정 창에서 편집합니다.
완료 여부는 이 앱의 체크박스로 관리합니다.

최대 2MB·500개 일정을 읽습니다. 취소된 일정과 반복 규칙이 있는 일정은 미리보기 안내에 표시하고 건너뜁니다.
반복 일정은 개별 일정으로 내보낸 파일을 사용할 수 있습니다. 날짜나 제목이 손상된 항목도 안내합니다.

## 저장과 프로젝트 구성

```text
app.py                 FastAPI 라우팅과 화면 제공
models.py              입력값 검증, 한국 시간 처리와 집계
storage.py             SQLite 읽기·쓰기
calendar_import.py     ICS 읽기와 중복 키 생성
run.py                 로컬 서버 실행
static/                HTML, CSS, JavaScript, 아이콘
tests/test_app.py      기능 검증
sample_assignments.ics 시연용 가상 일정
requirements.txt      실행 패키지
requirements-dev.txt  테스트 패키지
start.bat              Windows 실행 도우미
data/assignments.db    실행하면서 생성되는 개인 데이터
```

서버 접속 주소는 `127.0.0.1`이며 과제 데이터는 로컬 SQLite 파일에 저장됩니다.
저장소에는 소스, 테스트, 예시 일정, 설치 목록과 이 설명서가 포함됩니다.
`.gitignore`는 `.venv`, 개인 DB, 개인 캘린더 파일, 인증정보, 캐시와 로그를 제외합니다.
데이터 백업은 서버를 종료한 뒤 `data/assignments.db`를 복사합니다.

## 검증

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

테스트는 임시 DB를 사용합니다. 주요 시나리오는 다음과 같습니다.

- 오늘·과거·미래 및 월말·연말·윤년 날짜 계산
- 잘못된 날짜·빈 입력·잘못된 링크 차단
- 완료 처리 후 미완료 집계 갱신, 검색과 과목·상태 필터 조합
- 마감일 수정에 따른 정렬·집계 변경
- ICS 한국어·시간대·날짜 전용 일정, 중복 방지, 선택 가져오기
- 잘못된 파일·용량 초과·반복 및 취소 일정 처리
- 새 앱 인스턴스에서 저장된 내용과 완료 상태 복원

## 향후 계획

1. 학교 캘린더 피드 주소를 주기적으로 읽어 새 일정과 마감일 변경 반영
2. 같은 저장 데이터를 보여 주는 바탕화면 위젯 추가

## Docker와 자동 배포

`main`에 코드를 올리면 다음 순서로 실행됩니다.

1. **CI**: Python 테스트 → Docker 이미지 빌드 → 실제 컨테이너 API 검증 → Docker Hub 업로드
2. **CD**: Windows Runner에서 해당 커밋의 이미지 다운로드 → 새 컨테이너 실행 → 정상 응답 확인 → Nginx 연결 전환
3. 배포 전부터 별도 프로세스가 `/api/dashboard`를 계속 요청하고, 새 버전 전환 후에도 30초 이상 기록합니다.

서비스 주소는 **http://127.0.0.1:8000** 입니다.
브라우저 실시간 검증 화면은 **http://127.0.0.1:8000/deployment** 입니다.
검증 화면의 **측정 시작**을 누른 뒤 새 커밋을 올리면 요청 결과와 버전 전환을 볼 수 있습니다.

### 구성

| 파일 | 역할 |
| --- | --- |
| `Dockerfile`, `.dockerignore` | 실행 패키지와 소스만 담는 이미지 |
| `.github/workflows/ci.yml` | 테스트·빌드·실행 검증·Docker Hub 업로드 |
| `.github/workflows/cd.yml` | CI가 성공한 main 커밋을 로컬에 배포 |
| `scripts/deploy.py` | blue/green 컨테이너 교체와 Nginx 전환, 실패 시 이전 설정 복구 |
| `scripts/monitor.py` | 실제 FastAPI 목록·집계·버전 응답 연속 측정 |
| `VERSION` | 화면과 검증 응답의 앱 버전 |

Docker Hub 이미지는 `kingwooseok/assignment-dashboard`에 저장됩니다.
CI는 `latest`와 전체 커밋 SHA 태그를 올리며, CD는 CI가 검증한 SHA 태그를 사용합니다.
저장소의 `KINGWOOSEOK` Secret에 Docker Hub 액세스 토큰을 등록합니다. 사용자명은 `kingwooseok`입니다.

### 로컬 실행 환경

Windows에 Docker Desktop을 설치하고 Linux 컨테이너 엔진을 실행합니다.
저장소 Settings → Actions → Runners에서 Windows x64 Runner를 등록하고
추가 레이블에 `assignment-dashboard`를 지정합니다. Runner 실행 중에는 `run.cmd`를 유지합니다.
Runner와 로컬 검증 기록은 Git에 포함하지 않습니다.

Nginx 프록시는 `127.0.0.1:8000`에서 요청을 받습니다.
새 blue/green 컨테이너의 실제 API 응답을 검사한 뒤 Nginx를 graceful reload합니다.
기존 요청은 이전 컨테이너에서 마무리되며, 새 요청은 새 컨테이너로 전달됩니다.
SQLite 데이터는 두 컨테이너가 공유하는 `assignment-dashboard-data` 볼륨에 유지됩니다.
앱 컨테이너와 프록시에는 `unless-stopped` 재시작 정책을 설정합니다.

### 배포 검증 결과

GitHub Actions의 CD 실행 Summary에 배포 전·중·후 요청 결과를 표시합니다.
동일 실행의 Artifacts에는 `summary.md`, `result.json`, `requests.jsonl`, `requests.csv`, 컨테이너 로그가 저장됩니다.

- 요청마다 시작·종료 시각, HTTP 상태, 응답 시간, 앱 버전과 커밋을 기록
- 응답의 과제 목록·집계와 버전 헤더를 검사
- 요청 번호 연속성, 실제 요청 간격과 최대 관측 공백을 집계
- 배포 중 이전 커밋에서 새 커밋으로 응답이 전환되는지 검사
- 전환 후 30초 이상 새 버전 응답과 과제 데이터 유지를 검사
- 실패 요청이나 기준을 넘는 관측 공백이 있으면 검증 실패로 기록

직접 배포할 때는 새 커밋 SHA와 새로운 출력 폴더를 지정합니다.

```powershell
python scripts/deploy.py --revision <전체-커밋-SHA> --output artifacts/manual-deployment
```
