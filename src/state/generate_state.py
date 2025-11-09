"""
Layer 2: Generate Domain State

Generate Supervisor Agent의 상태 정의
- 자동화 코드 생성 → 파일 작성 → 검증
"""

from typing import TypedDict, Annotated, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class GenerateState(TypedDict):
    """Generate Domain Supervisor 상태"""

    # 메시지 히스토리
    messages: Annotated[list[BaseMessage], add_messages]

    # 다음 실행할 Worker Agent ("generate" | "write" | "validate" | "END")
    next_agent: str

    # 각 Worker Agent 결과
    generated_code: Optional[str]      # code_generator_agent 결과
    file_path: Optional[str]           # file_writer_agent 결과
    validation: Optional[dict]         # validator_agent 결과

    # 최종 출력
    final_output: Optional[str]
