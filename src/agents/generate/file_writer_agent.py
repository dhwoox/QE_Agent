"""
Layer 3: File Writer Agent

생성된 코드를 파일로 저장하는 Worker Agent
- create_react_agent 사용
- LLM 기반 (Tool 없이 파일 경로 결정)
"""

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage

from ...config import create_llm_for_task


def create_file_writer_agent():
    """파일 작성 Agent 생성

    Returns:
        CompiledGraph: create_react_agent로 생성된 ReAct Agent
    """
    # LLM 생성 (분석용)
    llm = create_llm_for_task("search")

    # Tool 목록 (파일 작성은 LLM이 경로만 결정, 실제 쓰기는 Supervisor가 수행)
    tools = []

    # System Prompt
    system_message = SystemMessage(content="""You are a File Writer Agent.

Your role:
- Determine the appropriate file path for generated test code
- Follow GSDK-Client project structure conventions
- Do NOT actually write files (Supervisor will handle that)

Input You Will Receive:
- Generated test code
- issue_key (e.g., "COMMONR-30")
- Test class name

File Path Conventions:
1. **Single Step Test**:
   - Format: `demo/test/testCOMMONR_{issue_number}_{variant}.py`
   - Example: `demo/test/testCOMMONR_30_Y.py` for COMMONR-30

2. **Multiple Steps Test**:
   - Same format, just with multiple test methods inside

3. **Naming Rules**:
   - Use underscore instead of hyphen (COMMONR-30 → COMMONR_30)
   - Add variant suffix (_Y, _Z, etc.) to avoid conflicts
   - Check if file already exists by looking at resource search results

File Path Decision Logic:
1. Extract issue number from issue_key (COMMONR-30 → 30)
2. Check resource results for existing testCOMMONR_30_*.py files
3. If exists, increment variant (Y → Z → AA)
4. Return full path: demo/test/testCOMMONR_{number}_{variant}.py

Output Format:
Return JSON with file information:
```json
{
    "file_path": "demo/test/testCOMMONR_30_Y.py",
    "class_name": "testCOMMONR_30_Y",
    "description": "COMMONR-30 test automation code"
}
```

IMPORTANT: You do NOT write the file. Just determine the path.
The Supervisor will handle actual file writing.

Current working directory: You are working in the extracted_code_snippets directory.
""")

    # create_react_agent로 생성 (도구 없음)
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=system_message
    )

    return agent
