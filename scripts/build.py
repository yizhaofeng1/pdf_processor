#!/usr/bin/env python3
"""Cross-platform packaging script for ExamSplit AI.
Supports Windows (.exe + .zip) and Linux (ELF + .tar.gz).
Avoids cmd.exe / bash encoding issues.
"""

import os
import sys
import io
import shutil
import zipfile
import tarfile
import subprocess
from pathlib import Path

# Ensure UTF-8 output on Windows console (e.g. GitHub Actions cp1252)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Ensure working directory is project root
BASE_DIR = Path(__file__).resolve().parent.parent
os.chdir(BASE_DIR)


def print_step(step: str) -> None:
    print(f"\n\033[1;36m>>> {step}\033[0m" if sys.platform != "win32" else f"\n>>> {step}")


def print_success(msg: str) -> None:
    print(f"\033[1;32m{msg}\033[0m" if sys.platform != "win32" else msg)


def print_error(msg: str) -> None:
    print(f"\033[1;31m[ERROR] {msg}\033[0m" if sys.platform != "win32" else f"[ERROR] {msg}")


def check_and_install_pyinstaller() -> None:
    """Ensure PyInstaller is installed in the current Python environment."""
    print_step("[1/4] 检查打包依赖环境...")
    try:
        import PyInstaller
        print(f"检测到 PyInstaller 版本: {PyInstaller.__version__}")
    except ImportError:
        print("未检测到 PyInstaller，正在通过 pip 自动安装...")
        cmd = [sys.executable, "-m", "pip", "install", "pyinstaller"]
        res = subprocess.run(cmd)
        if res.returncode != 0:
            print_error("PyInstaller 安装失败，请手动运行: pip install pyinstaller")
            sys.exit(1)


def clean_build_cache() -> None:
    """Clean build and dist folders."""
    print_step("[2/4] 清理旧构建缓存 (build, dist)...")
    for folder in ["build", "dist"]:
        p = BASE_DIR / folder
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
            print(f"已清理: {folder}/")


def run_pyinstaller() -> None:
    """Run PyInstaller with the project spec file."""
    print_step("[3/4] 执行 PyInstaller 编译构建...")
    spec_path = BASE_DIR / "ExamSplitAI.spec"
    if not spec_path.exists():
        print_error(f"找不到构建配置文件: {spec_path}")
        sys.exit(1)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        str(spec_path),
        "--clean",
        "--noconfirm",
    ]
    print(f"执行命令: {' '.join(cmd)}")
    res = subprocess.run(cmd)
    if res.returncode != 0:
        print_error(f"PyInstaller 构建失败，退出码: {res.returncode}")
        sys.exit(res.returncode)


def create_zip(source_dir: Path, output_zip: Path) -> None:
    """Zip folder with portable relative paths."""
    print(f"正在压缩为绿色便携包: {output_zip.name} ...")
    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                full_path = Path(root) / file
                rel_path = full_path.relative_to(source_dir.parent)
                zf.write(full_path, rel_path)


def create_tar_gz(source_dir: Path, output_tar: Path) -> None:
    """Tar.gz folder for Linux distribution."""
    print(f"正在打包为 Linux 归档包: {output_tar.name} ...")
    with tarfile.open(output_tar, "w:gz") as tar:
        tar.add(source_dir, arcname=source_dir.name)


def post_process_linux(dist_app: Path) -> None:
    """Generate Linux launchers and scripts."""
    launcher = dist_app / "启动ExamSplit.sh"
    launcher_content = """#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
exec "./ExamSplitAI" "$@"
"""
    launcher.write_text(launcher_content, encoding="utf-8")
    launcher.chmod(0o755)

    desktop = dist_app / "ExamSplitAI.desktop"
    desktop_content = """[Desktop Entry]
Name=ExamSplit AI
Comment=试卷 PDF 智能拆题与选题导出系统
Exec=sh -c '"$(dirname "%k")/启动ExamSplit.sh"'
Icon=$(dirname "%k")/_internal/resources/icon.png
Terminal=false
Type=Application
Categories=Education;Office;
"""
    desktop.write_text(desktop_content, encoding="utf-8")
    desktop.chmod(0o755)

    bin_file = dist_app / "ExamSplitAI"
    if bin_file.exists():
        bin_file.chmod(0o755)


def package_distribution() -> None:
    """Verify output and package archive."""
    print_step("[4/4] 校验构建产物并生成便携分发包...")
    dist_dir = BASE_DIR / "dist"
    dist_app = dist_dir / "ExamSplitAI"

    is_windows = sys.platform == "win32" or os.name == "nt"
    exe_name = "ExamSplitAI.exe" if is_windows else "ExamSplitAI"
    exe_path = dist_app / exe_name

    if not exe_path.exists():
        print_error(f"未能生成核心可执行文件: {exe_path}")
        sys.exit(1)

    print(f"核心可执行程序生成成功: {exe_path}")

    # Prepare clean models directory and instructions in release package
    dist_models = dist_app / "models"
    dist_models.mkdir(parents=True, exist_ok=True)
    models_readme = BASE_DIR / "models" / "README.md"
    if models_readme.exists():
        shutil.copy2(models_readme, dist_models / "README.md")
    models_guide = BASE_DIR / "models" / "模型存放与运行说明.txt"
    if models_guide.exists():
        shutil.copy2(models_guide, dist_models / "模型存放与运行说明.txt")

    if is_windows:
        zip_path = dist_dir / "ExamSplitAI_Windows_x64.zip"
        create_zip(dist_app, zip_path)
        print("\n" + "=" * 70)
        print_success(" Windows 独立发行版打包成功！")
        print(f" 输出目录: {dist_app}")
        print(f" 绿色便携压缩包: {zip_path}")
        print(" 运行方式: 解压后直接双击 'ExamSplitAI.exe' 即可启动，无需安装 Python！")
        print("=" * 70)
    else:
        post_process_linux(dist_app)
        tar_path = dist_dir / "ExamSplitAI_Linux_x64.tar.gz"
        create_tar_gz(dist_app, tar_path)
        print("\n" + "=" * 70)
        print_success(" Linux 独立发行版打包成功！")
        print(f" 输出目录: {dist_app}")
        print(f" 便携归档压缩包: {tar_path}")
        print(" 运行方式: 直接双击 '启动ExamSplit.sh' 或运行 './ExamSplitAI'！")
        print("=" * 70)


def main() -> None:
    print("=" * 70)
    print(" ExamSplit AI 跨平台自动化独立客户端打包程序")
    print(f" 工作根目录: {BASE_DIR}")
    print(f" 当前操作系统: {sys.platform} ({os.name})")
    print(f" Python 解释器: {sys.executable}")
    print("=" * 70)

    check_and_install_pyinstaller()
    clean_build_cache()
    run_pyinstaller()
    package_distribution()


if __name__ == "__main__":
    main()
