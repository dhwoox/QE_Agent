"""
Layer 2: Resource Supervisor Agent

Resource 도메인 작업을 조율하는 Supervisor
- Worker Agents 순차 실행: find → search → evaluate (직선형 파이프라인)
"""

from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, END

from ...state.resource_state import ResourceState
from .finder_agent import create_finder_agent
from .searcher_agent import create_searcher_agent
from .evaluator_agent import create_resource_evaluator_agent


def create_resource_supervisor():
    """Resource Supervisor Agent 생성 (직선형 파이프라인)

    Returns:
        CompiledGraph: Resource Domain Supervisor
    """
    # Worker Agents 생성
    finder_agent = create_finder_agent()
    searcher_agent = create_searcher_agent()
    eval_agent = create_resource_evaluator_agent()

    # 그래프 정의
    workflow = StateGraph(ResourceState)

    # 노드 정의 (직선형 파이프라인)

    async def find_node(state: ResourceState) -> ResourceState:
        """Worker Agent: 파일/폴더 검색"""
        messages = state["messages"]

        # 검색 시작 메시지
        start_msg = HumanMessage(content="[Resource - Find] 🔍 파일/폴더 검색 시작...")

        try:
            # finder_agent 실행 (비동기)
            result = await finder_agent.ainvoke({"messages": messages})

            # 마지막 AI 메시지 추출
            last_message = result["messages"][-1]

            # 검색 결과 저장
            find_result = {
                "content": last_message.content,
                "success": "error" not in last_message.content.lower()
            }

            # 검색 완료 메시지
            completion_msg = HumanMessage(
                content=f"[Resource - Find] {'✅ 검색 성공' if find_result['success'] else '⚠️ 검색 결과 없음'} → Search로 진행"
            )

            return {
                "messages": [start_msg, last_message, completion_msg],
                "find_result": find_result
            }

        except Exception as e:
            # 예외 발생 시
            error_msg = HumanMessage(
                content=f"[Resource - Find] ❌ 검색 중 오류 발생: {type(e).__name__}\n상세: {str(e)}"
            )

            find_result = {
                "content": f"검색 실패: {str(e)}",
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }

            return {
                "messages": [start_msg, error_msg],
                "find_result": find_result
            }

    async def search_node(state: ResourceState) -> ResourceState:
        """Worker Agent: 파일 내용 검색"""
        messages = state["messages"]
        find_result = state.get("find_result", {})

        # 검색 시작 메시지
        start_msg = HumanMessage(content="[Resource - Search] 📄 파일 내용 검색 시작...")

        # 파일 검색 결과를 포함한 메시지 생성
        search_messages = messages + [
            HumanMessage(content=f"찾은 파일들의 내용을 검색해주세요.\n\n찾은 파일:\n{find_result.get('content', '')}")
        ]

        # searcher_agent 실행 (비동기)
        result = await searcher_agent.ainvoke({"messages": search_messages})

        # 마지막 AI 메시지 추출
        last_message = result["messages"][-1]

        # 검색 결과 저장
        search_result = {
            "content": last_message.content,
            "success": True
        }

        # 검색 완료 메시지
        completion_msg = HumanMessage(content="[Resource - Search] ✅ 내용 검색 완료 → Evaluate로 진행")

        return {
            "messages": [start_msg, last_message, completion_msg],
            "search_result": search_result
        }

    async def evaluate_node(state: ResourceState) -> ResourceState:
        """Worker Agent: 검색 결과 평가"""
        messages = state["messages"]
        find_result = state.get("find_result", {})
        search_result = state.get("search_result", {})

        # 평가 시작 메시지
        start_msg = HumanMessage(content="[Resource - Evaluate] 📊 검색 결과 평가 시작...")

        # 평가 메시지 생성
        eval_messages = messages + [
            HumanMessage(content=f"""다음 검색 결과의 관련성을 평가해주세요.

원본 쿼리: {messages[0].content if messages else 'N/A'}

파일 검색 결과:
{find_result.get('content', 'N/A')}

내용 검색 결과:
{search_result.get('content', 'N/A')}
""")
        ]

        # eval_agent 실행 (비동기)
        result = await eval_agent.ainvoke({"messages": eval_messages})

        # 마지막 AI 메시지 추출
        last_message = result["messages"][-1]

        # 평가 결과 저장
        evaluation = {
            "content": last_message.content,
            "verdict": "PASS" if "PASS" in last_message.content else "NEEDS_IMPROVEMENT"
        }

        # 평가 완료 메시지
        completion_msg = HumanMessage(
            content=f"[Resource - Evaluate] ✅ 평가 완료: {evaluation['verdict']}"
        )

        # 최종 출력 생성
        final_output = f"""
Resource 검색 완료

파일 검색 결과:
{find_result.get('content', 'N/A')}

내용 검색 결과:
{search_result.get('content', 'N/A')}

평가 결과:
{evaluation['content']}
"""

        return {
            "messages": [start_msg, last_message, completion_msg],
            "evaluation": evaluation,
            "final_output": final_output
        }

    # 노드 추가
    workflow.add_node("find", find_node)
    workflow.add_node("search", search_node)
    workflow.add_node("evaluate", evaluate_node)

    # 엣지 연결 (직선형 파이프라인)
    workflow.set_entry_point("find")
    workflow.add_edge("find", "search")
    workflow.add_edge("search", "evaluate")
    workflow.add_edge("evaluate", END)

    # 그래프 컴파일
    return workflow.compile()
