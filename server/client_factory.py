from typing import List, Dict
from openai import OpenAI
from .config import settings

def get_client() -> OpenAI:
    """
    USE_LOCAL_LLM=true 면 LOCAL_LLM_BASE_URL 로 연결된 OpenAI 호환 서버를 사용.
    아니면 공식 OpenAI API 사용.
    """
    if settings.USE_LOCAL_LLM:
        return OpenAI(
            base_url=settings.LOCAL_LLM_BASE_URL,
            api_key=settings.LOCAL_LLM_API_KEY,  # 더미 허용
        )
    else:
        return OpenAI(api_key=settings.OPENAI_API_KEY)

def chat_completion(messages: List[Dict], temperature: float | None = None, max_tokens: int | None = None, model: str | None = None):
    client = get_client()

    use_model = model or (settings.LOCAL_LLM_MODEL if settings.USE_LOCAL_LLM else "gpt-4o-mini")
    use_temp = temperature if temperature is not None else (settings.LOCAL_LLM_TEMPERATURE if settings.USE_LOCAL_LLM else 0.2)
    use_max = max_tokens if max_tokens is not None else (settings.LOCAL_LLM_MAX_TOKENS if settings.USE_LOCAL_LLM else 2000)

    return client.chat.completions.create(
        model=use_model,
        messages=messages,
        temperature=use_temp,
        max_tokens=use_max,
    )
