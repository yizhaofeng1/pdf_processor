# ExamSplit AI —— 小规模本地模型题目分割正式实现规格

**文档版本：** v1.0  
**文档性质：** 可直接交给 Antigravity / Coding Agent 执行的工程实施规格  
**基础版本：** 以当前项目 `README.md` 为最高优先级，结合现有初版设计文档  
**核心目标：** 在保留现有云端识别能力的前提下，新增一条可真正投入使用的本地小模型题目分割链路  
**主要语言：** Python  
**桌面 UI：** PySide6  
**PDF：** PyMuPDF  
**本地文档解析：** PaddleOCR / PP-DocLayoutV3 / OCR  
**本地 VLM：** 优先支持 0.9B 级文档 VLM，例如 PaddleOCR-VL-1.6-0.9B  
**核心原则：** 本地模型负责文档理解与局部视觉确认，本地 Python 负责结构组合、坐标计算、边界修正和最终 PDF 导出

---

# 0. 这次方案的根本变化

此前曾实验：

> “PDF 虚拟地址空间 + 虚拟页/区域 + 模型返回虚拟地址 + 本地页表映射”。

实验结果表明，这种虚拟地址方案并没有达到预期，因此：

## 正式实现中明确删除

- Virtual Page
- Virtual Address
- Page Table
- 虚拟区域地址作为主要模型输出
- 通过虚拟地址替代 bbox 的方案
- 为虚拟地址设计的特殊 UI
- 为虚拟地址设计的特殊 Schema
- 为虚拟地址设计的实验缓存

**不要为了兼容旧实验而把这些设计重新引入正式链路。**

如果历史实验代码已经存在：

> 保留在独立 experiment 目录即可，不参与新的正式识别流程。

---

# 1. 新方案目标

目标不再是：

> “证明某一个新算法思想”。

而是：

> **做出一个实际可用的本地 PDF 题目分割功能，让较小规模的本地模型承担大部分结构理解工作，同时利用传统 OCR、版面分析和本地规则补足模型能力。**

核心思想从：

```text
PDF
 ↓
一个 VLM 直接理解整页
 ↓
输出题目 bbox
```

改为：

```text
PDF
 ↓
本地 PDF 结构解析
 ↓
版面检测
 ↓
OCR / 原生文本
 ↓
阅读顺序
 ↓
题号候选
 ↓
本地题目边界推导
 ↓
小型本地 VLM 局部复核
 ↓
最终 Question Segment
 ↓
现有 PDF 导出
```

这是成熟文档解析系统更常见的分工模式。

---

# 2. 参考的主流技术路线

当前公开的文档解析工具普遍采用：

```text
Layout Detection
+
OCR / 原生文档结构
+
Reading Order
+
局部元素识别 / VLM
+
Post-processing
```

而不是要求一个小型 VLM 从整页直接完成所有任务。

以当前 PaddleOCR-VL 系列为例，官方文档明确区分：

```text
完整 PaddleOCR-VL pipeline
=
Layout Analysis
+
VLM Recognition
```

其中 PaddleOCR-VL-1.6 保持 0.9B 级 VLM，同时继续采用 PP-DocLayoutV3 作为版面分析模型；官方文档特别指出，完整 pipeline 与单独运行 VLM 组件并不等价。 citeturn557887search1turn557887search5

PP-DocLayoutV3 的官方版面检测支持包括考试在内的多类文档，并输出文档元素类别与区域位置；这正适合作为本项目题目分割前端的候选区域生成器。 citeturn856550search1turn856550search5

因此新方案采用：

> **传统/专用模型负责“看结构”，小 VLM 负责“理解局部题目”。**

---

# 3. 重新定义“本地识别”

UI 中保留：

```text
识别方式：
[云端 AI ▼]
[本地识别 ▼]
```

其中：

```text
云端 AI
=
现有正式链路

本地识别
=
新的本地文档解析链路
```

第一阶段可以在 UI 标注：

> **本地识别**

代码层仍然保持模块隔离：

```text
Existing Cloud Path
        │
        │
        └───────────正式

Local Recognition Path
        │
        └───────────新增正式可用路径
```

本地路径不能破坏云端路径。

---

# 4. 最终系统架构

```text
                      ExamSplit AI
                            │
            ┌───────────────┴────────────────┐
            │                                │
       Cloud Recognition               Local Recognition
         现有正式路径                     新本地路径
            │                                │
            │                         ┌──────▼──────┐
            │                         │ PyMuPDF     │
            │                         │ PDF Parser  │
            │                         └──────┬──────┘
            │                                │
            │                         ┌──────▼──────┐
            │                         │ Layout      │
            │                         │ Detection   │
            │                         └──────┬──────┘
            │                                │
            │                         ┌──────▼──────┐
            │                         │ OCR /       │
            │                         │ Native Text │
            │                         └──────┬──────┘
            │                                │
            │                         ┌──────▼──────┐
            │                         │ Reading     │
            │                         │ Order       │
            │                         └──────┬──────┘
            │                                │
            │                         ┌──────▼──────┐
            │                         │ Question    │
            │                         │ Marker      │
            │                         └──────┬──────┘
            │                                │
            │                         ┌──────▼──────┐
            │                         │ Local       │
            │                         │ Boundary    │
            │                         │ Resolver    │
            │                         └──────┬──────┘
            │                                │
            │                         Candidate Region
            │                                │
            │                         ┌──────▼──────┐
            │                         │ Local Small │
            │                         │ VLM Verify  │
            │                         └──────┬──────┘
            │                                │
            └───────────────┬────────────────┘
                            │
                    Existing Question
                       / Review Layer
                            │
                            ▼
                    Existing PDF Exporter
```

---

# 5. 核心原则：不要让小模型包办整个任务

本地小模型不承担：

```text
整页版面分析
+
题号检测
+
阅读顺序
+
精确坐标
+
完整边界
+
跨页逻辑
+
题型分类
```

全部任务。

而采用：

```text
专用算法：
结构问题

小 VLM：
语义问题

Python：
确定性几何问题
```

---

# 6. 三类职责划分

## A. PyMuPDF

负责：

- PDF 打开。
- 页面尺寸。
- 原生文本。
- 文本块。
- PDF 坐标。
- 页面渲染。
- 原始 PDF crop。
- 最终导出。

---

## B. Layout / OCR

负责：

- 文本区域。
- 图片区域。
- 公式区域。
- 表格区域。
- 页面结构。
- OCR 文本。
- OCR bbox。
- reading order 所需基础信息。

---

## C. Local Small VLM

主要负责：

- 判断一个候选区域是不是完整题目。
- 判断题号是否真正属于题目开始。
- 判断题目是否漏掉图片/公式/选项。
- 判断边界是否需要向上/下扩展。
- 判断候选题目是否跨页。
- 在复杂区域进行视觉二次校验。

---

# 7. 默认本地模型组合

第一优先级推荐：

```text
Layout:
PP-DocLayoutV3

VLM:
PaddleOCR-VL-1.6-0.9B

OCR:
PaddleOCR / PP-OCR 系列
```

当前 PaddleOCR 官方资料显示：

- PaddleOCR-VL-1.6 仍采用 0.9B 级 VLM。
- PP-DocLayoutV3 用于版面分析。
- 完整 pipeline 将 layout analysis 与 VLM recognition 组合使用。
- PaddleOCR-VL-1.6 在 OmniDocBench v1.6 上报告 96.33% 的文档解析准确率。 citeturn557887search1turn557887search5

注意：

> 上述公开 benchmark 是通用文档解析 benchmark，不等于 ExamSplit AI 的“题目切分准确率”。

本项目必须自行建立试卷数据集评估。

---

# 8. 不要直接把“0.9B VLM”当成完整系统

这是新实现中特别重要的一条。

不能只下载：

```text
PaddleOCR-VL-1.6-0.9B
```

然后让它：

```text
PDF page
 ↓
all questions
```

官方已经明确说明：

> 直接运行 0.9B VLM 组件，并不等价于运行完整 PaddleOCR-VL pipeline。 citeturn557887search1

本项目应尽量采用：

```text
PP-DocLayoutV3
+
OCR
+
VLM
```

的完整分工思想。

---

# 9. PDF 输入阶段

继续使用现有：

```python
PyMuPDF
```

步骤：

```text
PDF
 ↓
文件校验
 ↓
页面尺寸
 ↓
页面方向
 ↓
是否原生文本
 ↓
文本块
 ↓
页面渲染
```

不要修改原 PDF。

---

# 10. 页面类型判断

继续使用：

```text
TEXT_PDF
IMAGE_PDF
MIXED_PDF
```

但本地识别下进一步：

```text
TEXT_PDF
    ↓
原生文本优先
    ↓
Layout 作为视觉补充

IMAGE_PDF
    ↓
Layout
    ↓
OCR

MIXED_PDF
    ↓
Native Text
+
Layout
+
局部 OCR
```

---

# 11. 原生文本优先

对于有文本层的 PDF：

```python
page.get_text("dict")
```

优先获得：

```text
block
line
span
bbox
font
font size
```

这些信息直接用于：

```text
题号候选
阅读顺序
题目边界
```

而不是让 VLM 重复读取已经存在的文本。

---

# 12. Layout Detection

使用本地版面检测模型：

```text
PP-DocLayoutV3
```

输出统一结构：

```python
class LayoutElement:
    page_index: int
    category: str
    bbox: tuple[float, float, float, float]
    confidence: float
    order_hint: int | None
```

关注类别：

```text
text
title
formula
image
table
figure
header
footer
page_number
```

如果实际模型标签名称不同：

> 必须由 adapter 映射到项目内部标准名称。

不要把 PaddleOCR 的模型标签散落到业务层。

---

# 13. OCR 结果

统一：

```python
class OCRBlock:
    text: str
    bbox: tuple[float, float, float, float]
    confidence: float
    page_index: int
    source: str
```

source：

```text
native_pdf
ocr
```

---

# 14. Reading Order

本地题目切分不能使用简单：

```text
y → x
```

作为唯一顺序。

需要：

```text
页面
 ↓
栏检测
 ↓
栏内排序
 ↓
元素排序
```

典型双栏：

```text
左栏：
Q1
Q2
Q3

右栏：
Q4
Q5
Q6
```

必须恢复为真实阅读顺序。

如果使用 PP-DocLayoutV3 的 reading-order 能力，则优先使用模型输出；否则使用项目已有 reading-order 逻辑。

PP-DocLayoutV3 / RT-DocLayout 当前公开设计已经将元素分类、bbox、分割和阅读顺序放入统一的版面分析框架中。 citeturn856550search0

---

# 15. Question Marker Detection

这是本项目最重要的本地算法层之一。

不要让 VLM 直接寻找完整题目。

优先识别：

```text
1.
2.
3.
17．
18.
19、
```

以及：

```text
一、选择题
二、填空题
三、解答题
```

但注意：

```text
“一、选择题”
```

不是 Question。

它是：

```text
SECTION_HEADER
```

---

# 16. Marker Detection 的多源融合

候选题号来自：

```text
Native PDF Text
+
OCR
+
Layout Text Region
+
Local VLM（仅困难页）
```

最终得到：

```python
class QuestionMarker:
    number: str
    page_index: int
    bbox: tuple[float, float, float, float]
    confidence: float
    source: str
```

source：

```text
native
ocr
layout
vlm
```

---

# 17. 题号检测规则

必须支持：

```text
1.
1、
1．
1)
（1）
17.
17、
17．
```

还必须避免误判：

```text
2025.
3.14
0.5
（1）函数性质...
```

因此不能只写一个简单 regex。

至少需要：

```text
Regex Candidate
+
Text Context
+
Font / Position
+
Neighbor Number Pattern
+
Reading Order
```

---

# 18. Question Candidate

一旦得到：

```text
Q17 marker
Q18 marker
```

本地程序首先产生：

```text
Candidate Q17
=
Q17 marker
→
Q18 marker previous readable region
```

这一步与当前项目的：

> Anchor First, Boundary Second

原则保持一致。

---

# 19. Boundary Resolver

边界计算优先使用：

```text
Question Marker
+
Reading Order
+
Layout Elements
+
Native Text Blocks
```

而不是 VLM。

---

# 20. 小题边界

例如：

```text
Q17
题干
A...
B...
C...
D...

Q18
```

本地边界：

```text
Q17:
marker(Q17)
→
content before marker(Q18)
```

然后通过：

```text
Layout element containment
```

确定真正底部。

---

# 21. 选择题特别处理

选择题必须覆盖：

```text
题干
+
公式
+
题图
+
A
+
B
+
C
+
D
```

不能只取：

```text
OCR text blocks
```

如果布局检测发现：

```text
image
formula
```

属于题目中间区域：

> 必须纳入 Candidate。

---

# 22. 大题特别处理

对于：

```text
解答题
证明题
计算题
综合题
```

不要默认：

```text
题目区域 = 页面剩余空间
```

优先：

```text
最后有效文字 / 子问
```

本地向量文本审查继续保留。

这与当前 README 中已经完成的：

> 大题本地矢量文本审查、去留白、子问题收缩

保持一致。

---

# 23. Local VLM 的真正任务

本地 VLM 不再负责：

> “把整张试卷全部拆完”。

它只负责：

> **审核一个本地程序已经确定好的 candidate。**

例如：

```text
Candidate Q17
```

输入：

```text
局部图片
+
题号
+
候选框
+
附近结构信息
```

输出：

```json
{
  "question_number": "17",
  "accept": true,
  "bbox": [0.03, 0.08, 0.97, 0.91],
  "cross_page": false,
  "contains_all_options": true,
  "contains_formula": true,
  "contains_figure": false,
  "confidence": 0.92
}
```

---

# 24. 为什么让小 VLM 只做“局部复核”

因为此时模型不需要回答：

```text
“整页有多少题？”
```

而只回答：

```text
“这个区域是不是 Q17？”
“边界是否完整？”
```

任务复杂度降低。

即使本地模型规模比云端模型小，也更容易获得稳定结果。

---

# 25. Local VLM Prompt

文件：

```text
prompts/local/boundary_verify_v1.txt
```

Prompt 核心：

```text
你是试卷题目区域复核器。

系统已经通过本地 PDF 结构分析得到一个候选题目区域。

你的任务不是重新分析整页，也不是解题。

请判断：

1. 候选区域是否完整包含题目。
2. 是否遗漏题干。
3. 是否遗漏选项。
4. 是否遗漏公式或题图。
5. 下边界是否过低或过高。
6. 是否包含下一道题。
7. 是否为跨页题。
8. 如果边界明显错误，请输出修正后的归一化 bbox。

如果候选区域正确，accept=true。

只返回 JSON。
```

---

# 26. VLM 输出 Schema

```python
class LocalBoundaryVerification(BaseModel):
    schema_version: str
    question_number: str
    accept: bool
    bbox: tuple[float, float, float, float] | None
    cross_page: bool
    contains_all_required_content: bool
    needs_expand_up: bool
    needs_expand_down: bool
    confidence: float
    reason_codes: list[str]
```

reason codes：

```text
MISSING_STEM
MISSING_OPTION
MISSING_FORMULA
MISSING_FIGURE
CONTAINS_NEXT_QUESTION
BOUNDARY_TOO_HIGH
BOUNDARY_TOO_LOW
CROSS_PAGE
AMBIGUOUS
```

---

# 27. Local VLM 不参与最终几何决策

VLM 输出：

```text
bbox
```

后仍然必须经过：

```text
Schema Validation
 ↓
Range Validation
 ↓
Page Validation
 ↓
Layout Validation
 ↓
Question Sequence Validation
```

与现有项目规则一致。

---

# 28. Boundary Resolver 的最终策略

推荐：

```text
初始边界
    ↓
本地文本/版面推导
    ↓
安全 padding
    ↓
Local VLM Verify
    ↓
必要时扩展 / 收缩
    ↓
重新运行 local checks
    ↓
Final Segment
```

VLM 只提供修正建议。

Python 才是最终执行者。

---

# 29. 跨页题目

本地路径支持：

```text
Q17
Page 3 bottom
+
Page 4 top
```

识别依据：

```text
Page continuity
+
Question marker absence
+
Reading order
+
Layout continuity
+
Local VLM verification
```

VLM 输入只需处理：

```text
Page 3 bottom candidate
+
Page 4 top candidate
```

而不是整个 PDF。

---

# 30. 低置信度触发 VLM

不要每道题都强制使用 VLM。

如果本地规则非常明确：

```text
marker confidence = 0.99
boundary consistency = strong
overlap = low
```

直接通过。

只有：

```text
borderline candidate
```

才调用本地 VLM。

因此：

```text
Easy Question
→ local rules only

Hard Question
→ local VLM verification
```

这比：

```text
所有题全部 VLM
```

更适合桌面本地软件。

---

# 31. 困难题触发条件

示例：

```text
marker confidence < 0.90

OR

candidate overlap > threshold

OR

question area abnormal

OR

cross-page uncertain

OR

image-heavy

OR

formula-heavy

OR

multi-column uncertain
```

阈值必须配置化。

---

# 32. 扫描 PDF

如果 PDF 没有文本层：

```text
PDF
 ↓
Page Render
 ↓
PP-DocLayoutV3
 ↓
OCR
 ↓
Reading Order
 ↓
Question Marker
```

必要时：

```text
Local VLM Verify
```

不要强制 OCR 全文重建最终 PDF。

OCR 仅作为：

> **结构分析输入。**

---

# 33. 数学公式

不能依赖 OCR 文本直接确定最终 PDF 内容。

公式只用于：

```text
是否存在公式
公式区域在哪里
公式属于哪道题
```

最终输出仍来自：

```text
Original PDF
```

保持：

```text
数学公式
上下标
根号
积分
矩阵
几何图
```

原始质量。

---

# 34. Layout Element 与 Question 的关系

构建一个本地内部关系：

```text
Question Q17
 ├── text block
 ├── formula
 ├── figure
 ├── table
 ├── option A
 ├── option B
 ├── option C
 └── option D
```

可以通过：

```text
bbox intersection
+
reading order
+
vertical range
+
column
```

判断某个 layout element 是否属于当前 Question。

---

# 35. Candidate Graph

建议新增：

```python
class QuestionCandidateGraph:
    markers
    layout_elements
    text_blocks
    reading_order
    relations
```

关系：

```text
NEXT_QUESTION
CONTAINS
ADJACENT
OVERLAPS
CONTINUES_TO
```

这会比单纯 bbox 列表更适合处理复杂试卷。

---

# 36. 两栏布局

对于：

```text
左栏 Q1 Q2
右栏 Q3 Q4
```

首先建立：

```text
Column A
Column B
```

之后分别解析题号。

不能：

```text
按全页面 y 从上到下
```

否则很容易变成：

```text
Q1
Q3
Q2
Q4
```

---

# 37. 大题空白处理

当前项目已经存在：

> 本地矢量文本审查 + 去留白

继续保留。

新的本地模型链路：

```text
Layout / OCR
 ↓
Candidate
 ↓
Local VLM Verify
 ↓
Existing Vector Text Review
```

而不是：

```text
VLM 自己估计所有白区
```

---

# 38. 题目类型

第一版只分类为：

```text
choice
fill_blank
solution
proof
comprehensive
unknown
```

优先：

```text
Marker + Section Header + Layout
```

识别题型。

本地 VLM 只有在不确定时才参与。

---

# 39. 本地识别结果 Schema

与正式项目的 Question 概念保持兼容。

不创建完全不同的 Question Model。

增加来源字段：

```python
source_mode:
    "cloud"
    "local"
    "manual"
```

以及：

```python
recognition_trace:
    list[str]
```

例如：

```text
native_pdf
layout_detection
ocr
local_vlm
vector_boundary
```

如果当前 Question Model 不方便修改：

> 使用扩展 DTO，在最终进入正式 Question 时做 Adapter。

---

# 40. Local Provider 设计

建议：

```text
app/local_ai/
├── base.py
├── layout_backend.py
├── ocr_backend.py
├── vlm_backend.py
├── paddle_layout.py
├── paddle_ocr.py
├── local_vlm.py
├── config.py
└── exceptions.py
```

如果当前项目已有 `app/ai` 并且结构适合：

> 可以共用抽象接口，但不能让云端 Provider 与本地模型强耦合。

---

# 41. Layout Provider

```python
class LocalLayoutProvider(ABC):

    @abstractmethod
    def analyze_page(self, image_path):
        ...
```

实现：

```text
PaddleOCRLayoutProvider
```

默认模型：

```text
PP-DocLayoutV3
```

---

# 42. OCR Provider

```python
class LocalOCRProvider(ABC):

    @abstractmethod
    def recognize(self, image_path):
        ...
```

实现：

```text
PaddleOCRProvider
```

可以支持：

```text
native_only
ocr_only
hybrid
```

默认：

```text
hybrid
```

---

# 43. Local VLM Provider

```python
class LocalVLMProvider(ABC):

    @abstractmethod
    def verify_question_region(self, request):
        ...
```

建议第一阶段使用：

```text
OpenAI-compatible local endpoint
```

这样可以接：

```text
vLLM
Ollama
LM Studio
其他兼容服务
```

但不要让业务层知道具体服务器。

---

# 44. 为什么建议 Endpoint 而不是直接绑模型

因为本地模型部署方式变化快。

当前 PaddleOCR 官方生态已经提供多种推理 backend / 服务方式，模型服务层与业务层解耦更利于迁移。 citeturn557887search1turn557887search8

第一阶段：

```text
ExamSplit AI
 ↓
Local Endpoint
```

第二阶段再考虑：

```text
ExamSplit AI
 ↓
Embedded Runtime
```

---

# 45. 本地模型配置 UI

新增：

```text
本地识别设置

Layout Model
[PP-DocLayoutV3]

OCR
[Auto / PaddleOCR]

VLM
[PaddleOCR-VL-1.6-0.9B]

Backend
[Local Endpoint]

Endpoint
[http://127.0.0.1:xxxx/v1]

Model
[...]

GPU / CPU
[Auto]

Advanced
[...]
```

---

# 46. 不要第一版实现自动模型下载

第一阶段禁止：

```text
点击本地识别
→ 自动下载数 GB 模型
```

第一版先：

```text
检查本地模型 / Endpoint
```

不存在则提示：

```text
本地模型未配置。

[查看配置]
[切换云端识别]
```

后续再考虑模型管理器。

---

# 47. 本地识别模式

建议：

## Normal Local

```text
Native PDF
+
Layout
+
OCR/Native Text
+
Local Rules
+
Local VLM on uncertain regions
```

默认。

## Fast Local

```text
Native PDF
+
Layout
+
OCR
+
Local Rules
```

不调用 VLM。

适合排版规整的试卷。

## High Accuracy Local

后续再增加：

```text
Layout
+
OCR
+
Local VLM
+
Existing vector verification
+
Cross-page verify
```

---

# 48. 本地识别的总体决策树

```text
页面
 │
 ▼
Native Text?
 │
 ├── Yes ──→ Native Text Analysis
 │
 └── No ───→ OCR
              │
              ▼
          Layout Detection
              │
              ▼
         Question Markers
              │
              ▼
        Boundary Resolver
              │
              ▼
        Confidence Check
          /          \
       High          Low
        │             │
        │        Local VLM
        │             │
        └──────┬──────┘
               ▼
       Existing Validation
               │
               ▼
       Existing Question UI
```

---

# 49. 与现有云端识别的关系

云端：

```text
整页 / 批次
 ↓
大模型
 ↓
question markers / bbox
```

本地：

```text
本地结构模型
 ↓
本地 OCR
 ↓
本地规则
 ↓
小 VLM 局部验证
```

二者最终输出：

```text
Question
QuestionSegment
```

这样可以共享：

```text
Review UI
Export
Selection
Cross-page model
```

---

# 50. 云端与本地不能自动互相覆盖

用户选择：

```text
本地识别
```

则默认生成：

```text
Local Result
```

不会：

```text
覆盖 Cloud Result
```

反之亦然。

项目允许：

```text
Cloud Result
Local Result
Manual Result
```

三者共存。

---

# 51. UI 比较功能

增加：

```text
识别结果来源：

[云端]
[本地]
[人工]
```

当前题：

```text
Q17

云端：
Page 5
BBox A

本地：
Page 5
BBox B

差异：
Boundary IoU = ...
```

---

# 52. “应用本地结果”

如果当前页面已经有正式结果：

```text
[应用本地识别结果]
```

必须显式确认。

如果用户存在手工修改：

```text
user_modified=true
```

默认不覆盖。

---

# 53. 本地识别的缓存

缓存独立：

```text
data/cache/local/
```

缓存：

```text
pdf_hash
page_hash
layout_model
ocr_model
vlm_model
pipeline_version
```

---

# 54. Layout Cache

```text
同一个 PDF
+
同一个 Layout Model
```

不要重复计算。

---

# 55. OCR Cache

```text
page_hash
+
ocr_config
```

作为 key。

---

# 56. VLM Cache

精定位：

```text
candidate_hash
+
model
+
prompt_version
```

作为 key。

---

# 57. 为什么必须分层缓存

例如：

```text
用户修改 Prompt
```

不应该重新做：

```text
PDF → OCR → Layout
```

只应该让：

```text
VLM 层
```

失效。

同样：

```text
换 VLM
```

也不应该重跑：

```text
OCR
Layout
```

---

# 58. 推荐项目目录

在现有项目基础上新增：

```text
app/
├── local_ai/
│   ├── base.py
│   ├── layout_backend.py
│   ├── ocr_backend.py
│   ├── vlm_backend.py
│   ├── paddle_layout.py
│   ├── paddle_ocr.py
│   ├── local_vlm.py
│   ├── config.py
│   └── exceptions.py
│
├── local_detection/
│   ├── marker_detector.py
│   ├── reading_order.py
│   ├── candidate_builder.py
│   ├── boundary_resolver.py
│   ├── cross_page.py
│   └── confidence.py
│
└── services/
    └── local_analysis_service.py
```

Prompt：

```text
prompts/
├── ...
└── local/
    ├── boundary_verify_v1.txt
    ├── cross_page_verify_v1.txt
    └── classify_question_v1.txt
```

---

# 59. 保持现有目录职责

不要把：

```text
local_detection
```

直接塞进：

```text
existing detection
```

除非现有 detection 目录已经明确设计成 provider-independent。

推荐：

```text
existing detection = 正式通用能力
local_detection = 本地路径专用候选生成
```

后续验证成熟后，再抽取公共组件。

---

# 60. 数据模型

建议：

```python
class LocalPageAnalysis:
    page_index: int
    layout_elements: list[LayoutElement]
    text_blocks: list[OCRBlock]
    markers: list[QuestionMarker]
```

```python
class LocalQuestionCandidate:
    question_number: str
    segments: list[CandidateSegment]
    confidence: float
    reasons: list[str]
```

```python
class LocalQuestionVerification:
    candidate_id: str
    accepted: bool
    corrected_bbox: tuple[float, float, float, float] | None
    confidence: float
    reasons: list[str]
```

---

# 61. 最终 Question 适配

```text
LocalPageAnalysis
        ↓
LocalQuestionCandidate
        ↓
LocalQuestionVerification
        ↓
QuestionAdapter
        ↓
Existing Question
```

---

# 62. 坐标系统

继续保留现有：

```text
A. PDF Coordinate
B. Rendered Image Coordinate
C. AI / Model Normalized Coordinate
```

本地 layout bbox：

```text
模型原始 image coordinate
```

先转换为：

```text
normalized
```

再进入：

```text
PDF coordinate
```

这样不会破坏现有坐标体系。

---

# 63. 严格禁止固定像素作为持久化坐标

继续遵循现有规则：

```text
persistent =
normalized / PDF logical coordinate
```

而不是：

```text
1920 × 1080 pixel bbox
```

---

# 64. Safety Padding

继续复用当前 padding 逻辑：

```text
horizontal = page width × ratio
vertical = page height × ratio
```

不要因本地模型重新写一套 padding 规则。

---

# 65. 本地识别的异常处理

分类：

```text
LOCAL_MODEL_UNAVAILABLE
LAYOUT_MODEL_ERROR
OCR_ERROR
VLM_ERROR
LOCAL_SCHEMA_ERROR
LOCAL_COORDINATE_ERROR
LOCAL_PIPELINE_ERROR
```

不能让异常扩散到：

```text
正式 Cloud Pipeline
```

---

# 66. 本地 VLM 不可用时

如果：

```text
Layout + OCR + rules
```

仍然能够得到高置信结果：

> 允许继续。

如果 candidate 低置信：

```text
review_required=true
```

然后交给人工。

这保证软件在没有本地 VLM 时仍然能工作。

---

# 67. Local OCR 不可用时

对于有原生文本的 PDF：

```text
Native Text
```

继续工作。

只有扫描 PDF 才强依赖 OCR。

---

# 68. Layout 模型不可用时

可以 fallback：

```text
Native text blocks
+
现有 detection rules
```

但必须提示：

```text
本地版面模型不可用，已切换到基础模式。
```

---

# 69. 不能让“本地模型缺失”导致整个软件打不开

应用启动：

```text
Cloud Ready
Local Optional
```

即：

```text
没有本地模型
≠
程序无法启动
```

---

# 70. 安装依赖策略

现有基础依赖保持不动。

本地识别作为可选依赖组：

```text
paddleocr
paddlepaddle
torch
transformers
```

具体版本必须根据实际运行平台验证后写入 lock / requirements。

不要在设计文档里随意锁定未经验证的版本。

---

# 71. Windows 打包原则

本地模型权重不要直接放进默认发行版。

默认发行版：

```text
ExamSplitAI.exe
```

只包含：

```text
正式应用
+
云端功能
+
本地识别框架
```

模型按需安装。

---

# 72. 模型文件管理

建议：

```text
data/models/
├── layout/
├── ocr/
└── vlm/
```

数据库或配置记录：

```text
model_name
version
path
sha256
enabled
```

---

# 73. 模型健康检查

进入：

```text
本地识别
```

自动检查：

```text
Layout OK?
OCR OK?
VLM OK?
```

显示：

```text
✓ Layout
✓ OCR
✓ VLM

本地识别可用
```

或者：

```text
✓ Layout
✓ OCR
✗ VLM

基础本地识别可用
局部视觉复核不可用
```

---

# 74. 本地模型资源限制

不要默认认为：

```text
本地 = 无限 GPU
```

所有推理参数都应该可配置：

```text
batch_size
image_size
max_new_tokens
temperature
num_workers
device
```

默认保守。

---

# 75. CPU fallback

至少要能够：

```text
Layout CPU
OCR CPU
```

运行。

VLM：

```text
GPU 优先
CPU 可选
```

如果 CPU 太慢：

> UI 只显示任务进行中，不冻结界面。

---

# 76. 任务队列

复用当前：

```text
QThread
QRunnable / QThreadPool
Signal / Slot
```

不要创建第二套 UI 任务框架。

---

# 77. 页面处理可以并行

可以：

```text
Page 1 layout
Page 2 layout
Page 3 layout
```

并发受配置限制。

第一版建议：

```text
MAX_LOCAL_WORKERS = 1
```

先保证稳定。

---

# 78. VLM 局部区域可以批处理

当候选题目较多时：

```text
Q1 crop
Q2 crop
Q3 crop
```

可根据 backend 支持：

```text
batch
```

但第一版优先单条，便于调试和错误定位。

---

# 79. 本地识别的详细流水线

最终正式流程：

```text
Step 1
打开 PDF

Step 2
检查 Native Text

Step 3
渲染页面

Step 4
Layout Detection

Step 5
OCR（必要时）

Step 6
Native Text + OCR + Layout 融合

Step 7
Reading Order

Step 8
Question Marker Detection

Step 9
Question Candidate Construction

Step 10
Boundary Resolution

Step 11
Confidence Calculation

Step 12
仅对低置信 Candidate 调用 Local VLM

Step 13
Local VLM Verify

Step 14
边界修正

Step 15
Cross-page Resolution

Step 16
Existing Consistency Engine

Step 17
Existing Question UI

Step 18
Existing Exporter
```

---

# 80. 与原有正式系统兼容

现有：

```text
Cloud AI
 ↓
Existing Detection
 ↓
Question
 ↓
Export
```

新增：

```text
Local Layout/OCR/VLM
 ↓
Local Detection
 ↓
Adapter
 ↓
Question
 ↓
Export
```

最后汇入：

```text
同一个 Question UI
同一个 Review UI
同一个 Export Engine
```

---

# 81. Golden Dataset

继续使用真实试卷。

至少覆盖：

```text
单栏
双栏
文字 PDF
扫描 PDF
数学公式
选择题
填空题
解答题
证明题
图片题
跨页
页眉页脚
异常排版
```

并保存人工标准答案。

---

# 82. 新增本地模型专项测试

对于每份 PDF 额外保存：

```text
layout ground truth
question marker ground truth
question bbox ground truth
cross-page ground truth
```

---

# 83. 指标

必须记录：

```text
Question Precision
Question Recall
Boundary IoU
Cross-page Accuracy
Missed Question
Duplicate Question
Over-Crop
Under-Crop
```

以及：

```text
Layout latency
OCR latency
VLM latency
Total latency
```

---

# 84. 模型规模实验

至少准备：

```text
Small VLM
Larger Local VLM
Cloud Baseline
```

重点观察：

```text
Local Small VLM
+
Pipeline
```

是否已经足够支撑软件使用。

---

# 85. 重要的对照组

必须有：

### Baseline A

```text
现有云端 AI
```

### Baseline B

```text
Local Layout + OCR + Rules
```

### Method C

```text
Local Layout + OCR + Rules + Small VLM Verification
```

这样才能知道：

> 本地 VLM 到底提供了多少额外价值。

---

# 86. 不再做的对照

不再加入：

```text
Virtual Address
Grid Address
Page Table
```

因为该方案已经通过实验确认不适合作为主路径。

历史实验可以继续保留，但不进入正式 benchmark。

---

# 87. 成功标准

本项目不是要求：

```text
Local == Cloud
```

而是：

> 在常见试卷上，本地方案能够达到“可实际使用”的题目检测与边界准确度。

最低标准应关注：

```text
绝大多数题目能够识别
+
关键题目不严重截断
+
跨页基本正确
+
人工修正成本低
+
完全离线可工作
```

具体数值应通过第一批 Golden Dataset 实测后设定。

---

# 88. 失败时的降级策略

如果：

```text
Local VLM
```

质量不好：

不要推翻整个本地链路。

可以逐层降级：

```text
Local VLM
 ↓
去掉 VLM
 ↓
Layout + OCR + Rules
```

如果：

```text
OCR
```

问题大：

```text
Native Text
 ↓
Layout
 ↓
Rules
```

这样软件仍然可运行。

---

# 89. 第一阶段不要做训练

本次实现：

```text
不训练模型
不微调模型
不制作专属 VLM
```

目标是：

> **利用现有小型预训练模型 + 工程 pipeline 做出可用产品。**

之后如果用户纠正数据积累够多，再考虑：

```text
Prompt tuning
Fine-tuning
Question-specific detector
```

---

# 90. 后续可能的优化方向

本地系统稳定后，再研究：

```text
1. 训练轻量 Question Marker Detector
2. 试卷模板规则
3. 更强的 reading order
4. 低置信度自适应 VLM 调用
5. 本地模型量化
6. GPU/CPU 自动路由
7. 用户纠正数据驱动规则
```

---

# 91. 本地识别性能优化顺序

不要首先优化：

```text
模型推理 FPS
```

先优化：

```text
Question Recall
Boundary IoU
Cross-page
```

确认可用后：

```text
缓存
批处理
并发
量化
```

---

# 92. 模型使用策略

推荐：

```text
Layout model
→ 每页一次

OCR
→ 仅无文本/异常区域

Local VLM
→ 仅低置信 candidate

Python rules
→ 全量执行
```

本地没有 API token 成本，但：

```text
GPU 时间
内存
功耗
```

依旧是真实成本。

---

# 93. Prompt 版本化

例如：

```text
local_boundary_verify_v1
local_cross_page_v1
local_question_type_v1
```

与当前云端 Prompt 完全独立。

---

# 94. 本地 Debug 可视化

必须提供调试开关：

```text
[✓] 显示 Layout
[✓] 显示 OCR
[✓] 显示 Question Markers
[✓] 显示 Candidate
[✓] 显示 Final BBox
```

便于排查：

```text
题号没找到
Layout 漏框
OCR 漏字
Candidate 太大
VLM 修正错误
```

---

# 95. Agent 修改现有代码的规则

首先：

```text
git status
git diff
```

然后查看：

```text
README.md
```

再扫描：

```text
app/
tests/
```

确认现有实现。

不要假设初版设计文档就是当前源码。

---

# 96. README 优先级

发生冲突时：

```text
当前 README
>
当前源码
>
本设计文档
>
旧设计文档
```

实际编码时：

> **源码行为高于历史设计文档描述。**

本规格只定义本次新增功能边界。

---

# 97. 第一阶段最少修改正式模块

优先：

```text
新增 Local Recognition
+
新增 UI Option
+
新增 Adapter
```

尽量不修改：

```text
Existing Cloud Provider
Existing Exporter
Existing Boundary Editor
Existing Question Engine
Existing Storage
```

---

# 98. 第一版数据库原则

尽量不要添加大量数据库表。

如果现有 Project / Question 能保存：

```text
source_mode
```

则优先扩展少量字段。

如果不方便：

> 本地中间结果保存 JSON，最终只在用户应用结果时进入现有 Question 数据。

---

# 99. Phase L0 —— 本地 Provider 骨架

任务：

```text
LocalLayoutProvider
LocalOCRProvider
LocalVLMProvider
```

验收：

```text
接口可 import
异常可分类
配置可读取
```

---

# 100. Phase L1 —— PP-DocLayoutV3

任务：

```text
单页图像
 ↓
PP-DocLayoutV3
 ↓
LayoutElement[]
```

验收：

- 文本框存在。
- 图片存在。
- 页面元素有 bbox。
- 结果能转换到内部标准模型。

---

# 101. Phase L2 —— OCR / Native Text Fusion

任务：

```text
Native Text
+
OCR
+
Layout
```

统一为：

```text
PageStructure
```

验收：

> 能在测试页面上得到稳定的文本块和空间信息。

---

# 102. Phase L3 —— Reading Order

任务：

```text
PageStructure
 ↓
ReadingOrder
```

验收：

```text
单栏
双栏
公式
图片
```

基本顺序正确。

---

# 103. Phase L4 —— Question Marker

任务：

```text
PageStructure
 ↓
QuestionMarker[]
```

验收：

> 能找到常见数字题号，并减少 section header / 正文数字误报。

---

# 104. Phase L5 —— Candidate

任务：

```text
QuestionMarker[]
+
ReadingOrder
+
Layout
 ↓
QuestionCandidate[]
```

验收：

> 每个题号都有合理的初始候选区域。

---

# 105. Phase L6 —— Local Boundary Resolver

复用已有：

```text
padding
coordinate
overlap
text review
cross-page
```

验收：

> 候选区域可以转换成现有 `QuestionSegment` 语义。

---

# 106. Phase L7 —— Local VLM

任务：

```text
Candidate Crop
 ↓
Small VLM
 ↓
accept / adjust
```

验收：

> 至少能正确处理典型选择题、填空题、大题候选区域。

---

# 107. Phase L8 —— Confidence Router

任务：

```text
Candidate
 ↓
confidence
 ↓
High → rules only
Low → VLM
```

验收：

> 简单题目不调用 VLM；困难题目调用 VLM。

---

# 108. Phase L9 —— Local Question UI

展示：

```text
Q1 [Local]
Q2 [Local]
Q3 [Local]
```

能够：

```text
预览
编辑
确认
```

---

# 109. Phase L10 —— Export Integration

只调用现有：

```text
Question
 ↓
Existing Exporter
```

不开发第二套 PDF 导出器。

---

# 110. Phase L11 —— Cache

按：

```text
PDF hash
Page hash
Model version
Pipeline version
Prompt version
```

缓存。

---

# 111. Phase L12 —— Golden Test

至少：

```text
10 套真实试卷
```

再逐步扩大。

---

# 112. Unit Tests

必须覆盖：

```text
marker regex
reading order
column detection
bbox intersection
candidate construction
boundary correction
cross-page
confidence routing
local result parsing
coordinate conversion
```

---

# 113. Integration Tests

至少测试：

```text
PDF
 ↓
Layout
 ↓
OCR
 ↓
Markers
 ↓
Candidates
 ↓
VLM
 ↓
Question
 ↓
Existing Export
```

---

# 114. Golden Tests

不要求：

```text
模型字符串完全一致
```

而要求：

```text
题目数量
题号
page range
Boundary IoU
Cross-page
```

达到标准。

---

# 115. 完整的本地识别验收链路

用户：

```text
打开 ExamSplit AI
```

然后：

```text
选择：
本地识别
```

输入：

```text
考研数学 PDF
```

系统：

```text
PyMuPDF
 ↓
Native Text
 ↓
Layout
 ↓
OCR
 ↓
Reading Order
 ↓
Question Marker
 ↓
Candidate
 ↓
Boundary
 ↓
Local VLM
 ↓
Validation
```

用户得到：

```text
☑ Q1
☑ Q2
☐ Q3
☑ Q4
...
```

然后：

```text
选择题目
 ↓
预览
 ↓
导出
```

最终：

```text
Original PDF
 ↓
PyMuPDF Crop
 ↓
Selected PDF
```

整个过程不重新 OCR 排版最终 PDF。

---

# 116. 推荐的最终软件定位

ExamSplit AI 不应该宣传：

> “本地小模型替代一切 AI。”

更合理的是：

> **ExamSplit AI 支持云端高能力识别与本地小模型识别两条路径，通过版面分析、OCR、局部视觉复核和本地几何算法，实现对原始 PDF 题目的自动定位与高保真拆分。**

---

# 117. 最终技术原则

```text
专用模型解决结构
        ↓
OCR / Native Text 提供证据
        ↓
Python 负责确定性逻辑
        ↓
小型 VLM 处理困难语义判断
        ↓
原 PDF 负责最终内容
```

而不是：

```text
一个模型
 ↓
从头看到尾
 ↓
决定所有坐标
```

---

# 118. Agent 最终不可违背的原则

```text
1. 不再实现 Virtual Address / Virtual Page Table。

2. 不因为本地方案而重构已经完成的云端识别。

3. 本地识别必须使用：
   Layout + OCR/Native Text + Rules
   作为主要骨架。

4. 小型 VLM 主要承担局部困难区域的视觉复核。

5. 最终 PDF 永远来自 Original PDF。

6. 本地 VLM 结果不得未经验证直接进入 Export。

7. 本地模型不存在时，程序仍然能够启动。

8. Local Recognition 与 Cloud Recognition 结果隔离。

9. 第一目标是：
   能用。

10. 第二目标是：
    稳定。

11. 第三目标是：
    再逐步优化速度和模型体积。

12. 每完成一个阶段必须先测试，再继续。
```

---

# 119. 一句话定义

> **本版本将 ExamSplit AI 的本地识别路线正式确定为“专用版面检测 + 原生 PDF 文本/OCR + 本地规则化题号锚点与边界推导 + 小型 VLM 局部复核”的分层文档解析架构；取消此前验证失败的虚拟地址分页方案，并通过独立 Local Recognition Provider 接入现有系统，在不破坏已经完成的云端识别、人工修正和原始 PDF 高保真导出能力的前提下，让小规模本地模型成为一条真正可用的题目分割路径。**

---

# 120. 官方技术参考

以下为本设计采用的主要公开技术参考：

- PaddleOCR / PaddleOCR-VL  
  https://github.com/PaddlePaddle/PaddleOCR

- PaddleOCR-VL Pipeline  
  https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PaddleOCR-VL.md

- PaddleOCR-VL-1.6  
  https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/algorithm/PaddleOCR-VL/PaddleOCR-VL-1.6.md

- PP-DocLayoutV3  
  https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/module_usage/layout_detection.md

- RT-DocLayout  
  https://arxiv.org/abs/2606.23344

- Docling  
  https://github.com/docling-project/docling

Docling 当前同样采用 PDF 解析、版面分析、OCR、后处理与结构组装的阶段化 pipeline，作为本设计的工程路线参考之一。 citeturn538336search0turn538336search2

---

# 文档结束
