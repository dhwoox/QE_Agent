"""
Layer 2: Resource Domain State

Resource Supervisor Agent의 상태 정의
- 파일 탐색 → 코드 검색 → 평가
"""

from typing import TypedDict, Annotated, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class ResourceState(TypedDict):
    """Resource Domain Supervisor 상태"""

    # 메시지 히스토리
    messages: Annotated[list[BaseMessage], add_messages]

    # 다음 실행할 Worker Agent ("find" | "search" | "evaluate" | "END")
    next_agent: str

    # 각 Worker Agent 결과
    find_result: Optional[dict]        # finder_agent 결과
    search_result: Optional[dict]      # searcher_agent 결과
    evaluation: Optional[dict]         # evaluator_agent 결과

    # 최종 출력
    final_output: Optional[str]
