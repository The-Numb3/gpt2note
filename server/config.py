import os
from dotenv import load_dotenv
from pydantic import BaseModel
load_dotenv()

class Settings(BaseModel):
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "AI Conversation Archiver")
    OBSIDIAN_VAULT_DIR: str = os.getenv("OBSIDIAN_VAULT_DIR", r"C:\KKM\obsidian\Vault")

    USE_LOCAL_LLM: bool = os.getenv("USE_LOCAL_LLM", "false").lower() == "true"
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")

    # Local LLM (OpenAI 호환 서버)
    LOCAL_LLM_BASE_URL: str = os.getenv("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")
    LOCAL_LLM_API_KEY: str = os.getenv("LOCAL_LLM_API_KEY", "ollama")
    LOCAL_LLM_MODEL: str = os.getenv("LOCAL_LLM_MODEL", "llama3.1:8b-instruct-q4_K_M")
    LOCAL_LLM_TEMPERATURE: float = float(os.getenv("LOCAL_LLM_TEMPERATURE", "0.2"))
    LOCAL_LLM_MAX_TOKENS: int = int(os.getenv("LOCAL_LLM_MAX_TOKENS", "1800"))

settings = Settings()
