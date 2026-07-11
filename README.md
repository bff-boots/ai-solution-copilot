# AI Solution Copilot

面向 AI 算力、机器人与智能硬件场景的企业方案助手。项目从一个基础 RAG 原型二次开发而来：用户填写行业、场景、预算与规模，系统生成“需求判断、推荐架构、实施步骤、风险与待确认项、下一步行动”五部分方案，并展示知识库引用。

## 二次开发亮点

- 将通用问答改造成面向售前和客户成功的方案工作台。
- 新增 `/api/solution` 接口，结构化接收行业、场景、预算和规模。
- 新增企业方案、机器人售后、AI 算力与高速互连三类演示知识库。
- 回答模板强制标记待确认项，禁止生成真实报价、厂商参数或性能承诺。
- 保留多轮追问、可追溯引用、本地关键词检索降级与可选向量检索链路。

## 运行

1. 使用 Python 3.11+ 创建虚拟环境并安装依赖：

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. 基础演示不需要模型密钥。需要大模型生成与向量检索时，复制 `.env.example` 为 `.env`，填入 `DASHSCOPE_API_KEY`，再安装完整 RAG 依赖：

   ```powershell
   pip install -r requirements-full-rag.txt
   ```

3. 仅在启用完整 RAG 后构建向量库（首次运行或知识库内容有变化时执行）：

   ```powershell
   python ingest.py --reset
   ```

4. 启动服务：

   ```powershell
   uvicorn app.main:app --reload
   ```

访问 <http://127.0.0.1:8000>。接口文档位于 <http://127.0.0.1:8000/docs>。

## 项目结构

```text
data/              企业方案演示知识文档（可自行添加脱敏 .txt 或 .md）
chroma_db/         自动生成的本地向量数据库
app/
  knowledge.py     清洗、按句分块、向量化、检索与重排序
  rag.py           多轮上下文、查询改写和带引用回答
  main.py          FastAPI 接口和静态页面托管
  static/          原生 HTML + CSS + JavaScript 前端
ingest.py          建库脚本
```

## 说明

- 默认使用阿里云百炼兼容接口：聊天模型为 `qwen-plus`，嵌入模型固定为 `text-embedding-v4`。
- 每块目标长度 420 字符、重叠约 42 字符，保留 `title`、`source`、`chunk_id` 元数据。
- 检索先取 12 条候选，再以词项匹配对向量结果重新排序，最终返回前 4 条；接入大模型时还会进行查询改写和基于上下文的回答。
- 未配置密钥时，网页仍可演示本地关键词检索和引用；配置密钥并运行建库后可使用完整 RAG 链。
- 演示知识库只包含通用业务方法，不包含真实客户资料、设备报价或厂商性能参数。
