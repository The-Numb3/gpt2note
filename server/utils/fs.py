from pathlib import Path
import re
from datetime import datetime

def ensure_dir(folder: str | Path) -> Path:
    p = Path(folder)
    p.mkdir(parents=True, exist_ok=True)
    return p

_slug_re = re.compile(r'[^0-9A-Za-z가-힣 _\-.]+')

def slugify(text: str, max_len: int = 80) -> str:
    s = _slug_re.sub('', (text or '').strip())
    s = s.replace('/', '-').replace('\\', '-').strip()
    return s[:max_len] or f"note-{datetime.now().strftime('%H%M%S')}"

def write_markdown(folder: str | Path, title: str, content: str) -> str:
    folder_p = ensure_dir(folder)
    safe_title = slugify(title)
    fname = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{safe_title}.md"
    file_path = folder_p / fname
    file_path.write_text(content or "", encoding="utf-8")
    # 쓰기 검증
    if not file_path.exists() or file_path.stat().st_size == 0 and (content or "") != "":
        raise RuntimeError(f"Write verification failed: {file_path}")
    return str(file_path)
