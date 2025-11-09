"""
Tool Parameter Models

Pydantic 기반 타입 안전 파라미터 정의
- 검증 자동화
- 명확한 docstring
- IDE 자동완성 지원
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field, validator
import os


class GlobParams(BaseModel):
    """파일/폴더 패턴 검색 파라미터"""

    pattern: str = Field(
        ...,
        description="검색 패턴 (예: '*.py', 'test*', 'src/**/*.ts')",
        min_length=1
    )

    path: str = Field(
        default=".",
        description="검색할 디렉토리 경로"
    )

    file_type: Optional[str] = Field(
        default=None,
        description="파일 타입 필터 (예: 'py', 'js', 'json')"
    )

    head_limit: int = Field(
        default=100,
        description="최대 결과 수",
        ge=1,
        le=1000
    )

    offset: int = Field(
        default=0,
        description="건너뛸 결과 수",
        ge=0
    )

    @validator("path")
    def validate_path_exists(cls, v):
        """경로 존재 확인"""
        if not os.path.exists(v):
            raise ValueError(f"경로가 존재하지 않습니다: {v}")
        return v


class ReadFileParams(BaseModel):
    """파일 읽기 파라미터"""

    file_path: str = Field(
        ...,
        description="읽을 파일의 절대 또는 상대 경로"
    )

    offset: int = Field(
        default=0,
        description="시작 라인 번호 (0부터 시작)",
        ge=0
    )

    limit: Optional[int] = Field(
        default=None,
        description="읽을 라인 수 (None이면 전체)",
        ge=1
    )

    show_line_numbers: bool = Field(
        default=True,
        description="라인 번호 표시 여부"
    )

    @validator("file_path")
    def validate_file_exists(cls, v):
        """파일 존재 확인"""
        if not os.path.exists(v):
            raise FileNotFoundError(f"파일이 존재하지 않습니다: {v}")
        if not os.path.isfile(v):
            raise ValueError(f"파일이 아닙니다: {v}")
        return v


class GrepParams(BaseModel):
    """파일 내용 검색 파라미터"""

    pattern: str = Field(
        ...,
        description="검색할 정규식 패턴",
        min_length=1
    )

    path: str = Field(
        default=".",
        description="검색할 디렉토리 경로"
    )

    glob_pattern: Optional[str] = Field(
        default=None,
        description="파일 필터 패턴 (예: '*.py', '**/*.js')"
    )

    file_type: Optional[str] = Field(
        default=None,
        description="파일 타입 필터 (예: 'py', 'js')"
    )

    case_insensitive: bool = Field(
        default=False,
        description="대소문자 무시 여부"
    )

    context: int = Field(
        default=0,
        description="전후 컨텍스트 라인 수",
        ge=0,
        le=10
    )

    output_mode: Literal["content", "files_with_matches", "count"] = Field(
        default="files_with_matches",
        description="출력 모드: content(내용), files_with_matches(파일명), count(개수)"
    )

    head_limit: int = Field(
        default=100,
        description="최대 결과 수",
        ge=1,
        le=1000
    )

    @validator("path")
    def validate_path_exists(cls, v):
        """경로 존재 확인"""
        if not os.path.exists(v):
            raise ValueError(f"경로가 존재하지 않습니다: {v}")
        return v


class AnalyzeStructureParams(BaseModel):
    """디렉토리 구조 분석 파라미터"""

    directory: str = Field(
        default=".",
        description="분석할 디렉토리 경로"
    )

    max_depth: int = Field(
        default=3,
        description="최대 탐색 깊이",
        ge=1,
        le=10
    )

    include_hidden: bool = Field(
        default=False,
        description="숨김 파일/폴더 포함 여부"
    )

    @validator("directory")
    def validate_directory_exists(cls, v):
        """디렉토리 존재 확인"""
        if not os.path.exists(v):
            raise ValueError(f"디렉토리가 존재하지 않습니다: {v}")
        if not os.path.isdir(v):
            raise ValueError(f"디렉토리가 아닙니다: {v}")
        return v


class BashParams(BaseModel):
    """Bash 명령어 실행 파라미터"""

    command: str = Field(
        ...,
        description="실행할 Bash 명령어",
        min_length=1
    )

    timeout: int = Field(
        default=120,
        description="타임아웃 (초)",
        ge=1,
        le=600
    )

    @validator("command")
    def validate_safe_command(cls, v):
        """위험한 명령어 차단"""
        dangerous_keywords = [
            "rm -rf /",
            "mkfs",
            "dd if=",
            "> /dev/",
            ":(){ :|:& };:",  # Fork bomb
            "mv /* ",
            "chmod -R 777 /"
        ]

        for keyword in dangerous_keywords:
            if keyword in v:
                raise ValueError(f"위험한 명령어가 포함되어 있습니다: {keyword}")

        return v


class TestCaseSearchParams(BaseModel):
    """테스트케이스 VectorDB 검색 파라미터"""

    query: str = Field(
        ...,
        description="검색 쿼리 텍스트",
        min_length=1
    )

    query_type: Literal["single", "multiple", "feature"] = Field(
        ...,
        description="검색 타입: single(단일), multiple(다중), feature(기능 기반)"
    )

    issue_key: Optional[str] = Field(
        default=None,
        description="JIRA 이슈 키 (예: 'COMMONR-30')"
    )

    step_number: Optional[int] = Field(
        default=None,
        description="테스트 스텝 번호",
        ge=1
    )

    top_k: int = Field(
        default=5,
        description="최대 검색 결과 수",
        ge=1,
        le=50
    )

    score_threshold: float = Field(
        default=0.0,
        description="최소 유사도 점수 (0.0~1.0)",
        ge=0.0,
        le=1.0
    )

    @validator("issue_key")
    def validate_issue_key_format(cls, v, values):
        """issue_key 형식 검증"""
        if v is not None:
            query_type = values.get("query_type")
            if query_type in ["single", "multiple"] and not v:
                raise ValueError(f"{query_type} 타입은 issue_key가 필요합니다")
            # 간단한 형식 검증 (COMMONR-숫자)
            if v and not v.replace("-", "").replace("_", "").isalnum():
                raise ValueError(f"유효하지 않은 issue_key 형식: {v}")
        return v

    @validator("step_number")
    def validate_step_number(cls, v, values):
        """step_number 검증"""
        if v is not None:
            query_type = values.get("query_type")
            if query_type == "single" and v is None:
                raise ValueError("single 타입은 step_number가 필요합니다")
        return v
