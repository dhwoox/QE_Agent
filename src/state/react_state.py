"""
Agent State: ReAct 패턴을 위한 최소 상태

LangGraph Best Practice:
- 최소한의 상태만 유지
- 계산 가능한 값은 포함하지 않음
- 메시지만으로 충분
"""

from typing import Annotated, Sequence
from typing_extensions import TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    ReAct Agent의 상태

    메시지만 유지:
    - 사용자 입력
    - AI 응답
    - 도구 호출
    - 도구 결과

    add_messages 리듀서로 자동 병합
    """
    messages: Annotated[Sequence[BaseMessage], add_messages]
