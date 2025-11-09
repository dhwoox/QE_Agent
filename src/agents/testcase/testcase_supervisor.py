"""
Layer 2: TestCase Supervisor Agent

TestCase 도메인 작업을 조율하는 Supervisor
- Worker Agents 순차 실행: search → design → evaluate (직선형 파이프라인)
"""

import re
import json
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, END

from ...state.testcase_state import TestCaseState
from ...tools.tool_models import TestCaseSearchParams
from ...config import create_llm_for_task
from .search_agent import create_testcase_search_agent
from .design_agent import create_testcase_design_agent
from .evaluator_agent import create_testcase_evaluator_agent


async def _parse_testcase_query(query: str) -> TestCaseSearchParams:
    """LLM을 사용하여 자연어 쿼리를 TestCaseSearchParams로 변환

    Args:
        query: 사용자 입력 쿼리 (예: "COMMONR-198의 테스트 스텝 2번 자동화 코드 생성")

    Returns:
        TestCaseSearchParams: 파싱된 검색 파라미터
    """
    # 빈 쿼리 처리
    if not query or not query.strip():
        return TestCaseSearchParams(
            query="기능 기반 검색",
            query_type="feature"
        )

    # LLM 생성 (파싱용)
    llm = create_llm_for_task("reasoning")

    # 파싱 프롬프트
    prompt = f"""다음 사용자 쿼리를 분석하여 테스트케이스 검색 파라미터로 변환하세요.

사용자 쿼리: "{query}"

분석 기준:
1. COMMONR-XXX 형태의 Issue Key가 있는가?
2. 특정 스텝 번호(숫자)가 언급되는가?
3. "전체", "모든", "all" 같은 키워드가 있는가?

타입 결정 규칙:
- single: Issue Key가 있고 + 특정 스텝 번호가 있음
  예: "COMMONR-198 스텝 2", "COMMONR-30의 테스트 4번"

- multiple: Issue Key가 있고 + "전체", "모든", "all" 키워드 있음
  예: "COMMONR-198 전체", "COMMONR-30 모든 스텝"

- feature: Issue Key가 없음 (기능 설명만)
  예: "로그인 기능 테스트", "사용자 인증"

JSON 형식으로만 답변하세요 (다른 설명 없이):
{{
  "query_type": "single" | "multiple" | "feature",
  "issue_key": "COMMONR-XXX" 또는 null,
  "step_number": 숫자 또는 null
}}"""

    try:
        # LLM 호출
        response = await llm.ainvoke([HumanMessage(content=prompt)])

        # JSON 파싱 (```json ``` 태그 제거)
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]  # ```json 제거
        if content.startswith("```"):
            content = content[3:]  # ``` 제거
        if content.endswith("```"):
            content = content[:-3]  # ``` 제거
        content = content.strip()

        parsed = json.loads(content)

        return TestCaseSearchParams(
            query=query,
            query_type=parsed["query_type"],
            issue_key=parsed.get("issue_key"),
            step_number=parsed.get("step_number")
        )

    except Exception as e:
        # LLM 파싱 실패 시 폴백: 정규식 사용
        print(f"⚠️ LLM 파싱 실패, 정규식 폴백 사용: {e}")

        # Single 패턴
        single_pattern = r'(COMMONR-\d+)[의\s]*(?:테스트\s*)?(?:step|스텝|단계)\s*(\d+)번?'
        match = re.search(single_pattern, query, re.IGNORECASE)
        if match:
            return TestCaseSearchParams(
                query=query,
                query_type="single",
                issue_key=match.group(1),
                step_number=int(match.group(2))
            )

        # Multiple 패턴
        multiple_pattern = r'(COMMONR-\d+)\s*(?:전체|모든|all|전부)'
        match = re.search(multiple_pattern, query, re.IGNORECASE)
        if match:
            return TestCaseSearchParams(
                query=query,
                query_type="multiple",
                issue_key=match.group(1)
            )

        # Feature (기본값)
        return TestCaseSearchParams(
            query=query,
            query_type="feature"
        )


def create_testcase_supervisor():
    """TestCase Supervisor Agent 생성 (직선형 파이프라인)

    Returns:
        CompiledGraph: TestCase Domain Supervisor
    """
    # Worker Agents 생성
    search_agent = create_testcase_search_agent()
    design_agent = create_testcase_design_agent()
    eval_agent = create_testcase_evaluator_agent()

    # 그래프 정의
    workflow = StateGraph(TestCaseState)

    # 노드 정의 (직선형 파이프라인)

    async def search_node(state: TestCaseState) -> TestCaseState:
        """Worker Agent: 테스트케이스 검색"""
        messages = state["messages"]

        # 검색 시작 메시지
        start_msg = HumanMessage(content="[TestCase - Search] 🔍 테스트케이스 검색 시작...")

        try:
            # 사용자 메시지 추출
            user_query = messages[0].content if messages else ""

            # 쿼리 파싱 (LLM 사용 - 비동기)
            search_params = await _parse_testcase_query(user_query)

            # 파싱 정보 로그
            parse_log_msg = HumanMessage(
                content=f"[TestCase - Search] 📝 파싱 결과:\n"
                        f"  - 쿼리: {search_params.query}\n"
                        f"  - 타입: {search_params.query_type}\n"
                        f"  - Issue Key: {search_params.issue_key}\n"
                        f"  - Step: {search_params.step_number}"
            )

            # search_agent 실행 (파라미터 직접 전달, 비동기)
            result = await search_agent(search_params)

            # 마지막 AI 메시지 추출
            last_message = result["messages"][-1]

            # 검색 결과 저장
            search_result = {
                "content": last_message.content,
                "success": "error" not in last_message.content.lower() and "cancelled" not in last_message.content.lower()
            }

            # 검색 완료 메시지
            completion_msg = HumanMessage(
                content=f"[TestCase - Search] {'✅ 검색 성공' if search_result['success'] else '❌ 검색 실패'} → Design로 진행"
            )

            return {
                "messages": [start_msg, parse_log_msg, last_message, completion_msg],
                "search_result": search_result
            }

        except Exception as e:
            # 예외 발생 시 (CancelledError 포함)
            error_msg = HumanMessage(
                content=f"[TestCase - Search] ❌ 검색 중 오류 발생: {type(e).__name__}\n상세: {str(e)}"
            )

            search_result = {
                "content": f"검색 실패: {str(e)}",
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }

            return {
                "messages": [start_msg, error_msg],
                "search_result": search_result
            }

    async def design_node(state: TestCaseState) -> TestCaseState:
        """Worker Agent: 테스트케이스 상세 분석 + 구현 설계"""
        messages = state["messages"]
        search_result = state.get("search_result", {})

        # 설계 시작 메시지
        start_msg = HumanMessage(content="[TestCase - Design] 📐 상세 분석 및 설계 시작...")

        # 검색 결과를 포함한 메시지 생성
        design_messages = messages + [
            HumanMessage(content=f"""다음 테스트케이스를 상세히 분석하고 구현 설계도를 작성해주세요.

테스트케이스:
{search_result.get('content', '')}

위 테스트케이스의:
1. 상세 분석 (목적, 시나리오, 사용 기능, 검증 포인트 등)
2. 클래스 공통 데이터 정의
3. 메서드별 구체적 설계 (전제조건, 실행 동작, 검증 대상, 예상 결과)
4. 테스트 커버리지 평가

모두를 포함하여 작성하세요.""")
        ]

        # design_agent 실행 (비동기)
        result = await design_agent.ainvoke({"messages": design_messages})

        # 마지막 AI 메시지 추출
        last_message = result["messages"][-1]

        # 설계 결과 저장
        design_plan = last_message.content

        # 설계 완료 메시지
        completion_msg = HumanMessage(content="[TestCase - Design] ✅ 설계 완료 → Evaluate로 진행")

        return {
            "messages": [start_msg, last_message, completion_msg],
            "design_plan": design_plan
        }

    async def evaluate_node(state: TestCaseState) -> TestCaseState:
        """Worker Agent: 설계도 품질 평가"""
        messages = state["messages"]
        design_plan = state.get("design_plan", "")

        # 평가 시작 메시지
        start_msg = HumanMessage(content="[TestCase - Evaluate] 📊 설계도 품질 평가 시작...")

        # 설계도 평가 메시지 생성
        eval_messages = messages + [
            HumanMessage(content=f"다음 구현 설계도의 품질을 평가해주세요.\n\n{design_plan}")
        ]

        # eval_agent 실행 (비동기)
        result = await eval_agent.ainvoke({"messages": eval_messages})

        # 마지막 AI 메시지 추출
        last_message = result["messages"][-1]

        # 평가 결과 저장 (정규식으로 정확하게 파싱)
        import re
        verdict_match = re.search(r'\b(PASS|NEEDS_IMPROVEMENT)\b', last_message.content, re.IGNORECASE)
        verdict = verdict_match.group(1).upper() if verdict_match else "NEEDS_IMPROVEMENT"

        evaluation = {
            "content": last_message.content,
            "verdict": verdict
        }

        # 평가 완료 메시지
        completion_msg = HumanMessage(
            content=f"[TestCase - Evaluate] ✅ 평가 완료: {evaluation['verdict']}"
        )

        # 최종 출력 생성
        final_output = f"""
TestCase 작업 완료

검색 결과:
{state.get('search_result', {}).get('content', 'N/A')}

설계 계획:
{design_plan}

평가 결과:
{evaluation['content']}
"""

        return {
            "messages": [start_msg, last_message, completion_msg],
            "evaluation": evaluation,
            "final_output": final_output
        }

    # 노드 추가
    workflow.add_node("search", search_node)
    workflow.add_node("design", design_node)
    workflow.add_node("evaluate", evaluate_node)

    # 엣지 연결 (직선형 파이프라인: search → design → evaluate)
    workflow.set_entry_point("search")
    workflow.add_edge("search", "design")
    workflow.add_edge("design", "evaluate")
    workflow.add_edge("evaluate", END)

    # 그래프 컴파일
    return workflow.compile()
