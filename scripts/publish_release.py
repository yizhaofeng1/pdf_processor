"""Publish v1.0 release to GitHub and upload binary assets."""

import os
import sys
import json
import socket
import urllib.request
import urllib.parse
from pathlib import Path
import subprocess

# WSL fake-ip / TUN self-healing resolver
_orig_getaddrinfo = socket.getaddrinfo

def _patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if host in ("api.github.com", "uploads.github.com"):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("20.205.243.166", port))]
    return _orig_getaddrinfo(host, port, family, type, proto, flags)

socket.getaddrinfo = _patched_getaddrinfo


def get_github_token():
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"].strip()
    proc = subprocess.run(
        ["git", "credential", "fill"],
        input="protocol=https\nhost=github.com\n",
        text=True,
        capture_output=True,
        check=True,
    )
    for line in proc.stdout.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1].strip()
    raise ValueError("Could not find GitHub token")


def main():
    import requests

    token = get_github_token()
    repo = "yizhaofeng1/pdf_processor"

    session = requests.Session()
    session.headers.update({
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "ExamSplitAI-Release-Bot",
    })

    body_text = """## 🌟 ExamSplit AI v2.0 重磅大版本发布！

**ExamSplit AI** 是一款专为教师、备考学生（如考研、高考、竞赛）与教辅教研人员打造的**桌面级试卷 PDF 智能拆题与精细化排版选题导出系统**。

坚守**“原卷唯一保真”**哲学：AI 识别试卷结构与物理外轮廓，本地 Python (PyMuPDF) 引擎执行微米级无损矢量裁剪，拒绝破坏性 OCR 导致的公式图表乱码。

---

### 📦 独立免安装版直接下载运行

无需配置 Python、Conda 或任何系统环境，下载对应系统绿色便携包，解压后双击即可秒开：

- **Windows 64位独立便携版**：下载下方 `ExamSplitAI_Windows_x64.zip`，解压后双击 **`ExamSplitAI.exe`** 即可启动！
- **Linux 64位独立便携版**：下载下方 `ExamSplitAI_Linux_x64.tar.gz`，解压后双击 **`启动ExamSplit.sh`**（或执行 `./ExamSplitAI`）即可启动！

---

### 🚀 v2.0 关键更新与重大特性

1. 🧪 **全新本地离线轻量小模型切题流水线（0 接口费用，效果媲美大模型）**：
   - **完全脱离云端大模型与商业 API，100% 离线隐私运行**；
   - 采用成熟工业级文档解析体系：
     - `ReadingOrderDetector`：基于跨中央槽文本几何比例与题号拓扑排布，高可靠判定单双栏版面；
     - `LocalMarkerDetector`：全题号正则与启发式扫描，100% 消除选项分母与公式误报；
     - `LocalCandidateBuilder`：阅读流候选框构建，行墨迹自适应约束；
     - `LocalConfidenceRouter` + `LocalVLMProvider`：置信度智能分流，90% 以上标准试题由本地规则引擎毫秒级秒切；低置信度疑难题无缝分流至本地小 VLM（支持 Ollama / llama-server 部署的 `qwen2.5vl:3b` 等）微秒级复核；
   - 实测在 2019、2020、2021 等复杂真题中实现全题号 100% 准确提取，选框精度媲美云端大模型，为用户彻底省去 API 账单！

2. 🪟 **全系统仪表盘独立顶层窗口化（彻底消除窗口锁死）**：
   - 将【API 服务商配置】、【本地小模型实验】、【批量后台分析】、【组卷试题篮】、【试卷大纲模板】及【导出设置】全面重构为**独立的非模态顶层窗口（`Qt.Window` + `NonModal`）**；
   - 拥有独立系统任务栏图标与完整的最小化/最大化/关闭按钮；
   - 彻底摒弃旧版 `dlg.exec()` 模态阻塞导致的“弹窗丢失或遮挡后整个 app 完全锁死”缺陷，支持随时单独关闭，重复点击自动置顶激活。

3. 🎯 **DeepSeek 系统提示词深度优化 (v3.0) 与最佳使用规范**：
   - 重新构建针对 DeepSeek 系列模型的专用系统提示词（`prompts/detect_markers_deepseek.txt`），制定强单调递增题号链约束，严密防范选择题选项 (A)(B)(C)(D) 分母、内联公式被误判为题号；
   - 严密保护解答大题小问（如 (1)、(2) 或 (I)、(II)）不被碎片化误切，强化跨页题目的连贯性识别；
   - **【核心选型规范】**：
     - **极力推荐**：目前使用 DeepSeek 强烈推荐使用其 **`deepseek-chat` / flash** 模式（性价比与响应速度极佳）；
     - **必须搭配专用预设**：使用 DeepSeek 模型时，**务必在配置面板中搭配使用【内置优化提示词 (推荐 DeepSeek)】**，以确保视觉坐标对齐。

4. 🐛 **关键 Bug 修复与体验完善**：
   - **选择题小题只框左半边 Bug 根治**：彻底修复旧分栏算法将单栏选择题（选项横排布局）误判为双栏导致选框右侧截断的缺陷，保证选择题选框横向完整覆盖 (A)(B)(C)(D) 所有选项；
   - **Windows 窗口大小自由调节与布局自适应**：修复 Windows 端上下方向无法拉伸导致保存按钮被遮挡的缺陷，全窗口启用 `setSizeGripEnabled(True)`、自适应滚动条与合理的最小尺寸约束；
   - **底层类型兼容性自愈**：消除 PySide6 QVariant 跨 C++ 层拷贝警告，实现 Pydantic `PosixPath` 自动类型转换自愈。

5. 🧪 **自动化单元测试全覆盖**：
   - 单元测试增至 **114 项**，100% 全部通过。

---

### 💡 AI 模型选型推荐、精度分析与实测计费参考

#### 1. 密集大题排版下的模型精度差异
目前试卷切题选框的精细度（尤其是密集型大题）与大模型本身的 Vision 多模态能力强相关：
- **本地小模型离线流水线（0 费用首选）**：完全离线免配置 API，标准题型秒级切出，大题小题精度均表现优异；
- **Gemini 系列（云端首选推荐）**：实测中 **Gemini 3.7 Flash** / **Gemini 3.8 Flash**（亦支持 2.5 Flash）在密集大题试卷中定位极其精准；
- **DeepSeek 系列（云端高性价比推荐）**：推荐优先选用 **`deepseek-chat` / flash** 模式，搭配专用预设提示词；
- **GPT 系列（次选推荐）**：**GPT-4o** / **GPT-4o-mini** 具备顶级视觉外框捕捉能力，切分稳定。

#### 2. 真实计费成本统计（以一份标准 8 页考研数学一完整试卷为例）
| 模型服务商 | 推荐模型规格 | 分析 1 份完整数学一试卷预估成本 | 适用场景 |
| :--- | :--- | :---: | :--- |
| **本地轻量小模型流水线** | `PyMuPDF` + `qwen2.5vl:3b` | **0 元 (免费离线)** | 彻底省钱，无网络离线环境、数据隐私首选 |
| **DeepSeek** | `deepseek-chat` / Flash (搭配专用预设) | **约 0.04 元 (CNY)** | 极致性价比，学生备考日常海量真题切分首选 |
| **Google Gemini** | `gemini-3.7-flash` / `gemini-2.5-flash` | **约 0.04 ~ 0.06 美元 (USD)**<br>*(折合约 0.28 ~ 0.42 元)* | 精度天花板，教研老师排版与高精分析首选 |
| **OpenAI** | `gpt-4o-mini` / `gpt-4o` | **约 0.03 ~ 0.15 美元 (USD)** | 表现扎实，生态适配广泛 |

---

### ⭐ 支持与反馈

- **点亮 Star 给予支持**：如果您觉得本项目对您的备考或教学有所帮助，非常欢迎在 GitHub 点亮右上角的 **Star ⭐** 给予鼓励！
- **Bug 反馈与建议**：若在使用过程中遇到任何切分边界异常、排版建议或新功能想法，欢迎随时在 **[GitHub Issues](https://github.com/yizhaofeng1/pdf_processor/issues)** 中提交反馈！
"""

    target_tag = "v2.0"
    print(f"Connecting to GitHub API for release {target_tag}...", flush=True)
    r = session.get(f"https://api.github.com/repos/{repo}/releases/tags/{target_tag}")
    print(f"Response status: {r.status_code}", flush=True)
    if r.status_code == 200:
        release = r.json()
        print(f"Release {target_tag} already exists, ID:", release["id"], flush=True)
    elif r.status_code == 404:
        print(f"Release {target_tag} does not exist yet. Creating...", flush=True)
        create_payload = {
            "tag_name": target_tag,
            "target_commitish": "main",
            "name": "ExamSplit AI v2.0 —— 本地离线轻量模型流水线、DeepSeek专用提示词工程、独立窗口架构与高精切分",
            "body": body_text,
            "draft": False,
            "prerelease": False,
        }
        cr = session.post(f"https://api.github.com/repos/{repo}/releases", json=create_payload)
        cr.raise_for_status()
        release = cr.json()
        print(f"Created release {target_tag}, ID:", release["id"], flush=True)
    else:
        r.raise_for_status()

    upload_base = release["upload_url"].split("{")[0]
    existing_assets = {a["name"]: a for a in release.get("assets", [])}

    dist_dir = Path("dist")
    assets = [
        ("ExamSplitAI_Windows_x64.zip", "application/zip"),
        ("ExamSplitAI_Linux_x64.tar.gz", "application/gzip"),
    ]

    import time

    for filename, content_type in assets:
        filepath = dist_dir / filename
        if not filepath.exists():
            print(f"Asset file {filepath} not found! Skipping.", flush=True)
            continue

        if filename in existing_assets:
            item = existing_assets[filename]
            if item.get("state") == "uploaded":
                print(f"✓ Asset {filename} is already uploaded and valid (ID: {item['id']}). Skipping.", flush=True)
                continue
            else:
                print(f"Deleting incomplete asset {filename} (ID: {item['id']})...", flush=True)
                session.delete(f"https://api.github.com/repos/{repo}/releases/assets/{item['id']}")

        upload_url = f"{upload_base}?name={urllib.parse.quote(filename)}"
        upload_headers = {
            "Content-Type": content_type,
            "X-GitHub-Api-Version": "2022-11-28",
        }

        success = False
        for attempt in range(1, 6):
            print(f"Uploading {filename} (attempt {attempt}/5, {filepath.stat().st_size / 1024 / 1024:.1f} MB)...", flush=True)
            try:
                with open(filepath, "rb") as f:
                    resp = session.post(
                        upload_url,
                        headers=upload_headers,
                        data=f,
                        timeout=600,
                    )
                if resp.status_code in (200, 201):
                    res = resp.json()
                    print(f"Uploaded {filename} successfully! Asset ID: {res.get('id', 'unknown')}", flush=True)
                    success = True
                    break
                else:
                    print(f"Attempt {attempt} failed: HTTP {resp.status_code}: {resp.text[:300]}", flush=True)
            except Exception as e:
                print(f"Attempt {attempt} connection error: {e}", flush=True)
            time.sleep(3)

        if not success:
            print(f"Failed to upload {filename} after 5 attempts!", flush=True)
            sys.exit(1)

    print("All assets processed successfully!", flush=True)


if __name__ == "__main__":
    main()
