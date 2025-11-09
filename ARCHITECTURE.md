# QE Agent v3 Architecture

> **계층적 멀티 에이전트 시스템 - Hierarchical Multi-Agent Architecture**

## 📋 목차

1. [개요](#개요)
2. [아키텍처 진화](#아키텍처-진화)
3. [핵심 설계 철학](#핵심-설계-철학)
4. [3계층 아키텍처](#3계층-아키텍처)
5. [Layer 1: Supervisor Agent](#layer-1-supervisor-agent)
6. [Layer 2: Domain Supervisors](#layer-2-domain-supervisors)
7. [Layer 3: Worker Agents](#layer-3-worker-agents)
8. [State 관리](#state-관리)
9. [실행 흐름](#실행-흐름)
10. [디렉토리 구조](#디렉토리-구조)
11. [확장 가능성](#확장-가능성)

---

## 개요

QE Agent v3는 **계층적 멀티 에이전트 시스템**으로, 복잡한 테스트 자동화 작업을 전문화된 에이전트들이 협력하여 처리합니다.

### 주요 특징

- ✅ **3계층 구조**: Supervisor → Domain Supervisors → Worker Agents
- ✅ **전문화**: 각 도메인별 특화된 Supervisor Agent (TestCase, Resource, CodeReview)
- ✅ **순차적 평가**: 각 단계마다 Supervisor가 결과 평가 및 다음 단계 결정
- ✅ **모듈화**: 도메인별로 독립적인 모듈로 분리
- ✅ **확장성**: 새로운 Domain Supervisor 추가 용이
- ✅ **ReAct 패턴**: 모든 Agent가 Reason + Act 사이클로 동작
- ✅ **타입 안전성**: Pydantic 기반 State 및 파라미터 검증

### 성능

| 항목 | v2 (단일 Agent) | v3 (멀티 Agent) | 변화 |
|------|----------------|----------------|------|
| Agent 수 | 1개 | 10+개 | **계층화** |
| 전문성 | 일반 | 도메인 특화 | **향상** |
| 확장성 | 제한적 | 높음 | **개선** |
| 복잡도 | 낮음 | 중간 | **증가** |
| 작업 품질 | 양호 | 우수 | **개선** |

---

## 아키텍처 진화

### v1: Supervisor-Planner-Executor (구식)
```
Supervisor → Planner → Executor
(복잡, Few-shot 의존, 상태 과다)
```

### v2: 단일 ReAct Agent (현재 → 폐기)
```
ReAct Agent (단일)
    ↓
Tools (glob, read_file, grep, ...)
(단순, 효율적, but 전문성 부족)
```

### v3: 계층적 멀티 Agent (신규)
```
Supervisor Agent (최상위)
    ↓
Domain Supervisors (TestCase, Resource, Review)
    ↓
Worker Agents (Search, Generate, Evaluate)
(전문화, 확장 가능, 고품질)
```

**전환 이유**:
- v2는 간단하지만 **복잡한 다단계 작업 처리가 어려움**
- 테스트케이스 검색 → 메서드 생성 → 리소스 검색 등 **각 단계마다 전문 지식 필요**
- 단일 Agent로는 **각 단계의 결과 평가 및 재시도 로직 구현이 복잡**

---

## 핵심 설계 철학

### 1. 계층적 책임 분리 (Hierarchical Separation of Concerns)

```
┌──────────────────────────────────────────────────────────┐
│  Layer 1: Supervisor Agent (전략가)                       │
│  - 전체 작업 흐름 조율                                     │
│  - 어떤 Domain Supervisor를 호출할지 결정                  │
│  - 최종 결과 통합 및 사용자에게 전달                        │
└────────────────────┬─────────────────────────────────────┘
                     │
         ┌───────────┴───────────┬──────────────┐
         │                       │              │
┌────────▼────────┐    ┌────────▼────────┐    ▼
│ Layer 2:        │    │ Layer 2:        │   ...
│ TestCase        │    │ Resource        │
│ Supervisor      │    │ Supervisor      │
│ (도메인 전문가) │    │ (도메인 전문가) │
│                 │    │                 │
│ - 테스트케이스  │    │ - 리소스 검색   │
│   작업 조율     │    │   작업 조율     │
│ - 각 단계 평가  │    │ - 각 단계 평가  │
└────────┬────────┘    └────────┬────────┘
         │                       │
    ┌────┴────┬────┐        ┌───┴───┬───┐
    │         │    │        │       │   │
┌───▼──┐ ┌───▼──┐ ▼     ┌──▼─┐ ┌───▼─┐ ▼
│Layer3│ │Layer3│ ...   │L3  │ │L3   │...
│Search│ │Create│       │Find│ │Search│
│Agent │ │Agent │       │Agent│ │Agent│
│      │ │      │       │    │ │     │
│(실행)│ │(실행)│       │(실행)│(실행)│
└──────┘ └──────┘       └────┘ └─────┘
```

### 2. 전문화 (Specialization)

각 Agent는 **하나의 역할**만 담당:

| Agent | 역할 | 추론 | 실행 |
|-------|------|------|------|
| Supervisor | 전체 조율 | ✅ | ❌ |
| Domain Supervisor | 도메인 조율 | ✅ | ❌ |
| Worker Agent | 작업 실행 | ✅ | ✅ (Tools 사용) |
| Tool | 명령 실행 | ❌ | ✅ |

### 3. 순차적 평가 (Sequential Evaluation)

```
User: "COMMONR-30 스텝 4번의 완벽한 테스트 메서드를 만드세요"
    ↓
[Supervisor] 평가: "testcase_supervisor 호출 필요"
    ↓
[TestCase Supervisor]
    ├─ Step 1: search_agent 호출 → 테스트케이스 검색
    ├─ [평가] "검색 성공? → 다음 단계"
    ├─ Step 2: create_method_agent 호출 → 메서드 생성
    ├─ [평가] "메서드 완벽한가? → 검증 필요"
    ├─ Step 3: evaluator_agent 호출 → 코드 검증
    ├─ [평가] "완벽함 → Supervisor에게 전달"
    └─ → Supervisor
    ↓
[Supervisor] 평가: "테스트케이스 완료, resource_supervisor 필요"
    ↓
[Resource Supervisor]
    ├─ Step 1: finder_agent → 필요 파일 검색
    ├─ [평가] "파일 찾음 → 리소스 검색"
    ├─ Step 2: searcher_agent → 리소스 내용 검색
    ├─ [평가] "리소스 충분 → 평가"
    ├─ Step 3: evaluator_agent → 리소스 평가
    └─ → Supervisor
    ↓
[Supervisor] 최종 결과 → 사용자
```

**핵심**: 각 단계마다 **반드시 평가**하여 품질 보장

---

## 3계층 아키텍처

### 전체 구조 다이어그램

```
┌─────────────────────────────────────────────────────────────┐
│                        User Query                            │
│      "COMMONR-30 스텝 4번의 완벽한 테스트 메서드 생성"       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│  Layer 1: Supervisor Agent (최상위 조율자)                    │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 역할:                                                   │  │
│  │ • 전체 작업 분석 및 전략 수립                            │  │
│  │ • 적절한 Domain Supervisor 선택                         │  │
│  │ • 각 Domain 결과 평가 및 다음 단계 결정                  │  │
│  │ • 최종 결과 통합 및 사용자에게 반환                      │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │
       ┌───────────────┼───────────────┐
       │               │               │
       ▼               ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ Layer 2:     │ │ Layer 2:     │ │ Layer 2:     │
│ TestCase     │ │ Resource     │ │ CodeReview   │
│ Supervisor   │ │ Supervisor   │ │ Supervisor   │
│              │ │              │ │              │
│ (테스트케이스│ │ (리소스      │ │ (코드 리뷰   │
│  전문가)     │ │  전문가)     │ │  전문가)     │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                │
   ┌───┴───┬───┐    ┌───┴───┬───┐    ┌───┴───┬───┐
   │       │   │    │       │   │    │       │   │
   ▼       ▼   ▼    ▼       ▼   ▼    ▼       ▼   ▼
┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐
│Layer│ │Layer│ │Layer│ │Layer│ │Layer│ │Layer│
│  3: │ │  3: │ │  3: │ │  3: │ │  3: │ │  3: │
│     │ │     │ │     │ │     │ │     │ │     │
│Search│Create│Eval │ │Find │Search│Eval │
│Agent │Agent │Agent│ │Agent│Agent │Agent│
│     │ │     │ │     │ │     │ │     │ │     │
│(실행)│(실행)│(실행)│(실행)│(실행)│(실행)│
└─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘
   │       │       │       │       │       │
   └───────┴───────┴───────┴───────┴───────┘
                   │
                   ▼
            ┌─────────────┐
            │   Tools     │
            ├─────────────┤
            │ • search_   │
            │   testcase  │
            │ • generate_ │
            │   method    │
            │ • validate  │
            │ • glob      │
            │ • read_file │
            │ • grep      │
            └─────────────┘
```

---

## Layer 1: Supervisor Agent

### 역할

1. **전략 수립**: 사용자 요청 분석 및 전체 작업 계획
2. **Domain 선택**: 어떤 Domain Supervisor를 호출할지 결정
3. **결과 평가**: 각 Domain의 결과를 평가하여 다음 단계 결정
4. **최종 통합**: 모든 결과를 통합하여 사용자에게 반환

### State

```python
# state/supervisor_state.py
class SupervisorState(TypedDict):
    messages: Annotated[list, add_messages]
    next_supervisor: str  # "testcase" | "resource" | "review" | "END"
    testcase_result: Optional[dict]
    resource_result: Optional[dict]
    review_result: Optional[dict]
    final_output: Optional[str]
```

### 노드 구성

```python
# agents/supervisor_agent.py
workflow = StateGraph(SupervisorState)

workflow.add_node("supervisor", supervisor_node)           # 조율 노드
workflow.add_node("testcase_supervisor", testcase_wrapper) # TestCase 호출
workflow.add_node("resource_supervisor", resource_wrapper) # Resource 호출
workflow.add_node("review_supervisor", review_wrapper)     # Review 호출

workflow.set_entry_point("supervisor")

workflow.add_conditional_edges(
    "supervisor",
    route_to_domain,  # 다음 Domain Supervisor 결정
    {
        "testcase": "testcase_supervisor",
        "resource": "resource_supervisor",
        "review": "review_supervisor",
        "END": END
    }
)

# 각 Domain Supervisor 실행 후 다시 Supervisor로
workflow.add_edge("testcase_supervisor", "supervisor")
workflow.add_edge("resource_supervisor", "supervisor")
workflow.add_edge("review_supervisor", "supervisor")
```

### 결정 로직

```python
def route_to_domain(state: SupervisorState) -> str:
    """다음 Domain Supervisor 결정"""
    messages = state["messages"]

    # LLM에게 다음 단계 질문
    system_prompt = """You are the top-level supervisor.

    Based on the current state, decide which domain supervisor to call next:
    - testcase: For testcase search and method generation
    - resource: For finding necessary files and resources
    - review: For code review and validation
    - END: Task completed

    Rules:
    - Always start with 'testcase' for test automation tasks
    - After testcase, call 'resource' to find dependencies
    - Finally call 'review' to validate the result
    """

    response = llm.invoke([SystemMessage(content=system_prompt)] + messages)

    # 응답에서 다음 Domain 추출
    next_domain = parse_next_domain(response.content)

    return next_domain
```

---

## Layer 2: Domain Supervisors

각 도메인별로 특화된 Supervisor Agent

### 1. TestCase Supervisor

**역할**: 테스트케이스 검색, 메서드 생성, 검증 조율

**Worker Agents**:
- `search_agent`: 테스트케이스 검색
- `create_method_agent`: 자동화 메서드 생성
- `evaluator_agent`: 생성된 메서드 검증

**State**:
```python
# state/testcase_state.py
class TestCaseState(TypedDict):
    messages: Annotated[list, add_messages]
    next_agent: str  # "search" | "create" | "evaluate" | "END"
    search_result: Optional[dict]
    method_code: Optional[str]
    evaluation: Optional[dict]
```

**워크플로우**:
```python
# agents/testcase/testcase_supervisor.py
workflow = StateGraph(TestCaseState)

workflow.add_node("supervisor", testcase_supervisor_node)
workflow.add_node("search", search_agent_node)
workflow.add_node("create", create_method_agent_node)
workflow.add_node("evaluate", evaluator_agent_node)

workflow.set_entry_point("supervisor")

workflow.add_conditional_edges(
    "supervisor",
    route_next_worker,
    {
        "search": "search",
        "create": "create",
        "evaluate": "evaluate",
        "END": END
    }
)

# 각 Worker 실행 후 다시 Supervisor로 (평가를 위해)
workflow.add_edge("search", "supervisor")
workflow.add_edge("create", "supervisor")
workflow.add_edge("evaluate", "supervisor")
```

**평가 로직**:
```python
def testcase_supervisor_node(state: TestCaseState):
    """TestCase Supervisor: 각 단계 평가"""
    messages = state["messages"]

    # 현재 상태 평가
    if not state.get("search_result"):
        # Step 1: 검색 필요
        return {"next_agent": "search"}

    # 검색 결과 평가
    if not is_search_result_valid(state["search_result"]):
        # 재검색 필요
        return {"next_agent": "search"}

    if not state.get("method_code"):
        # Step 2: 메서드 생성 필요
        return {"next_agent": "create"}

    if not state.get("evaluation"):
        # Step 3: 검증 필요
        return {"next_agent": "evaluate"}

    # 검증 결과 평가
    if state["evaluation"]["status"] != "pass":
        # 재생성 필요
        return {"next_agent": "create"}

    # 모든 단계 완료
    return {"next_agent": "END"}
```

### 2. Resource Supervisor

**역할**: 필요한 파일 및 리소스 검색, 평가

**Worker Agents**:
- `finder_agent`: 관련 파일 검색
- `searcher_agent`: 리소스 내용 검색
- `evaluator_agent`: 리소스 평가

**State**:
```python
# state/resource_state.py
class ResourceState(TypedDict):
    messages: Annotated[list, add_messages]
    next_agent: str  # "find" | "search" | "evaluate" | "END"
    found_files: Optional[List[str]]
    resource_content: Optional[dict]
    evaluation: Optional[dict]
```

### 3. CodeReview Supervisor

**역할**: 생성된 코드 리뷰 및 개선 제안

**Worker Agents**:
- `syntax_checker_agent`: 문법 검사
- `logic_reviewer_agent`: 로직 검토
- `improvement_agent`: 개선 제안

---

## Layer 3: Worker Agents

실제 작업을 수행하는 ReAct Agent들

### 설계 원칙

모든 Worker Agent는 **LangGraph의 `create_react_agent`**로 생성:

```python
from langgraph.prebuilt import create_react_agent

def create_search_agent():
    """테스트케이스 검색 Agent"""
    llm = create_llm(temperature=0.0)
    tools = [search_testcase_vectordb, parse_testcase_fields]

    return create_react_agent(
        llm,
        tools,
        state_modifier="""You are a TestCase Search Agent.

        Your role:
        - Search for testcases accurately using search_testcase_vectordb
        - Parse the testcase content using parse_testcase_fields
        - Return structured results

        Do NOT:
        - Generate code
        - Evaluate results (Supervisor will do that)
        """
    )
```

### Worker Agent 목록

#### TestCase Domain
1. **search_agent**:
   - Tools: `search_testcase_vectordb`, `parse_testcase_fields`
   - 역할: ChromaDB에서 테스트케이스 검색

2. **create_method_agent**:
   - Tools: `search_example_code`, `generate_method_template`, `read_file`
   - 역할: example 코드 참조하여 자동화 메서드 생성

3. **evaluator_agent**:
   - Tools: `validate_method_code`, `check_syntax`, `check_pb2_usage`
   - 역할: 생성된 메서드 검증

#### Resource Domain
4. **finder_agent**:
   - Tools: `glob`, `grep`, `bash`
   - 역할: 필요한 파일 검색

5. **searcher_agent**:
   - Tools: `read_file`, `grep`, `analyze_structure`
   - 역할: 파일 내용 검색

6. **evaluator_agent**:
   - Tools: (평가 전용, tool 없음)
   - 역할: 리소스 충분성 평가

---

## State 관리

### State 계층

```
SupervisorState (최상위)
    ├─ messages (전체 대화 기록)
    ├─ next_supervisor (다음 Domain)
    ├─ testcase_result (TestCase 결과)
    │   └─ TestCaseState (TestCase Supervisor 내부)
    │       ├─ messages (TestCase 대화)
    │       ├─ next_agent (다음 Worker)
    │       ├─ search_result
    │       ├─ method_code
    │       └─ evaluation
    │
    ├─ resource_result (Resource 결과)
    │   └─ ResourceState (Resource Supervisor 내부)
    │       ├─ messages
    │       ├─ next_agent
    │       ├─ found_files
    │       ├─ resource_content
    │       └─ evaluation
    │
    └─ final_output (최종 결과)
```

### State 전달

```python
# Supervisor → Domain Supervisor
def testcase_supervisor_wrapper(state: SupervisorState):
    """Supervisor State → TestCase State 변환"""
    testcase_state = {
        "messages": state["messages"],
        "next_agent": "search",  # 초기값
        "search_result": None,
        "method_code": None,
        "evaluation": None
    }

    # TestCase Supervisor 실행
    result = testcase_supervisor.invoke(testcase_state)

    # 결과를 Supervisor State에 반영
    return {
        "testcase_result": result,
        "messages": result["messages"]
    }
```

---

## 실행 흐름

### 예시: "COMMONR-30 스텝 4번의 완벽한 테스트 메서드 생성"

```
[1] User Input
    messages: [("user", "COMMONR-30 스텝 4번의 완벽한 테스트 메서드 생성")]

[2] Supervisor Agent (1차)
    → 분석: "테스트 메서드 생성 작업"
    → 결정: next_supervisor = "testcase"

[3] TestCase Supervisor
    ├─ [Supervisor 평가] "검색부터 시작"
    ├─ → next_agent = "search"
    │
    ├─ [search_agent 실행]
    │   ├─ Tool: search_testcase_vectordb(
    │   │         query="COMMONR-30 step 4",
    │   │         query_type="single",
    │   │         issue_key="COMMONR-30",
    │   │         step_number=4
    │   │       )
    │   └─ Result: {"status": "success", "content": "TNA 설정 변경 테스트..."}
    │
    ├─ [Supervisor 평가] "검색 성공 → 메서드 생성"
    ├─ → next_agent = "create"
    │
    ├─ [create_method_agent 실행]
    │   ├─ Tool: search_example_code(category="tna", keyword="setTNAConfig")
    │   ├─ Tool: read_file("example/tna/setTNAConfig.py")
    │   ├─ Tool: generate_method_template(...)
    │   └─ Result: method_code = "def test_tna_config_update(self): ..."
    │
    ├─ [Supervisor 평가] "메서드 생성 완료 → 검증"
    ├─ → next_agent = "evaluate"
    │
    ├─ [evaluator_agent 실행]
    │   ├─ Tool: validate_method_code(code)
    │   ├─ Tool: check_syntax(code)
    │   └─ Result: {"status": "pass", "score": 0.95}
    │
    ├─ [Supervisor 평가] "완벽함 → Supervisor에게 전달"
    └─ → next_agent = "END"

[4] Supervisor Agent (2차)
    → testcase_result 수신
    → 평가: "테스트 메서드 완성, 필요한 리소스는?"
    → 결정: next_supervisor = "resource"

[5] Resource Supervisor
    ├─ [Supervisor 평가] "필요한 파일 찾기"
    ├─ → next_agent = "find"
    │
    ├─ [finder_agent 실행]
    │   ├─ Tool: grep(pattern="tna_pb2", path="demo")
    │   ├─ Tool: glob(pattern="*manager.py", path="demo")
    │   └─ Result: ["demo/manager.py", "biostar/service/tna_pb2.py"]
    │
    ├─ [Supervisor 평가] "파일 찾음 → 내용 검색"
    ├─ → next_agent = "search"
    │
    ├─ [searcher_agent 실행]
    │   ├─ Tool: read_file("demo/manager.py", grep="setTNAConfig")
    │   └─ Result: resource_content = {...}
    │
    ├─ [Supervisor 평가] "리소스 충분 → 평가"
    ├─ → next_agent = "evaluate"
    │
    ├─ [evaluator_agent 실행]
    │   └─ Result: {"status": "sufficient"}
    │
    └─ → next_agent = "END"

[6] Supervisor Agent (3차)
    → resource_result 수신
    → 평가: "모든 작업 완료"
    → 결정: next_supervisor = "END"
    → final_output 생성 및 사용자에게 전달

[7] User Output
    """
    완벽한 테스트 메서드를 생성했습니다:

    ```python
    def test_tna_config_update(self):
        config = self.svcManager.getTNAConfig(self.targetID)
        expected = copy.deepcopy(config)
        expected.mode = tna_pb2.MODE_FIXED
        expected.key = 123
        self.svcManager.setTNAConfig(self.targetID, expected)
        actual = self.svcManager.getTNAConfig(self.targetID)
        self.assertEqual(expected.mode, actual.mode)
    ```

    필요한 리소스:
    - demo/manager.py (ServiceManager.setTNAConfig)
    - biostar/service/tna_pb2.py (TNAConfig)
    """
```

---

## 디렉토리 구조

```
QE_Agent/
├── src/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── supervisor_agent.py          # Layer 1: 최상위 Supervisor
│   │   │
│   │   ├── testcase/                    # TestCase Domain
│   │   │   ├── __init__.py
│   │   │   ├── testcase_supervisor.py   # Layer 2: TestCase Supervisor
│   │   │   ├── search_agent.py          # Layer 3: Worker
│   │   │   ├── create_method_agent.py   # Layer 3: Worker
│   │   │   └── evaluator_agent.py       # Layer 3: Worker
│   │   │
│   │   ├── resource/                    # Resource Domain
│   │   │   ├── __init__.py
│   │   │   ├── resource_supervisor.py   # Layer 2: Resource Supervisor
│   │   │   ├── finder_agent.py          # Layer 3: Worker
│   │   │   ├── searcher_agent.py        # Layer 3: Worker
│   │   │   └── evaluator_agent.py       # Layer 3: Worker
│   │   │
│   │   └── code_review/                 # CodeReview Domain
│   │       ├── __init__.py
│   │       ├── review_supervisor.py     # Layer 2: Review Supervisor
│   │       ├── syntax_checker_agent.py  # Layer 3: Worker
│   │       ├── logic_reviewer_agent.py  # Layer 3: Worker
│   │       └── improvement_agent.py     # Layer 3: Worker
│   │
│   ├── tools/                            # 도구들 (기존 유지)
│   │   ├── __init__.py
│   │   ├── testcase_tools.py             # 테스트케이스 관련 도구
│   │   ├── search_tools.py               # 파일 검색 도구
│   │   ├── code_generation_tools.py      # 코드 생성 도구 (NEW)
│   │   ├── validation_tools.py           # 검증 도구 (NEW)
│   │   └── tool_models.py                # Pydantic 모델
│   │
│   ├── state/
│   │   ├── __init__.py
│   │   ├── supervisor_state.py           # Supervisor State
│   │   ├── testcase_state.py             # TestCase State
│   │   ├── resource_state.py             # Resource State
│   │   └── review_state.py               # Review State
│   │
│   ├── config.py                         # LLM 및 VectorStore 설정
│   └── main.py                           # 메인 진입점
│
├── tests/
│   ├── test_supervisor.py
│   ├── test_testcase_supervisor.py
│   └── test_worker_agents.py
│
├── checkpoints/                          # SQLite checkpoints
│   └── checkpoints.db
│
├── ARCHITECTURE.md                       # 이 문서
├── README.md                             # 사용 가이드
└── .env                                  # 환경 변수
```

---

## 확장 가능성

### 1. 새로운 Domain Supervisor 추가

```python
# agents/deployment/deployment_supervisor.py
def create_deployment_supervisor():
    """배포 전문 Supervisor"""
    workflow = StateGraph(DeploymentState)

    workflow.add_node("supervisor", deployment_supervisor_node)
    workflow.add_node("build", build_agent_node)
    workflow.add_node("test", test_agent_node)
    workflow.add_node("deploy", deploy_agent_node)

    # ... (워크플로우 구성)

    return workflow.compile()

# supervisor_agent.py에 등록
workflow.add_node("deployment_supervisor", deployment_wrapper)
workflow.add_conditional_edges(
    "supervisor",
    route_to_domain,
    {
        "testcase": "testcase_supervisor",
        "resource": "resource_supervisor",
        "deployment": "deployment_supervisor",  # NEW
        "END": END
    }
)
```

### 2. 새로운 Worker Agent 추가

```python
# agents/testcase/refactoring_agent.py
def create_refactoring_agent():
    """코드 리팩토링 Agent"""
    llm = create_llm(temperature=0.2)
    tools = [analyze_code_complexity, suggest_improvements]

    return create_react_agent(
        llm,
        tools,
        state_modifier="You are a Code Refactoring Agent..."
    )

# testcase_supervisor.py에 등록
workflow.add_node("refactor", refactoring_agent_node)
```

### 3. Parallel Execution (병렬 실행)

```python
# 여러 Worker를 병렬로 실행 (독립적인 작업)
from langgraph.graph import START

workflow.add_edge(START, ["search", "validate"])  # 병렬 시작
workflow.add_edge(["search", "validate"], "create")  # 둘 다 완료 후 진행
```

### 4. Human-in-the-Loop

```python
# 중요한 단계에서 사람의 승인 필요
graph = workflow.compile(
    checkpointer=checkpoint_conn,
    interrupt_before=["create_method_agent", "deploy_agent"]
)

# 사용자 승인 후 재개
result = graph.invoke(None, config)
```

---

## 베스트 프랙티스

### 1. Supervisor 설계
- ✅ **평가 로직 명확화**: 각 단계 평가 기준 명시
- ✅ **재시도 전략**: 실패 시 재시도 또는 대체 Agent 호출
- ✅ **상태 최소화**: 필요한 정보만 State에 저장

### 2. Worker Agent 설계
- ✅ **단일 책임**: 하나의 작업만 수행
- ✅ **평가 제외**: 평가는 Supervisor가 담당
- ✅ **명확한 출력**: 구조화된 결과 반환

### 3. Tool 설계
- ✅ **Pydantic 검증**: 모든 파라미터 타입 안전
- ✅ **오류 처리**: 모든 오류를 dict로 반환
- ✅ **실행만 담당**: 추론 로직 제거

### 4. State 관리
- ✅ **계층화**: Supervisor State ⊃ Domain State
- ✅ **메시지 중심**: 대화 기록은 messages로 관리
- ✅ **계산 가능한 값 제거**: 필요 시 계산

---

## 참고 자료

### LangGraph
- [Hierarchical Agent Teams](https://langchain-ai.github.io/langgraph/tutorials/multi_agent/hierarchical_agent_teams/)
- [create_react_agent](https://langchain-ai.github.io/langgraph/reference/prebuilt/#create_react_agent)
- [Conditional Edges](https://langchain-ai.github.io/langgraph/concepts/#conditional-edges)

### 설계 패턴
- **계층적 구조**: Supervisor of Supervisors
- **전문화**: Domain-Specific Agents
- **순차적 평가**: Step-by-Step Validation

---

## 라이선스

MIT

---

**마지막 업데이트**: 2025-11-08
**버전**: v3.0
**작성자**: QE Agent Team
