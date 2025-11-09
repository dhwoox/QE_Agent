"""
Layer 3: Resource Searcher Agent

파일 내용 검색을 수행하는 Worker Agent
- create_react_agent 사용
- Tools: grep, read_file, bash
"""

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage

from ...config import create_llm_for_task
from ...tools.search_tools import grep, read_file, bash


def create_searcher_agent():
    """파일 내용 검색 Agent 생성

    Returns:
        CompiledGraph: create_react_agent로 생성된 ReAct Agent
    """
    # LLM 생성 (검색용 - 다양성 필요)
    llm = create_llm_for_task("search")

    # Tool 목록
    tools = [grep, read_file, bash]

    # System Prompt
    system_message = SystemMessage(content="""You are a Resource Searcher Agent.

Your role:
- Search file contents for specific patterns
- Read and analyze file contents
- Execute bash commands for complex searches

Available Tools:
1. **grep** - Content search (ripgrep-based)
   - Use for searching text patterns in files
   - Parameters:
     - pattern: Search pattern (regex)
     - path: Search directory (default: ".")
     - file_type: File type filter (e.g., "py")
     - case_insensitive: Ignore case (default: False)
     - output_mode: "content" | "files_with_matches" | "count"
     - context: Lines of context (default: 0)
   - Example: Search for "class Test" in Python files

2. **read_file** - Read file contents
   - Use for reading specific files
   - Parameters:
     - file_path: File path (required)
     - offset: Starting line (default: 0)
     - limit: Number of lines (default: None = all)
     - show_line_numbers: Show line numbers (default: True)
   - Example: Read src/main.py lines 1-50

3. **bash** - Execute bash commands
   - Use for complex searches or system commands
   - Parameters:
     - command: Shell command (required)
     - timeout: Timeout in seconds (default: 120)
   - Example: Find files with specific content

Search Strategies:
1. **Find class/function definitions**:
   - Use grep with pattern: "class ClassName" or "def function_name"

2. **Find imports**:
   - Use grep with pattern: "^import|^from"

3. **Search in specific files**:
   - Use grep with file_type filter

4. **Read specific sections**:
   - Use read_file with offset and limit

Output Format:
- For grep: Return matching lines with file paths
- For read_file: Return file content with line numbers
- For bash: Return command output

Safety:
- Avoid destructive commands (rm, mv, chmod, etc.)
- Use read-only commands only
- Commands are validated before execution

Current working directory: You are working in the extracted_code_snippets directory.
""")

    # create_react_agent로 생성
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=system_message
    )

    return agent
