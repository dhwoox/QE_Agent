# QE Agent 빠른 시작 가이드

## 🚀 5분 안에 시작하기

### 1단계: 사전 준비 ✅

#### LM Studio 실행
```bash
# 1. LM Studio 앱 실행
# 2. qwen-coder-30b 모델 다운로드 및 로드
# 3. Local Server 탭 이동
# 4. 포트 확인: 1234
# 5. "Start Server" 버튼 클릭
```

**확인 방법:**
```bash
curl http://localhost:1234/v1/models
```

성공 시 모델 목록이 JSON으로 반환됩니다.

---

### 2단계: 환경 설정 ⚙️

```bash
# 프로젝트 디렉토리로 이동
cd QE_Agent

# .env 파일 생성
cp .env.example .env

# .env 파일 편집 (필수!)
# LANGSMITH_API_KEY="여기에_LangSmith_API_키_입력"
```

**LangSmith API 키 발급 방법:**
1. https://smith.langchain.com/ 접속
2. 회원가입 (무료)
3. Settings → API Keys → Create API Key
4. 생성된 키를 `.env` 파일에 붙여넣기

---

### 3단계: 패키지 설치 📦

```bash
# 가상환경 생성 (권장)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt
```

**또는 UV 사용:**
```bash
uv pip install -r requirements.txt
```

---

### 4단계: CLI로 테스트 🧪

```bash
# Python으로 직접 실행
python src/main.py
```

**예상 출력:**
```
============================================================
QE Agent - File & Code Search Assistant
============================================================

🔍 테스트 쿼리: 'Python 파일 찾아줘'

📊 실행 결과:
------------------------------------------------------------
✓ 최종 Agent: finder
✓ 쿼리 의도: search
✓ 확신도: 0.80

✓ 찾은 파일 (5개):
  - src/main.py
  - src/config.py
  - src/agents/finder_agent.py
  - src/agents/supervisor.py
  - src/state/agent_state.py

💬 Agent 응답:
------------------------------------------------------------
[Finder Agent의 응답 내용]
...
```

---

### 5단계: LangGraph Studio로 시각화 🎨

#### Docker 확인
```bash
docker --version  # Docker version 20.10.0 이상
docker-compose --version  # v2.22.0 이상
```

#### LangGraph 개발 서버 실행
```bash
langgraph dev
```

**또는 터널 모드 (외부 접속 가능):**
```bash
langgraph dev --tunnel
```

**실행 결과:**
```
- API server running at: http://localhost:8123
- Studio UI running at: http://localhost:8123/studio
- API docs at: http://localhost:8123/docs
```

---

### 6단계: LangGraph Studio 사용 🖥️

1. **브라우저에서 자동으로 열림**
   - URL: `http://localhost:8123/studio`

2. **Graph Mode (개발자 모드)**
   - 그래프 구조 시각화
   - 노드 클릭하여 상태 확인
   - 단계별 실행 및 디버깅

3. **Chat Mode (테스트 모드)**
   - 실제 사용자처럼 대화 테스트
   - 예시 질문:
     - "Python 파일 찾아줘"
     - "src 폴더 구조 분석해줘"
     - "main 함수가 있는 파일 검색해줘"

---

## 🎯 주요 기능 테스트

### 파일 검색
```
질문: "Python 파일 찾아줘"
→ Supervisor가 Finder Agent로 라우팅
→ search_files 도구 사용
→ 결과 반환
```

### 코드 검색
```
질문: "def create_llm이 있는 파일 찾아줘"
→ Supervisor가 Finder Agent로 라우팅
→ search_code 도구 사용
→ 파일명:라인번호:내용 반환
```

### 디렉토리 분석
```
질문: "src 폴더 구조 분석해줘"
→ Supervisor가 Finder Agent로 라우팅
→ analyze_structure 도구 사용
→ 파일 수, 확장자별 통계, 디렉토리 목록 반환
```

### 파일 읽기
```
질문: "src/config.py 파일 내용 보여줘"
→ Supervisor가 Finder Agent로 라우팅
→ read_file 도구 사용
→ 파일 내용 반환 (최대 5000자)
```

---

## ⚠️ 트러블슈팅

### LM Studio 연결 실패
```
Error: Connection refused to localhost:1234
```

**해결 방법:**
1. LM Studio가 실행 중인지 확인
2. Local Server가 시작되었는지 확인
3. 포트가 1234인지 확인
4. 방화벽 설정 확인

### LangSmith 로그인 실패
```
Error: Invalid API key
```

**해결 방법:**
1. `.env` 파일의 `LANGSMITH_API_KEY` 확인
2. https://smith.langchain.com/ 에서 키 재발급
3. `.env` 파일 저장 후 재시작

### Docker 오류
```
Error: docker-compose version too old
```

**해결 방법:**
```bash
# Docker Desktop 업데이트
# 또는
brew upgrade docker-compose  # macOS
```

### 모듈 import 오류
```
ModuleNotFoundError: No module named 'langgraph'
```

**해결 방법:**
```bash
# 가상환경 활성화 확인
source venv/bin/activate

# 패키지 재설치
pip install -r requirements.txt
```

---

## 📚 다음 단계

### 1. 커스텀 도구 추가
[src/tools/search_tools.py](src/tools/search_tools.py)에 새로운 `@tool` 함수 추가

### 2. 새 Agent 추가
[src/agents/](src/agents/) 폴더에 새 Agent 파일 생성

예: `code_agent.py`, `debug_agent.py`

### 3. Supervisor 라우팅 개선
[src/agents/supervisor.py](src/agents/supervisor.py)의 `supervisor_node` 함수 수정

### 4. 프로덕션 배포
- SQLite → PostgreSQL/MongoDB 전환
- InMemoryStore → MongoDBStore 전환
- LangSmith로 모니터링 설정

---

## 🆘 도움말

### 문서
- [README.md](README.md) - 프로젝트 개요
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - 상세 설계
- [FOLDER_STRUCTURE.md](FOLDER_STRUCTURE.md) - 폴더 구조

### 외부 리소스
- [LangGraph 공식 문서](https://langchain-ai.github.io/langgraph/)
- [LangGraph Studio 가이드](https://docs.langchain.com/langgraph-platform/langgraph-studio)
- [LM Studio 문서](https://lmstudio.ai/docs)

### 커뮤니티
- LangChain Discord: https://discord.gg/langchain
- GitHub Issues: (여기에 이슈 링크)

---

**만든 날짜:** 2025-11-08
**최종 업데이트:** 2025-11-08
**버전:** 1.0.0 (Phase 1 - Supervisor + Finder Agent)
