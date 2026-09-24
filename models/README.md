# 本地轻量级多模态模型 (Local Lightweight Vision Models)

本项目在 `models/` 目录下预置了适合本地实验与试卷题目分析的轻量级视觉大模型（Vision LLM）。

---

## 🌟 推荐模型：Qwen2.5-VL-3B-Instruct (GGUF Q4_K_M)

- **模型全称**：`Qwen2.5-VL-3B-Instruct`
- **开发机构**：阿里巴巴通义千问团队 (Alibaba Cloud Qwen Team)
- **文件路径**：`models/qwen2.5-vl-3b/Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf`
- **文件体积**：约 3.0 GB
- **参数规模**：约 3.8B 参数
- **量化精度**：`Q4_K_M`（兼顾极低显存占用与高精度输出）

### 为什么选择该模型进行本实验？
1. **强大的中文文档与试卷理解能力**：
   Qwen-VL 系列在中文多模态基准（如 MathVista、DocVQA、OCRBench、ChartQA）上均位列小参数量模型（< 4B）的 SOTA（State of the Art），对中文题干、选择题选项、公式上下标、几何插图具有极高的空间与语义感知能力。
2. **极小的显存与计算开销**：
   - 显存需求：仅需约 3.5GB ~ 4.5GB VRAM（可在 RTX 4050 6GB 显卡上完全加载并全速 GPU 推理，或在 CPU 上以极小内存流畅运行）。
   - 推理延迟：单次粗寻址约 1~3 秒，局部精修约 0.8~1.5 秒。
3. **与 VAQL（虚拟地址寻题）实验高度契合**：
   本实验核心验证“离散虚拟网格空间寻址 + 局部高分辨率精修”对小模型的赋能效果。3B 参数规模恰好是验证“通过良好算法设计弥补模型参数规模”的最佳测试对象。

---

## 🚀 启动与调用方式

### 方式 A：通过本地 Ollama 服务调用（推荐，已配置好）
当前系统中 Ollama 服务已在后台运行，并已映射该模型：
- **服务端点 (Endpoint)**：`http://127.0.0.1:11434/v1`
- **模型标识 (Model ID)**：`qwen2.5vl:3b`
- **协议**：标准 OpenAI 兼容 Chat Completion 接口

在 ExamSplit AI 软件的【更多功能 ▾】->【🧪 本地识别实验 (VAQL)...】对话框中：
- 填入 Endpoint：`http://127.0.0.1:11434/v1`
- 模型选择：`qwen2.5vl:3b`
- 点击【测试连接】即可直接通信。

### 方式 B：使用 llama.cpp / llama-server 原生运行
如果您希望脱离 Ollama 独立运行 GGUF 模型：
```bash
# 启动 llama-server 提供 OpenAI 兼容接口
llama-server \
  -m models/qwen2.5-vl-3b/Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf \
  --port 11434 \
  -ngl 99 \
  -c 4096
```

---

## 📥 扩展其他实验模型

如果您希望下载或对比其他小规模模型（如 `Qwen2-VL-2B-Instruct` 或 `MiniCPM-V-2.6`），可以使用：
```bash
python scripts/download_model.py --model qwen2-vl-2b --save-dir models/qwen2-vl-2b
```
