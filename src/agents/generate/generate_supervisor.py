"""
Layer 2: Generate Supervisor Agent

Generate 도메인 작업을 조율하는 Supervisor
- Worker Agents 순차 실행: generate → write → validate (직선형 파이프라인)
"""

from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, END

from ...state.generate_state import GenerateState
from .code_generator_agent import create_code_generator_agent
from .file_writer_agent import create_file_writer_agent
from .validator_agent import create_code_validator_agent


def create_generate_supervisor():
    """Generate Supervisor Agent 생성 (직선형 파이프라인)

    Returns:
        CompiledGraph: Generate Domain Supervisor
    """
    # Worker Agents 생성
    generator_agent = create_code_generator_agent()
    writer_agent = create_file_writer_agent()
    validator_agent = create_code_validator_agent()

    # 그래프 정의
    workflow = StateGraph(GenerateState)

    # 노드 정의 (직선형 파이프라인)

    async def generate_node(state: GenerateState) -> GenerateState:
        """Worker Agent: 자동화 코드 생성"""
        messages = state["messages"]

        # 코드 생성 시작 메시지
        start_msg = HumanMessage(content="[Generate - Code] 💻 자동화 코드 생성 시작...")

        # generator_agent 실행 (비동기)
        result = await generator_agent.ainvoke({"messages": messages})

        # 마지막 AI 메시지 추출
        last_message = result["messages"][-1]

        # 생성된 코드 저장
        generated_code = last_message.content

        # 코드 생성 완료 메시지
        completion_msg = HumanMessage(content="[Generate - Code] ✅ 코드 생성 완료 → Write로 진행")

        return {
            "messages": [start_msg, last_message, completion_msg],
            "generated_code": generated_code
        }

    async def write_node(state: GenerateState) -> GenerateState:
        """Worker Agent: 파일 경로 결정"""
        messages = state["messages"]
        generated_code = state.get("generated_code", "")

        # 파일 경로 결정 시작 메시지
        start_msg = HumanMessage(content="[Generate - Write] 📝 파일 경로 결정 시작...")

        # 파일 경로 결정 메시지 생성
        write_messages = messages + [
            HumanMessage(content=f"다음 코드를 저장할 파일 경로를 결정해주세요.\n\n```python\n{generated_code}\n```")
        ]

        # writer_agent 실행 (비동기)
        result = await writer_agent.ainvoke({"messages": write_messages})

        # 마지막 AI 메시지 추출
        last_message = result["messages"][-1]

        # 파일 경로 추출 (간단히 메시지에서 추출, 실제로는 JSON 파싱)
        file_path = "demo/test/testCOMMONR_XX_Y.py"  # TODO: 실제 파싱 로직
        if "file_path" in last_message.content:
            # 간단한 추출 (실제로는 더 정교하게)
            import re
            match = re.search(r'"file_path":\s*"([^"]+)"', last_message.content)
            if match:
                file_path = match.group(1)

        # 파일 경로 결정 완료 메시지
        completion_msg = HumanMessage(content=f"[Generate - Write] ✅ 파일 경로 결정 완료: {file_path} → Validate로 진행")

        return {
            "messages": [start_msg, last_message, completion_msg],
            "file_path": file_path
        }

    async def validate_node(state: GenerateState) -> GenerateState:
        """Worker Agent: 코드 검증"""
        messages = state["messages"]
        generated_code = state.get("generated_code", "")
        file_path = state.get("file_path", "")

        # 코드 검증 시작 메시지
        start_msg = HumanMessage(content="[Generate - Validate] 📊 코드 검증 시작...")

        # 코드 검증 메시지 생성
        validate_messages = messages + [
            HumanMessage(content=f"다음 생성된 코드를 검증해주세요.\n\n```python\n{generated_code}\n```")
        ]

        # validator_agent 실행 (비동기)
        result = await validator_agent.ainvoke({"messages": validate_messages})

        # 마지막 AI 메시지 추출
        last_message = result["messages"][-1]

        # 검증 결과 저장
        validation = {
            "content": last_message.content,
            "verdict": "READY_TO_RUN" if "READY_TO_RUN" in last_message.content else "NEEDS_IMPROVEMENT"
        }

        # 검증 완료 메시지
        completion_msg = HumanMessage(
            content=f"[Generate - Validate] ✅ 검증 완료: {validation['verdict']}"
        )

        # 최종 출력 생성
        final_output = f"""
자동화 코드 생성 완료

생성된 코드:
```python
{generated_code}
```

파일 경로: {file_path}

검증 결과:
{validation['content']}

---
✅ 코드가 성공적으로 생성되었습니다!
파일: {file_path}
"""

        return {
            "messages": [start_msg, last_message, completion_msg],
            "validation": validation,
            "final_output": final_output
        }

    # 노드 추가
    workflow.add_node("generate", generate_node)
    workflow.add_node("write", write_node)
    workflow.add_node("validate", validate_node)

    # 엣지 연결 (직선형 파이프라인)
    workflow.set_entry_point("generate")
    workflow.add_edge("generate", "write")
    workflow.add_edge("write", "validate")
    workflow.add_edge("validate", END)

    # 그래프 컴파일
    return workflow.compile()
