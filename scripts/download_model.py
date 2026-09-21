"""Script to download lightweight vision models from ModelScope or HuggingFace."""

import argparse
import sys
from pathlib import Path
import urllib.request
import json
import time


SUPPORTED_PRESETS = {
    "qwen2.5-vl-3b": {
        "name": "Qwen2.5-VL-3B-Instruct",
        "modelscope_id": "Qwen/Qwen2.5-VL-3B-Instruct",
        "description": "阿里通义千问 3B 多模态视觉模型，中文试卷/文档理解极强",
    },
    "qwen2-vl-2b": {
        "name": "Qwen2-VL-2B-Instruct",
        "modelscope_id": "Qwen/Qwen2-VL-2B-Instruct",
        "description": "阿里通义千问 2B 超轻量多模态模型，推理极快，显存开销低",
    },
}


def download_file(url: str, dest_path: Path) -> None:
    """Download a file with real-time progress display."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    with urllib.request.urlopen(req) as resp:
        total_size = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        block_size = 1024 * 1024  # 1MB
        t0 = time.time()

        with open(dest_path, "wb") as f:
            while True:
                chunk = resp.read(block_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                elapsed = max(0.1, time.time() - t0)
                speed = downloaded / elapsed / 1024 / 1024  # MB/s

                if total_size > 0:
                    pct = (downloaded / total_size) * 100
                    sys.stdout.write(
                        f"\rDownloading: {dest_path.name} [{pct:5.1f}%] "
                        f"{downloaded / 1024 / 1024:.1f}/{total_size / 1024 / 1024:.1f} MB ({speed:.1f} MB/s)"
                    )
                else:
                    sys.stdout.write(
                        f"\rDownloading: {dest_path.name} {downloaded / 1024 / 1024:.1f} MB ({speed:.1f} MB/s)"
                    )
                sys.stdout.flush()

    print()


def main():
    parser = argparse.ArgumentParser(description="Download lightweight vision models for ExamSplit AI.")
    parser.add_argument(
        "--model",
        choices=list(SUPPORTED_PRESETS.keys()),
        default="qwen2.5-vl-3b",
        help="Model preset identifier",
    )
    parser.add_argument(
        "--save-dir",
        type=str,
        default=None,
        help="Destination directory under models/",
    )
    args = parser.parse_args()

    preset = SUPPORTED_PRESETS[args.model]
    save_dir = Path(args.save_dir) if args.save_dir else Path("models") / args.model
    save_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== Downloading {preset['name']} ===")
    print(f"Description: {preset['description']}")
    print(f"Target Directory: {save_dir.resolve()}\n")

    # Fetch file list from ModelScope
    api_url = f"https://www.modelscope.cn/api/v1/models/{preset['modelscope_id']}/repo/files"
    req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
            files = data.get("Data", {}).get("Files", [])
    except Exception as e:
        print(f"Error querying ModelScope repository: {e}")
        return 1

    print(f"Found {len(files)} files to download.")
    for f_info in files:
        f_path = f_info.get("Path")
        if not f_path:
            continue
        dest = save_dir / f_path
        if dest.exists() and dest.stat().st_size == f_info.get("Size", 0):
            print(f"Skipping already downloaded file: {f_path}")
            continue

        file_url = (
            f"https://www.modelscope.cn/api/v1/models/{preset['modelscope_id']}"
            f"/repo?Revision=master&FilePath={f_path}"
        )
        print(f"Fetching {f_path} ({f_info.get('Size', 0) / 1024 / 1024:.2f} MB)...")
        try:
            download_file(file_url, dest)
        except Exception as e:
            print(f"\nFailed to download {f_path}: {e}")

    print(f"\nModel {preset['name']} ready at: {save_dir.resolve()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
