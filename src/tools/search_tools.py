"""
타입 안전한 검색 도구 (Pydantic 기반)

Tool의 역할:
- 실행만 담당 (추론 없음)
- 타입 검증
- 오류 처리
- 구조화된 결과 반환
"""

from langchain_core.tools import tool
from pathlib import Path
from glob import glob as python_glob
import subprocess
import shutil
from typing import List, Dict, Any
from .tool_models import (
    GlobParams,
    ReadFileParams,
    GrepParams,
    AnalyzeStructureParams,
    BashParams
)


@tool
def glob(params: GlobParams) -> Dict[str, Any]:
    """
    파일 패턴 검색

    Args:
        params: GlobParams 객체

    Returns:
        dict: {
            "status": "success" | "error",
            "files": List[str],
            "count": int,
            "error": str (오류 시)
        }
    """
    try:
        # 패턴 구성
        pattern = params.pattern
        if params.file_type and not pattern.endswith(f".{params.file_type}"):
            pattern = f"*.{params.file_type}"

        # Glob 검색
        search_path = Path(params.path)
        results = python_glob(f"{search_path}/**/{pattern}", recursive=True)

        # 존재하는 항목만 필터링
        items = [str(Path(r).resolve()) for r in results if Path(r).exists()]

        # 정렬
        items.sort()

        # Pagination
        paginated_items = items[params.offset:params.offset + params.head_limit]

        return {
            "status": "success",
            "files": paginated_items,
            "count": len(paginated_items),
            "total": len(items)
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }


@tool
def read_file(params: ReadFileParams) -> Dict[str, Any]:
    """
    파일 내용 읽기

    Args:
        params: ReadFileParams 객체

    Returns:
        dict: {
            "status": "success" | "error",
            "content": str,
            "lines_read": int,
            "error": str (오류 시)
        }
    """
    try:
        with open(params.file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Offset + limit 적용
        end_line = params.offset + params.limit if params.limit else len(lines)
        selected_lines = lines[params.offset:end_line]

        # 라인 번호 포함 여부
        if params.show_line_numbers:
            content = ""
            for i, line in enumerate(selected_lines, start=params.offset + 1):
                content += f"{i:6d}\t{line}"
        else:
            content = "".join(selected_lines)

        return {
            "status": "success",
            "content": content,
            "lines_read": len(selected_lines),
            "total_lines": len(lines)
        }

    except FileNotFoundError as e:
        return {
            "status": "error",
            "error": f"파일을 찾을 수 없습니다: {params.file_path}",
            "error_type": "FileNotFoundError"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }


@tool
def grep(params: GrepParams) -> Dict[str, Any]:
    """
    파일 내용 검색 (ripgrep 기반)

    Args:
        params: GrepParams 객체

    Returns:
        dict: {
            "status": "success" | "error",
            "matches": List[str] | List[Dict],
            "count": int,
            "error": str (오류 시)
        }
    """
    try:
        # ripgrep 확인
        rg_path = shutil.which("rg")
        if not rg_path:
            return {
                "status": "error",
                "error": "ripgrep이 설치되지 않았습니다. 'brew install ripgrep' 실행 필요",
                "error_type": "CommandNotFound"
            }

        # 명령어 구성
        cmd = [rg_path]

        # 옵션 추가
        if params.case_insensitive:
            cmd.append("-i")

        if params.context > 0:
            cmd.extend(["-C", str(params.context)])

        if params.glob_pattern:
            cmd.extend(["--glob", params.glob_pattern])

        if params.file_type:
            cmd.extend(["-t", params.file_type])

        # 출력 모드
        if params.output_mode == "files_with_matches":
            cmd.append("-l")
        elif params.output_mode == "count":
            cmd.append("-c")
        else:  # content
            cmd.append("-n")  # 라인 번호 포함

        # 패턴 및 경로
        cmd.append(params.pattern)
        cmd.append(params.path)

        # 실행
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        # 결과 파싱
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            lines = lines[:params.head_limit]

            return {
                "status": "success",
                "matches": lines,
                "count": len(lines)
            }
        elif result.returncode == 1:
            # 매칭 없음
            return {
                "status": "success",
                "matches": [],
                "count": 0
            }
        else:
            return {
                "status": "error",
                "error": result.stderr,
                "error_type": "CommandError"
            }

    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "error": "검색 시간 초과 (30초)",
            "error_type": "TimeoutError"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }


@tool
def analyze_structure(params: AnalyzeStructureParams) -> Dict[str, Any]:
    """
    디렉토리 구조 분석

    Args:
        params: AnalyzeStructureParams 객체

    Returns:
        dict: {
            "status": "success" | "error",
            "file_count": int,
            "dir_count": int,
            "extensions": Dict[str, int],
            "subdirectories": List[str],
            "error": str (오류 시)
        }
    """
    try:
        directory = Path(params.directory)

        file_count = 0
        dir_count = 0
        extensions = {}
        subdirectories = []

        # 디렉토리 탐색
        for item in directory.rglob("*"):
            # 숨김 파일 제외 (설정에 따라)
            if not params.include_hidden and any(part.startswith(".") for part in item.parts):
                continue

            # 깊이 체크
            depth = len(item.relative_to(directory).parts)
            if depth > params.max_depth:
                continue

            if item.is_file():
                file_count += 1
                ext = item.suffix.lower()
                extensions[ext] = extensions.get(ext, 0) + 1
            elif item.is_dir():
                dir_count += 1
                if depth == 1:
                    subdirectories.append(item.name)

        return {
            "status": "success",
            "file_count": file_count,
            "dir_count": dir_count,
            "extensions": dict(sorted(extensions.items(), key=lambda x: x[1], reverse=True)[:10]),
            "subdirectories": sorted(subdirectories)
        }

    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }


@tool
def bash(params: BashParams) -> Dict[str, Any]:
    """
    Bash 명령어 실행

    Args:
        params: BashParams 객체

    Returns:
        dict: {
            "status": "success" | "error",
            "stdout": str,
            "stderr": str,
            "returncode": int,
            "error": str (오류 시)
        }
    """
    try:
        result = subprocess.run(
            params.command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=params.timeout
        )

        return {
            "status": "success" if result.returncode == 0 else "error",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode
        }

    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "error": f"명령어 실행 시간 초과 ({params.timeout}초)\n명령어: {params.command}",
            "error_type": "TimeoutError"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }
