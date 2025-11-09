"""
Layer 3: TestCase Search Agent

ChromaDB VectorStore에서 테스트케이스를 검색하는 Worker Agent
- 단순 검색 함수 (LLM 없음)
- 파라미터를 받아 VectorDB 검색만 수행
"""

from langchain_core.messages import HumanMessage, AIMessage

from ...tools.testcase_tools import search_testcase_vectordb
from ...tools.tool_models import TestCaseSearchParams


def create_testcase_search_agent():
    """테스트케이스 검색 Agent 생성

    Returns:
        function: 파라미터를 받아 검색 결과를 반환하는 함수
    """

    async def search_function(params: TestCaseSearchParams) -> dict:
        """TestCaseSearchParams를 받아 VectorDB 검색 수행

        Args:
            params: 검색 파라미터 (issue_key, step_number, query_type 등)

        Returns:
            dict: messages 키를 포함한 결과 딕셔너리
        """
        # VectorDB 검색 도구 호출 (비동기) - Pydantic 객체를 dict로 변환
        search_result = await search_testcase_vectordb.ainvoke({"params": params})

        # 검색 결과를 포맷팅
        if search_result.get("status") == "success" and search_result.get("count", 0) > 0:
            # 성공 시 결과 포맷팅
            results = search_result.get("results", [])
            formatted_output = f"검색 성공! {len(results)}개의 테스트케이스를 찾았습니다.\n\n"

            for idx, item in enumerate(results, 1):
                formatted_output += f"--- 결과 {idx} ---\n"
                formatted_output += f"Issue Key: {item.get('issue_key')}\n"
                formatted_output += f"Step: {item.get('step_index')}\n"
                formatted_output += f"Summary: {item.get('summary')}\n"
                formatted_output += f"Score: {item.get('score'):.4f}\n"
                formatted_output += f"Content:\n{item.get('content')}\n\n"

            return {
                "messages": [AIMessage(content=formatted_output)]
            }
        elif search_result.get("status") == "success" and search_result.get("count", 0) == 0:
            # 결과 없음
            return {
                "messages": [AIMessage(content=f"검색 결과가 없습니다.\n쿼리: {params.query}\n타입: {params.query_type}")]
            }
        else:
            # 오류 발생
            error_msg = search_result.get("error", "Unknown error")
            return {
                "messages": [AIMessage(content=f"검색 중 오류 발생: {error_msg}")]
            }

    return search_function
