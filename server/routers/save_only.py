from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Literal
from server.utils.fs import write_markdown
from pathlib import Path
import os
VAULT_PATH = Path(
    os.environ.get(
        "OBSIDIAN_VAULT_DIR",
        str(Path.home() / "ObsidianVaultDev")  # 개발용 기본
    )
)

class Msg(BaseModel):
    role: Literal["user","assistant","system"]="user"
    content: str

class SaveReq(BaseModel):
    project: str="General"
    source: str="extension"
    conversation: List[Msg]=[]

router = APIRouter()

def _md_from_conv(conv: List[Msg]) -> str:
    lines = []
    for m in conv:
        who = "👤 User" if m.role=="user" else ("🤖 Assistant" if m.role=="assistant" else "🛠 System")
        lines.append(f"### {who}\n{m.content}\n")
    return "\n---\n".join(lines)

@router.post("/api/conversation/save")
def save_only(req: SaveReq):
    md = _md_from_conv(req.conversation) or "_(빈 대화)_"
    fm = (
        f"---\n"
        f"title: Raw_Conversation\n"
        f"project: {req.project}\n"
        f"source: {req.source}\n"
        f"turns: {len(req.conversation)}\n"
        f"---\n\n"
    )
    path = write_markdown(VAULT_PATH / req.project, "Raw_Conversation", fm + md)
    return {"ok": True, "file": path}
