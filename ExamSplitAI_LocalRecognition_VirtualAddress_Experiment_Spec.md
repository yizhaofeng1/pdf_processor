# ExamSplit AI —— 本地识别与虚拟地址寻题实验模块设计规格

**文档版本：** v1.0  
**文档性质：** 可直接交给 Antigravity / Coding Agent 执行的实验性开发规格  
**基础版本：** 以当前项目 `README.md` / 现有已完成功能为准  
**实验性质：** 独立、可回退、不破坏主流程的技术验证模块  
**目标：** 在不改造现有成熟云端识别链路的前提下，验证：

> **“虚拟地址分页 + 粗粒度区域寻址 + 局部高分辨率识别”是否可以让本地小型 VLM 完成可用的试卷题目定位，并降低对云端大模型的依赖。**

---

# 0. 给 Agent 的最高优先级指令

## 0.1 第一原则：不要破坏当前项目

当前项目已经具备成熟功能，包括但不限于：

- 现有 PDF 读取与解析。
- PyMuPDF 页面渲染。
- 原生 PDF 坐标处理。
- 当前云端多模态 AI Provider。
- AI JSON / Pydantic 校验。
- 题号识别。
- 题目边界推导。
- 跨页题目处理。
- 本地矢量文本审查。
- 题目列表与预览。
- 人工边界调整。
- PDF 导出。
- SQLite / 缓存。
- 多试卷及现有 UI。

**上述能力视为当前稳定基线。**

Agent 不得为了实验而重构、重写或迁移这些已有模块。

### 明确禁止

- 不得删除原有 AI Provider。
- 不得修改现有云端识别 Prompt 的默认行为。
- 不得改变现有 Question / Segment 数据结构的既有语义。
- 不得改变既有 PDF 导出逻辑。
- 不得让本地实验结果自动覆盖原有正式识别结果。
- 不得把实验模块直接塞进现有 `detection/` 核心算法而造成耦合。
- 不得为了本地模型强行引入 JavaScript 前端。
- 不得默认下载或捆绑大型模型权重。
- 不得把实验功能改成默认识别方式。

### 必须遵守

```text
现有正式功能 = 稳定基线
本地识别 = Experimental
虚拟地址算法 = Experimental
实验失败 = 可以一键回到原有云端识别
```

---

# 1. 当前项目基线

当前正式项目的核心思想是：

```text
PDF
 ↓
PyMuPDF 页面解析 / 渲染
 ↓
云端多模态 AI
 ↓
结构化结果
 ↓
本地坐标与边界计算
 ↓
跨页 / 一致性检查
 ↓
人工修正
 ↓
原始 PDF 高保真裁切导出
```

正式项目仍然保持：

> **AI 负责理解与定位，本地 Python 负责坐标计算、边界修正、PDF 裁剪和最终导出。**

当前项目已经采用归一化坐标作为 AI 结果的重要坐标表达方式，同时区分 PDF Coordinate、Rendered Image Coordinate、AI Normalized Coordinate。实验模块必须兼容这一理念，但**不要替换正式坐标系统**。

---

# 2. 本次实验真正要验证的问题

不要把实验目标定义为：

> “开发一个新的 PDF 拆题系统。”

而必须定义为：

> **验证小型本地 VLM 是否可以通过分层任务分解完成试卷题目定位。**

实验核心假设：

```text
直接方案：

整页 PDF
 ↓
小型 VLM
 ↓
题号 + 完整 bbox
```

可能存在：

- 空间定位误差较大。
- 连续坐标回归不稳定。
- 双栏 / 密集选择题容易混淆。
- 长页面上下文过重。
- 对模型参数规模要求较高。

实验方案：

```text
整页低分辨率
 ↓
虚拟地址空间
 ↓
小型 VLM 粗定位
 ↓
虚拟区域地址
 ↓
本地页表映射
 ↓
候选局部区域
 ↓
小型 VLM 局部精定位
 ↓
真实 PDF 坐标
 ↓
现有本地裁切 / 检查
```

核心验证：

```text
小模型 + 分层空间寻址
是否能够接近
大模型 + 整页直接定位
```

以及：

```text
Token 是否下降
错误率是否下降
局部定位是否更稳定
```

---

# 3. 实验模块名称

建议名称：

**Local Recognition (Experimental)**

中文 UI：

> **本地识别（实验）**

算法模块内部暂定名称：

> **Virtual Address Question Localization**

中文：

> **虚拟地址分页寻题**

简称：

> `VAQL`

如果后续实验结果不理想，可以随时删除或替换该模块。

---

# 4. 总体架构

正式系统：

```text
                     ExamSplit AI
                          │
             ┌────────────┴────────────┐
             │                         │
      Existing Cloud AI         Local Recognition
          正式路径                  实验路径
             │                         │
      原有 Provider              Experimental Module
             │                         │
             ▼                         ▼
       原有 Question Engine      Virtual Address Engine
             │                         │
             └────────────┬────────────┘
                          │
                     Review / Export
```

但实验阶段实际上应尽可能独立：

```text
PDF
 │
 ├─────────────── 正式云端路径
 │
 └─────────────── 本地实验路径
                          │
                   Virtual Address
                          │
                    Local VLM
                          │
                    Experiment Result
                          │
                 不自动覆盖正式结果
```

---

# 5. 建议新增目录

不要大规模修改现有目录。

新增：

```text
app/
└── experimental/
    ├── __init__.py
    └── local_recognition/
        ├── __init__.py
        ├── service.py
        ├── config.py
        ├── types.py
        ├── virtual_address.py
        ├── page_table.py
        ├── tiler.py
        ├── candidate_builder.py
        ├── local_refiner.py
        ├── prompt_builder.py
        ├── provider.py
        ├── result_store.py
        ├── metrics.py
        └── ui.py
```

实验 Prompt：

```text
prompts/
└── experimental/
    └── local_recognition/
        ├── coarse_address_v1.txt
        ├── local_refine_v1.txt
        └── verify_v1.txt
```

实验结果：

```text
data/
└── experiments/
    └── local_recognition/
        ├── runs/
        ├── crops/
        ├── results/
        └── metrics/
```

测试：

```text
tests/
└── experimental/
    └── local_recognition/
        ├── test_virtual_address.py
        ├── test_page_table.py
        ├── test_tiler.py
        ├── test_candidate_builder.py
        ├── test_parser.py
        └── test_metrics.py
```

---

# 6. 为什么实验模块必须独立

这是本次开发最重要的工程要求之一。

当前项目已经完成的正式逻辑应该继续作为 Baseline。

因此：

```text
正式代码
app/detection/
app/ai/
app/pdf/
app/models/
app/services/
```

原则上不动。

实验新增：

```text
app/experimental/local_recognition/
```

实验结果也不能直接写入正式 `Question` 数据。

推荐：

```python
class LocalRecognitionExperimentResult:
    run_id: str
    source_pdf_hash: str
    page_results: list
    question_candidates: list
    metrics: dict
    raw_model_outputs: list
```

只有在用户明确执行：

> “使用实验结果生成题目”

时，才允许通过一个明确的适配器转换：

```text
ExperimentResult
        ↓
Adapter
        ↓
Existing Question / Segment
```

而不是实验模块直接操作正式 Domain Model。

---

# 7. UI 接口设计

当前项目已有 AI Provider 选择机制。

在不破坏原 UI 的情况下增加：

```text
AI Provider / 识别方式
--------------------------------

OpenAI
DeepSeek
Gemini
Claude
GLM
...

-------------------------------
本地识别（实验）
```

当用户选择：

> **本地识别（实验）**

UI 只增加实验相关设置。

例如：

```text
识别方式：
[本地识别（实验） ▼]

本地模型：
[qwen-vl-xxx ▼]

Endpoint：
http://127.0.0.1:11434/v1

模式：
(●) 虚拟地址粗到细
( ) 直接本地 bbox（Baseline）

虚拟分页：
列数：4
行数：8

局部精修：
[✓] 启用

[开始实验识别]
```

注意：

**不要把“本地识别（实验）”伪装成正式稳定 Provider。**

UI 必须显示：

> ⚠ 实验功能：结果仅用于算法测试，不会自动替换正式识别结果。

---

# 8. 本地模型接入策略

## 8.1 第一阶段不要直接把模型权重打包进项目

本实验只是验证算法。

因此：

```text
ExamSplit AI
      ↓
Local VLM Endpoint
```

推荐兼容：

- Ollama OpenAI-compatible API。
- LM Studio OpenAI-compatible API。
- vLLM OpenAI-compatible API。
- 其他本地 OpenAI-compatible Vision Endpoint。

统一抽象：

```python
class LocalVisionProvider(ABC):

    @abstractmethod
    def analyze_image(self, request):
        raise NotImplementedError
```

配置：

```python
class LocalVisionConfig:
    endpoint: str
    model: str
    api_key: str | None
    timeout_seconds: int
```

这样以后可以把：

```text
小型 VLM A
小型 VLM B
小型 VLM C
```

全部作为实验对象，而无需改 VAQL 核心。

---

# 9. 虚拟地址空间定义

这是本实验的核心。

## 9.1 页面不是简单的“图片”

程序内部定义：

```text
Virtual Document Space
```

结构：

```text
Document
 ├── Page 0
 │    ├── R0C0
 │    ├── R0C1
 │    ├── R0C2
 │    ├── R0C3
 │    ├── R1C0
 │    └── ...
 │
 ├── Page 1
 └── ...
```

---

# 10. 虚拟地址格式

第一版采用：

```text
P{page}:R{row}:C{column}
```

例如：

```text
P03:R05:C02
```

表示：

```text
PDF 第 4 页（内部 page_index=3）
第 6 行
第 3 列
```

不要使用真正的物理内存概念作为代码命名，以避免误解。

这是：

> **逻辑地址 / 虚拟区域地址**

而不是 OS 意义上的内存地址。

---

# 11. 分页方式

第一版使用固定网格。

默认：

```text
rows = 8
columns = 4
```

因此每页：

```text
8 × 4 = 32 个虚拟区域
```

逻辑示意：

```text
┌────────┬────────┬────────┬────────┐
│ R0C0   │ R0C1   │ R0C2   │ R0C3   │
├────────┼────────┼────────┼────────┤
│ R1C0   │ R1C1   │ R1C2   │ R1C3   │
├────────┼────────┼────────┼────────┤
│ R2C0   │ R2C1   │ R2C2   │ R2C3   │
├────────┼────────┼────────┼────────┤
│ R3C0   │ R3C1   │ R3C2   │ R3C3   │
├────────┼────────┼────────┼────────┤
│ R4C0   │ R4C1   │ R4C2   │ R4C3   │
├────────┼────────┼────────┼────────┤
│ R5C0   │ R5C1   │ R5C2   │ R5C3   │
├────────┼────────┼────────┼────────┤
│ R6C0   │ R6C1   │ R6C2   │ R6C3   │
├────────┼────────┼────────┼────────┤
│ R7C0   │ R7C1   │ R7C2   │ R7C3   │
└────────┴────────┴────────┴────────┘
```

第一阶段不要做动态复杂分块。

固定网格主要用于验证：

> 离散虚拟寻址是否比直接连续 bbox 预测更稳定。

---

# 12. Page Table

建立：

```python
@dataclass
class VirtualRegion:
    page_index: int
    row: int
    col: int
    normalized_rect: tuple[float, float, float, float]
    pdf_rect: tuple[float, float, float, float]
```

页表：

```python
class VirtualPageTable:
    def resolve(self, address: VirtualAddress) -> VirtualRegion:
        ...
```

例如：

```text
P03:R05:C02
       ↓
normalized_rect
       ↓
pdf_rect
```

核心要求：

> **任何虚拟地址最终必须可以被确定性地映射到真实 PDF 坐标。**

模型不能参与这个映射。

---

# 13. 坐标映射

仍然遵循正式项目现有三层坐标理念：

```text
Virtual Address
        ↓
Normalized Coordinate
        ↓
PDF Coordinate
```

实验不得保存：

```text
固定像素坐标
```

作为长期结果。

---

# 14. 粗定位阶段

## 输入

本地程序生成：

```text
低分辨率整页图像
+
页面编号
+
虚拟网格参数
+
可选的本地文本块统计
```

建议初始渲染：

```text
120~160 DPI
```

实验的核心不是追求低清到无法识别。

必须保证：

> **题号与主要版面结构仍然可见。**

---

# 15. 粗定位 Prompt

文件：

```text
prompts/experimental/local_recognition/coarse_address_v1.txt
```

核心要求：

```text
你是考试试卷版面分析器。

当前页面已经被程序划分为规则虚拟区域。

你不需要输出像素坐标，也不要输出归一化 bbox。

你的任务只有：

1. 找出题号。
2. 判断题目属于哪些虚拟区域。
3. 判断题目是否跨越多个区域。
4. 判断是否可能跨页。
5. 不需要精确描述题目底部。
6. 不要解题。
7. 不要重新转录题目。
8. 如果不确定，降低 confidence。

虚拟地址格式：

P{page}:R{row}:C{column}

请只返回 JSON。
```

---

# 16. 粗定位输出 Schema

第一版：

```json
{
  "schema_version": "vaql-coarse-v1",
  "page_index": 3,
  "questions": [
    {
      "question_number": "17",
      "regions": [
        "P03:R04:C00",
        "P03:R04:C01",
        "P03:R05:C00",
        "P03:R05:C01"
      ],
      "confidence": 0.91,
      "cross_page": false
    }
  ]
}
```

注意：

> 这个阶段绝对不要要求模型输出精确 bbox。

---

# 17. 为什么要让模型输出“区域集合”

一个题可能跨越一个虚拟区域：

```text
R4C0
```

也可能跨多个：

```text
R4C0
R4C1
R5C0
R5C1
```

因此：

```python
regions: list[VirtualAddress]
```

而不是：

```python
region: VirtualAddress
```

这样可以避免网格太粗而导致信息截断。

---

# 18. 候选区域构建

模型粗定位结束后：

```text
AI：

Q17
P03:R04:C00
P03:R04:C01
P03:R05:C00
P03:R05:C01
```

本地程序：

```text
虚拟地址
 ↓
Page Table
 ↓
合并所有区域
 ↓
生成 Candidate Rect
```

例如：

```text
┌────────────────────────────┐
│            Q17             │
│                            │
└────────────────────────────┘
```

必须加入少量安全扩展：

```text
padding = configurable
```

但不要覆盖整页。

---

# 19. 邻域扩展

为了防止粗定位区域切断题目边界，候选区域需要支持：

```text
Neighbor Expansion
```

例如：

```text
模型返回：

R4C0
R4C1
```

本地程序可以产生：

```text
R3C0
R3C1
R4C0
R4C1
R5C0
R5C1
```

但是不要默认无限扩张。

第一版：

```text
neighbor_radius = 1
```

作为可配置参数。

---

# 20. 防止跨题污染

这是本实验必须验证的问题。

如果：

```text
Q17 → R4C0 R4C1
Q18 → R5C0 R5C1
```

粗定位候选区域可能发生重叠。

因此 Candidate Builder 必须计算：

```text
candidate_overlap
```

如果两个题候选区域高度重叠：

```text
Q17 <-> Q18
```

则进入：

```text
LOCAL_VERIFY_REQUIRED
```

不要直接交给导出。

---

# 21. 局部精定位阶段

粗定位之后：

```text
Candidate Rect
 ↓
从原始 PDF / 高 DPI 页面渲染局部图
 ↓
Local VLM
```

注意：

> 局部图是来自原始 PDF，而不是把低清截图再次放大。

推荐：

```text
200~300 DPI
```

或者使用能够保证小字体可见的动态尺寸。

---

# 22. 局部精定位任务

局部模型只处理：

> “这一块里，第 17 题真实边界在哪里？”

输出：

```json
{
  "schema_version": "vaql-local-v1",
  "question_number": "17",
  "bbox": [0.03, 0.08, 0.98, 0.94],
  "confidence": 0.94,
  "boundary_complete": true,
  "needs_neighbor": false
}
```

注意：

局部阶段允许输出：

```text
normalized bbox
```

因为此时上下文已经很小。

---

# 23. 局部精定位不是最终 PDF 坐标

局部 bbox 必须经过：

```text
Local normalized bbox
        ↓
Candidate image coordinate
        ↓
PDF coordinate
```

最终仍然交给已有 PDF Coordinate Engine。

---

# 24. 与现有正式算法连接方式

推荐：

```text
Local Experiment Result
        ↓
Experimental Adapter
        ↓
Existing Coordinate / Validation Utilities
        ↓
Preview Only
```

允许复用：

- 现有坐标转换函数。
- 现有 bbox 安全范围检查。
- 现有 padding。
- 现有 PDF preview。
- 现有导出预览。

但不要修改这些函数的既有语义。

如果必须修改正式模块：

> 优先新增函数，而不是改变现有函数默认行为。

---

# 25. 实验模式建议提供两个子模式

为了比较算法效果，本地识别实验必须至少支持：

## A. Direct Local Baseline

```text
整页低 / 中分辨率
 ↓
Local VLM
 ↓
直接 bbox
```

## B. Virtual Address Mode

```text
整页低分辨率
 ↓
Virtual Address
 ↓
Page Table
 ↓
Local Crop
 ↓
Local VLM
 ↓
bbox
```

这样才能真正验证：

> 虚拟地址机制是否带来收益。

否则只能证明：

> 小模型做局部识别可能有效。

---

# 26. 推荐完整实验流水线

```text
用户加载 PDF
        │
        ▼
读取 PDF 页面
        │
        ▼
建立 Virtual Page Table
        │
        ▼
低分辨率整页渲染
        │
        ▼
Local VLM / Coarse Address
        │
        ▼
题号 + Virtual Addresses
        │
        ▼
Pydantic / Schema Validation
        │
        ▼
Candidate Builder
        │
        ├── Neighbor Expansion
        ├── Overlap Check
        └── Cross Page Candidate
        │
        ▼
局部高 DPI Crop
        │
        ▼
Local VLM / Fine BBox
        │
        ▼
Local Result Validation
        │
        ▼
现有 Coordinate Engine
        │
        ▼
Experimental Question Segments
        │
        ├── 仅预览
        ├── 统计指标
        └── 可选转正式结果
```

---

# 27. 跨页处理

实验第一版只需要支持基础跨页识别。

例如：

```text
Page 3:
Q17
...
```

```text
Page 4:
...
...
Q18
```

粗定位：

```text
Q17:
P02:R06:C00
P02:R06:C01
P03:R00:C00
P03:R00:C01
```

本地算法根据：

- 页码连续。
- 虚拟区域靠近页面边缘。
- 下一页没有新的题号。
- 局部模型结果。
- OCR / 原生文本 marker。

进行判断。

不需要在本实验中重新发明 Cross Page Resolver。

优先调用已有能力或建立实验包装层。

---

# 28. 题号识别策略

第一版可以保留双路径：

```text
Path A:
Local VLM → question number

Path B:
existing native text / OCR → candidate marker
```

然后：

```text
Local VLM marker
+
Local PDF text marker
```

进行一致性检查。

这样可以验证：

> 小模型是否真的能理解题目结构，而不仅仅是被题号 OCR 带着走。

---

# 29. 可选：让本地模型不负责题型

第一版实验不要一次给本地小模型过多任务。

推荐：

```text
粗阶段：
只做题号 + 区域

精阶段：
只做题目边界

题型：
复用现有本地 / 云端分类能力
```

原因：

实验首先要验证的是：

> **空间定位**

而不是：

> 小模型是否能完成全部 ExamSplit AI 功能。

---

# 30. 实验结果必须与正式结果并列

UI 推荐：

```text
正式识别结果
----------------
Q1
Q2
Q3
...

实验识别结果
----------------
Q1
Q2
Q3
...

[对比]
```

或者：

```text
当前题：
Q17

正式：
bbox A

实验：
bbox B

[显示差异]
```

这样可以直接比较。

---

# 31. 实验对比指标

必须记录以下指标：

## 题目级

```text
Question Detection Precision
Question Detection Recall
```

## 边界级

```text
Boundary IoU
```

## 跨页

```text
Cross-page Accuracy
```

## 错误

```text
Missed Question Count
Duplicate Question Count
Over-Crop Count
Under-Crop Count
```

## 模型资源

```text
Input Image Count
Local VLM Call Count
Approximate Tokens
Latency
```

## 系统级

```text
End-to-End Success Rate
```

---

# 32. 必须额外记录“模型规模”

实验重点之一是验证：

> 是否能够降低对大模型规模的依赖。

因此每次 run 记录：

```json
{
  "provider": "local",
  "model": "xxx",
  "parameter_scale": "0.5B",
  "mode": "virtual_address",
  "rows": 8,
  "columns": 4
}
```

如果模型参数规模未知：

```text
parameter_scale = null
```

不能猜测。

---

# 33. 实验 Run Schema

建议：

```python
class ExperimentRun:
    run_id: str
    source_pdf_hash: str
    model_provider: str
    model_name: str
    model_parameter_scale: str | None
    mode: str
    grid_rows: int
    grid_columns: int
    coarse_resolution: tuple[int, int]
    local_resolution: tuple[int, int]
    prompt_version: str
    start_time: str
    end_time: str
```

---

# 34. 实验结果保存

默认保存：

```text
data/experiments/local_recognition/runs/<run_id>/
```

结构：

```text
run.json
coarse_results.json
local_results.json
metrics.json
candidate_regions.json
crops/
```

原始 PDF 不复制进入实验目录。

使用：

```text
source_pdf_hash
source_path
```

引用原文件。

---

# 35. 原始 PDF 隔离原则

实验模块：

```text
read-only
```

绝不：

```text
覆盖源 PDF
修改源 PDF
重写源 PDF
```

最终导出仍然调用正式 exporter。

---

# 36. 缓存策略

实验可以拥有自己的缓存。

建议缓存键：

```text
SHA256(
    pdf_hash
    + page_index
    + model
    + mode
    + grid_rows
    + grid_columns
    + prompt_version
    + render_config
)
```

注意：

> 实验缓存与正式 AI 缓存隔离。

不要让实验结果污染正式缓存。

---

# 37. Prompt 必须单独版本化

实验 Prompt：

```text
coarse_address_v1
local_refine_v1
verify_v1
```

之后：

```text
coarse_address_v2
```

即视为新实验。

不能静默覆盖历史实验结果。

---

# 38. 实验页面操作

用户选中：

> 本地识别（实验）

之后：

```text
[运行粗定位]

[查看虚拟地址覆盖图]

[运行局部精修]

[查看实验结果]

[与正式识别对比]

[将实验结果应用到当前项目]
```

特别是：

> **“将实验结果应用到当前项目”**

必须作为显式按钮。

不能自动应用。

---

# 39. 虚拟地址可视化

这是实验非常重要的调试功能。

PDF 页面上允许显示：

```text
R0C0 | R0C1 | R0C2 | R0C3
-----+------+------+-----
R1C0 | R1C1 | R1C2 | R1C3
...
```

题目 Q17 对应：

```text
[绿色高亮]
R4C0
R4C1
R5C0
R5C1
```

这样可以直观看到：

> 小模型到底把题目放到了什么地址。

这对于算法迭代非常有价值。

---

# 40. 可视化不应污染模型输入

非常重要：

> 网格 overlay 只用于 UI / 调试，不默认叠加到送给模型的图片上。

模型可以通过 Prompt 知道：

```text
8 rows × 4 columns
```

但是实际图片默认保持干净。

后续如果实验发现模型更适合看可视化网格，再增加：

```text
Grid Overlay Mode
```

作为额外实验变量。

---

# 41. Grid Overlay 必须可开关

配置：

```text
send_grid_overlay = false
```

可选：

```text
false = 干净图片
true  = 带地址网格图片
```

这本身也可以成为实验对照。

---

# 42. 自适应分块暂不实现

虽然最终可以研究：

```text
高密度区域 → 更细网格
低密度区域 → 更粗网格
```

但第一阶段禁止直接实现复杂动态分页。

原因：

当前实验首先回答：

> **固定虚拟地址是否有效。**

如果第一版就同时加入：

- 自适应分页。
- 网格合并。
- 动态邻域。
- 多模型投票。
- OCR 融合。
- 模板规则。

那么无法判断收益来自哪里。

---

# 43. 第一实验变量只保留这些

建议固定：

```text
Grid = 8 × 4
Neighbor Radius = 1
Coarse DPI = 150
Local DPI = 250
```

变量：

```text
Model
Mode
Prompt Version
Grid Overlay
```

后续才研究：

```text
8×4
6×3
12×6
...
```

---

# 44. 第一阶段 MVP

本地实验只要求完成：

```text
1. UI 增加“本地识别（实验）”
2. 本地模型 Endpoint 配置
3. LocalVisionProvider
4. VirtualPageTable
5. 固定 8×4 Grid
6. 粗定位 Prompt
7. Virtual Address JSON
8. Candidate Builder
9. Local Crop
10. Local Refine Prompt
11. Experiment Result 保存
12. 虚拟网格可视化
13. 指标统计
14. Direct Local Baseline
15. Virtual Address Mode
```

暂时不要做：

```text
模型自动下载
模型训练
自动微调
自适应网格
自动模型选择
复杂数据库迁移
新的正式导出算法
```

---

# 45. 推荐开发顺序

严格按照：

```text
Phase E0
实验模块骨架
        ↓
Phase E1
Local Provider
        ↓
Phase E2
Virtual Page Table
        ↓
Phase E3
低分辨率页面 + Grid
        ↓
Phase E4
粗定位 Prompt + Parser
        ↓
Phase E5
Candidate Builder
        ↓
Phase E6
Local Crop + Refiner
        ↓
Phase E7
Experiment Result Storage
        ↓
Phase E8
Direct Local Baseline
        ↓
Phase E9
Virtual Address Mode
        ↓
Phase E10
指标与可视化
        ↓
Phase E11
与正式云端结果对比
```

每一步完成：

```text
pytest
```

再继续下一步。

---

# 46. Phase E0：实验目录

验收：

```text
app/experimental/local_recognition/
```

可以正常 import。

不能改变主项目行为。

---

# 47. Phase E1：Local Provider

接口：

```python
class LocalVisionProvider:
    def analyze_image(...):
        ...
```

支持 OpenAI-compatible local endpoint。

验收：

```text
一张测试图片
 ↓
本地模型
 ↓
成功返回文本 / JSON
```

---

# 48. Phase E2：Virtual Page Table

输入：

```text
page.rect
rows=8
columns=4
```

输出：

```text
32 VirtualRegion
```

测试：

- 左上角区域。
- 右下角区域。
- 页面非 A4 比例。
- 横向页面。
- 旋转页面。

---

# 49. Phase E3：Grid

生成：

```text
Page Image
+
Virtual Region Metadata
```

UI 可以显示：

```text
P0:R0:C0
...
```

不改变 PDF。

---

# 50. Phase E4：粗定位

输入：

```text
low-res page image
```

输出：

```text
question_number
regions[]
confidence
```

必须通过 Pydantic。

非法：

```text
R9C99
P-1:R2:C3
```

必须被拒绝。

---

# 51. Phase E5：Candidate Builder

输入：

```text
VirtualRegion[]
```

输出：

```text
CandidateRect
```

要求：

- 正确合并相邻区域。
- 支持 padding。
- 支持 neighbor radius。
- 不超过页面。
- 记录来源地址。

---

# 52. Phase E6：Local Refiner

输入：

```text
Candidate Crop
+
Question Number
```

输出：

```text
local normalized bbox
```

验收：

> bbox 能正确转换回源 PDF 坐标。

---

# 53. Phase E7：实验结果

每次运行保存：

```text
coarse_result
candidate_regions
local_result
metrics
```

可重新加载。

---

# 54. Phase E8：Direct Local Baseline

必须实现：

```text
同一个本地模型
+
同一套测试 PDF
+
直接整页 bbox
```

否则没有比较意义。

---

# 55. Phase E9：Virtual Address Mode

实现：

```text
coarse
→ address
→ page table
→ crop
→ refine
```

要求：

> 不允许粗阶段直接输出最终 bbox 并跳过页表。

---

# 56. Phase E10：指标

至少计算：

```text
precision
recall
boundary IoU
cross-page accuracy
miss count
duplicate count
over-crop
under-crop
model calls
latency
```

Token：

如果本地 Endpoint 无法提供真实 token：

```text
estimated_tokens = null
```

不要伪造。

可以额外记录：

```text
input_image_count
input_image_pixels
image_resolution
```

作为资源消耗代理指标。

---

# 57. Phase E11：与正式结果对比

同一份 PDF：

```text
Cloud Baseline
Local Direct
Local Virtual Address
```

结果并排。

最终判断不通过单次样本。

至少保存多份真实测试结果。

---

# 58. Golden Dataset

不要立即复制现有 Golden Dataset 结构。

实验可以建立：

```text
tests/golden/local_recognition/
```

每个样本保存：

```json
{
  "pdf_hash": "...",
  "page": 3,
  "question_number": "17",
  "ground_truth_segments": [
    {
      "bbox": [0.05, 0.23, 0.95, 0.81]
    }
  ]
}
```

人工 Ground Truth 才是比较基准。

---

# 59. 实验结果不要“为了指标好看”自动修正

例如：

```text
AI bbox
 ↓
很差
 ↓
大量本地规则修正
 ↓
指标变好
```

这样无法证明：

> 虚拟地址算法本身有效。

因此实验必须区分：

```text
Raw Local Result
Local Result + Basic Safety Validation
Local Result + Existing Boundary Resolver
```

这样才能知道具体收益来自哪里。

---

# 60. 实验报告自动生成

建议每次 Run 都生成：

```text
summary.json
summary.md
```

示例：

```text
Model: Local-VLM-X
Mode: Virtual Address
Grid: 8×4

Questions:
Recall: 92.3%
Precision: 94.1%

Boundary:
Mean IoU: 0.87

Cross Page:
91.7%

Calls:
Coarse: 12
Local: 34
Total: 46
```

数值只能来自真实运行。

---

# 61. 重要的对照实验矩阵

第一轮：

```text
                    Direct       Virtual Address
---------------------------------------------------
Small Model A          ✓                ✓
Small Model B          ✓                ✓
Medium Model           ✓                ✓
```

第二轮：

```text
Grid:
4×2
8×4
12×6
```

第三轮：

```text
Grid Overlay:
OFF
ON
```

第四轮：

```text
Neighbor Radius:
0
1
2
```

---

# 62. 重点验证假设

实验最终至少回答：

### H1

离散虚拟区域定位是否比直接 bbox 更稳定？

### H2

粗定位 + 局部精定位是否提高小模型 Question Recall？

### H3

局部精定位是否提高 Boundary IoU？

### H4

随着模型规模下降，虚拟地址方案的收益是否增加？

### H5

总视觉输入量是否下降？

### H6

调用次数增加以后，整体 Token / 延迟是否仍然可接受？

---

# 63. 最关键的成功标准

不要提前规定：

> “一定成功。”

应该定义为：

如果：

```text
Virtual Address
```

相对于：

```text
Direct Local
```

在多个测试集上呈现：

```text
Recall ↑
Boundary IoU ↑
Miss Rate ↓
```

并且资源成本没有不可接受地增加，

则认为：

> 实验支持该方法继续研究。

如果没有：

> 保留实验代码用于结论记录，不影响正式系统。

---

# 64. 不能直接得出的结论

实验阶段禁止在 README 或 UI 中宣传：

```text
“本算法可以替代大模型”
“本算法一定节省 token”
“本算法让 0.5B 模型达到大模型水平”
```

只有完成实验后，才能根据数据描述结果。

---

# 65. 实验的理论结构

最终代码应体现：

```text
                 Document
                     │
              Virtual Address
                     │
              Coarse Grounding
                     │
            ┌────────┴────────┐
            │                 │
        Question A         Question B
            │                 │
       Candidate Region   Candidate Region
            │                 │
       Local Refinement  Local Refinement
            │                 │
        Physical PDF Coordinates
            │
       Existing PDF Engine
```

核心职责划分：

```text
Local VLM
=
semantic + coarse spatial understanding

Python
=
address mapping + geometry + validation

PyMuPDF
=
original PDF extraction/export
```

---

# 66. 为什么这个实验设计适合当前项目

当前正式项目已经采用：

```text
AI → 结构分析
Python → 坐标 / 边界 / PDF
```

实验只是进一步把：

```text
AI → 连续坐标
```

改成尝试：

```text
AI → 离散虚拟地址
```

然后：

```text
Python → 连续坐标恢复
```

因此该实验不会破坏当前项目最核心的职责分离。

---

# 67. Agent 编码时的文件修改策略

Agent 每次开始任务必须先：

```text
1. 查看当前 README.md
2. 查看当前 git diff
3. 检查相关模块实际结构
4. 确认不存在同名功能
```

然后才开发。

**不要假设文件结构一定与本规格完全一致。**

本规格定义的是目标架构，不是对当前源码结构的绝对假设。

---

# 68. 修改前必须建立 Git 回退点

在正式编码实验模块之前：

```bash
git status
git branch
git diff
```

确认工作区状态。

建议创建：

```text
experiment/local-recognition
```

分支。

若项目当前不方便建立 branch：

> 至少保证所有实验修改集中且可被完整回滚。

---

# 69. 最小化对正式代码的修改

优先采用：

```text
新增模块
+
Provider Registry 增加一个可选项
+
UI 增加一个实验入口
```

尽量不要修改：

```text
Question Engine
Boundary Resolver
Cross Page Resolver
Exporter
Database Core
```

如果必须连接：

```text
Adapter
```

优先。

---

# 70. 实验入口优先于正式 Provider 重构

不要因为 Local Provider 而重写整个：

```text
app/ai/
```

如果现有 Provider Registry 足够使用：

> 只增加一个注册入口。

如果现有结构不适合：

> 新增实验侧自己的 `provider.py`，再由 UI 调用。

实验成功以后再考虑正式抽象。

---

# 71. 线程和 UI

本地模型请求同样不能阻塞 UI。

使用项目现有：

```text
QThread
QRunnable / QThreadPool
Signal / Slot
```

如果当前项目已经存在后台任务机制：

> 直接复用。

不要再创建第二套任务调度框架。

---

# 72. 本地模型请求超时

第一版：

```text
connect timeout
read timeout
```

均可配置。

单次局部识别失败：

```text
该 Candidate 标记为 LOCAL_MODEL_ERROR
```

不要让整个 PDF 分析崩溃。

---

# 73. 本地模型 JSON 失败

沿用实验独立重试：

```text
Attempt 1
 ↓
JSON Parse
 ↓ fail
Attempt 2
 ↓
Correction Prompt
 ↓
fail
 ↓
LOCAL_OUTPUT_ERROR
```

最多 2 次。

---

# 74. 实验日志

记录：

```text
run_id
page
question
virtual addresses
candidate bbox
provider
model
request duration
response parse status
exception category
```

不能记录：

```text
API Key
```

本地 Endpoint 如果无需 Key：

> 也不要把敏感配置直接打到日志。

---

# 75. 实验 UI 不应改变正式结果颜色和状态

例如：

```text
正式结果：
Q17 正常

实验结果：
Q17 Experimental
```

建议实验框使用单独视觉标识：

```text
实验
```

避免用户误认为正式结果已被替换。

---

# 76. “应用实验结果”行为

点击：

```text
[应用实验结果]
```

之前弹出：

```text
实验结果不会自动成为正式识别结果。

应用后将把实验得到的 Question Segments
转换为当前项目题目区域。

是否继续？
```

确认后：

```text
ExperimentResult
 ↓
Adapter
 ↓
QuestionSegment
 ↓
现有 Question UI
```

并记录：

```text
user_modified = false
source = "local_experiment"
```

如果当前 Question 已存在：

> 不覆盖用户手动修改结果，除非用户明确确认覆盖。

---

# 77. 不要在第一版做自动融合

暂时禁止：

```text
Cloud result
+
Local result
=
自动融合
```

因为第一阶段需要知道：

> Local VAQL 自己到底表现怎样。

后续才可以做：

```text
Cloud + Local Consensus
```

---

# 78. 第二阶段可考虑的扩展

只有第一阶段证明有效后，才能继续：

```text
自适应网格
动态区域大小
多尺度分页
Local OCR
局部文本块提示
小模型多轮自校验
多模型本地投票
```

---

# 79. 第三阶段可能形成的完整系统

如果实验成功，未来可以变成：

```text
PDF
 ↓
本地几何分析
 ↓
Virtual Address Space
 ↓
Small VLM
 ↓
Coarse Address
 ↓
Local Crop
 ↓
Small VLM
 ↓
Fine Boundary
 ↓
Existing Boundary Resolver
 ↓
Original PDF
```

云端大模型则变成：

```text
Fallback / High Accuracy Mode
```

而不是整个系统的唯一识别核心。

---

# 80. 最终技术目标

本实验最终不是为了证明：

> “本地模型比云端模型强。”

而是为了验证：

> **更好的任务分解与空间表示，是否能够降低视觉模型对参数规模和长上下文的依赖。**

因此实验评价重点：

```text
算法结构
>
模型大小
```

不是简单：

```text
大模型 vs 小模型
```

---

# 81. Agent 最终验收清单

实验模块完成后，Agent 必须逐项确认：

### 工程隔离

- [ ] 正式识别路径仍可正常运行。
- [ ] 原有云端 Provider 未被删除。
- [ ] 原有 PDF 导出未被改变。
- [ ] 原有 Question UI 未被实验逻辑污染。
- [ ] 实验代码位于独立目录。
- [ ] 实验缓存独立。

### 本地识别

- [ ] UI 有“本地识别（实验）”。
- [ ] 可以配置 local endpoint。
- [ ] 可以选择 local model。
- [ ] 可以运行 Direct Local。
- [ ] 可以运行 Virtual Address。

### 虚拟地址

- [ ] 8×4 Grid 正常生成。
- [ ] Virtual Address 可序列化。
- [ ] Page Table 可映射真实 PDF 坐标。
- [ ] 非 A4 页面正常。
- [ ] 旋转页面基础支持正常。
- [ ] 地址越界可检测。

### 粗到细

- [ ] coarse prompt 正常。
- [ ] JSON schema 正常。
- [ ] candidate builder 正常。
- [ ] neighbor expansion 正常。
- [ ] local crop 正常。
- [ ] local refinement 正常。

### 评估

- [ ] Direct Local baseline 可运行。
- [ ] Virtual Address 可运行。
- [ ] precision / recall 有统计。
- [ ] Boundary IoU 有统计。
- [ ] cross-page 有统计。
- [ ] call count 有统计。
- [ ] latency 有统计。
- [ ] token 无数据时不会伪造。

### 回退

- [ ] 实验失败不会影响正式系统。
- [ ] 删除实验目录后主项目仍可运行。
- [ ] “本地识别（实验）”可以隐藏/禁用。

---

# 82. 最终 Agent 指令

Agent 在任何时候都必须牢记：

```text
这是一个实验，不是一次架构迁移。

不要因为实验方案看起来更先进，
就重写已经工作的正式系统。

首先证明：

“Virtual Address + Small VLM”
是否真的有收益。

如果没有收益：
保留实验结果，
放弃或调整方案，
正式系统不受影响。

如果有收益：
再逐步把经过验证的组件迁移为正式能力。
```

---

# 83. 一句话定义本实验

> **在当前 ExamSplit AI 已完成的云端多模态识别与本地 PDF 高保真处理架构之上，新增一个完全隔离的“本地识别（实验）”入口，以固定虚拟分页建立二维逻辑地址空间，让本地小型 VLM 先完成离散区域寻址，再由 Python 通过页表恢复真实 PDF 坐标，并对候选局部区域进行高分辨率二次定位，从实验数据验证该方法是否能够提升小模型题目定位能力并降低对大型云端模型的依赖。**

---

# 84. 参考实现的最终数据流

```text
[Existing PDF]
     │
     ├──────────── Existing Cloud AI Path
     │
     └──────────── Local Experimental Path
                          │
                  Virtual Page Table
                          │
                    8 × 4 Regions
                          │
                    Low-res Render
                          │
                    Small Local VLM
                          │
                  Virtual Addresses
                          │
                    Schema Validate
                          │
                  Candidate Builder
                          │
                    Local Crop
                          │
                 High-res Small VLM
                          │
                     Local BBox
                          │
                  Coordinate Mapping
                          │
                    Basic Validate
                          │
                 Experimental Result
                     /           \
                    /             \
             Compare              Preview
                │                   │
                ▼                   ▼
        Existing Cloud         Optional Apply
             Result                 │
                                    ▼
                         Existing Question Engine
                                    │
                                    ▼
                         Existing PDF Exporter
```

---

# 文档结束
