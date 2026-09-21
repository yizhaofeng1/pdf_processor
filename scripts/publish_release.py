"""Publish v1.0 release to GitHub and upload binary assets."""

import os
import sys
import json
import urllib.request
import urllib.parse
from pathlib import Path
import subprocess


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
    token = get_github_token()
    repo = "yizhaofeng1/pdf_processor"

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "ExamSplitAI-Release-Bot",
    }

    body_text = """## 🌟 ExamSplit AI v1.1 升级发布！

**ExamSplit AI** 是一款专为教师、备考学生（如考研、高考、竞赛）与教辅教研人员打造的**桌面级试卷 PDF 智能拆题与精细化排版选题导出系统**。

---

### 📦 独立免安装版直接下载运行

无需安装 Python、Conda 或任何开发环境，下载对应平台的便携压缩包，解压后双击即可直接使用：

- **Windows 64位独立便携版**：下载下方 `ExamSplitAI_Windows_x64.zip`，解压后双击 **`ExamSplitAI.exe`** 即可启动！
- **Linux 64位独立便携版**：下载下方 `ExamSplitAI_Linux_x64.tar.gz`，解压后双击 **`启动ExamSplit.sh`**（或执行 `./ExamSplitAI`）即可启动！

---

### 🚀 v1.1 关键更新与 Bug 修复

1. 🐛 **彻底修复多模型配置回退问题**：
   - 彻底修复了在设置窗口中配置其他 AI 模型（如 DeepSeek、OpenAI、Claude、GLM）后始终退回 Gemini 的严重缺陷；
   - 优化【设为当前激活生效的服务商】机制，编辑保存任何模型默认保持激活，且只要配置有效 Key 自动提升为生效项；
   - 杜绝因默认服务商未配置 Key 导致的误报与死锁。

2. 🎯 **新增顶部菜单栏【快速切换当前生效服务商】**：
   - 在【设置(&C)】菜单中新增快捷子菜单，展示所有支持的 AI 服务商并附带单选勾选标记（●）；
   - 无需打开复杂弹窗，直接在菜单点击即可随时切换当前生效的 AI 模型，状态栏和分析流水线即刻联动。

3. 🖱️ **状态栏网关快捷交互**：
   - 右下角 `AI网关: 🟢/🟡 ...` 状态标签支持鼠标手型悬停与点击，一键直达设置。

4. 🌐 **代理与超时全链路注入**：
   - 单试卷与多试卷批量后台分析统一继承全局代理（Proxy）与超时设定，解决外网中继访问不稳定问题。

5. 🧪 **测试套件全面升级**：
   - 81 项自动化单元测试 100% 通过。

---

### 🌟 核心特性回顾

1. **100% 原始矢量保真**：彻底告别破坏性 OCR 导致的公式错位、上下标断裂与几何图表乱码；
2. **跨试卷组卷试题篮**：支持多试卷跨卷挑题、一键连续重排题号与按标准题型智能排序；
3. **自适应空白排版导出**：小题紧凑排列省纸，大题预留自定义答题草稿空白（支持浅灰虚线框）；
4. **试卷批量后台分析队列**：多份试卷后台流水线分析，智能检索 SQLite 缓存秒开；
5. **大气暗色科技风 UI**：全局 15.5px 大字号、44px 渐变操作按钮、高对比度上下文菜单。

---

### ⭐ 支持与反馈

- **点亮 Star 给予支持**：如果您觉得本项目对您的备考或教学有所帮助，非常欢迎在 GitHub 点亮右上角的 **Star ⭐** 鼓励作者！
- **Bug 反馈与建议**：若在使用过程中遇到任何切分边界异常、排版建议或新功能想法，欢迎随时在 **[GitHub Issues](https://github.com/yizhaofeng1/pdf_processor/issues)** 中提交反馈，每一条建议都会认真跟进修复！
"""

    # Check if release already exists
    target_tag = "v1.1"
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases/tags/{target_tag}", headers=headers)
    release = None
    try:
        with urllib.request.urlopen(req) as resp:
            release = json.loads(resp.read().decode())
            print(f"Release {target_tag} already exists, ID:", release["id"])
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"Release {target_tag} does not exist yet. Creating...")
        else:
            raise

    if not release:
        create_payload = json.dumps({
            "tag_name": target_tag,
            "target_commitish": "main",
            "name": "ExamSplit AI v1.1 —— 试卷 PDF 智能拆题与精细化选题导出系统",
            "body": body_text,
            "draft": False,
            "prerelease": False,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/releases",
            data=create_payload,
            headers={**headers, "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req) as resp:
            release = json.loads(resp.read().decode())
            print(f"Created release {target_tag}, ID:", release["id"])

    upload_base = release["upload_url"].split("{")[0]
    existing_assets = {a["name"]: a["id"] for a in release.get("assets", [])}

    dist_dir = Path("dist")
    assets = [
        ("ExamSplitAI_Windows_x64.zip", "application/zip"),
        ("ExamSplitAI_Linux_x64.tar.gz", "application/gzip"),
    ]

    for filename, content_type in assets:
        filepath = dist_dir / filename
        if not filepath.exists():
            print(f"Asset file {filepath} not found! Skipping.")
            continue

        if filename in existing_assets:
            print(f"Deleting existing asset {filename} (ID: {existing_assets[filename]})...")
            del_req = urllib.request.Request(
                f"https://api.github.com/repos/{repo}/releases/assets/{existing_assets[filename]}",
                headers=headers,
                method="DELETE",
            )
            urllib.request.urlopen(del_req)

        print(f"Uploading {filename} ({filepath.stat().st_size / 1024 / 1024:.1f} MB)...")
        upload_url = f"{upload_base}?name={urllib.parse.quote(filename)}"
        upload_headers = {
            "Authorization": f"token {token}",
            "Content-Type": content_type,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Length": str(filepath.stat().st_size),
        }

        class ProgressFileReader:
            def __init__(self, p):
                self.p = p
                self.f = open(p, "rb")
                self.total = os.path.getsize(p)
                self.read_bytes = 0
                self.last_pct = -1

            def read(self, size=-1):
                chunk = self.f.read(size if size > 0 else 65536)
                self.read_bytes += len(chunk)
                pct = int(self.read_bytes * 100 / self.total)
                if pct != self.last_pct and pct % 10 == 0:
                    self.last_pct = pct
                    print(f"  [{os.path.basename(self.p)}] {pct}% ({self.read_bytes / 1024 / 1024:.1f} / {self.total / 1024 / 1024:.1f} MB)", flush=True)
                return chunk

            def __len__(self):
                return self.total

            def close(self):
                self.f.close()

        import requests
        reader = ProgressFileReader(filepath)
        try:
            resp = requests.post(
                upload_url,
                data=reader,
                headers=upload_headers,
                timeout=(30, 600),
            )
        finally:
            reader.close()

        if resp.status_code not in (200, 201):
            print(f"Failed to upload {filename}: HTTP {resp.status_code}: {resp.text[:300]}")
            sys.exit(1)

        res = resp.json()
        print(f"Uploaded {filename} successfully! Asset ID: {res.get('id', 'unknown')}")

    print("All assets uploaded successfully!")


if __name__ == "__main__":
    main()
