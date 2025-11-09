# GSDK 테스트 자동화를 위한 LangGraph 멀티 에이전트 시스템 설계서

## 📋 목차
1. [시스템 개요](#1-시스템-개요)
2. [아키텍처 설계](#2-아키텍처-설계)
3. [Agent 상세 설계](#3-agent-상세-설계)
4. [State 관리 전략](#4-state-관리-전략)
5. [Tool 설계](#5-tool-설계)
6. [워크플로우](#6-워크플로우)
7. [Memory 및 Checkpointing](#7-memory-및-checkpointing)
8. [구현 로드맵](#8-구현-로드맵)

---

## 1. 시스템 개요

### 1.1 목적
GSDK 테스트 자동화를 위한 능동적이고 지능적인 멀티 에이전트 시스템 구축. LM Studio Agent의 tool 기반 워크플로우를 LangGraph의 supervisor 패턴으로 전환하여 각 agent가 자율적으로 판단하고 협업하는 구조로 개선.

### 1.2 핵심 요구사항
- **LM Studio 기반**: qwen-coder-30b 모델 활용 (로컬 실행)
- **Supervisor 패턴**: 중앙 orchestrator가 전체 워크플로우 관리
- **능동적 Agent**: 각 agent가 필요 시 능동적으로 다른 agent 호출
- **RAG 통합**: 테스트케이스 및 리소스 검색
- **Long-term Memory**: 학습 및 컨텍스트 유지
- **ReAct 추론**: 각 agent가 reasoning + acting 패턴으로 작동

### 1.3 기존 시스템 분석
**현재 상태** (lm_studio_agent):
- 단일 LLM agent + Tool 시스템
- 순차적 tool 호출 (TestCaseRetriever → CategoryMapper → CodeGenerator → ChecklistValidator)
- ChromaDB RAG 통합 (jira_test_cases)
- 기본 memory 없음 (대화 히스토리만 유지)

**개선 필요 사항**:
1. Tool → Agent로 전환 (능동적 의사결정)
2. 병렬 처리 가능한 구조
3. Long-term memory 도입
4. Supervisor를 통한 workflow 제어
5. Checkpointing으로 재시작 가능

---

## 2. 아키텍처 설계

### 2.1 전체 구조도

```
┌─────────────────────────────────────────────────────────────────────┐
│                          사용자 (User)                                │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   Orchestrator (총괄 지휘자)                          │
│  - 전체 워크플로우 제어                                               │
│  - Agent 간 routing 결정                                             │
│  - State 관리 및 checkpointing                                       │
│  - Human-in-the-loop 처리                                            │
└──────┬──────────────────────────────────────────────────────────────┘
       │
       ├─────────────┬─────────────┬─────────────┬─────────────┐
       │             │             │             │             │
       ▼             ▼             ▼             ▼             ▼
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│ Finder   │  │Generator │  │ Reviewer │  │ Executor │  │ Memory   │
│ Agent    │  │ Agent    │  │ Agent    │  │ Agent    │  │ Agent    │
└────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │             │             │
     │             │             │             │             │
     ▼             ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Shared State Graph                            │
│  - AgentState (conversation, context, generated_code, etc.)         │
│  - Immutable state updates                                           │
│  - History tracking                                                  │
└─────────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   Memory & Persistence Layer                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Checkpointer │  │ Long-term    │  │ ChromaDB     │              │
│  │ (SQLite)     │  │ Memory       │  │ (RAG)        │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 아키텍처 패턴 선택

#### 2.2.1 Supervisor 패턴 (LangGraph 공식 권장)
- **Orchestrator**: 중앙 감독 agent가 모든 워크플로우 제어
- **Specialized Agents**: 각 agent는 독립적인 scratchpad 보유
- **Global Scratchpad**: Orchestrator가 관리하는 공유 상태
- **Routing Logic**: Orchestrator가 다음 agent 결정

#### 2.2.2 State Graph 구조
```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

# State 정의
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    current_task: str
    test_case_content: Optional[str]
    categories: Optional[List[str]]
    generated_code: Optional[str]
    review_result: Optional[Dict]
    execution_result: Optional[Dict]
    next_agent: Optional[str]
    iteration: int
    max_iterations: int
    metadata: Dict[str, Any]

# Graph 구성
workflow = StateGraph(AgentState)

# Nodes 추가
workflow.add_node("orchestrator", orchestrator_node)
workflow.add_node("finder", finder_agent_node)
workflow.add_node("generator", generator_agent_node)
workflow.add_node("reviewer", reviewer_agent_node)
workflow.add_node("executor", executor_agent_node)
workflow.add_node("memory", memory_agent_node)

# Edges 정의
workflow.set_entry_point("orchestrator")
workflow.add_conditional_edges(
    "orchestrator",
    route_to_next_agent,  # routing 함수
    {
        "finder": "finder",
        "generator": "generator",
        "reviewer": "reviewer",
        "executor": "executor",
        "memory": "memory",
        "end": END
    }
)

# 각 agent에서 orchestrator로 복귀
for agent in ["finder", "generator", "reviewer", "executor", "memory"]:
    workflow.add_edge(agent, "orchestrator")
```

---

## 3. Agent 상세 설계

### 3.1 Orchestrator (총괄 지휘자)

**역할**:
- 전체 워크플로우 관리 및 제어
- Agent 간 routing 결정
- State 업데이트 조율
- Human-in-the-loop 처리
- 작업 완료 판단

**주요 로직**:
```python
def orchestrator_node(state: AgentState) -> AgentState:
    """
    Orchestrator의 핵심 로직:
    1. 현재 상태 분석
    2. 다음 실행할 agent 결정
    3. 필요 시 사용자 승인 요청
    4. State 업데이트
    """
    # 현재 진행 상황 분석
    current_task = state["current_task"]
    iteration = state.get("iteration", 0)

    # 다음 agent 결정
    if not state.get("test_case_content"):
        next_agent = "finder"  # 테스트케이스 검색 필요
    elif not state.get("categories"):
        next_agent = "finder"  # 카테고리 매핑 필요
    elif not state.get("generated_code"):
        next_agent = "generator"  # 코드 생성 필요
    elif not state.get("review_result"):
        next_agent = "reviewer"  # 코드 리뷰 필요
    elif state["review_result"]["needs_revision"]:
        next_agent = "generator"  # 재생성 필요
    elif not state.get("execution_result"):
        next_agent = "executor"  # 실행 필요
    else:
        next_agent = "end"  # 완료

    # Iteration 체크
    if iteration >= state["max_iterations"]:
        next_agent = "end"

    # State 업데이트
    return {
        **state,
        "next_agent": next_agent,
        "iteration": iteration + 1
    }
```

**Tools**:
- `human_approval`: 위험한 작업 전 사용자 승인
- `save_checkpoint`: 현재 상태 저장
- `load_checkpoint`: 이전 상태 복원

---

### 3.2 Finder Agent (리소스 탐색자)

**역할**:
- 테스트케이스 검색 (ChromaDB RAG)
- GSDK 카테고리 매핑
- 관련 리소스 파일 탐색
- 메타데이터 추출

**주요 로직**:
```python
def finder_agent_node(state: AgentState) -> AgentState:
    """
    Finder Agent의 ReAct 패턴:
    1. Reasoning: 필요한 정보 파악
    2. Acting: 적절한 tool 선택 및 실행
    3. Observation: 결과 분석
    4. Repeat or Return
    """
    messages = state["messages"]
    current_task = state["current_task"]

    # ReAct loop
    for _ in range(3):  # 최대 3회 반복
        # LLM에게 다음 행동 결정 요청
        response = llm_with_tools.invoke(messages)

        if response.tool_calls:
            # Tool 실행
            for tool_call in response.tool_calls:
                result = execute_tool(tool_call)
                messages.append(ToolMessage(result, tool_call_id=...))
        else:
            # 작업 완료
            break

    # State 업데이트
    return {
        **state,
        "test_case_content": extracted_test_case,
        "categories": mapped_categories,
        "messages": messages
    }
```

**Tools**:
1. `testcase_retriever`: ChromaDB에서 테스트케이스 검색
   - Input: query (issue_key + step_index)
   - Output: test case content + metadata

2. `category_mapper`: 테스트케이스 → GSDK 카테고리 매핑
   - Input: test case content
   - Output: categories (access, auth, door, etc.)

3. `resource_finder`: 카테고리별 리소스 파일 탐색
   - Input: categories
   - Output: file paths (pb2, manager methods, examples)

4. `glob_search`: 파일 패턴 검색
5. `grep_search`: 코드 내용 검색

---

### 3.3 Generator Agent (코드 생성자)

**역할**:
- Python 테스트 코드 자동 생성
- GSDK 패턴 준수 (testCOMMONR 기반)
- Few-shot learning 적용
- 리소스 파일 직접 로드 및 활용

**주요 로직**:
```python
def generator_agent_node(state: AgentState) -> AgentState:
    """
    Generator Agent의 코드 생성 로직:
    1. 리소스 수집 (pb2, manager.py, util.py)
    2. Few-shot examples 구성
    3. LLM 호출 (streaming)
    4. 코드 검증 (syntax check)
    """
    test_case = state["test_case_content"]
    categories = state["categories"]

    # 리소스 로드
    resources = load_resources(categories)

    # Few-shot examples (유사 테스트케이스)
    examples = find_similar_tests(test_case)

    # Prompt 구성
    prompt = build_code_generation_prompt(
        test_case=test_case,
        categories=categories,
        resources=resources,
        examples=examples
    )

    # LLM 호출 (streaming)
    generated_code = ""
    for chunk in llm.stream(prompt):
        generated_code += chunk
        # Optional: on_progress callback

    # Syntax 검증
    is_valid = validate_python_syntax(generated_code)

    return {
        **state,
        "generated_code": generated_code,
        "code_valid": is_valid,
        "messages": state["messages"] + [
            AIMessage(content=f"Generated code ({len(generated_code)} chars)")
        ]
    }
```

**Tools**:
1. `gsdk_file_reader`: GSDK 리소스 파일 읽기
2. `rag_query`: automation_rag에서 유사 코드 검색
3. `syntax_validator`: Python AST 검증
4. `extract_methods`: manager.py에서 API 메서드 추출
5. `read_file`: 파일 읽기

---

### 3.4 Reviewer Agent (코드 검토자)

**역할**:
- 생성된 코드 품질 검증
- GSDK 가이드라인 준수 확인
- 개선 사항 제안
- 체크리스트 기반 평가

**주요 로직**:
```python
def reviewer_agent_node(state: AgentState) -> AgentState:
    """
    Reviewer Agent의 검토 로직:
    1. Checklist 기반 검증
    2. 패턴 매칭 검증
    3. 개선 사항 도출
    4. 재생성 필요 여부 판단
    """
    generated_code = state["generated_code"]
    test_case = state["test_case_content"]

    # Checklist 검증
    checklist_result = run_checklist_validation(generated_code, test_case)

    # 패턴 검증 (ReAct)
    validation_messages = [
        SystemMessage(content=REVIEWER_SYSTEM_PROMPT),
        HumanMessage(content=f"Review this code:\n\n{generated_code}")
    ]

    review_response = llm_with_tools.invoke(validation_messages)

    # 개선 사항 추출
    needs_revision = not checklist_result["passed"]
    suggestions = checklist_result["failed_items"]

    return {
        **state,
        "review_result": {
            "passed": checklist_result["passed"],
            "needs_revision": needs_revision,
            "suggestions": suggestions,
            "score": checklist_result["score"]
        },
        "messages": state["messages"] + [
            AIMessage(content=f"Review: {checklist_result['summary']}")
        ]
    }
```

**Tools**:
1. `checklist_validator`: 체크리스트 기반 검증
   - TestCase 구조 (setUp, test methods, tearDown)
   - Import 검증
   - ServiceManager 사용
   - EventMonitor 패턴
   - Assert 패턴

2. `pattern_matcher`: GSDK 패턴 매칭
3. `suggest_improvements`: LLM 기반 개선 제안
4. `compare_with_examples`: 기존 예제와 비교

---

### 3.5 Executor Agent (실행 관리자)

**역할**:
- 생성된 코드 실행 준비
- 파일 저장
- 다음 단계 지시
- 실행 결과 기록

**주요 로직**:
```python
def executor_agent_node(state: AgentState) -> AgentState:
    """
    Executor Agent의 실행 로직:
    1. 파일 저장 경로 결정
    2. 사용자 승인 요청 (선택적)
    3. 파일 저장
    4. 다음 단계 안내
    """
    generated_code = state["generated_code"]
    test_case_meta = state["metadata"]

    # 파일명 생성
    issue_key = test_case_meta["issue_key"]
    step_index = test_case_meta["step_index"]
    filename = f"testCOMMONR_{issue_key}_{step_index}.py"
    filepath = GSDK_TEST_PATH / filename

    # 사용자 승인 (위험한 작업)
    if requires_approval(filepath):
        approved = request_human_approval(
            f"Save file to {filepath}?"
        )
        if not approved:
            return {**state, "execution_result": {"status": "cancelled"}}

    # 파일 저장
    save_result = write_file(filepath, generated_code)

    # 다음 단계 안내
    next_steps = [
        f"1. Review the generated file: {filepath}",
        f"2. Run the test: pytest {filepath}",
        f"3. Check the results and adjust if needed"
    ]

    return {
        **state,
        "execution_result": {
            "status": "completed",
            "filepath": str(filepath),
            "next_steps": next_steps
        },
        "messages": state["messages"] + [
            AIMessage(content=f"Saved to {filepath}")
        ]
    }
```

**Tools**:
1. `write_file`: 파일 저장
2. `create_directory`: 디렉토리 생성
3. `request_approval`: 사용자 승인 요청
4. `bash_command`: 명령 실행 (pytest 등)

---

### 3.6 Memory Agent (기억 관리자)

**역할**:
- Long-term memory 관리
- 학습 데이터 저장
- 컨텍스트 검색 및 제공
- 과거 작업 이력 조회

**주요 로직**:
```python
def memory_agent_node(state: AgentState) -> AgentState:
    """
    Memory Agent의 기억 관리 로직:
    1. 현재 작업을 long-term memory에 저장
    2. 유사한 과거 작업 검색
    3. 학습된 패턴 제공
    """
    current_task = state["current_task"]
    generated_code = state.get("generated_code")

    # Long-term memory에 저장
    if generated_code:
        save_to_long_term_memory({
            "task": current_task,
            "test_case": state["test_case_content"],
            "categories": state["categories"],
            "generated_code": generated_code,
            "review_result": state.get("review_result"),
            "timestamp": datetime.now()
        })

    # 유사 작업 검색
    similar_tasks = search_long_term_memory(current_task)

    return {
        **state,
        "similar_tasks": similar_tasks,
        "messages": state["messages"] + [
            AIMessage(content=f"Found {len(similar_tasks)} similar tasks")
        ]
    }
```

**Tools**:
1. `save_memory`: Long-term memory 저장
2. `search_memory`: 유사 작업 검색
3. `get_learning_patterns`: 학습된 패턴 조회
4. `update_user_preferences`: 사용자 선호도 저장

---

## 4. State 관리 전략

### 4.1 AgentState 정의

```python
from typing import TypedDict, Annotated, Optional, List, Dict, Any
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    """
    공유 State 정의 (Immutable updates)
    """
    # 대화 메시지
    messages: Annotated[List[BaseMessage], add_messages]

    # 작업 정보
    current_task: str  # 사용자 요청
    task_type: str  # "code_generation", "search", "review"

    # Finder Agent 결과
    test_case_content: Optional[str]
    test_case_metadata: Optional[Dict[str, Any]]
    categories: Optional[List[str]]
    resource_files: Optional[Dict[str, List[str]]]

    # Generator Agent 결과
    generated_code: Optional[str]
    code_valid: bool
    generation_metadata: Optional[Dict[str, Any]]

    # Reviewer Agent 결과
    review_result: Optional[Dict[str, Any]]
    # {
    #     "passed": bool,
    #     "needs_revision": bool,
    #     "suggestions": List[str],
    #     "score": float
    # }

    # Executor Agent 결과
    execution_result: Optional[Dict[str, Any]]
    # {
    #     "status": "completed" | "cancelled" | "failed",
    #     "filepath": str,
    #     "next_steps": List[str]
    # }

    # Memory Agent 결과
    similar_tasks: Optional[List[Dict[str, Any]]]
    learning_patterns: Optional[Dict[str, Any]]

    # Workflow 제어
    next_agent: Optional[str]
    iteration: int
    max_iterations: int

    # 메타데이터
    metadata: Dict[str, Any]
    # {
    #     "issue_key": str,
    #     "step_index": str,
    #     "start_time": datetime,
    #     "user_id": str
    # }
```

### 4.2 State Update 패턴

**Immutable Updates**:
```python
# ❌ 잘못된 방법 (mutable)
def bad_update(state: AgentState):
    state["generated_code"] = "new code"  # 원본 변경
    return state

# ✅ 올바른 방법 (immutable)
def good_update(state: AgentState) -> AgentState:
    return {
        **state,  # 기존 state 복사
        "generated_code": "new code"  # 새 값 추가
    }
```

**Additive Updates** (messages):
```python
# messages는 add_messages 함수로 자동 병합
def add_message(state: AgentState) -> AgentState:
    return {
        "messages": [AIMessage(content="New message")]
    }
# → state["messages"]에 자동으로 추가됨
```

---

## 5. Tool 설계

### 5.1 Tool 분류

| Tool Category | Tools | 사용 Agent |
|--------------|-------|-----------|
| **Search** | testcase_retriever, category_mapper, resource_finder, glob_search, grep_search | Finder |
| **Generation** | gsdk_file_reader, rag_query, syntax_validator, extract_methods, read_file | Generator |
| **Validation** | checklist_validator, pattern_matcher, suggest_improvements, compare_with_examples | Reviewer |
| **Execution** | write_file, create_directory, request_approval, bash_command | Executor |
| **Memory** | save_memory, search_memory, get_learning_patterns, update_user_preferences | Memory |
| **Common** | human_approval, save_checkpoint, load_checkpoint | Orchestrator |

### 5.2 Tool 구현 패턴

```python
from langchain.tools import tool
from langchain.pydantic_v1 import BaseModel, Field

class TestCaseRetrieverInput(BaseModel):
    """Input schema for testcase_retriever"""
    query: str = Field(description="Search query (issue_key + step_index)")
    issue_key: Optional[str] = Field(default=None, description="JIRA issue key")
    step_index: Optional[str] = Field(default=None, description="Step index")

@tool("testcase_retriever", args_schema=TestCaseRetrieverInput)
def testcase_retriever(query: str, issue_key: str = None, step_index: str = None) -> Dict[str, Any]:
    """
    ChromaDB에서 JIRA 테스트케이스를 검색합니다.

    Args:
        query: 검색 쿼리
        issue_key: JIRA 이슈 키 (optional)
        step_index: 스텝 인덱스 (optional)

    Returns:
        {
            "success": bool,
            "results": List[Dict],
            "n_results": int
        }
    """
    # 기존 TestCaseRetriever.execute() 로직 사용
    ...
```

---

## 6. 워크플로우

### 6.1 전체 워크플로우

```
사용자 입력
    ↓
[Orchestrator] ← ─────────────┐
    │                          │
    ├→ [Finder Agent]          │
    │   ├ testcase_retriever   │
    │   ├ category_mapper      │
    │   └ resource_finder      │
    │         ↓                 │
    ├→ [Generator Agent]       │
    │   ├ gsdk_file_reader     │
    │   ├ rag_query            │
    │   └ generate_code        │
    │         ↓                 │
    ├→ [Reviewer Agent]        │
    │   ├ checklist_validator  │
    │   └ suggest_improvements │
    │         ↓                 │
    │   Needs revision? ───────┘ (yes → back to Generator)
    │         │ (no)
    ├→ [Executor Agent]
    │   ├ write_file
    │   └ provide_next_steps
    │         ↓
    ├→ [Memory Agent]
    │   └ save_to_long_term_memory
    │         ↓
    └→ [END]
```

### 6.2 Routing 로직

```python
def route_to_next_agent(state: AgentState) -> str:
    """
    Orchestrator의 routing 로직

    Returns:
        다음 실행할 agent 이름 또는 "end"
    """
    next_agent = state.get("next_agent")

    if next_agent:
        return next_agent

    # Default routing logic
    if not state.get("test_case_content"):
        return "finder"
    elif not state.get("generated_code"):
        return "generator"
    elif not state.get("review_result"):
        return "reviewer"
    elif state.get("review_result", {}).get("needs_revision"):
        return "generator"  # 재생성
    elif not state.get("execution_result"):
        return "executor"
    else:
        return "end"
```

---

## 7. Memory 및 Checkpointing

### 7.1 Checkpointer 설정

```python
from langgraph.checkpoint.sqlite import SqliteSaver

# SQLite Checkpointer 초기화
checkpointer = SqliteSaver.from_conn_string("checkpoints.db")

# Graph에 checkpointer 추가
app = workflow.compile(checkpointer=checkpointer)

# 사용
config = {"configurable": {"thread_id": "user_123_task_456"}}
result = app.invoke(initial_state, config=config)

# 재시작 (동일한 thread_id로)
resumed_result = app.invoke(None, config=config)  # 마지막 checkpoint부터 재시작
```

### 7.2 Long-term Memory 설계

**MongoDB 기반 Long-term Memory**:
```python
from pymongo import MongoClient
from datetime import datetime

class LongTermMemory:
    """
    MongoDB 기반 Long-term Memory

    Collections:
    - tasks: 완료된 작업 이력
    - patterns: 학습된 패턴
    - user_preferences: 사용자 선호도
    """

    def __init__(self, connection_string: str):
        self.client = MongoClient(connection_string)
        self.db = self.client["gsdk_agent_memory"]

        # Collections
        self.tasks = self.db["tasks"]
        self.patterns = self.db["patterns"]
        self.user_preferences = self.db["user_preferences"]

    def save_task(self, task_data: Dict[str, Any]) -> str:
        """완료된 작업 저장"""
        task_data["timestamp"] = datetime.now()
        result = self.tasks.insert_one(task_data)
        return str(result.inserted_id)

    def search_similar_tasks(self, query: str, limit: int = 5) -> List[Dict]:
        """유사한 작업 검색 (text search)"""
        results = self.tasks.find(
            {"$text": {"$search": query}},
            {"score": {"$meta": "textScore"}}
        ).sort([("score", {"$meta": "textScore"})]).limit(limit)

        return list(results)

    def get_learning_patterns(self, category: str) -> Dict[str, Any]:
        """카테고리별 학습된 패턴 조회"""
        return self.patterns.find_one({"category": category})

    def update_pattern(self, category: str, pattern_data: Dict[str, Any]):
        """패턴 업데이트 (증분 학습)"""
        self.patterns.update_one(
            {"category": category},
            {"$set": pattern_data},
            upsert=True
        )
```

### 7.3 Memory Integration

```python
# Agent에서 Memory 사용
def generator_agent_node(state: AgentState) -> AgentState:
    # Long-term memory에서 유사 작업 검색
    memory = LongTermMemory("mongodb://localhost:27017")
    similar_tasks = memory.search_similar_tasks(
        state["current_task"]
    )

    # 유사 작업의 패턴 활용
    if similar_tasks:
        learned_patterns = [task["generated_code"] for task in similar_tasks]
        # Few-shot examples에 추가
        ...

    # 코드 생성
    ...

    # 결과를 long-term memory에 저장
    memory.save_task({
        "task": state["current_task"],
        "test_case": state["test_case_content"],
        "generated_code": generated_code,
        "categories": state["categories"]
    })

    return updated_state
```

---

## 8. 구현 로드맵

### Phase 1: 기본 구조 구축 (Week 1-2)
1. ✅ LangGraph 환경 설정
   - langgraph, langchain-openai 설치
   - LM Studio 연동 확인

2. ✅ AgentState 정의
   - TypedDict 구조 작성
   - Annotation 설정

3. ✅ Orchestrator 구현
   - StateGraph 생성
   - Routing 로직 작성
   - Conditional edges 설정

4. ✅ SQLite Checkpointer 설정
   - 기본 checkpoint 저장/로드 테스트

### Phase 2: Agent 구현 (Week 3-4)
1. ✅ Finder Agent
   - 기존 TestCaseRetriever, CategoryMapper tool 변환
   - ReAct 패턴 적용

2. ✅ Generator Agent
   - 기존 CodeGenerator tool 변환
   - Few-shot learning 통합
   - Streaming 응답 처리

3. ✅ Reviewer Agent
   - 기존 ChecklistValidator tool 변환
   - 패턴 매칭 로직 추가

4. ✅ Executor Agent
   - 파일 저장 로직
   - Human-in-the-loop 통합

### Phase 3: Memory 통합 (Week 5)
1. ✅ Long-term Memory 설계
   - MongoDB 연동
   - Collections 정의

2. ✅ Memory Agent 구현
   - save_memory, search_memory tools
   - 증분 학습 로직

3. ✅ Orchestrator-Memory 통합
   - 작업 완료 시 자동 저장
   - 작업 시작 시 유사 작업 검색

### Phase 4: 고급 기능 (Week 6-7)
1. ✅ ReAct 패턴 최적화
   - 각 agent별 reasoning 강화
   - Tool selection 개선

2. ✅ Parallel Execution
   - 독립적인 tool 병렬 실행
   - 성능 최적화

3. ✅ Human-in-the-loop 고도화
   - Chainlit UI 통합
   - 실시간 피드백

4. ✅ Monitoring & Logging
   - LangSmith 통합
   - 성능 메트릭 수집

### Phase 5: 테스트 및 최적화 (Week 8)
1. ✅ End-to-end 테스트
   - 실제 GSDK 테스트케이스로 검증
   - Edge case 처리

2. ✅ 성능 최적화
   - 토큰 사용 최적화
   - 응답 속도 개선

3. ✅ 문서화
   - 사용자 가이드
   - Agent별 상세 문서

---

## 9. 기술 스택

### 9.1 Core Framework
- **LangGraph**: 0.2.x (최신 stable)
- **LangChain**: 0.2.x
- **LangChain-OpenAI**: LM Studio 연동

### 9.2 LLM
- **LM Studio**: qwen-coder-30b
- **Base URL**: http://127.0.0.1:1234/v1
- **Temperature**: 0.1 (코드 생성), 0.7 (검색/분석)

### 9.3 Memory & Persistence
- **Checkpointer**: SQLite (langgraph-checkpoint-sqlite)
- **Long-term Memory**: MongoDB
- **RAG**: ChromaDB (jira_test_cases)

### 9.4 Monitoring
- **LangSmith**: Trace 및 디버깅
- **Logging**: Python logging module

### 9.5 UI (Optional)
- **Chainlit**: 실시간 UI
- **Streamlit**: 대시보드

---

## 10. 예상 효과

### 10.1 기존 대비 개선
| 항목 | 기존 (Tool 방식) | 개선 (Agent 방식) |
|-----|-----------------|------------------|
| **유연성** | 순차적, 고정된 흐름 | 동적, 상황별 판단 |
| **병렬성** | 제한적 | 독립적 agent 병렬 실행 |
| **재사용성** | Tool 단위 재사용 | Agent 단위 재사용 (더 높은 수준) |
| **확장성** | Tool 추가 시 복잡도 증가 | Agent 추가로 모듈화 유지 |
| **복구성** | 대화 히스토리만 유지 | Checkpoint로 언제든 재시작 |
| **학습성** | 없음 | Long-term memory로 지속 학습 |

### 10.2 성능 지표 (예상)
- **코드 생성 성공률**: 75% → 90%
- **평균 생성 시간**: 60초 → 45초 (병렬 처리)
- **재생성 비율**: 30% → 15% (Reviewer 개선)
- **사용자 만족도**: 향상 (Human-in-the-loop)

---

## 11. 주요 참고 자료

1. **LangGraph 공식 문서**
   - [LangGraph Multi-Agent Workflows](https://blog.langchain.com/langgraph-multi-agent-workflows/)
   - [Supervisor Pattern](https://github.com/langchain-ai/langgraph-supervisor-py)

2. **LangGraph Checkpointing**
   - [Memory Documentation](https://docs.langchain.com/oss/python/langgraph/add-memory)
   - [Persistence Guide](https://langchain-ai.github.io/langgraphjs/how-tos/persistence/)

3. **ReAct Pattern**
   - [Create ReAct Agent](https://langchain-ai.github.io/langgraph/how-tos/react-agent-from-scratch/)

4. **State Management**
   - [LangGraph Architecture](https://medium.com/@shuv.sdr/langgraph-architecture-and-design-280c365aaf2c)

---

## 12. 결론

본 설계서는 GSDK 테스트 자동화를 위한 **LangGraph 기반 멀티 에이전트 시스템**의 상세한 아키텍처와 구현 전략을 제시합니다.

**핵심 특징**:
1. **Supervisor 패턴**: Orchestrator가 전체 워크플로우 제어
2. **Specialized Agents**: Finder, Generator, Reviewer, Executor, Memory
3. **ReAct 패턴**: 각 agent가 추론 + 행동
4. **State Graph**: Immutable state updates
5. **Checkpointing**: SQLite 기반 재시작 가능
6. **Long-term Memory**: MongoDB 기반 학습
7. **Human-in-the-loop**: 위험한 작업 전 승인

**다음 단계**:
1. Phase 1 구현 시작 (기본 구조)
2. Orchestrator + Finder Agent 우선 구현
3. 점진적으로 나머지 Agent 추가
4. 실제 테스트케이스로 검증
