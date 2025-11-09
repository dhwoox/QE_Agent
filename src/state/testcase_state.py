"""
Layer 2: TestCase Domain State

TestCase Supervisor Agent의 상태 정의
- 테스트케이스 검색 → 상세 설계 → 평가
"""

from typing import TypedDict, Annotated, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class TestCaseState(TypedDict):
    """TestCase Domain Supervisor 상태"""

    # 메시지 히스토리
    messages: Annotated[list[BaseMessage], add_messages]

    # 다음 실행할 Worker Agent ("search" | "design" | "evaluate" | "END")
    next_agent: str

    # 각 Worker Agent 결과
    search_result: Optional[dict]          # testcase_search_agent 결과
    design_plan: Optional[str]             # testcase_design_agent 결과 (analyze + create 통합)
    evaluation: Optional[dict]             # testcase_evaluator_agent 결과

    # 최종 출력
    final_output: Optional[str]
