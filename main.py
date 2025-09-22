# main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
import httpx
import json
import os
import re

app = FastAPI()

# === CORS ===
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # 개발 중은 * 허용
    allow_credentials=False,      # "*"와 함께 True는 브라우저에서 막힐 수 있음
    allow_methods=["*"],
    allow_headers=["*"],
)

# === 환경/설정 ===
# 기본 저장 경로: Obsidian 없어도 개발 폴더로 동작
VAULT_PATH = Path(
    os.environ.get(
        "OBSIDIAN_VAULT_DIR",
        str(Path.home() / "ObsidianVaultDev")  # 개발용 기본
    )
)

# 로컬 LLM (Ollama) 기본 설정
LOCAL_LLM_BASE_URL = os.environ.get("LOCAL_LLM_BASE_URL", "http://localhost:11434")
LOCAL_LLM_MODEL = os.environ.get("LOCAL_LLM_MODEL", "llama3.1:8b-instruct-q4_K_M")
LOCAL_LLM_TEMPERATURE = float(os.environ.get("LOCAL_LLM_TEMPERATURE", "0.2"))
LOCAL_LLM_MAX_TOKENS = int(os.environ.get("LOCAL_LLM_MAX_TOKENS", "1600"))

# === 유틸 ===
def slugify(s: str) -> str:
    s = re.sub(r"[^\w\s\-\.]", "", s, flags=re.UNICODE)
    s = re.sub(r"\s+", "_", s, flags=re.UNICODE)
    return s.strip("_")[:80] or "note"

def ensure_dir(p: Path) -> Path:
    if not p.exists():
        try:
            p.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"경로를 만들 수 없습니다: {p} ({e})")
    return p

def to_frontmatter(meta: Dict[str, Any]) -> str:
    # 모든 값을 JSON으로 직렬화하여 한글/특수문자 보존
    return "---\n" + "\n".join(
        f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in meta.items()
    ) + "\n---\n"

def build_basic_markdown(project: str, conversation: List[Dict[str, str]]) -> str:
    md_conv = []
    for msg in conversation:
        role = msg.get("role", "")
        content = (msg.get("content") or "").strip()
        role_md = "👤 User" if role == "user" else "🤖 Assistant"
        md_conv.append(f"### {role_md}\n{content}\n")
    conv_md = "\n---\n".join(md_conv)
    return f"""# 📝 Chat Conversation Report
**프로젝트**: {project}  
**날짜**: {datetime.now().strftime('%Y-%m-%d')}  
**대화 길이**: {len(conversation)} turns  

---

## 💬 원본 대화 기록
{conv_md}
""".strip()

def conversation_to_plaintext(convo: List[Dict[str, str]], max_chars: int = 12000) -> str:
    lines, total = [], 0
    for m in convo:
        role = m.get("role", "user")
        content = (m.get("content") or "").strip()
        line = f"[{role}] {content}"
        if total + len(line) > max_chars:
            break
        lines.append(line)
        total += len(line)
    return "\n".join(lines)

# === 프롬프트 ===
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
5) 짧은 '태그' 제안 (예: #선형대수, #벡터)

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

# === LLM 호출 (OpenAI-호환 → 실패시 Ollama 네이티브) ===
async def _try_openai_compat(client: httpx.AsyncClient, model: str, sys_prompt: str, user_prompt: str) -> Optional[str]:
    url = f"{LOCAL_LLM_BASE_URL.rstrip('/')}/v1/chat/completions"
    payload = {
        "model": model,
        "temperature": LOCAL_LLM_TEMPERATURE,
        "max_tokens": LOCAL_LLM_MAX_TOKENS,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    r = await client.post(url, json=payload)
    if r.status_code >= 400:
        return None
    data = r.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None

async def _try_ollama_native(client: httpx.AsyncClient, model: str, sys_prompt: str, user_prompt: str) -> Optional[str]:
    # https://github.com/ollama/ollama/blob/main/docs/api.md#generate-a-chat-completion
    url = f"{LOCAL_LLM_BASE_URL.rstrip('/')}/api/chat"
    payload = {
        "model": model,
        "options": {
            "temperature": LOCAL_LLM_TEMPERATURE,
            "num_predict": LOCAL_LLM_MAX_TOKENS
        },
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False
    }
    r = await client.post(url, json=payload)
    if r.status_code >= 400:
        return None
    data = r.json()
    try:
        return (data.get("message", {}) or {}).get("content", "").strip()
    except Exception:
        return None

async def call_local_llm(conversation: List[Dict[str, str]], project: str) -> Tuple[Optional[Dict[str, Any]], Optional[str], str]:
    """
    LLM 호출 → (meta_json, markdown, raw_text)
    - OpenAI-compat 실패 시 Ollama native로 재시도
    - 파싱 실패 시 전체 텍스트를 Markdown으로 사용
    - 완전 빈 응답 방지
    """
    title_hint = f"{project} - {datetime.now().strftime('%Y-%m-%d')}"
    convo_text = conversation_to_plaintext(conversation)
    user_prompt = USER_PROMPT_TEMPLATE.format(conversation_text=convo_text, title_hint=title_hint)

    text = ""
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            text = await _try_openai_compat(client, LOCAL_LLM_MODEL, SYSTEM_PROMPT, user_prompt) or ""
            if not text:
                text = await _try_ollama_native(client, LOCAL_LLM_MODEL, SYSTEM_PROMPT, user_prompt) or ""
    except Exception as e:
        text = f"[LLM 호출 실패] {e}"

    # 파싱
    meta_json, md = None, None
    if "====JSON====" in text and "====MARKDOWN====" in text:
        try:
            parts = text.split("====JSON====", 1)[1]
            meta_part, md_part = parts.split("====MARKDOWN====", 1)
            meta_json = json.loads(meta_part.strip())
            md = md_part.strip()
        except Exception:
            md = text.strip()
    else:
        md = text.strip()

    if not md:
        md = "## 요약 생성에 실패했습니다.\n- 모델 응답이 비어있거나 파싱에 실패했습니다."

    return meta_json, md, text

# === 라우트 ===
@app.get("/health")
def health():
    return {"ok": True, "vault": str(VAULT_PATH), "model": LOCAL_LLM_MODEL}

@app.post("/api/conversation/analyze")
async def analyze_only(req: Request):
    """
    저장 없이 분석 결과만 반환
    """
    data = await req.json()
    project = data.get("project", "General")
    conversation = data.get("conversation", [])

    meta, md, raw = await call_local_llm(conversation, project)
    if not md or not md.strip():
        md = build_basic_markdown(project, conversation)

    return {"meta": meta or {}, "markdown": md}

@app.post("/api/conversation/save+analyze")
async def save_and_analyze(req: Request):
    """
    분석 결과를 파일로 저장 (frontmatter + markdown 본문)
    - 요청 body에서 vault_dir가 있으면 우선 사용
    """
    data = await req.json()
    project = data.get("project", "General")
    source = data.get("source", "extension")
    conversation = data.get("conversation", [])
    vault_override = data.get("vault_dir")

    vault_dir = Path(vault_override) if vault_override else VAULT_PATH
    ensure_dir(vault_dir)
    project_dir = ensure_dir(vault_dir / project)

    # 분석
    meta, md, raw = await call_local_llm(conversation, project)

    # 메타 보강
    meta = meta or {}
    meta.setdefault("title", f"{project} - {datetime.now().strftime('%Y-%m-%d')}")
    meta.setdefault("project", project)
    meta.setdefault("created", datetime.utcnow().isoformat())
    meta.setdefault("tags", [])
    meta.setdefault("source", source)
    meta.setdefault("turns", len(conversation))

    # 본문 보강: 비어있으면 기본 마크다운으로 대체
    if not md or not md.strip():
        md = build_basic_markdown(project, conversation)

    # 파일 저장
    title = meta.get("title") or f"{project} - {datetime.now().strftime('%Y-%m-%d')}"
    fname = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{slugify(title)}.md"
    content = to_frontmatter(meta) + "\n" + md.strip() + "\n"

    file_path = project_dir / fname
    file_path.write_text(content, encoding="utf-8")

    return {"status": "success", "file": str(file_path), "meta": meta}

# 하위호환: 분석 없이 저장
@app.post("/api/conversation/save")
async def save_conversation_legacy(req: Request):
    data = await req.json()
    project = data.get("project", "General")
    conversation = data.get("conversation", [])
    vault_override = data.get("vault_dir")

    vault_dir = Path(vault_override) if vault_override else VAULT_PATH
    ensure_dir(vault_dir)
    project_dir = ensure_dir(vault_dir / project)

    md = build_basic_markdown(project, conversation)
    filename = project_dir / f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    filename.write_text(md, encoding="utf-8")
    return {"status": "success", "file": str(filename)}
