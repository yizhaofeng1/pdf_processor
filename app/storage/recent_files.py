"""Recent files tracker and history persistence with rich metadata."""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
from ..config import DATA_DIR, ensure_data_directories

RECENT_FILES_PATH = DATA_DIR / "recent_files.json"
MAX_RECENT_FILES = 12


def _format_file_size(size_bytes: int) -> str:
    """Format bytes into human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def get_recent_files() -> List[Dict[str, Any]]:
    """Return list of valid, existing recent file records."""
    ensure_data_directories()
    if not RECENT_FILES_PATH.exists():
        return []
    try:
        data = json.loads(RECENT_FILES_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []

        cleaned: List[Dict[str, Any]] = []
        for item in data:
            if isinstance(item, str):
                p = Path(item)
                if p.exists() and p.is_file():
                    cleaned.append({
                        "file_path": str(p.resolve()),
                        "file_name": p.name,
                        "file_size": _format_file_size(p.stat().st_size),
                        "last_opened": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
                        "page_count": 0,
                    })
            elif isinstance(item, dict) and "file_path" in item:
                p = Path(item["file_path"])
                if p.exists() and p.is_file():
                    cleaned.append({
                        "file_path": str(p.resolve()),
                        "file_name": item.get("file_name") or p.name,
                        "file_size": item.get("file_size") or _format_file_size(p.stat().st_size),
                        "last_opened": item.get("last_opened") or datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "page_count": item.get("page_count", 0),
                    })
        return cleaned[:MAX_RECENT_FILES]
    except Exception:
        return []


def add_recent_file(file_path: str | Path, page_count: Optional[int] = None) -> None:
    """Add or promote file_path to the top of recent files list with metadata."""
    ensure_data_directories()
    p = Path(file_path).resolve()
    if not p.exists() or not p.is_file():
        return

    path_str = str(p)
    recents = get_recent_files()

    existing_meta = None
    new_recents = []
    for r in recents:
        if r["file_path"] == path_str:
            existing_meta = r
        else:
            new_recents.append(r)

    pages = page_count or (existing_meta.get("page_count", 0) if existing_meta else 0)

    record = {
        "file_path": path_str,
        "file_name": p.name,
        "file_size": _format_file_size(p.stat().st_size),
        "last_opened": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "page_count": pages,
    }

    new_recents.insert(0, record)
    new_recents = new_recents[:MAX_RECENT_FILES]

    try:
        RECENT_FILES_PATH.write_text(json.dumps(new_recents, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def remove_recent_file(file_path: str | Path) -> None:
    """Remove a specific file from recent history."""
    norm_path = str(Path(file_path).resolve())
    recents = get_recent_files()
    filtered = [r for r in recents if r["file_path"] != norm_path]
    try:
        RECENT_FILES_PATH.write_text(json.dumps(filtered, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def clear_recent_files() -> None:
    """Clear history."""
    try:
        if RECENT_FILES_PATH.exists():
            RECENT_FILES_PATH.unlink()
    except Exception:
        pass
