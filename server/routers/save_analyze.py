from fastapi import APIRouter
from .analyze import analyze, AnalyzeReq, AnalyzeRes
from ..config import settings
from ..services.formatters import inject_frontmatter
from ..utils.fs import write_markdown
from datetime import datetime

router = APIRouter()

def _fallback_from_conv(conv):
    parts = []
    for m in conv:
        who = "👤 User" if m.role == "user" else ("🤖 Assistant" if m.role == "assistant" else "🛠 System")
        parts.append(f"### {who}\n{m.content}\n")
    return "\n---\n".join(parts)

@router.post("/api/conversation/save+analyze", response_model=AnalyzeRes)
def save_and_analyze(req: AnalyzeReq):
    # 1) LLM 분석 시도
    try:
        res: AnalyzeRes = analyze(req)
    except Exception as e:
        # 분석 실패 → 빈 결과로 처리하고 폴백
        print("[save+analyze] analyze() failed:", repr(e))
        res = AnalyzeRes(meta={}, markdown="")

    # 2) 결과 검증 + 폴백
    md = (res.markdown or "").strip()
    if len(md.replace("#", "").replace("-", "").replace("`", "").strip()) < 80:
        # 너무 짧거나 비면 원본 대화로 폴백
        print("[save+analyze] markdown too short → fallback to raw conversation")
        md = _fallback_from_conv(req.conversation)

    # 3) 프런트매터 주입
    title = (res.meta or {}).get("title") or "Conversation_Note"
    md_ready = inject_frontmatter(
        markdown=md,
        title=title,
        project=req.project,
        source=req.source,
        turns=len(req.conversation),
        tags=(res.meta or {}).get("tags", []),
        created=datetime.utcnow().isoformat()
    )

    # 4) 저장 (항상 시도) + 검증 로그
    folder = settings.OBSIDIAN_VAULT_DIR + f"\\{req.project}"
    try:
        path = write_markdown(folder, title, md_ready)
        print(f"[save+analyze] saved: {path} (len={len(md_ready)})")
        # 응답에 파일 경로/길이 첨부해서 확장 콘솔에서 바로 확인 가능
        res.meta = {**(res.meta or {}), "file": path, "saved": True, "body_len": len(md_ready)}
    except Exception as e:
        print("[save+analyze] write_markdown failed:", repr(e))
        # 실패 시에도 클라이언트가 알 수 있게 플래그와 에러 메시지 전달
        res.meta = {**(res.meta or {}), "saved": False, "save_error": repr(e), "target_folder": folder}

    # 5) res.markdown을 우리가 최종 md로 갱신해 돌려주자 (디버깅할 때 편함)
    res.markdown = md
    return res
