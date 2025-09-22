from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
from datetime import datetime

app = FastAPI()

# ★ CORS 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 필요 시 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VAULT_PATH = Path(r"C:/Users/BEAR4/Documents/Obsidian Vault")

@app.post("/api/conversation/save")
async def save_conversation(req: Request):
    data = await req.json()
    project = data.get("project", "General")
    conversation = data.get("conversation", [])

    project_path = VAULT_PATH / project
    project_path.mkdir(parents=True, exist_ok=True)

    md_conv = []
    for msg in conversation:
        role = "👤 User" if msg["role"] == "user" else "🤖 Assistant"
        md_conv.append(f"### {role}\n{msg['content']}\n")
    conv_md = "\n---\n".join(md_conv)

    final_md = f"""
# 📝 ChatGPT Conversation Report
**프로젝트**: {project}  
**날짜**: {datetime.now().strftime('%Y-%m-%d')}  
**대화 길이**: {len(conversation)} turns  

---

## 💬 원본 대화 기록
{conv_md}
""".strip()

    filename = project_path / f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    filename.write_text(final_md, encoding="utf-8")
    return {"status": "success", "file": str(filename)}
