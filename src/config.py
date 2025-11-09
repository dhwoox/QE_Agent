"""QE Agent 설정 및 LM Studio 연동"""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from typing import Optional

# 환경변수 로드
load_dotenv()

# 전역 VectorStore 캐시 (싱글톤)
_VECTORSTORE_CACHE: Optional[object] = None


def initialize_vectorstore():
    """VectorStore 초기화 및 캐싱

    애플리케이션 시작 시 한 번만 호출하여 임베딩 모델과 VectorStore를 초기화합니다.
    이후 get_vectorstore()를 통해 캐시된 인스턴스를 재사용합니다.

    Returns:
        Chroma VectorStore 인스턴스

    Note:
        - 이미 초기화된 경우 기존 캐시를 반환
        - 임베딩 모델: intfloat/multilingual-e5-large
        - DB 경로: testcase_rag/testcase_vectordb
    """
    global _VECTORSTORE_CACHE

    # 이미 초기화된 경우 캐시 반환
    if _VECTORSTORE_CACHE is not None:
        return _VECTORSTORE_CACHE

    try:
        from chromadb import PersistentClient
        from langchain_huggingface import HuggingFaceEmbeddings
        from langchain_chroma import Chroma

        # VectorStore 경로 설정 (프로젝트 루트 기준)
        vectorstore_path = os.path.join(
            os.getcwd(),  # extracted_code_snippets
            "testcase_rag",
            "testcase_vectordb"
        )

        # 경로 확인
        if not os.path.exists(vectorstore_path):
            raise FileNotFoundError(f"VectorStore 경로가 존재하지 않습니다: {vectorstore_path}")

        # 임베딩 모델 초기화
        embeddings = HuggingFaceEmbeddings(
            model_name="intfloat/multilingual-e5-large",
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True}
        )

        # ChromaDB 클라이언트 초기화
        chroma_client = PersistentClient(path=vectorstore_path)

        # VectorStore 초기화
        vectorstore = Chroma(
            client=chroma_client,
            collection_name="testcase_vectordb",
            embedding_function=embeddings
        )

        # 캐시에 저장
        _VECTORSTORE_CACHE = vectorstore

        print(f"✅ VectorStore 초기화 완료: {vectorstore_path}")
        return vectorstore

    except Exception as e:
        print(f"❌ VectorStore 초기화 실패: {e}")
        raise


def get_vectorstore():
    """캐시된 VectorStore 인스턴스 반환

    Returns:
        Chroma VectorStore 인스턴스

    Raises:
        RuntimeError: VectorStore가 초기화되지 않은 경우

    Note:
        사용 전 반드시 initialize_vectorstore()를 먼저 호출해야 합니다.
    """
    global _VECTORSTORE_CACHE

    if _VECTORSTORE_CACHE is None:
        raise RuntimeError(
            "VectorStore가 초기화되지 않았습니다. "
            "먼저 initialize_vectorstore()를 호출하세요."
        )

    return _VECTORSTORE_CACHE


def create_llm(temperature: float = None) -> ChatOpenAI:
    """LM Studio 연결 LLM 생성

    LM Studio의 OpenAI 호환 API를 사용하여 LLM을 생성합니다.

    Args:
        temperature: 생성 온도 (0.0-1.0)
                    None이면 환경변수의 TEMPERATURE_DEFAULT 사용

    Returns:
        ChatOpenAI 인스턴스 (LM Studio 연결)

    Examples:
        >>> llm = create_llm(temperature=0.1)  # 코드 생성용 (정확성)
        >>> llm = create_llm(temperature=0.7)  # 검색/분석용 (다양성)
    """
    if temperature is None:
        temperature = float(os.getenv("TEMPERATURE_DEFAULT", "0.5"))

    return ChatOpenAI(
        base_url=os.getenv("OPENAI_API_BASE_URL", "http://localhost:1234/v1"),
        api_key=os.getenv("OPENAI_API_KEY", "lm-studio"),
        model=os.getenv("MODEL_NAME", "qwen/qwen3-4b-thinking-2507"),
        temperature=temperature
    )


def get_checkpoint_path() -> str:
    """체크포인트 파일 경로 반환

    Returns:
        SQLite 체크포인트 파일 경로
    """
    return os.getenv("CHECKPOINT_PATH", "checkpoints/checkpoints.db")


# 사전 정의된 온도 설정
TEMPERATURE_CONFIG = {
    "code": float(os.getenv("TEMPERATURE_CODE", "0.1")),      # 코드 생성용 (정확성)
    "search": float(os.getenv("TEMPERATURE_SEARCH", "0.7")),  # 검색/분석용 (다양성)
    "default": float(os.getenv("TEMPERATURE_DEFAULT", "0.5")) # 기본값
}


def create_llm_for_task(task_type: str = "default") -> ChatOpenAI:
    """작업 유형에 맞는 LLM 생성

    Args:
        task_type: 작업 유형 ("code", "search", "default")

    Returns:
        해당 작업에 최적화된 ChatOpenAI 인스턴스

    Examples:
        >>> code_llm = create_llm_for_task("code")
        >>> search_llm = create_llm_for_task("search")
    """
    temperature = TEMPERATURE_CONFIG.get(task_type, TEMPERATURE_CONFIG["default"])
    return create_llm(temperature)
