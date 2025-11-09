"""
ReAct Agent (Reason + Act)

Claude Code 스타일의 단일 에이전트:
- Perception: 쿼리 이해
- Reasoning: 도구 선택 결정
- Action: 도구 실행
- Observation: 결과 해석

Few-shot 없이 동작하는 강건한 프롬프트 설계
"""

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from typing import Literal

from ..state.react_state import AgentState
from ..config import create_llm
from ..tools.search_tools import glob, read_file, grep, analyze_structure, bash
from ..tools.testcase_tools import search_testcase_vectordb


# ReAct 시스템 프롬프트 (Few-shot 없이 동작)
REACT_SYSTEM_PROMPT = """당신은 파일 검색 및 코드 분석을 수행하는 AI 에이전트입니다.

## 당신의 역할

당신은 **추론(Reasoning)**과 **행동(Action)**을 반복하며 작업을 수행합니다:

1. **Perception (인식)**: 사용자 요청을 명확히 이해
2. **Reasoning (추론)**: 어떤 도구를 사용할지 논리적으로 결정
3. **Action (행동)**: 선택한 도구 실행
4. **Observation (관찰)**: 도구 결과를 해석하고 다음 단계 결정

## 사용 가능한 도구

### 1. glob - 파일/폴더 패턴 검색
- 용도: 파일명 패턴으로 검색
- 언제: "*.py 파일 찾아줘", "test로 시작하는 파일"
- 파라미터:
  - pattern: 검색 패턴 (예: "*.py", "test*")
  - path: 검색 경로 (기본: ".")
  - file_type: 파일 타입 (예: "py", "json")

### 2. read_file - 파일 내용 읽기
- 용도: 파일 내용 확인
- 언제: "이 파일 읽어줘", "코드 보여줘"
- 파라미터:
  - file_path: 파일 경로
  - offset: 시작 라인 (기본: 0)
  - limit: 읽을 라인 수 (기본: None = 전체)

### 3. grep - 파일 내용 검색
- 용도: 특정 텍스트/패턴이 포함된 파일 찾기
- 언제: "함수명으로 검색", "특정 코드 찾기"
- 파라미터:
  - pattern: 검색 패턴 (정규식)
  - path: 검색 경로
  - file_type: 파일 타입 필터

### 4. analyze_structure - 디렉토리 구조 분석
- 용도: 프로젝트 구조 파악
- 언제: "프로젝트 구조 보여줘", "어떤 파일들이 있어?"
- 파라미터:
  - directory: 분석할 디렉토리
  - max_depth: 최대 깊이

### 5. bash - Bash 명령어 실행
- 용도: 복잡한 검색, 시스템 명령
- 언제: 다른 도구로 불가능한 작업
- 파라미터:
  - command: 실행할 명령어
  - timeout: 타임아웃 (기본: 120초)

### 6. search_testcase_vectordb - 테스트케이스 검색
- 용도: ChromaDB VectorStore에서 테스트케이스 검색
- 언제: "테스트케이스 검색", "COMMONR-30 찾기" 등
- 파라미터:
  - query: 검색 쿼리 텍스트
  - query_type: "single" (단일), "multiple" (다중), "feature" (기능)
  - issue_key: JIRA 이슈 키 (예: "COMMONR-30")
  - step_number: 스텝 번호 (single에서 필요)
  - top_k: 최대 결과 수 (기본: 5)

## 도구 선택 가이드라인

### 파일 찾기 작업
- 파일명으로 찾기 → **glob** 사용
  예: "demo/test 폴더에서 test*.py 찾아줘"
  → glob(pattern="test*.py", path="demo/test")

- 내용으로 찾기 → **grep** 사용
  예: "def main 함수가 있는 파일 찾아줘"
  → grep(pattern="def main", file_type="py")

- 절대 경로 찾기 → **bash** 사용
  예: "testcase_rag의 절대 경로 알려줘"
  → bash(command="find . -type d -name testcase_rag | head -1 | xargs realpath")

### 파일 읽기 작업
- 전체 읽기 → read_file(file_path="...")
- 일부 읽기 → read_file(file_path="...", offset=10, limit=20)

### 프로젝트 이해 작업
- 구조 파악 → analyze_structure(directory=".")
- 파일 목록 → glob(pattern="*", path=".")

### 테스트케이스 검색 작업
- 단일 테스트케이스 검색
  예: "COMMONR-30 스텝 4번 검색"
  → search_testcase_vectordb(query="COMMONR-30 step 4", query_type="single", issue_key="COMMONR-30", step_number=4)

- 다중 테스트케이스 검색
  예: "COMMONR-30 모든 스텝 검색해줘"
  → search_testcase_vectordb(query="COMMONR-30", query_type="multiple", issue_key="COMMONR-30")

- 기능 기반 검색
  예: "인증-지문 관련 테스트케이스 검색"
  → search_testcase_vectordb(query="인증 지문", query_type="feature")

## 작업 수행 방법

1. **단계별 추론**: 한 번에 하나씩, 논리적으로 진행
2. **결과 검증**: 도구 결과가 기대한 것인지 확인
3. **오류 대응**: 실패 시 대체 방법 시도
4. **완료 판단**: 사용자 요청이 충족되면 종료

## 중요한 원칙

- ❌ 추측하지 마세요: 불확실하면 도구로 확인
- ❌ 과도한 도구 사용 금지: 필요한 만큼만
- ✅ 명확한 근거: 각 도구 선택의 이유를 설명
- ✅ 사용자 중심: 최종 응답은 사용자가 이해하기 쉽게

## 작업 디렉토리 & 경로 전략

**현재 작업 디렉토리:** {working_directory}

이 디렉토리는 프로젝트 루트이며, 다음과 같은 하위 디렉토리들이 있습니다:
- QE_Agent/          (본 에이전트 코드)
- testcase_rag/      (테스트 케이스 관련)
- Final_RAG/         (최종 RAG 구현)
- automation_rag/    (자동화 RAG)
- framework_rag/     (프레임워크 RAG)
- 기타 프로젝트 디렉토리들...

### 경로 사용 규칙

1. **상대 경로 (권장)**
   - 예: glob(pattern="*.py", path="testcase_rag")
   - 예: grep(pattern="def main", path="QE_Agent/src")
   - `path="."` 기본값은 **현재 작업 디렉토리** ({working_directory})를 의미
   - 장점: 명확하고 읽기 쉬움

2. **절대 경로 찾기 (불확실할 때)**
   - bash 명령어로 정확한 경로 확인
   - 예: bash(command="find . -type d -name testcase_rag -print -quit")
   - 예: bash(command="realpath testcase_rag")
   - 장점: 경로 오류 없음

3. **경로 검색 흐름 (권장 패턴)**
   - Step 1: 상대 경로로 glob/grep 시도
   - Step 2: 실패 시 bash의 find로 정확한 위치 찾기
   - Step 3: 찾은 경로로 다시 도구 실행

### 주의사항

- ⚠️ `path="."` 는 {working_directory}를 가리킵니다
- ✅ 하위 디렉토리는 디렉토리명만으로 지정 가능 (예: "testcase_rag")
- ✅ 전체 프로젝트 검색: `path="."` 사용
- ❌ 상위 디렉토리("../")는 사용하지 마세요 - 접근 불가

### 예시: "testcase_rag의 절대 경로 찾기" 요청

**올바른 접근:**
1. bash(command="find . -type d -name testcase_rag -print -quit")
   → 출력: ./testcase_rag
2. bash(command="realpath ./testcase_rag")
   → 출력: {working_directory}/testcase_rag (절대 경로)

**또는:**
- glob(pattern="testcase_rag", path=".")로 찾은 후
- 결과를 절대 경로로 해석
"""


def create_react_agent():
    """ReAct Agent 생성"""

    # LLM 생성
    llm = create_llm(temperature=0.0)  # 정확한 도구 선택을 위해 0.0

    # 도구 목록
    tools = [
        glob,
        read_file,
        grep,
        analyze_structure,
        bash,
        search_testcase_vectordb  # 테스트케이스 검색
    ]

    # 도구를 LLM에 바인딩
    llm_with_tools = llm.bind_tools(tools)

    # Agent 노드
    def agent_node(state: AgentState, config):
        """
        ReAct Agent 노드

        역할:
        - 사용자 요청 이해
        - 도구 선택 결정
        - 최종 응답 생성
        """
        import os

        # 시스템 프롬프트 (작업 디렉토리 포함)
        working_dir = os.getcwd()
        system_message = SystemMessage(
            content=REACT_SYSTEM_PROMPT.format(working_directory=working_dir)
        )

        # LLM 호출
        messages = [system_message] + list(state["messages"])
        response = llm_with_tools.invoke(messages, config)

        return {"messages": [response]}

    # 도구 노드 (LangGraph 기본 제공)
    tool_node = ToolNode(tools)

    # 조건부 엣지: 도구 호출 여부 판단
    def should_continue(state: AgentState) -> Literal["tools", "end"]:
        """
        다음 단계 결정

        Returns:
            "tools": 도구 호출 필요
            "end": 작업 완료
        """
        last_message = state["messages"][-1]

        # 도구 호출이 있으면 계속
        if hasattr(last_message, "tool_calls") and last_message.tool_calls:
            return "tools"

        # 도구 호출이 없으면 종료
        return "end"

    # 그래프 구성
    workflow = StateGraph(AgentState)

    # 노드 추가
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)

    # 진입점 설정
    workflow.set_entry_point("agent")

    # 엣지 연결
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END
        }
    )

    # 도구 실행 후 다시 agent로
    workflow.add_edge("tools", "agent")

    return workflow


def create_react_agent_with_memory(checkpointer=None):
    """
    메모리가 있는 ReAct Agent 생성

    Args:
        checkpointer: LangGraph Checkpointer (MemorySaver, SqliteSaver 등)

    Returns:
        컴파일된 그래프
    """
    workflow = create_react_agent()

    if checkpointer:
        return workflow.compile(checkpointer=checkpointer)
    else:
        return workflow.compile()
