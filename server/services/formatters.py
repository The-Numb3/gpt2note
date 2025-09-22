import json, re
from datetime import datetime, timezone

def build_conversation_block(conversation):
    lines = []
    for i, m in enumerate(conversation, start=1):
        lines.append(f"[{i}][{m['role']}] {m['content']}")
    return "\n".join(lines)

def parse_dual_output(text: str) -> tuple[dict, str]:
    j, md = {}, ""
    m = re.search(r"====JSON====\s*(\{.*?\})\s*====MARKDOWN====\s*(.*)\Z", text, flags=re.S)
    if m:
        try:
            j = json.loads(m.group(1))
        except Exception:
            j = {}
        md = m.group(2).strip()
    else:
        md = f"# 자동 노트(임시)\n\n```\n{text.strip()}\n```"
    return j, md

def inject_frontmatter(markdown: str, title: str, project: str, source: str | None, turns: int, tags: list[str] | None = None) -> str:
    iso = datetime.now(timezone.utc).isoformat()
    tags_str = "[" + ", ".join(tags or []) + "]"
    fm = f"""---
title: {title}
project: {project}
created: {iso}
tags: {tags_str}
source: {source or "chat"}
turns: {turns}
---
"""
    if markdown.lstrip().startswith("---"):
        # 이미 frontmatter 있으면 그대로 둠
        return markdown
    return fm + "\n" + markdown
