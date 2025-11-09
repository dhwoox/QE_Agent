"""
QE Agent v3 - Hierarchical Multi-Agent System

변경 사항:
- v2 Single ReAct Agent → v3 3-Layer Hierarchical Multi-Agent
- Layer 1: Supervisor Agent (도메인 라우팅)
- Layer 2: Domain Supervisors (TestCase, Resource)
- Layer 3: Worker Agents (create_react_agent)
"""

import os
from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver

from src.agents.supervisor_agent import create_supervisor_agent
from src.config import get_checkpoint_path, initialize_vectorstore

# 작업 디렉토리를 extracted_code_snippets로 변경
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE_ROOT = os.path.dirname(REPO_ROOT)
os.chdir(WORKSPACE_ROOT)

# 환경변수 로드
load_dotenv()

# VectorStore 초기화 (캐싱)
try:
    initialize_vectorstore()
except Exception as e:
    print(f"⚠️  VectorStore 초기화 실패 (계속 진행): {e}")

# Checkpoint 생성 (SQLite)
checkpoint_path = get_checkpoint_path()
checkpoint_conn = SqliteSaver.from_conn_string(checkpoint_path)

# Supervisor Agent 생성 (v3 Hierarchical System)
graph = create_supervisor_agent()

if __name__ == "__main__":
    print("=" * 70)
    print("QE Agent v3 - Hierarchical Multi-Agent System")
    print("=" * 70)
    print(f"작업 디렉토리: {os.getcwd()}")
    print(f"Checkpoint: {checkpoint_path}")
    print()
    print("아키텍처:")
    print("  Layer 1: Supervisor Agent (도메인 라우팅)")
    print("  Layer 2: Domain Supervisors (TestCase, Resource)")
    print("  Layer 3: Worker Agents (create_react_agent)")
    print()
    print("명령어:")
    print("  /clear - 대화 초기화")
    print("  /exit  - 종료")
    print("=" * 70)
    print()

    # 대화형 모드
    thread_id = "cli-session"
    config = {"configurable": {"thread_id": thread_id}}

    while True:
        try:
            # 사용자 입력
            user_input = input("You: ").strip()

            if not user_input:
                continue

            # 명령어 처리
            if user_input == "/exit":
                print("종료합니다.")
                break

            if user_input == "/clear":
                # 새 thread로 시작
                import time
                thread_id = f"cli-session-{int(time.time())}"
                config = {"configurable": {"thread_id": thread_id}}
                print("대화가 초기화되었습니다.")
                continue

            # Supervisor Agent 실행
            print()
            print("[System] 실행 과정을 실시간으로 표시합니다...")
            print("=" * 70)
            print()

            try:
                input_data = {
                    "messages": [("user", user_input)],
                    "next_supervisor": None,
                    "testcase_retry_count": 0,
                    "resource_retry_count": 0,
                    "generate_retry_count": 0,
                    "testcase_result": None,
                    "resource_result": None,
                    "generate_result": None,
                    "final_output": None
                }

                # stream with subgraphs=True로 중첩 그래프 가시화
                final_result = None
                for chunk in graph.stream(
                    input_data,
                    config,
                    subgraphs=True,
                    stream_mode="updates"
                ):
                    # messages 출력
                    for node_name, node_output in chunk.items():
                        if node_name == "__metadata__":
                            continue

                        # messages 출력
                        if "messages" in node_output:
                            for msg in node_output["messages"]:
                                print(f"{msg.content}")

                        # 최종 결과 저장
                        if "final_output" in node_output and node_output["final_output"]:
                            final_result = node_output

                # 최종 결과 출력
                print()
                print("=" * 70)
                if final_result and "final_output" in final_result:
                    print("최종 결과:")
                    print("=" * 70)
                    print(final_result["final_output"])
                    print("=" * 70)
                else:
                    print("결과가 없습니다.")
                    print("=" * 70)

                print()

            except Exception as e:
                print(f"⚠️  실행 중 오류 발생: {e}")
                import traceback
                traceback.print_exc()
                print()

        except KeyboardInterrupt:
            print("\n\n종료합니다.")
            break
        except Exception as e:
            print(f"\n오류 발생: {e}")
            print()
