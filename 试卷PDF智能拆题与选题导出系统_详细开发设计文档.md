# ExamSplit AI —— 试卷 PDF 智能拆题与选题导出系统

**文档版本：** v2.0
**文档性质：** Agent 可执行的完整软件设计与开发规格说明
**目标用户：** 个人学习 / 教师备课 / 试卷整理 / 考研复习
**主要语言：** Python
**桌面 UI：** PySide6
**核心 PDF 引擎：** PyMuPDF
**AI 方式：** 云端多模态大模型 API（OpenAI / DeepSeek / 其他兼容 Provider）
**首要目标：** 识别准确度 > 结果可修正性 > 原始 PDF 保真度 > 处理速度
**推荐产品形态：** 本地桌面应用 + 用户自己的 API Key
**核心原则：** AI 负责理解与定位，本地程序负责坐标计算、边界修正、PDF 裁剪和最终导出

---

# 0. 给 Agent 的核心开发指令

本项目不是“PDF OCR 转文字软件”，也不是“AI 重新生成试卷 PDF”。

本项目的核心任务是：

> **从试卷 PDF 中识别每一道题的逻辑边界，建立 Question → 原始 PDF 页面区域 的映射，然后允许用户选择题目并使用原始 PDF 内容无损组合导出。**

Agent 在实现时必须遵守以下优先级：

1. **绝不默认通过 AI 重新生成题目文本来制作最终 PDF。**
2. **原始 PDF 内容必须优先保留。**
3. AI 的职责主要是识别题号、题目开始位置、题目结束位置、跨页关系以及异常情况。
4. 最终题目区域必须在本地二次校验后才能进入导出流程。
5. 所有 AI 输出必须经过 Schema 验证，禁止直接信任自然语言响应。
6. AI API 与 PDF 引擎必须解耦，未来可以更换模型供应商而不改核心业务逻辑。
7. 所有识别结果都必须可人工修改。
8. 识别错误不能导致源 PDF 被修改；源 PDF 永远只读。
9. 所有坐标必须支持归一化表示，避免受渲染 DPI 影响。
10. 速度不是第一优先级，可以采用多轮模型调用、二次验证和多模型投票提高准确度。

---

# 1. 项目概述

## 1.1 项目名称

暂定：**ExamSplit AI —— 试卷 PDF 智能拆题与选题打印工具**

备选名称：

- PaperSegment AI
- ExamCrop
- ExamSplit
- PaperSlice AI

## 1.2 项目背景

用户拥有考研数学一、数学二、数学三、考研英语、政治、专业课等 PDF 试卷，希望：

1. 导入 PDF。
2. 系统自动理解每一页的试卷布局。
3. 自动识别题号与题目边界。
4. 将跨页题目识别为一个完整逻辑题目。
5. 在界面中把每道题作为独立对象展示。
6. 用户勾选需要打印的题目。
7. 用户可以调整题目顺序。
8. 最终生成只包含所选题目的统一 PDF。
9. 输出尽可能保持原始 PDF 的文字、公式、图片、字体、清晰度和排版质量。

## 1.3 为什么采用 API 模型而不是本地大模型

本项目首要目标是“可用的高识别准确度”和“开发复杂度可控”。

不要求用户安装显卡驱动、CUDA、本地 VLM、模型权重，也不要求项目自行训练模型。

项目采用：

```text
本地 PDF
   ↓
Python 页面解析
   ↓
图片 + OCR/原生文本 + 坐标
   ↓
云端多模态 AI
   ↓
严格 JSON
   ↓
本地边界计算与校验
   ↓
原 PDF 裁剪/重组
```

这样做具有以下优势：

- 不需要训练模型。
- 不需要向用户发放大型模型权重。
- 不要求用户具有 GPU。
- 可以持续替换更优秀的模型。
- 可以利用大模型视觉理解复杂试卷排版。
- 可以多模型投票提高准确度。
- 本地 PDF 不需要重新 OCR 排版即可保持原始质量。

## 1.4 核心思想

### 错误路线

```text
PDF
 ↓
OCR
 ↓
文字
 ↓
AI 重写
 ↓
重新排版
 ↓
PDF
```

数学试卷中可能出现：

- 分式
- 积分
- 矩阵
- 行列式
- 极限
- 上下标
- 根号
- 分段函数
- 手写/扫描图像
- 复杂公式

重新生成很容易导致视觉或数学内容失真。

### 正确路线

```text
PDF
 ↓
识别题目边界
 ↓
记录原 PDF 页面 + 坐标
 ↓
本地直接裁剪原始内容
 ↓
重新组合 PDF
```

因此本项目把 AI 当作：

> **结构分析器 / 视觉定位器**

而不是：

> **试卷内容生成器**

---

# 2. 产品范围

## 2.1 MVP 必须实现

第一版只要求实现：

1. 打开 PDF。
2. 自动识别 PDF 页面。
3. 自动提取原生 PDF 文本（如果有）。
4. 页面渲染为图片。
5. 调用多模态 AI。
6. AI 返回严格 JSON。
7. 本地解析题目边界。
8. 展示题目列表。
9. 展示题目预览。
10. 勾选/取消题目。
11. 调整题目顺序。
12. 人工修正题目边界。
13. 生成新 PDF。
14. 保存项目分析结果，避免重复消耗 API。

## 2.2 第二阶段

- GPT / DeepSeek 双模型验证。
- 自动冲突检测。
- 低置信度警告。
- 自动发现漏题。
- 自动发现重复题。
- 用户拖动边界。
- 添加题目。
- 拆分题目。
- 合并题目。
- 导出分析 JSON。
- 读取历史项目。
- 页面缩略图。
- 批量处理多套试卷。

## 2.3 第三阶段

- 保存用户纠正记录形成 Golden Dataset。
- 针对出版社/试卷模板建立规则。
- 自动识别科目和年份。
- 章节标签。
- 题型标签。
- 同类题模板匹配。
- 多模型自动路由。
- API 成本估算。
- 服务器代理模式（可选）。

## 2.4 非目标

第一版不负责：

- 自动解题。
- 自动生成答案。
- 自动批改。
- 自动知识点讲解。
- 训练自己的视觉语言大模型。
- 本地部署大型 VLM。
- 把所有题目重新 OCR 排版成纯文本 PDF。
- 在线多人协作。
- 用户账号系统。

---

# 3. 用户核心流程

```text
启动
 ↓
新建项目
 ↓
选择 PDF
 ↓
PDF 预检
 ↓
页面解析
 ↓
本地文本/布局分析
 ↓
页面图像生成
 ↓
调用 AI 分析
 ↓
严格 JSON Schema 校验
 ↓
本地坐标转换
 ↓
题目边界推导
 ↓
跨页题目合并
 ↓
一致性检查
 ↓
低置信度检查
 ↓
生成题目列表
 ↓
用户检查
 ↓
必要时人工修正
 ↓
勾选题目
 ↓
调整顺序
 ↓
导出 PDF
 ↓
保存项目
```

---

# 4. 总体系统架构

```text
┌─────────────────────────────────────────────────────────────┐
│                      PySide6 Desktop UI                     │
├─────────────────────────────────────────────────────────────┤
│                    Application Services                     │
│  Project / Analyze / Review / Selection / Export / Settings │
├─────────────────────────────────────────────────────────────┤
│                     Question Engine                         │
│                                                             │
│ PDF Loader                                                  │
│    ↓                                                        │
│ Page Analyzer                                               │
│    ↓                                                        │
│ Native Text + OCR + Layout Features                         │
│    ↓                                                        │
│ Page Renderer                                               │
│    ↓                                                        │
│ AI Provider                                                 │
│    ↓                                                        │
│ JSON Schema Validation                                      │
│    ↓                                                        │
│ Question Marker Detector                                    │
│    ↓                                                        │
│ Boundary Resolver                                           │
│    ↓                                                        │
│ Cross-page Resolver                                         │
│    ↓                                                        │
│ Confidence / Consistency Engine                             │
│    ↓                                                        │
│ Question Model                                              │
├─────────────────────────────────────────────────────────────┤
│                Original PDF Export Engine                   │
│           PyMuPDF crop / clip / merge                      │
├─────────────────────────────────────────────────────────────┤
│              SQLite + JSON Project Storage                  │
├─────────────────────────────────────────────────────────────┤
│                Provider Adapter Layer                       │
│    OpenAI / DeepSeek / Future Vision Providers              │
└─────────────────────────────────────────────────────────────┘
```

---

# 5. 技术选型

## 5.1 Python

Python 用于：

- 应用逻辑。
- PDF 读取。
- 页面分析。
- OCR 调度。
- AI API 调用。
- JSON Schema 校验。
- 数据持久化。
- PDF 导出。
- PySide6 UI。

## 5.2 UI：PySide6

推荐 PySide6。

原因：

- Python 原生绑定。
- 桌面应用成熟。
- 支持高 DPI。
- 支持列表、树、GraphicsView、自绘框选等复杂 UI。
- 后期可以实现拖动题目边界。

不得为了 UI 引入大型 JavaScript 前端，除非后期确实需要 Web 版本。

## 5.3 PDF：PyMuPDF

推荐作为默认 PDF 核心引擎。

职责：

- 打开 PDF。
- 读取页数。
- 获取页面尺寸。
- 提取原生文本和文本块坐标。
- 页面渲染。
- 裁剪区域。
- 创建新 PDF。
- 插入原页面区域。
- 保存导出的 PDF。

## 5.4 OCR

推荐 PaddleOCR 作为可选 OCR 后端。

原则：

> OCR 只是辅助结构分析，不是最终输出源。

OCR 输出至少包含：

```json
{
  "text": "17．设函数...",
  "bbox": [105, 342, 850, 421],
  "confidence": 0.98,
  "page_index": 4
}
```

## 5.5 AI API

定义统一 Provider 接口：

```python
class VisionModelProvider(ABC):
    @abstractmethod
    def analyze_pages(self, request: VisionAnalysisRequest) -> VisionAnalysisResult:
        ...
```

第一期实现：

- OpenAI Provider
- DeepSeek Provider

以后可添加：

- Gemini
- Anthropic
- 其他 OpenAI-compatible Provider

不要在业务层直接调用某个模型 SDK。

## 5.6 数据校验

推荐：Pydantic + JSON Schema。

所有 AI 响应必须：

```text
API Response
 ↓
JSON parse
 ↓
Pydantic validation
 ↓
Schema validation
 ↓
Range validation
 ↓
Coordinate validation
 ↓
Logical validation
```

## 5.7 数据库

第一版使用 SQLite。

不需要 Redis、PostgreSQL 或服务器数据库。

---

# 6. AI 的职责边界

## 6.1 AI 负责什么

AI 负责：

- 判断页面属于试卷还是其他内容。
- 识别题号。
- 判断题号是否属于新题开始位置。
- 判断题目结束位置。
- 判断题目是否跨页。
- 判断两个题目是否属于同一题。
- 判断是否存在异常排版。
- 判断题目类型。
- 对边界进行视觉二次校验。
- 给出置信度。

## 6.2 AI 不负责什么

AI 不负责：

- 最终 PDF 裁剪。
- PDF 坐标换算。
- 页面顺序控制。
- 用户选择。
- 最终文件生成。
- 直接修改原 PDF。
- 自由生成最终题目文本。

---

# 7. “特殊格式”——ExamSplit JSON Protocol

这是项目最重要的接口之一。

模型不得返回普通自然语言格式作为主要结果。

必须要求模型返回 JSON。

## 7.1 顶层结构

```json
{
  "schema_version": "1.0",
  "document": {
    "title": "",
    "subject": "数学一",
    "year": 2025,
    "page_count": 12
  },
  "pages": [],
  "questions": [],
  "warnings": []
}
```

## 7.2 Question 结构

```json
{
  "question_id": "q001",
  "display_number": "1",
  "question_type": "choice",
  "segments": [
    {
      "page_index": 0,
      "normalized_bbox": [
        0.04,
        0.08,
        0.96,
        0.25
      ]
    }
  ],
  "start_anchor": {
    "page_index": 0,
    "normalized_point": [0.04, 0.08]
  },
  "end_anchor": {
    "page_index": 0,
    "normalized_point": [0.96, 0.25]
  },
  "continuation": false,
  "confidence": 0.98,
  "review_required": false,
  "reason_codes": []
}
```

## 7.3 reason_codes

示例：

```text
LOW_OCR_CONFIDENCE
AMBIGUOUS_QUESTION_NUMBER
CROSS_PAGE
MULTI_COLUMN_LAYOUT
IMAGE_HEAVY
BOUNDARY_ESTIMATED
MODEL_DISAGREEMENT
POSSIBLE_MISSED_QUESTION
POSSIBLE_DUPLICATE
```

## 7.4 为什么使用 normalized_bbox

不能要求所有 AI 都返回固定像素坐标。

应该让模型返回：

```text
0~1 的归一化坐标
```

例如：

```json
[0.05, 0.20, 0.95, 0.45]
```

表示：

```text
x1 = 5%
 y1 = 20%
x2 = 95%
y2 = 45%
```

本地根据页面真实尺寸和实际渲染尺寸换算。

这样可避免：

- DPI 不一致。
- 图片缩放。
- 不同模型图片尺寸不同。
- 不同 API 图片预处理造成的尺寸变化。

---

# 8. PDF 坐标系统设计

必须明确区分三个坐标系统：

```text
A. PDF Coordinate
B. Rendered Image Coordinate
C. AI Normalized Coordinate
```

## 8.1 AI 坐标

例如：

```text
[x1, y1, x2, y2] = [0.1, 0.2, 0.9, 0.5]
```

## 8.2 图片坐标

如果图片大小：

```text
2048 × 2732
```

转换：

```python
image_x1 = 0.1 * 2048
image_y1 = 0.2 * 2732
image_x2 = 0.9 * 2048
image_y2 = 0.5 * 2732
```

## 8.3 PDF 坐标

通过页面宽高比例转换为 PyMuPDF 坐标。

不得直接假设：

```text
图片像素 = PDF point
```

## 8.4 坐标必须经过安全扩展

AI 识别出的区域可能刚好贴近字符。

因此本地必须添加 padding：

```text
left   = x1 - padding_x
right  = x2 + padding_x
top    = y1 - padding_y
bottom = y2 + padding_y
```

padding 不是固定像素，应以 PDF point 或页面百分比配置。

例如默认：

```text
horizontal = 页面宽度 × 0.005
vertical   = 页面高度 × 0.004
```

并限制不得超出页面边界。

---

# 9. 核心识别算法

## 9.1 总体策略

不要完全依赖一个 AI 的 bbox。

采用：

```text
本地文本/布局分析
        ↓
候选题号
        ↓
AI 视觉确认
        ↓
AI 返回题目锚点
        ↓
本地推导题目区域
        ↓
AI 二次校验
        ↓
最终 Question Segment
```

## 9.2 题号优先策略

对数学试卷而言，题目通常具备明显题号：

```text
1.
2.
3.
...
17．
18．
```

因此第一阶段尽量提取题号，而不是直接要求 AI 画完整框。

例如：

```json
{
  "markers": [
    {
      "number": "1",
      "page_index": 0,
      "normalized_point": [0.05, 0.08]
    },
    {
      "number": "2",
      "page_index": 0,
      "normalized_point": [0.05, 0.31]
    }
  ]
}
```

## 9.3 本地推导题目边界

如果：

```text
Q1 起点 = Page 1, y=100
Q2 起点 = Page 1, y=600
```

则：

```text
Q1 = Page1, y=100 → Page1, y=600
```

最后一道题使用：

```text
最后题号起点 → 页面/区段结束位置
```

## 9.4 为什么“题号锚点 + 本地推导”优于全框预测

因为 AI 判断：

> “这里是第 17 题的开始”

通常比判断：

> “第 17 题完整矩形的底边准确到哪里”

更容易稳定。

因此系统默认采用：

> **Anchor First，Boundary Second。**

---

# 10. 跨页题目处理

## 10.1 典型情况

```text
Page 3
-----------------
第5题
题干...
计算...

Page 4
-----------------
继续上一题...
...
第6题
```

AI 应返回：

```json
{
  "question_id": "q005",
  "continuation": true,
  "segments": [
    {
      "page_index": 2,
      "normalized_bbox": [0.04, 0.60, 0.96, 1.00]
    },
    {
      "page_index": 3,
      "normalized_bbox": [0.04, 0.00, 0.96, 0.22]
    }
  ]
}
```

## 10.2 本地处理

一个 Question 可以拥有多个 Segment。

```text
Question
 ├── Segment 1
 ├── Segment 2
 └── Segment 3
```

导出时按 Segment 顺序写入。

## 10.3 禁止把跨页题目复制成两个题目

例如：

错误：

```text
Q5
Q5-continued
```

正确：

```text
Q5
 ├── page 3
 └── page 4
```

---

# 11. 多模型验证机制

由于用户明确优先考虑准确度，推荐支持：

```text
单模型模式
双模型模式
三阶段验证模式
```

## 11.1 单模型模式

```text
PDF
 ↓
GPT
 ↓
本地校验
```

适合快速使用。

## 11.2 双模型模式

```text
               PDF
                │
       ┌────────┴────────┐
       ↓                 ↓
     GPT             DeepSeek
       ↓                 ↓
   Result A          Result B
       └────────┬────────┘
                ↓
          Consensus Engine
                ↓
          Final Question
```

## 11.3 冲突判定

例如：

```text
GPT:
Q5 Page4 y=0.73

DeepSeek:
Q5 Page4 y=0.74
```

属于小差异。

如果：

```text
GPT:
Q5 在 Page4~5

DeepSeek:
Q5 只在 Page4
```

则：

```text
review_required = true
reason_codes += MODEL_DISAGREEMENT
```

## 11.4 不强制要求多数投票

不同模型并不一定具有独立错误。

Consensus Engine 应采用：

- 页面一致性。
- 题号连续性。
- 坐标相交率。
- OCR marker 一致性。
- 模型置信度。
- 文本块边界。
- 跨页逻辑。

进行综合评分。

---

# 12. 本地一致性检查

模型结果返回后，必须运行本地逻辑验证。

## 12.1 坐标范围检查

必须满足：

```text
0 <= x1 < x2 <= 1
0 <= y1 < y2 <= 1
```

否则结果无效。

## 12.2 题号连续性检查

例如 AI 返回：

```text
1, 2, 4, 5
```

程序应提示：

```text
可能缺失 Q3
```

不能自动判定 Q3 一定存在，但应进入审查列表。

## 12.3 重叠检查

如果：

```text
Q1 bbox 与 Q2 bbox 高度重叠 60%
```

应触发异常。

## 12.4 页面方向检查

检测：

- 正常竖向。
- 横向页面。
- 旋转页面。

统一转换到逻辑坐标后再处理。

## 12.5 题目面积异常检查

例如：

```text
Q1 占页面 2%
Q2 占页面 85%
```

即使 AI 给出高置信度，也应触发审查。

---

# 13. AI Prompt 设计

Prompt 必须明确告诉模型：

1. 你是“试卷版面分析器”。
2. 不要解题。
3. 不要重写题目。
4. 不要生成 Markdown。
5. 只输出 JSON。
6. 题目边界优先基于题号、视觉分隔和上下文。
7. 跨页题目必须合并。
8. 不确定时降低 confidence，而不是猜得很确定。
9. 坐标必须是归一化 0~1。
10. 所有页面都必须考虑。

## 13.1 基础 Prompt

```text
你是考试试卷版面结构分析器。

你的任务不是解题，也不是重新转录试题。

你的任务是：
1. 识别页面中的题号。
2. 判断每个题号是否代表一道独立题目。
3. 判断题目的开始位置和结束位置。
4. 判断题目是否跨页。
5. 给出每道题在页面中的归一化坐标。
6. 输出严格 JSON。

不要修改题目内容。
不要省略页面。
不要把题目转换成 Markdown。
不要输出额外说明。
如果不确定，请降低 confidence 并设置 review_required=true。
```

## 13.2 输出要求

模型必须返回：

```json
{
  "schema_version": "1.0",
  "questions": []
}
```

不得返回：

```text
以下是分析结果：
...
```

---

# 14. AI API Adapter

目录：

```text
app/ai/
├── base.py
├── openai_provider.py
├── deepseek_provider.py
├── provider_factory.py
├── prompt_manager.py
├── response_parser.py
└── exceptions.py
```

## 14.1 Base Provider

```python
from abc import ABC, abstractmethod

class VisionModelProvider(ABC):

    @abstractmethod
    def analyze_pages(self, request):
        raise NotImplementedError
```

## 14.2 Provider 不得直接修改 Question Model

错误：

```python
provider.analyze(pdf)
provider.questions.append(...)
```

正确：

```text
Provider
  ↓
Raw JSON
  ↓
Parsed DTO
  ↓
Validation
  ↓
Domain Model
```

这样可以避免 API 层与业务层耦合。

---

# 15. 页面发送策略

不能一开始就把整套 PDF 全部发送给 AI。

推荐采用批次：

```text
页面 1~2
页面 3~4
页面 5~6
...
```

然后再用一个全局分析步骤整合。

## 15.1 第一阶段：独立页面分析

输入：

- 页面截图。
- OCR 文本块。
- 页面尺寸。
- 页码。

输出：

- 题号 markers。
- 页面类型。
- 候选边界。

## 15.2 第二阶段：上下文合并

例如分析：

```text
Page 3
Page 4
```

向模型补充：

```text
上一页最后出现 Q5
下一页没有新题号
```

让 AI 判断是否为 Q5 延续。

## 15.3 第三阶段：全局一致性验证

模型输入一个轻量结构：

```text
Page 1: Q1 Q2 Q3
Page 2: continuation, Q4
Page 3: Q5
...
```

检查：

- 是否缺号。
- 是否重复。
- 是否跨页误切。
- 是否有明显异常。

---

# 16. PDF 输入预处理

## 16.1 文件校验

导入时检查：

- 扩展名。
- 文件大小。
- 是否可打开。
- 页数。
- 是否加密。
- 是否损坏。

## 16.2 页面类型判断

至少分类：

```text
TEXT_PDF
IMAGE_PDF
MIXED_PDF
```

## 16.3 原生文本优先

优先：

```python
page.get_text("dict")
```

获取：

- block
- line
- span
- bbox
- font size
- font name

如果文字太少或结构异常，再启用 OCR。

## 16.4 页面渲染

AI 视觉分析建议优先 150~250 DPI。

本地裁剪不应依赖截图，而是依赖原 PDF。

因此：

```text
AI 图像质量
≠
最终输出质量
```

AI 图像只是分析材料。

最终输出必须来自原 PDF。

---

# 17. Question Domain Model

建议使用 Pydantic 或 dataclass。

```python
class QuestionSegment:
    page_index: int
    normalized_bbox: tuple[float, float, float, float]
    pdf_bbox: tuple[float, float, float, float] | None

class Question:
    question_id: str
    number: str
    question_type: str | None
    segments: list[QuestionSegment]
    confidence: float
    review_required: bool
    selected: bool
    user_modified: bool
```

## 17.1 Question 状态

```text
DETECTED
VALIDATED
REVIEW_REQUIRED
USER_CONFIRMED
USER_MODIFIED
SELECTED
EXPORTED
```

---

# 18. SQLite 数据库设计

## 18.1 projects

```sql
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    source_pdf TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

## 18.2 pages

```sql
CREATE TABLE pages (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    page_index INTEGER NOT NULL,
    width REAL NOT NULL,
    height REAL NOT NULL,
    page_type TEXT,
    thumbnail_path TEXT,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);
```

## 18.3 questions

```sql
CREATE TABLE questions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    display_number TEXT NOT NULL,
    question_type TEXT,
    confidence REAL NOT NULL,
    review_required INTEGER NOT NULL DEFAULT 0,
    selected INTEGER NOT NULL DEFAULT 0,
    sort_order INTEGER NOT NULL,
    user_modified INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);
```

## 18.4 question_segments

```sql
CREATE TABLE question_segments (
    id TEXT PRIMARY KEY,
    question_id TEXT NOT NULL,
    page_index INTEGER NOT NULL,
    x1 REAL NOT NULL,
    y1 REAL NOT NULL,
    x2 REAL NOT NULL,
    y2 REAL NOT NULL,
    user_modified INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(question_id) REFERENCES questions(id)
);
```

## 18.5 ai_runs

```sql
CREATE TABLE ai_runs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_hash TEXT,
    input_hash TEXT,
    raw_response_path TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);
```

---

# 19. 缓存机制

因为 API 调用可能收费，所以必须缓存。

核心原则：

> 相同 PDF + 相同页面 + 相同模型 + 相同 Prompt 版本，不重复调用。

缓存键建议：

```text
SHA256(
    pdf_hash
    + page_index
    + image_hash
    + provider
    + model
    + prompt_version
    + schema_version
)
```

缓存内容：

```text
raw response
parsed result
validation result
```

---

# 20. 项目文件结构

```text
exam_split_ai/
│
├── app/
│   ├── main.py
│   │
│   ├── ui/
│   │   ├── main_window.py
│   │   ├── project_panel.py
│   │   ├── question_list.py
│   │   ├── pdf_viewer.py
│   │   ├── boundary_editor.py
│   │   ├── settings_dialog.py
│   │   └── export_dialog.py
│   │
│   ├── ai/
│   │   ├── base.py
│   │   ├── openai_provider.py
│   │   ├── deepseek_provider.py
│   │   ├── provider_factory.py
│   │   ├── prompt_manager.py
│   │   ├── response_parser.py
│   │   └── exceptions.py
│   │
│   ├── pdf/
│   │   ├── reader.py
│   │   ├── renderer.py
│   │   ├── text_extractor.py
│   │   ├── coordinate.py
│   │   ├── cropper.py
│   │   └── exporter.py
│   │
│   ├── ocr/
│   │   ├── base.py
│   │   └── paddleocr_backend.py
│   │
│   ├── detection/
│   │   ├── marker_detector.py
│   │   ├── boundary_resolver.py
│   │   ├── cross_page_resolver.py
│   │   ├── consistency.py
│   │   └── confidence.py
│   │
│   ├── models/
│   │   ├── document.py
│   │   ├── page.py
│   │   ├── question.py
│   │   ├── segment.py
│   │   └── ai_result.py
│   │
│   ├── storage/
│   │   ├── database.py
│   │   ├── repositories.py
│   │   └── cache.py
│   │
│   └── services/
│       ├── project_service.py
│       ├── analysis_service.py
│       ├── review_service.py
│       ├── selection_service.py
│       └── export_service.py
│
├── prompts/
│   ├── detect_markers.txt
│   ├── resolve_boundaries.txt
│   ├── verify_cross_page.txt
│   └── global_consistency.txt
│
├── schemas/
│   └── exam_split_v1.json
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── golden/
│
├── sample/
│
├── data/
│   ├── cache/
│   ├── thumbnails/
│   └── projects/
│
├── AGENTS.md
├── README.md
├── pyproject.toml
└── .env.example
```

---

# 21. UI 设计

## 21.1 主界面

```text
┌────────────────────────────────────────────────────────────────┐
│ ExamSplit AI                                                   │
├────────────────────────────────────────────────────────────────┤
│ 文件 | 分析 | 项目 | 设置 | 帮助                               │
├───────────────┬──────────────────────────────┬───────────────┤
│ 题目列表       │ PDF 预览                      │ 题目信息       │
│               │                              │               │
│ ☑ Q1          │     ┌──────────────────┐     │ Q1            │
│ ☑ Q2          │     │                  │     │ 类型：选择题   │
│ ☐ Q3          │     │      试卷内容     │     │ 页码：1        │
│ ☐ Q4          │     │                  │     │ 置信度：98%   │
│ ☑ Q5          │     └──────────────────┘     │ 状态：正常     │
│               │                              │               │
│ [全选]        │                              │ [编辑边界]    │
│ [反选]        │                              │ [确认]        │
│ [仅选择...]   │                              │               │
├───────────────┴──────────────────────────────┴───────────────┤
│ 已识别 23 题 | 已选 8 题 | 待检查 2 题        [导出选中题目] │
└────────────────────────────────────────────────────────────────┘
```

## 21.2 PDF 预览控件

必须支持：

- 缩放。
- 平移。
- 上一页/下一页。
- 页码跳转。
- 显示题目区域矩形。
- 高亮当前题目。
- 调整 bbox。
- 显示多个 segment。

## 21.3 边界编辑

用户点击“编辑边界”后进入编辑状态：

```text
┌───────────────────────────────┐
│     ┌────────────────────┐    │
│     │                    │    │
│     │       第17题        │    │
│     │                    │    │
│     └────────────────────┘    │
│      ↑                ↑       │
│      可拖动控制点              │
└───────────────────────────────┘
```

支持：

- 上边界拖动。
- 下边界拖动。
- 左右边界拖动。
- 整体移动。
- 重置到 AI 结果。
- 保存修改。

---

# 22. PDF 导出设计

## 22.1 核心原则

导出必须优先使用源 PDF 内容。

不要：

```text
AI文字 → 重新排版 → PDF
```

而是：

```text
Source PDF
 ↓
Crop / Clip
 ↓
New PDF
```

## 22.2 两种导出策略

### 模式 A：裁剪式导出

每道题对应一个或多个原始 PDF 矩形区域。

按照题目顺序创建新的 PDF 页面。

优点：

- 原始清晰度高。
- 数学公式保持原样。
- 图片不丢失。

### 模式 B：标准纸张重排

例如用户指定：

```text
A4
边距 10mm
```

将题目区域缩放后排列在 A4 页面中。

这是推荐的默认输出形式，因为方便打印。

## 22.3 输出模式

提供：

```text
原尺寸裁剪
A4 单题一页
A4 自动紧凑排版
```

第一版至少实现：

> **A4 单题一页**

后续增加自动紧凑排版。

---

# 23. 导出算法

伪代码：

```python
def export_questions(project, selected_questions, output_path):
    src = fitz.open(project.source_pdf)
    out = fitz.open()

    for question in selected_questions:
        for segment in question.segments:
            src_page = src[segment.page_index]
            rect = normalized_to_pdf_rect(
                src_page,
                segment.normalized_bbox,
            )

            rect = add_padding(src_page, rect)

            page = out.new_page(width=A4_WIDTH, height=A4_HEIGHT)

            target = calculate_fit_rect(
                source_rect=rect,
                target_page=page.rect,
                margin=MM10,
            )

            page.show_pdf_page(
                target,
                src,
                segment.page_index,
                clip=rect,
            )

    out.save(output_path)
```

具体 API 使用必须根据最终 PyMuPDF 版本验证，但架构必须保持上述职责分离。

---

# 24. PDF 导出中的特殊问题

## 24.1 页眉/页脚

题目区域不能误包含过多重复页眉页脚。

但第一版宁可多一点，也不要裁掉题目内容。

因此默认策略：

> **宁可轻微包含题目外空白，不要截断题目。**

## 24.2 页码

如果页码位于区域底部且明显属于页面元素，可以根据规则裁掉。

但不能因为页码判断错误而裁掉题目内容。

## 24.3 两栏试卷

两栏布局是重点测试对象。

必须注意：

```text
左栏 Q1
右栏 Q2
```

不是：

```text
Q1
 ↓
 Q2
```

必须引入页面阅读顺序。

## 24.4 图片型题目

题目可能包含：

- 几何图。
- 曲线图。
- 表格。
- 坐标图。

必须保留。

## 24.5 题目内图片

bbox 必须覆盖：

```text
题干 + 公式 + 图片 + 选项
```

不能只覆盖 OCR 文字。

---

# 25. 页面阅读顺序

页面中的元素需要建立 Reading Order。

建议排序：

```text
page_index
→ column_index
→ y_position
→ x_position
```

但不能只依赖简单排序。

两栏页面需要先检测 column。

后期可基于文本块 x 坐标聚类实现。

---

# 26. 低置信度系统

不能只看 AI 自己返回的 confidence。

需要综合：

```text
model_confidence
+ OCR_confidence
+ marker_consistency
+ bbox_validity
+ question_sequence
+ cross_page_consistency
+ overlap_score
```

最终得到：

```text
final_confidence
```

## 26.1 推荐等级

```text
0.90 ~ 1.00  高
0.75 ~ 0.89  中
< 0.75       低
```

规则不是固定死值，可配置。

## 26.2 UI

```text
Q1   ● 高
Q2   ● 高
Q3   ▲ 中
Q4   ! 低
```

低置信度题目默认：

```text
review_required = true
```

---

# 27. 人工修正工作流

## 27.1 修改边界

```text
原 AI 结果
 ↓
进入编辑模式
 ↓
拖动边界
 ↓
实时预览
 ↓
确认
 ↓
user_modified=true
```

## 27.2 合并题目

```text
Q17
Q18
```

选择：

```text
合并
```

结果：

```text
Q17+Q18
```

并允许用户修改最终显示名称。

## 27.3 拆分题目

允许用户在一个 bbox 中创建两个 Question。

## 27.4 手工添加题目

用户可以：

```text
新建题目
 ↓
选择页面
 ↓
拖出矩形
 ↓
填写题号
 ↓
保存
```

---

# 28. API Key 与隐私设计

推荐本地客户端模式：

```text
用户电脑
├── PDF
├── API Key
├── SQLite
└── 缓存
```

默认不建设项目服务器。

## 28.1 API Key 保存

不要把 API Key 写入：

- SQLite 普通字段。
- 日志。
- Git。
- 项目导出 JSON。

建议使用系统凭据存储：

- Windows Credential Manager。
- macOS Keychain。
- Linux Secret Service。

第一版如果实现困难，可以使用本地配置文件，但必须：

- 加入 `.gitignore`。
- 文件权限尽可能收紧。
- UI 提供删除 Key。

## 28.2 PDF 隐私

程序应明确提示：

> 页面图像/文本将按当前 AI 服务配置发送到对应模型服务商。

本地软件不得默默上传完整 PDF。

默认只发送当前分析所需要的页面数据。

---

# 29. API 调用策略

## 29.1 可配置模型

```text
Provider: OpenAI
Model: xxx

Provider: DeepSeek
Model: xxx
```

不要把具体型号写死在业务层。

## 29.2 重试

针对：

- 网络错误。
- 超时。
- 429。
- 5xx。
- JSON 解析失败。

实现指数退避。

## 29.3 JSON 失败自动修复

如果 AI 返回非法 JSON：

```text
第一次：标准 JSON 请求
 ↓
解析失败
 ↓
第二次：发送原始响应 + 纠错提示
 ↓
仍失败
 ↓
第三次：标记 AI_RUN_FAILED
```

不要无限重试。

## 29.4 结构化输出优先

如果目标 Provider 支持 JSON Schema / Structured Outputs，应优先使用。

如果 Provider 不支持，则使用：

```text
Prompt + parser + validation + retry
```

---

# 30. AI Prompt 版本化

Prompt 必须带版本。

例如：

```text
marker_detection_v1
boundary_validation_v1
cross_page_v1
```

当 Prompt 修改时：

```text
prompt_version = v2
```

缓存自然失效。

---

# 31. 测试方案

## 31.1 Golden Dataset

建立真实测试数据集：

第一批至少：

```text
10 套考研数学真题
```

最好覆盖：

- 文本型 PDF。
- 扫描型 PDF。
- 双栏。
- 单栏。
- 公式密集型。
- 图片题。
- 跨页题。
- 页眉页脚明显。
- 题号格式不同。

## 31.2 必须记录人工标准答案

例如：

```json
{
  "question_number": "17",
  "segments": [
    {
      "page": 5,
      "bbox": [0.05, 0.21, 0.95, 0.79]
    }
  ]
}
```

## 31.3 指标

### Question Detection Precision

识别出的题目中，有多少是真实题目。

### Question Detection Recall

真实题目中，有多少被识别出来。

### Boundary IoU

模型 bbox 与人工 bbox 的重叠程度。

```text
IoU = intersection / union
```

### Cross-page Accuracy

跨页题是否正确合并。

### Export Integrity

最终导出的 PDF 是否完整：

- 无裁切。
- 无缺页。
- 无顺序错误。
- 无空白页异常。

---

# 32. 测试分级

## 单元测试

测试：

- 坐标换算。
- bbox padding。
- overlap。
- normalized → PDF coordinate。
- question sorting。
- page merging。

## 集成测试

测试：

```text
PDF
→ AI JSON
→ Question Model
→ Export PDF
```

## Golden Test

固定测试 PDF + 固定期望结果。

AI 结果可能因模型变化而变化，所以 Golden Test 不应强制逐字符串一致，而应以：

- 题目数量。
- 题号。
- page range。
- Boundary IoU。
- 跨页关系。

为主要判断标准。

---

# 33. 日志系统

日志必须分级：

```text
DEBUG
INFO
WARNING
ERROR
```

## 33.1 必须记录

- PDF 打开。
- 页面数量。
- OCR 是否启用。
- AI Provider。
- AI model。
- request id（若有）。
- API 重试次数。
- JSON 验证结果。
- Question 数量。
- review_required 数量。
- 导出结果。

## 33.2 禁止记录

- API Key。
- 完整 PDF 内容。
- 不必要的用户隐私信息。

---

# 34. 错误处理

必须把异常分为：

```text
PDF_ERROR
OCR_ERROR
API_ERROR
MODEL_OUTPUT_ERROR
SCHEMA_ERROR
COORDINATE_ERROR
EXPORT_ERROR
USER_ACTION_ERROR
```

用户界面不要显示 Python traceback。

例如：

```text
无法分析当前页面。
原因：AI 返回的数据格式不符合要求。

[重试]
[切换模型]
[查看详细信息]
```

---

# 35. 性能设计

速度不是第一目标，但必须保持 UI 可用。

## 35.1 后台任务

所有耗时任务都不能阻塞主线程：

- PDF 渲染。
- OCR。
- API 调用。
- PDF 导出。

PySide6 使用：

- QThread。
- QRunnable / QThreadPool。
- Signal/Slot。

## 35.2 并发

API 请求可以限制并发：

```text
MAX_CONCURRENT_REQUESTS = 2
```

第一版宁可慢，也不要疯狂并发导致：

- 429。
- API 成本突然增加。
- 本地内存过高。

---

# 36. AI 成本控制

UI 显示预计：

```text
本次分析：12 页
预计 AI 请求：8 次
预计费用：未知/按 Provider 实时计算
```

如 Provider 无价格接口，则显示：

```text
请根据当前模型定价估算。
```

必须缓存已分析页面。

---

# 37. 项目保存格式

建议每个项目包含：

```text
project/
├── project.db
├── source.json
├── thumbnails/
├── ai_results/
└── metadata.json
```

源 PDF 可以由用户指定原路径，不必复制，以降低存储空间。

但必须记录：

```text
source_path
source_hash
```

当用户重新打开项目时，如果文件 hash 改变：

```text
源 PDF 已变化，需要重新分析。
```

---

# 38. 推荐的开发顺序

## Phase 0：工程骨架

目标：项目可启动。

任务：

1. 创建 Python 项目。
2. 配置 pyproject.toml。
3. 创建 app 目录。
4. 创建 PySide6 主窗口。
5. 配置日志。
6. 配置 SQLite。
7. 建立 AGENTS.md。

验收：

```text
python -m app.main
```

能正常启动窗口。

---

## Phase 1：PDF 读取与页面预览

目标：不接 AI，先把 PDF 基础能力做好。

任务：

1. 打开 PDF。
2. 获取页数。
3. 读取页面尺寸。
4. 获取文本。
5. 获取文本块坐标。
6. 页面渲染。
7. UI 显示页面。
8. 缩放。
9. 翻页。

验收：

用户可以浏览整份 PDF。

---

## Phase 2：PDF 坐标系统

目标：证明“图片坐标 → PDF 坐标”可靠。

任务：

1. normalized bbox。
2. PDF bbox。
3. padding。
4. 边界裁切。
5. 页面旋转适配。

验收：

给出任意 bbox，可以准确在 PDF 中裁剪对应区域。

---

## Phase 3：AI Provider

目标：成功调用一个多模态 API。

任务：

1. Provider interface。
2. OpenAI Provider。
3. DeepSeek Provider。
4. Prompt Manager。
5. JSON Parser。
6. Pydantic validation。
7. Retry。
8. Cache。

验收：

单页 PDF → JSON。

---

## Phase 4：题号识别

目标：不追求完整 bbox，先识别题号。

输入：

```text
页面图片
+
文本块
```

输出：

```text
1
2
3
4
...
```

并有坐标。

验收：

针对 10 个测试页面达到可接受的题号识别率。

---

## Phase 5：题目边界推导

目标：

```text
Question Marker
 ↓
Boundary Resolver
 ↓
Question Segment
```

实现：

- 同页边界。
- 跨页边界。
- 最后一题边界。
- 两栏页面。

---

## Phase 6：AI 二次校验

目标：

让 AI 检查本地推导结果。

输入：

```text
candidate questions
```

AI 返回：

```text
accept
reject
adjust
```

或者返回修正后的坐标。

---

## Phase 7：Question UI

实现：

- 题目列表。
- 勾选。
- 当前题预览。
- 低置信度标记。
- 状态。

---

## Phase 8：人工边界编辑

实现：

- 拖动。
- 保存。
- 重置。
- 添加。
- 删除。
- 拆分。
- 合并。

---

## Phase 9：PDF 导出

目标：

```text
勾选 Q1 Q3 Q7
 ↓
导出
 ↓
selected.pdf
```

测试：

- 单页题目。
- 跨页题目。
- 图片。
- 公式。
- 双栏。

---

## Phase 10：多模型一致性

加入：

```text
GPT
+
DeepSeek
+
Consensus Engine
```

并提供：

```text
[高准确度模式]
```

---

# 39. Agent Task 规范

每一个 Agent 任务都应该：

1. 明确输入。
2. 明确输出。
3. 明确验收条件。
4. 不跨越无关模块。
5. 尽量保证可独立测试。

示例：

```text
TASK: Implement coordinate.py

目标：
实现 normalized bbox → PDF Rect。

输入：
page.rect
normalized_bbox
padding

输出：
fitz.Rect

约束：
- 坐标不能超出页面。
- x1 < x2。
- y1 < y2。
- 必须支持旋转页面。

测试：
至少 10 个单元测试。
```

---

# 40. AGENTS.md 建议内容

项目根目录创建：

```text
AGENTS.md
```

建议：

```markdown
# ExamSplit AI Agent Rules

## Core Principle
AI identifies structure; local Python operates on the original PDF.

## Never
- Never regenerate final exam PDF from OCR text by default.
- Never trust raw model output without schema validation.
- Never modify the original PDF.
- Never hardcode one AI vendor into business logic.
- Never use fixed pixel coordinates as the persistent coordinate system.

## Always
- Use normalized coordinates in persisted AI results.
- Preserve source PDF page and segment references.
- Validate all model outputs.
- Make all AI results user-correctable.
- Write tests for coordinate transformations.
- Keep provider adapters isolated.

## Preferred Stack
Python + PySide6 + PyMuPDF + Pydantic + SQLite.

## Quality Priority
Accuracy > source fidelity > recoverability > speed.
```

---

# 41. 安全边界

## API Key

API Key 绝不能：

- 提交到 Git。
- 写日志。
- 写进截图。
- 写进导出 PDF。

## 文件路径

处理外部路径时必须避免：

- 路径遍历。
- 非法路径。
- 覆盖源 PDF。

## PDF

默认永远：

```text
read-only
```

导出创建新文件。

---

# 42. 版本兼容策略

第三方 API、模型名称和 SDK 接口都可能变化。

因此：

- 业务层不得直接依赖具体 SDK 数据结构。
- Provider 负责适配 SDK。
- Prompt 版本化。
- Schema 版本化。
- API Model Name 配置化。
- README 记录当前已验证的 Provider/Model。

例如：

```text
schema_version = 1.0
prompt_version = boundary_v2
provider = deepseek
model = configured_by_user
```

---

# 43. 未来扩展：规则缓存

用户长期处理同一种试卷模板时，可建立：

```text
Template Profile
```

例如：

```text
2020~2025 考研数学一某出版社排版
```

记录：

- 页眉位置。
- 页脚位置。
- 题号样式。
- 双栏规则。
- 默认 padding。
- 默认题目类型。

以后：

```text
规则预处理
 ↓
AI 只负责异常判断
```

可以明显减少 API 消耗。

---

# 44. 未来扩展：用户纠正数据

每次用户修正：

```text
AI Result
 ↓
User Correction
```

都应该保存：

```text
original_bbox
corrected_bbox
page
question_number
reason
```

形成自己的 Golden Dataset。

注意：

第一阶段不要直接“自动训练模型”。

先用于：

- 测试。
- 统计。
- 规则优化。
- Prompt 优化。

---

# 45. 关键架构决策总结

## 决策 1

**不训练自己的大模型。**

原因：

- 开发和维护成本高。
- 对项目核心价值没有必要。
- 云端多模态模型已经足够承担结构分析任务。

## 决策 2

**AI 输出 JSON，而不是自然语言。**

原因：

- 可解析。
- 可验证。
- 可缓存。
- 可测试。
- Provider 可替换。

## 决策 3

**保存 normalized bbox，而不是图片像素。**

原因：

- 与 DPI 解耦。
- 与图片缩放解耦。

## 决策 4

**题号锚点优先于完整 bbox。**

原因：

- 题号识别更容易稳定。
- 边界可由本地算法推导。

## 决策 5

**原 PDF 是最终内容源。**

原因：

- 数学公式不重新生成。
- 图片不重新编码。
- 字体和清晰度尽可能保持。

## 决策 6

**人工修正是正式功能，不是异常情况。**

原因：

- 真实世界 PDF 排版复杂。
- 即使高质量模型也存在误判。
- 用户可以用极低成本修正一个错误。

## 决策 7

**速度让位于准确率。**

支持：

- 多轮 AI。
- 二次校验。
- 双模型比较。
- 本地一致性分析。

---

# 46. MVP 最终验收标准

必须完成以下完整链路：

```text
用户选择一个考研数学 PDF
        ↓
程序读取 PDF
        ↓
提取页面内容
        ↓
渲染页面
        ↓
调用 OpenAI 或 DeepSeek 多模态 API
        ↓
返回严格 ExamSplit JSON
        ↓
本地验证 JSON
        ↓
识别题目
        ↓
生成题目区域
        ↓
用户看到题目列表
        ↓
用户可以勾选
        ↓
用户可以查看题目原图
        ↓
用户可以修正边界
        ↓
用户选择 Q1/Q5/Q17
        ↓
点击导出
        ↓
生成新的 A4 PDF
        ↓
PDF 内容来自原始 PDF
```

## 最终最低质量要求

对于经过人工检查的测试集，系统必须能够：

1. 正确识别绝大多数题目。
2. 正确处理常见跨页题目。
3. 不截断题目主体。
4. 不依赖 OCR 重新排版最终 PDF。
5. 允许用户快速修正错误。
6. 导出的 PDF 能直接打印。

---

# 47. 第一版推荐开发命令顺序

Agent 不要一次性生成整个项目。

按照以下顺序：

```text
1. Create project scaffold
2. Implement PDF loader
3. Implement PDF viewer
4. Implement coordinate engine
5. Implement OpenAI Provider interface
6. Implement DeepSeek Provider interface
7. Implement structured JSON schema
8. Implement marker detection prompt
9. Implement local boundary resolver
10. Implement cross-page resolver
11. Implement consistency engine
12. Implement question UI
13. Implement boundary editor
14. Implement PDF exporter
15. Implement SQLite persistence
16. Implement cache
17. Implement multi-model verification
18. Build golden tests
19. Package desktop application
```

每一步完成后必须先运行测试，再进入下一阶段。

---

# 48. 推荐 Python 依赖

第一版可以考虑：

```text
PySide6
PyMuPDF
pydantic
httpx
orjson
Pillow
jsonschema
platformdirs
keyring
pytest
pytest-qt
```

可选：

```text
paddleocr
numpy
opencv-python
```

除非确有需要，不要无目的引入大型依赖。

---

# 49. 最终产品形态

最终软件应该让用户感觉像一个普通的桌面工具，而不是一个复杂 AI 开发工具：

```text
打开 ExamSplit AI

↓

拖入试卷.pdf

↓

选择 AI 模型

[OpenAI ▼]

[高准确度模式 ☑]

↓

开始分析

↓

┌───────────────────────┐
│ ☑ 1 选择题             │
│ ☑ 2 选择题             │
│ ☐ 3 选择题             │
│ ☐ 4 选择题             │
│ ☑ 5 选择题             │
│ ...                    │
│ ☐ 17 解答题            │
└───────────────────────┘

↓

检查题目

↓

勾选需要的题

↓

导出

↓

数学一_精选题目.pdf
```

最终用户真正关心的不是：

> “你用了 GPT 还是 DeepSeek？”

而是：

> **“我能不能把 PDF 里的第 1、5、8、17 题选出来，然后得到一个可以直接打印的 PDF？”**

因此所有底层架构都必须围绕这个目标设计。

---

# 50. 项目一句话定义

> **ExamSplit AI 是一个以本地 PDF 原始内容为最终数据源、以云端多模态 AI 为试卷结构分析器、以 Python 为核心处理引擎的桌面应用，用于自动识别试卷题目边界，让用户选择题目并高保真导出为统一打印 PDF。**

---

# 51. Agent 最终执行原则

当 Agent 对项目进行任何开发时，应始终先问自己：

```text
我是在让 AI “理解试卷”吗？
还是在让 AI “重新生成试卷”？
```

必须选择前者。

正确架构：

```text
                AI
                 │
        理解 / 定位 / 验证
                 │
                 ▼
         Structured JSON
                 │
                 ▼
              Python
                 │
       坐标 / 校验 / 裁剪
                 │
                 ▼
          Original PDF
                 │
                 ▼
          Selected PDF
```

而不是：

```text
PDF
 ↓
OCR
 ↓
LLM 重写题目
 ↓
重新生成 PDF
```

前者是本项目的正式架构，后者默认禁止。

---

**文档结束。**
