from fastapi import APIRouter
from pydantic import BaseModel
from typing import Literal, List, Dict, Any
from datetime import datetime, timezone
import json

from ..services.prompt import PROMPT_V2
from ..services.formatters import build_conversation_block, parse_dual_output
from ..services.weakness_hints import build_weakness_hints
from ..client_factory import chat_completion

router = APIRouter()

class Msg(BaseModel):
    role: Literal["user","assistant","system"]
    content: str

class AnalyzeReq(BaseModel):
    project: str = "AI Conversation Archiver"
    source: str | None = None
    conversation: List[Msg]
    weakness_hints: Dict[str, Any] | None = None

class AnalyzeRes(BaseModel):
    meta: Dict[str, Any]
    markdown: str

@router.post("/api/conversation/analyze", response_model=AnalyzeRes)
def analyze(req: AnalyzeReq):
    now_iso = datetime.now(timezone.utc).isoformat()
    hints = req.weakness_hints or build_weakness_hints([m.model_dump() for m in req.conversation])
    convo_block = build_conversation_block([m.model_dump() for m in req.conversation])

    prompt = PROMPT_V2\
        .replace("{{now_iso}}", now_iso)\
        .replace("{{turn_count}}", str(len(req.conversation)))\
        .replace("{{weakness_hints_json}}", json.dumps(hints, ensure_ascii=False))\
        .replace("{{conversation_block}}", convo_block)

    messages = [{"role":"system","content": prompt}]

    resp = chat_completion(messages)
    text = resp.choices[0].message.content
    meta, md = parse_dual_output(text)
    return AnalyzeRes(meta=meta, markdown=md)
