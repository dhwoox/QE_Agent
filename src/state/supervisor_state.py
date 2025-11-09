"""
Layer 1: Supervisor Agent State

최상위 Supervisor Agent의 상태 정의
- CEO 역할: 각 본부(Domain) 결과 검토 및 승인/반려
- 루프백 가능: 결과 불만족 시 재실행 지시
"""

from typing import TypedDict, Annotated, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class SupervisorState(TypedDict):
    """최상위 Supervisor Agent 상태 (CEO 역할)"""

    # 메시지 히스토리
    messages: Annotated[list[BaseMessage], add_messages]

    # 다음 실행할 도메인 ("testcase" | "evaluate_testcase" | "resource" | "evaluate_resource" | "generate" | "evaluate_generate" | "END")
    next_supervisor: str

    # 재시도 카운터 (무한 루프 방지)
    testcase_retry_count: int
    resource_retry_count: int
    generate_retry_count: int

    # 각 도메인 결과
    testcase_result: Optional[dict]
    resource_result: Optional[dict]
    generate_result: Optional[dict]

    # 최종 출력
    final_output: Optional[str]
