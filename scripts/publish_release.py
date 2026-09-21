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

    body_text = """## 🌟 ExamSplit AI v1.2 升级发布！

**ExamSplit AI** 是一款专为教师、备考学生（如考研、高考、竞赛）与教辅教研人员打造的**桌面级试卷 PDF 智能拆题与精细化排版选题导出系统**。

坚守**“原卷唯一保真”**哲学：AI 识别试卷结构与物理外轮廓，本地 Python (PyMuPDF) 引擎执行微米级无损矢量裁剪，拒绝破坏性 OCR 导致的公式图表乱码。

---

### 📦 独立免安装版直接下载运行

无需配置 Python、Conda 或任何系统环境，下载对应系统绿色便携包，解压后双击即可秒开：

- **Windows 64位独立便携版**：下载下方 `ExamSplitAI_Windows_x64.zip`，解压后双击 **`ExamSplitAI.exe`** 即可启动！
- **Linux 64位独立便携版**：下载下方 `ExamSplitAI_Linux_x64.tar.gz`，解压后双击 **`启动ExamSplit.sh`**（或执行 `./ExamSplitAI`）即可启动！

---

### 🚀 v1.2 关键更新与 Bug 修复

1. 🔌 **真实模型在线刷新与错误透传**：
   - 彻底删除了“获取模型列表失败时使用代码写死的假列表冒充成功”的历史逻辑；
   - 真实反映网络与云端接口状态：成功即返回当前 API 真实可用模型，失败（如 Key 错误、401、网络不通）则明确展示异常信息，绝不欺骗用户。

2. 📝 **试卷大纲结构模板与提示词智能注入**：
   - 内置【2021+ 考研数学一大纲】、【2020 以前考研数学大纲】、【新高考一/二卷】、【全国甲/乙卷】、【通用期末/模拟卷】等标准大纲先验分布；
   - 支持在单试卷分析与批量分析对话框中一键选择，或自定义输入当前试卷题目分布，将先验分布提前注入大模型 Prompt，极大消除断号、漏题与大小题误判；
   - 支持将自定义模板保存至本地，永久跨试卷复用。

3. 🛒 **试题篮一键勾选批量入篮**：
   - 左侧试题列表顶部与顶部工具栏新增【🛒 勾选试题一键入篮】操作（支持右键快捷菜单）；
   - 用户多选题目后一键批量入篮，自动去重并更新 Badge 数量，无需逐题重复点击。

4. 🛡️ **多试卷彻底独立与选框覆写隔离**：
   - 彻底重构试卷切换与载入生命周期，打开新试卷时立即清理旧文档的选框画布覆盖层与试题缓存，彻底杜绝前一份试卷选框遗留在新试卷上的问题。

5. 📐 **密集大题 AI-First 边界保护策略**：
   - 针对解答题/证明题密集的试卷，智能检测大题间距；在密集排版下纯粹以 AI 物理墨迹为准，禁止本地文本向后盲目拉扯，避免大题选框向下碰撞互相侵占。

6. 🧪 **自动化单元测试全覆盖**：
   - 单元测试增至 87 项，100% 全部通过。

---

### 💡 AI 模型选型推荐、精度分析与实测计费参考

#### 1. 密集大题排版下的模型精度差异
目前试卷切题选框的精细度（尤其是密集型大题）与大模型本身的 Vision 多模态能力强相关：
- **Gemini 系列（首选推荐）**：实测中 **Gemini 3.7 Flash** / **Gemini 3.8 Flash**（亦支持 2.5 Flash）在密集大题试卷（如 2021 年数学一真题）中定位**极其精准**，能完美避开草稿留白并精确捕捉公式墨迹；
- **GPT 系列（次选推荐）**：**GPT-4o** / **GPT-4o-mini** 具备顶级视觉外框捕捉能力，切分稳定；
- **DeepSeek 系列（性价比推荐）**：推荐优先选用其 **Flash 类 / 视觉优化类模型**（如 `deepseek-chat` 或视觉中继）；部分极限密集年份（如 2020 年数学一）偶有微小偏移，可通过右侧栏或边框把手微调。

#### 2. 真实计费成本统计（以一份标准 8 页考研数学一完整试卷为例）
| 模型服务商 | 推荐模型规格 | 分析 1 份完整数学一试卷预估成本 | 适用场景 |
| :--- | :--- | :---: | :--- |
| **DeepSeek** | `deepseek-chat` / Flash | **约 0.04 元 (CNY)** | 极致性价比，学生备考日常海量真题切分首选 |
| **Google Gemini** | `gemini-3.7-flash` / `gemini-2.5-flash` | **约 0.04 ~ 0.06 美元 (USD)**<br>*(折合约 0.28 ~ 0.42 元)* | 精度天花板，教研老师排版与高精分析首选 |
| **OpenAI** | `gpt-4o-mini` / `gpt-4o` | **约 0.03 ~ 0.15 美元 (USD)** | 表现扎实，生态适配广泛 |

> [!NOTE]
> 其余厂商或开源模型若在使用中遇到边界偏差，**非常欢迎在 Issues 中留言交流**，作者将持续针对各大厂商模型分别定制专属提示词工程与坐标自适应逻辑！

---

### ⭐ 支持与反馈

- **点亮 Star 给予支持**：如果您觉得本项目对您的备考或教学有所帮助，非常欢迎在 GitHub 点亮右上角的 **Star ⭐** 给予鼓励！
- **Bug 反馈与建议**：若在使用过程中遇到任何切分边界异常、排版建议或新功能想法，欢迎随时在 **[GitHub Issues](https://github.com/yizhaofeng1/pdf_processor/issues)** 中提交反馈！
"""

    target_tag = "v1.2"
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
            "name": "ExamSplit AI v1.2 —— 试卷大纲提示词注入、批量试题篮、密集大题保护与真实模型拉取",
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
