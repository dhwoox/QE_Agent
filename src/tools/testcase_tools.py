"""
테스트케이스 검색 Tools

ChromaDB VectorStore를 사용한 테스트케이스 검색 도구
- 단일 테스트케이스 검색
- 다중 테스트케이스 검색 (이슈 키 기반)
- 기능 기반 검색
"""

from langchain_core.tools import tool
from typing import Dict, Any, List
import asyncio

from .tool_models import TestCaseSearchParams
from ..config import get_vectorstore


@tool
async def search_testcase_vectordb(params: TestCaseSearchParams) -> Dict[str, Any]:
    """
    ChromaDB VectorStore에서 테스트케이스 검색

    역할: 쿼리에 따라 관련 테스트케이스를 검색
    추론: 없음 (검색 실행만 수행)

    Args:
        params: 검색 파라미터
            - query: 검색 쿼리
            - query_type: "single" (단일), "multiple" (다중), "feature" (기능 기반)
            - issue_key: JIRA 이슈 키 (예: "COMMONR-30")
            - step_number: 스텝 번호 (single 타입에서 필요)
            - top_k: 최대 결과 수
            - score_threshold: 최소 유사도 점수

    Returns:
        Dict[str, Any]: 검색 결과
            - status: "success" | "error"
            - results: List[Dict] 검색된 테스트케이스 목록
            - count: 결과 개수
            - error: 오류 메시지 (실패 시)

    Examples:
        # 단일 테스트케이스
        search_testcase_vectordb(
            query="COMMONR-30 테스트 스텝 4번",
            query_type="single",
            issue_key="COMMONR-30",
            step_number=4
        )

        # 다중 테스트케이스
        search_testcase_vectordb(
            query="COMMONR-30 모든 스텝",
            query_type="multiple",
            issue_key="COMMONR-30"
        )

        # 기능 기반 검색
        search_testcase_vectordb(
            query="인증-지문 관련 테스트케이스",
            query_type="feature"
        )
    """
    try:
        # 캐시된 VectorStore 가져오기
        vectorstore = get_vectorstore()

        # 검색 쿼리 구성 (query_type에 따라)
        search_query = params.query
        filter_dict = None

        if params.query_type == "single":
            # 단일 테스트케이스: issue_key + step_index (ChromaDB $and 구문)
            filter_dict = {
                "$and": [
                    {"issue_key": {"$eq": params.issue_key}},
                    {"step_index": {"$eq": str(params.step_number)}}
                ]
            }
            search_query = f"{params.issue_key} step {params.step_number}"

        elif params.query_type == "multiple":
            # 다중 테스트케이스: issue_key만
            filter_dict = {
                "issue_key": {"$eq": params.issue_key}
            }
            search_query = params.issue_key

        elif params.query_type == "feature":
            # 기능 기반: 쿼리만 사용 (필터 없음)
            filter_dict = None
            search_query = params.query

        # 유사도 검색 수행 (비동기로 래핑)
        if filter_dict:
            # 필터 적용 검색
            docs_and_scores = await asyncio.to_thread(
                vectorstore.similarity_search_with_score,
                query=search_query,
                k=params.top_k,
                filter=filter_dict
            )
        else:
            # 일반 검색
            docs_and_scores = await asyncio.to_thread(
                vectorstore.similarity_search_with_score,
                query=search_query,
                k=params.top_k
            )

        # 결과 처리
        results = []
        for doc, score in docs_and_scores:
            # score_threshold 적용
            if score < params.score_threshold:
                continue

            result_item = {
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": float(score),
                "issue_key": doc.metadata.get("issue_key", "N/A"),
                "step_index": doc.metadata.get("step_index", "N/A"),
                "summary": doc.metadata.get("summary", "N/A")
            }
            results.append(result_item)

        return {
            "status": "success",
            "results": results,
            "count": len(results),
            "query_type": params.query_type,
            "search_query": search_query,
            "filter": filter_dict
        }

    except asyncio.CancelledError:
        # 비동기 취소 발생 시
        return {
            "status": "cancelled",
            "error": "검색 작업이 취소되었습니다. (Timeout 또는 시스템 중단)",
            "error_type": "CancelledError",
            "results": [],
            "count": 0,
            "query": params.query,
            "query_type": params.query_type
        }
    except Exception as e:
        # 오류 발생 시 구조화된 오류 반환
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__,
            "results": [],
            "count": 0,
            "query": params.query,
            "query_type": params.query_type
        }
