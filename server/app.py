from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from datetime import datetime
import os
import json
import re
import httpx
from typing import List, Dict, Any, Tuple, Optional

app = FastAPI()

# === CORS (개발 중은 * 허용) ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # "*"와 함께 True는 브라우저에서 막힐 수 있음
    allow_methods=["*"],
    allow_headers=["*"],
)

# === 설정값 ===
# Obsidian Vault 경로
VAULT_PATH = Path(os.environ.get("OBSIDIAN_VAULT_DIR", r"C:/김강민/obsidian_vault/vineyard"))

# 로컬 LLM 사용여부/엔드포인트 (Ollama OpenAI-호환 /v1/chat/completions 권장)
USE_LOCAL_LLM = os.environ.get("USE_LOCAL_LLM", "true").lower() == "true"
LOCAL_LLM_BASE_URL = os.environ.get("LOCAL_LLM_BASE_URL", "http://localhost:11434/v1")  # Ollama 기본
LOCAL_LLM_MODEL = os.environ.get("LOCAL_LLM_MODEL", "llama3.1:8b-instruct-q4_K_M")
LOCAL_LLM_TEMPERATURE = float(os.environ.get("LOCAL_LLM_TEMPERATURE", "0.2"))
LOCAL_LLM_MAX_TOKENS = int(os.environ.get("LOCAL_LLM_MAX_TOKENS", "1600"))

# --- 유틸 ---
def slugify(s: str) -> str:
    s = re.sub(r"[^\w\s\-\.]", "", s, flags=re.UNICODE)
    s = re.sub(r"\s+", "_", s, flags=re.UNICODE)
    return s.strip("_")[:80] or "note"

def ensure_project_dir(project: str) -> Path:
    p = VAULT_PATH / project
    p.mkdir(parents=True, exist_ok=True)
    return p

def to_frontmatter(meta: Dict[str, Any]) -> str:
    return "---\n" + "\n".join(f'{k}: {json.dumps(v, ensure_ascii=False)}' for k, v in meta.items()) + "\n---\n"

def build_basic_markdown(project: str, conversation: List[Dict[str, str]]) -> str:
    md_conv = []
    for msg in conversation:
        role = "👤 User" if msg.get("role") == "user" else "🤖 Assistant"
        md_conv.append(f"### {role}\n{msg.get('content','')}\n")
    conv_md = "\n---\n".join(md_conv)
    return f"""# 📝 Chat Conversation Report
**프로젝트**: {project}  
**날짜**: {datetime.now().strftime('%Y-%m-%d')}  
**대화 길이**: {len(conversation)} turns  

---

## 💬 원본 대화 기록
{conv_md}
""".strip()

# --- 프롬프트 ---
SYSTEM_PROMPT = """당신은 대화 노트를 Obsidian에 저장하기 좋게 '요약/구조화/하이라이트'하는 어시스턴트입니다.
- 출력은 두 섹션으로 나누세요:
====JSON====
{...메타데이터 JSON...}
====MARKDOWN====
...정리된 마크다운...
- JSON은 반드시 유효한 JSON 객체여야 합니다.
- MARKDOWN은 Obsidian 친화적으로 #, ##, - 목록, ``` 코드블록 등을 활용하세요.
- 한국어로 작성하세요.
"""

USER_PROMPT_TEMPLATE = """다음 대화를 '프로젝트 노트'로 정리해 주세요.

요구사항:
1) 상단 '요약' (핵심 포인트 5줄 이내)
2) '배운 점 / 결론'
3) '약한 개념/오개념' 탐지 및 '학습 가이드'(링크 없이 키워드 리스트)
4) '다음 할 일'(체크박스 목록)
5) 원한다면 짧은 '태그' 제안 (예: #선형대수, #벡터)

대화:
{conversation_text}

출력 형식은 반드시 아래와 같이:
====JSON====
{{
  "title": "{title_hint}",
  "tags": ["ai", "notes"],
  "weak_topics": ["..."],
  "todo": ["..."]
}}
====MARKDOWN====
# {title_hint}
...본문...
"""

def conversation_to_plaintext(convo: List[Dict[str, str]], max_chars: int = 12000) -> str:
    lines = []
    total = 0
    for m in convo:
        role = m.get("role", "user")
        content = (m.get("content") or "").strip()
        line = f"[{role}] {content}"
        if total + len(line) > max_chars:
            break
        lines.append(line)
        total += len(line)
    return "\n".join(lines)

async def call_local_llm(conversation: List[Dict[str, str]], project: str) -> Tuple[Optional[Dict[str, Any]], Optional[str], str]:
    """
    로컬 LLM(OpenAI-호환 /v1/chat/completions) 호출 → (meta_json, markdown, raw_text)
    실패시 (None, None, raw_text)
    """
    title_hint = f"{project} - {datetime.now().strftime('%Y-%m-%d')}"
    convo_text = conversation_to_plaintext(conversation)

    user_prompt = USER_PROMPT_TEMPLATE.format(conversation_text=convo_text, title_hint=title_hint)

    payload = {
        "model": LOCAL_LLM_MODEL,
        "temperature": LOCAL_LLM_TEMPERATURE,
        "max_tokens": LOCAL_LLM_MAX_TOKENS,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ]
    }

    url = f"{LOCAL_LLM_BASE_URL}/chat/completions"  # Ollama OpenAI-compat 경로
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
            text = data["choices"][0]["message"]["content"]
    except Exception as e:
        # 실패하면 원본 마크다운만 사용하도록 raw 반환
        return None, None, f"[LLM 호출 실패] {e}"

    # 분리 파싱
    meta_json, md = None, None
    if "====JSON====" in text and "====MARKDOWN====" in text:
        try:
            parts = text.split("====JSON====", 1)[1]
            meta_part, md_part = parts.split("====MARKDOWN====", 1)
            meta_json = json.loads(meta_part.strip())
            md = md_part.strip()
        except Exception:
            # 파싱 실패 시 통으로 md 취급
            md = text.strip()
    else:
        md = text.strip()

    return meta_json, md, text

# --- 라우트 ---

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/api/conversation/analyze")
async def analyze_only(req: Request):
    """
    대화를 분석만 해서 meta + markdown을 반환 (저장은 안 함)
    """
    data = await req.json()
    project = data.get("project", "General")
    conversation = data.get("conversation", [])

    if USE_LOCAL_LLM:
        meta, md, raw = await call_local_llm(conversation, project)
    else:
        # 여기서 OpenAI 등 외부 API 분기 가능 (현재는 로컬만)
        meta, md, raw = await call_local_llm(conversation, project)

    if md is None:
        # 실패 시 기본 마크다운만 생성
        md = build_basic_markdown(project, conversation)

    return {
        "meta": meta or {},
        "markdown": md
    }

@app.post("/api/conversation/save+analyze")
async def save_and_analyze(req: Request):
    """
    대화를 분석하고, Obsidian Vault에 저장
    - frontmatter(meta) + markdown 본문
    """
    data = await req.json()
    project = data.get("project", "General")
    source = data.get("source", "extension")
    conversation = data.get("conversation", [])

    # 분석
    if USE_LOCAL_LLM:
        meta, md, raw = await call_local_llm(conversation, project)
    else:
        meta, md, raw = await call_local_llm(conversation, project)

    # 메타 기본값
    meta = meta or {}
    meta.setdefault("project", project)
    meta.setdefault("source", source)
    meta.setdefault("saved_at", datetime.now().isoformat(timespec="seconds"))

    # 본문 확보(실패 시 기본 템플릿)
    if md is None:
        md = build_basic_markdown(project, conversation)

    # 파일 저장
    project_dir = ensure_project_dir(project)
    title = meta.get("title") or f"{project} - {datetime.now().strftime('%Y-%m-%d')}"
    fname = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{slugify(title)}.md"

    content = to_frontmatter(meta) + "\n" + md.strip() + "\n"

    file_path = project_dir / fname
    file_path.write_text(content, encoding="utf-8")

    return {"status": "success", "file": str(file_path), "meta": meta}

# === 하위호환: 기존 경로 유지 ===
@app.post("/api/conversation/save")
async def save_conversation_legacy(req: Request):
    """
    기존 확장이 호출하던 단순 저장 엔드포인트(분석 없이)
    """
    data = await req.json()
    project = data.get("project", "General")
    conversation = data.get("conversation", [])

    project_path = ensure_project_dir(project)

    md = build_basic_markdown(project, conversation)
    filename = project_path / f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    filename.write_text(md, encoding="utf-8")
    return {"status": "success", "file": str(filename)}
