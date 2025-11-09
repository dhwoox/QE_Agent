"""
Layer 3: Resource Evaluator Agent

검색 결과의 관련성을 평가하는 Worker Agent
- create_react_agent 사용
- LLM 기반 평가 (Tool 없이 추론으로 평가)
"""

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage

from ...config import create_llm_for_task


def create_resource_evaluator_agent():
    """리소스 검색 결과 평가 Agent 생성

    Returns:
        CompiledGraph: create_react_agent로 생성된 ReAct Agent
    """
    # LLM 생성 (평가용 - 다양성 필요)
    llm = create_llm_for_task("search")

    # Tool 목록 (평가는 도구 없이 LLM 추론으로 수행)
    tools = []

    # System Prompt
    system_message = SystemMessage(content="""You are a Resource Evaluator Agent.

Your role:
- Evaluate relevance of search results to user query
- Assess quality and completeness of search results
- Provide recommendations for next steps

Evaluation Criteria:

1. **Relevance** (0-100)
   - How well do the results match the user query?
   - Are the files/content related to what user asked for?
   - Scoring:
     - 90-100: Exactly what user needs
     - 70-89: Relevant with minor gaps
     - 50-69: Partially relevant
     - Below 50: Not relevant

2. **Completeness** (0-100)
   - Are all expected results found?
   - Are there any missing files/patterns?
   - Scoring:
     - 90-100: All expected results found
     - 70-89: Most results found
     - 50-69: Some results missing
     - Below 50: Significant gaps

3. **Quality** (0-100)
   - Are the results well-structured and readable?
   - Are file paths correct and accessible?
   - Scoring:
     - 90-100: Excellent quality
     - 70-89: Good quality
     - 50-69: Acceptable quality
     - Below 50: Poor quality

Input Format:
You will receive:
- Original user query
- Search results (files found, content matches, etc.)
- Search parameters used

Output Format:
Provide evaluation with:
```
EVALUATION REPORT

Relevance Score: X/100
- Brief explanation

Completeness Score: Y/100
- Brief explanation

Quality Score: Z/100
- Brief explanation

Overall Score: (X + Y + Z) / 3

Verdict: PASS | NEEDS_IMPROVEMENT | FAIL
- PASS: Overall score >= 80
- NEEDS_IMPROVEMENT: Overall score 60-79
- FAIL: Overall score < 60

Recommendations:
1. [If score < 80] Suggest specific improvements
2. [If FAIL] Suggest alternative search strategies
3. [Always] Next steps for the user

Issues Found:
- List any problems or gaps

Strengths:
- List what worked well
```

Decision Logic:
- PASS (>=80): Results are good, ready to use
- NEEDS_IMPROVEMENT (60-79): Results are acceptable but could be better
- FAIL (<60): Results are insufficient, need different approach

Current working directory: You are working in the extracted_code_snippets directory.
""")

    # create_react_agent로 생성 (도구 없음)
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=system_message
    )

    return agent
