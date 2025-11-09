"""
Layer 1: Supervisor Agent (CEO 역할)

최상위 Supervisor Agent
- 각 Domain Supervisor 결과를 검토하고 승인/반려
- 결과 불만족 시 재실행 지시 (루프백)
- Checkpointer로 상태 관리 및 롤백 가능
"""

from typing import Literal
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

from ..state.supervisor_state import SupervisorState
from ..config import create_llm_for_task
from .testcase.testcase_supervisor import create_testcase_supervisor
from .resource.resource_supervisor import create_resource_supervisor
from .generate.generate_supervisor import create_generate_supervisor


# 재시도 최대 횟수
MAX_RETRIES = 2


def create_supervisor_agent():
    """최상위 Supervisor Agent 생성 (CEO 역할)

    Returns:
        CompiledGraph: 최상위 Supervisor Agent
    """
    # Domain Supervisors 생성
    testcase_supervisor = create_testcase_supervisor()
    resource_supervisor = create_resource_supervisor()
    generate_supervisor = create_generate_supervisor()

    # CEO LLM (평가 및 의사결정용)
    ceo_llm = create_llm_for_task("search")

    # 그래프 정의
    workflow = StateGraph(SupervisorState)

    # ========== 노드 정의 ==========

    def start_node(_state: SupervisorState) -> SupervisorState:
        """시작: 초기 상태 설정"""
        return {
            "next_supervisor": "testcase",
            "testcase_retry_count": 0,
            "resource_retry_count": 0,
            "generate_retry_count": 0
        }

    # ----- TestCase Domain -----

    async def testcase_node(state: SupervisorState) -> SupervisorState:
        """TestCase 본부장에게 작업 지시"""
        messages = state["messages"]
        user_messages = [msg for msg in messages if isinstance(msg, HumanMessage) and not str(msg.content).startswith("[")]

        # 작업 시작 메시지
        start_msg = HumanMessage(content="[CEO → TestCase 본부] 테스트케이스 검색 작업 지시")

        # TestCase Supervisor 실행 (비동기)
        result = await testcase_supervisor.ainvoke({
            "messages": user_messages,
            "next_agent": None,
            "search_result": None,
            "analysis_result": None,
            "implementation_plan": None,
            "evaluation": None,
            "final_output": None
        })

        # 하위 그래프 메시지 전파
        subgraph_messages = result.get("messages", [])

        # 완료 메시지
        completion_msg = HumanMessage(
            content=f"""[CEO] TestCase 본부 작업 완료

결과 요약:
{str(result.get('final_output') or 'N/A')[:300]}..."""
        )

        # 결과 저장
        testcase_result = {
            "final_output": result.get("final_output", ""),
            "search_result": result.get("search_result"),
            "analysis_result": result.get("analysis_result"),
            "implementation_plan": result.get("implementation_plan"),
            "evaluation": result.get("evaluation")
        }

        return {
            "messages": [start_msg, *subgraph_messages, completion_msg],
            "testcase_result": testcase_result,
            "next_supervisor": "evaluate_testcase"
        }

    async def evaluate_testcase_node(state: SupervisorState) -> SupervisorState:
        """CEO가 TestCase 결과 검토"""
        testcase_result = state.get("testcase_result", {})
        retry_count = state.get("testcase_retry_count", 0)
        messages = state["messages"]

        # 평가 시작 메시지
        eval_start_msg = HumanMessage(
            content=f"[CEO 평가] TestCase 결과 검토 중... (재시도: {retry_count}/{MAX_RETRIES})"
        )

        # CEO의 검토
        review_prompt = f"""당신은 CEO입니다. TestCase 본부장의 보고서를 검토하세요.

사용자 요청:
{messages[0].content if messages else 'N/A'}

TestCase 본부 보고서:
{testcase_result.get('final_output', 'N/A')}

검토 기준:
1. 테스트케이스를 찾았는가?
2. 찾은 테스트케이스가 사용자 요청과 관련이 있는가?
3. 검색 결과가 충분한가?

결정:
- APPROVED: 결과가 만족스러움 → 다음 단계(Resource) 진행
- RETRY: 결과가 불만족 → TestCase 본부에 재작업 지시
- FAILED: 최대 재시도 횟수 초과 또는 치명적 오류

현재 재시도 횟수: {retry_count}/{MAX_RETRIES}

답변 형식: APPROVED 또는 RETRY 또는 FAILED 중 하나만 출력하세요.
"""

        review_response = await ceo_llm.ainvoke([SystemMessage(content=review_prompt)])
        decision = review_response.content.strip().upper()

        # 평가 결과 메시지
        eval_result_msg = HumanMessage(
            content=f"""[CEO 평가] 결정: {decision}

평가 내용:
{review_response.content}"""
        )

        # 결정 처리
        if "APPROVED" in decision:
            approved_msg = HumanMessage(content="[CEO] ✅ TestCase 작업 승인! → Resource 단계로 진행")
            return {
                "messages": [eval_start_msg, eval_result_msg, approved_msg],
                "next_supervisor": "resource"
            }
        elif "RETRY" in decision and retry_count < MAX_RETRIES:
            retry_msg = HumanMessage(content=f"[CEO] 🔄 TestCase 결과 불만족. 재작업 지시 ({retry_count + 1}/{MAX_RETRIES})")
            return {
                "messages": [eval_start_msg, eval_result_msg, retry_msg],
                "next_supervisor": "testcase",
                "testcase_retry_count": retry_count + 1
            }
        else:
            # FAILED 또는 최대 재시도 초과
            failed_msg = HumanMessage(content="[CEO] ❌ TestCase 작업 실패. 최대 재시도 횟수 초과.")
            return {
                "messages": [eval_start_msg, eval_result_msg, failed_msg],
                "next_supervisor": "END",
                "final_output": f"[실패] TestCase 작업을 완료하지 못했습니다.\n\n마지막 결과:\n{testcase_result.get('final_output', 'N/A')}"
            }

    # ----- Resource Domain -----

    async def resource_node(state: SupervisorState) -> SupervisorState:
        """Resource 본부장에게 작업 지시"""
        messages = state["messages"]
        testcase_result = state.get("testcase_result", {})
        user_messages = [msg for msg in messages if isinstance(msg, HumanMessage) and not str(msg.content).startswith("[")]

        # 작업 시작 메시지
        start_msg = HumanMessage(content="[CEO → Resource 본부] 관련 파일 및 코드 검색 작업 지시")

        # TestCase 결과 포함하여 Resource에 전달
        resource_messages = user_messages + [
            HumanMessage(content=f"TestCase 검색 결과:\n{testcase_result.get('search_result', {}).get('content', '')}\n\n관련 파일 및 코드를 찾아주세요.")
        ]

        # Resource Supervisor 실행 (비동기)
        result = await resource_supervisor.ainvoke({
            "messages": resource_messages,
            "next_agent": None,
            "find_result": None,
            "search_result": None,
            "evaluation": None,
            "final_output": None
        })

        # 하위 그래프 메시지 전파
        subgraph_messages = result.get("messages", [])

        # 완료 메시지
        completion_msg = HumanMessage(
            content=f"""[CEO] Resource 본부 작업 완료

결과 요약:
{str(result.get('final_output') or 'N/A')[:300]}..."""
        )

        # 결과 저장
        resource_result = {
            "final_output": result.get("final_output", ""),
            "find_result": result.get("find_result"),
            "search_result": result.get("search_result"),
            "evaluation": result.get("evaluation")
        }

        return {
            "messages": [start_msg, *subgraph_messages, completion_msg],
            "resource_result": resource_result,
            "next_supervisor": "evaluate_resource"
        }

    async def evaluate_resource_node(state: SupervisorState) -> SupervisorState:
        """CEO가 Resource 결과 검토"""
        resource_result = state.get("resource_result", {})
        retry_count = state.get("resource_retry_count", 0)
        messages = state["messages"]

        # 평가 시작 메시지
        eval_start_msg = HumanMessage(
            content=f"[CEO 평가] Resource 결과 검토 중... (재시도: {retry_count}/{MAX_RETRIES})"
        )

        # CEO의 검토
        review_prompt = f"""당신은 CEO입니다. Resource 본부장의 보고서를 검토하세요.

사용자 요청:
{messages[0].content if messages else 'N/A'}

Resource 본부 보고서:
{resource_result.get('final_output', 'N/A')}

검토 기준:
1. 관련 파일을 찾았는가?
2. 참고할 코드 패턴이 있는가?
3. 자동화 코드 생성에 필요한 정보가 충분한가?

결정:
- APPROVED: 결과가 만족스러움 → 다음 단계(Generate) 진행
- RETRY: 결과가 불만족 → Resource 본부에 재작업 지시
- FAILED: 최대 재시도 횟수 초과 또는 치명적 오류

현재 재시도 횟수: {retry_count}/{MAX_RETRIES}

답변 형식: APPROVED 또는 RETRY 또는 FAILED 중 하나만 출력하세요.
"""

        review_response = await ceo_llm.ainvoke([SystemMessage(content=review_prompt)])
        decision = review_response.content.strip().upper()

        # 평가 결과 메시지
        eval_result_msg = HumanMessage(
            content=f"""[CEO 평가] 결정: {decision}

평가 내용:
{review_response.content}"""
        )

        # 결정 처리
        if "APPROVED" in decision:
            approved_msg = HumanMessage(content="[CEO] ✅ Resource 작업 승인! → Generate 단계로 진행")
            return {
                "messages": [eval_start_msg, eval_result_msg, approved_msg],
                "next_supervisor": "generate"
            }
        elif "RETRY" in decision and retry_count < MAX_RETRIES:
            retry_msg = HumanMessage(content=f"[CEO] 🔄 Resource 결과 불만족. 재작업 지시 ({retry_count + 1}/{MAX_RETRIES})")
            return {
                "messages": [eval_start_msg, eval_result_msg, retry_msg],
                "next_supervisor": "resource",
                "resource_retry_count": retry_count + 1
            }
        else:
            failed_msg = HumanMessage(content="[CEO] ❌ Resource 작업 실패. 최대 재시도 횟수 초과.")
            return {
                "messages": [eval_start_msg, eval_result_msg, failed_msg],
                "next_supervisor": "END",
                "final_output": f"[실패] Resource 작업을 완료하지 못했습니다.\n\n마지막 결과:\n{resource_result.get('final_output', 'N/A')}"
            }

    # ----- Generate Domain -----

    async def generate_node(state: SupervisorState) -> SupervisorState:
        """Generate 본부장에게 작업 지시"""
        messages = state["messages"]
        testcase_result = state.get("testcase_result", {})
        resource_result = state.get("resource_result", {})
        user_messages = [msg for msg in messages if isinstance(msg, HumanMessage) and not str(msg.content).startswith("[")]

        # 작업 시작 메시지
        start_msg = HumanMessage(content="[CEO → Generate 본부] 자동화 코드 생성 작업 지시")

        # TestCase + Resource 결과를 통합하여 Generate에 전달
        generate_messages = user_messages + [
            HumanMessage(content=f"""자동화 코드를 생성해주세요.

TestCase 정보:
{testcase_result.get('search_result', {}).get('content', '')}

Resource 정보 (참고 코드):
{resource_result.get('search_result', {}).get('content', '')}

위 정보를 기반으로 실행 가능한 GSDK 테스트 자동화 코드를 생성하세요.
""")
        ]

        # Generate Supervisor 실행 (비동기)
        result = await generate_supervisor.ainvoke({
            "messages": generate_messages,
            "next_agent": None,
            "generated_code": None,
            "file_path": None,
            "validation": None,
            "final_output": None
        })

        # 하위 그래프 메시지 전파
        subgraph_messages = result.get("messages", [])

        # 완료 메시지
        completion_msg = HumanMessage(
            content=f"""[CEO] Generate 본부 작업 완료

결과 요약:
{str(result.get('final_output') or 'N/A')[:300]}..."""
        )

        # 결과 저장
        generate_result = {
            "final_output": result.get("final_output", ""),
            "generated_code": result.get("generated_code"),
            "file_path": result.get("file_path"),
            "validation": result.get("validation")
        }

        return {
            "messages": [start_msg, *subgraph_messages, completion_msg],
            "generate_result": generate_result,
            "next_supervisor": "evaluate_generate"
        }

    async def evaluate_generate_node(state: SupervisorState) -> SupervisorState:
        """CEO가 Generate 결과 검토 (최종 승인)"""
        generate_result = state.get("generate_result", {})
        retry_count = state.get("generate_retry_count", 0)
        messages = state["messages"]
        testcase_result = state.get("testcase_result", {})
        resource_result = state.get("resource_result", {})

        # 평가 시작 메시지
        eval_start_msg = HumanMessage(
            content=f"[CEO 최종 평가] Generate 결과 검토 중... (재시도: {retry_count}/{MAX_RETRIES})"
        )

        # CEO의 최종 검토
        review_prompt = f"""당신은 CEO입니다. Generate 본부장의 보고서를 최종 검토하세요.

사용자 요청:
{messages[0].content if messages else 'N/A'}

Generate 본부 보고서:
{generate_result.get('final_output', 'N/A')}

검토 기준:
1. 코드가 생성되었는가?
2. 문법이 올바른가?
3. 실행 가능한 코드인가?

결정:
- APPROVED: 최종 승인 → 작업 완료
- RETRY: 재작업 지시 → Generate 본부에 재작업 지시
- FAILED: 최대 재시도 횟수 초과

현재 재시도 횟수: {retry_count}/{MAX_RETRIES}

답변 형식: APPROVED 또는 RETRY 또는 FAILED 중 하나만 출력하세요.
"""

        review_response = await ceo_llm.ainvoke([SystemMessage(content=review_prompt)])
        decision = review_response.content.strip().upper()

        # 평가 결과 메시지
        eval_result_msg = HumanMessage(
            content=f"""[CEO 최종 평가] 결정: {decision}

평가 내용:
{review_response.content}"""
        )

        # 결정 처리
        if "APPROVED" in decision:
            # 최종 승인 메시지
            approved_msg = HumanMessage(content="[CEO] ✅ 최종 승인! 전체 파이프라인 완료!")

            # 최종 성공!
            final_output = f"""
========================================
QE Agent v3 - 자동화 코드 생성 완료
========================================

1. TestCase 검색 결과:
{testcase_result.get('final_output', 'N/A')}

2. Resource 검색 결과:
{resource_result.get('final_output', 'N/A')}

3. 자동화 코드 생성 결과:
{generate_result.get('final_output', 'N/A')}

========================================
✅ CEO 최종 승인! 전체 파이프라인 완료!
========================================
"""
            return {
                "messages": [eval_start_msg, eval_result_msg, approved_msg],
                "next_supervisor": "END",
                "final_output": final_output
            }
        elif "RETRY" in decision and retry_count < MAX_RETRIES:
            retry_msg = HumanMessage(content=f"[CEO] 🔄 Generate 결과 불만족. 재작업 지시 ({retry_count + 1}/{MAX_RETRIES})")
            return {
                "messages": [eval_start_msg, eval_result_msg, retry_msg],
                "next_supervisor": "generate",
                "generate_retry_count": retry_count + 1
            }
        else:
            failed_msg = HumanMessage(content="[CEO] ❌ Generate 작업 실패. 최대 재시도 횟수 초과.")
            return {
                "messages": [eval_start_msg, eval_result_msg, failed_msg],
                "next_supervisor": "END",
                "final_output": f"[실패] Generate 작업을 완료하지 못했습니다.\n\n마지막 결과:\n{generate_result.get('final_output', 'N/A')}"
            }

    # ========== 조건부 엣지 함수 ==========

    def route_next(state: SupervisorState) -> Literal["testcase", "evaluate_testcase", "resource", "evaluate_resource", "generate", "evaluate_generate", "END"]:
        """다음 실행할 노드 결정"""
        next_supervisor = state.get("next_supervisor", "END")
        return next_supervisor

    # ========== 그래프 구성 ==========

    # 노드 추가
    workflow.add_node("start", start_node)
    workflow.add_node("testcase", testcase_node)
    workflow.add_node("evaluate_testcase", evaluate_testcase_node)
    workflow.add_node("resource", resource_node)
    workflow.add_node("evaluate_resource", evaluate_resource_node)
    workflow.add_node("generate", generate_node)
    workflow.add_node("evaluate_generate", evaluate_generate_node)

    # 엣지 연결
    workflow.set_entry_point("start")

    # start → testcase
    workflow.add_conditional_edges(
        "start",
        route_next,
        {
            "testcase": "testcase",
            "END": END
        }
    )

    # testcase → evaluate_testcase (항상)
    workflow.add_edge("testcase", "evaluate_testcase")

    # evaluate_testcase → resource OR testcase(재시도) OR END
    workflow.add_conditional_edges(
        "evaluate_testcase",
        route_next,
        {
            "resource": "resource",
            "testcase": "testcase",  # 루프백!
            "END": END
        }
    )

    # resource → evaluate_resource (항상)
    workflow.add_edge("resource", "evaluate_resource")

    # evaluate_resource → generate OR resource(재시도) OR END
    workflow.add_conditional_edges(
        "evaluate_resource",
        route_next,
        {
            "generate": "generate",
            "resource": "resource",  # 루프백!
            "END": END
        }
    )

    # generate → evaluate_generate (항상)
    workflow.add_edge("generate", "evaluate_generate")

    # evaluate_generate → END OR generate(재시도)
    workflow.add_conditional_edges(
        "evaluate_generate",
        route_next,
        {
            "generate": "generate",  # 루프백!
            "END": END
        }
    )

    # 그래프 컴파일
    return workflow.compile()
