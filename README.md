# 南越王博物院深度知识图谱与智慧导览

本项目面向南越王博物院王墓展区，将可靠资料通过大模型转换为可追溯的知识图谱，并在后续阶段结合 RAG 与 Agent，开发智能问答、AI 深度讲解和局部图谱探索功能。

Day 1 已提供以下技术底座：

- 冻结的研究范围与知识图谱 Schema V1。
- Pydantic 实体、关系、文档和抽取结果模型。
- DeepSeek 严格 JSON 抽取客户端。
- Neo4j Aura 约束、幂等写入和局部关系查询。
- DeepSeek、Neo4j 及端到端样例验证脚本。

Day 2 与 Day 3 已在此基础上完成 36 份官方资料的批量抽取、人工消歧、统一图谱 V1 和 Aura 入库验收。

## 环境要求

- Python 3.11 或更高版本。
- DeepSeek API Key。
- Neo4j Aura 实例及连接凭据。

项目不要求 Docker。本机未安装 Docker 时直接使用 Neo4j Aura 即可。

## 安装

在 PowerShell 中执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

编辑 `.env`，填入真实凭据：

```dotenv
DEEPSEEK_API_KEY=your-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password
NEO4J_DATABASE=neo4j
```

`.env` 已被 Git 忽略。不要把真实密钥写入 `.env.example`、源代码、测试或提交记录。

## 本地测试

离线测试不调用 DeepSeek 或 Neo4j：

```powershell
pytest
```

测试覆盖实体与关系字段、置信度、关系方向、实体引用、配置错误和 DeepSeek 响应解析。

## 云服务验证

分别验证 DeepSeek 与 Neo4j：

```powershell
python -m scripts.verify_deepseek
python -m scripts.verify_neo4j
```

Neo4j 验证脚本会写入两个带 `test:` 前缀的临时节点，验证重复写入不会产生重复节点或关系，并在结束时删除测试数据。

## 运行 Day 1 完整样例

```powershell
python -m scripts.run_sample_pipeline
```

该命令执行：

```text
data/raw/sample_nanyue.txt
  -> DeepSeek 实体与关系抽取
  -> Pydantic Schema V1 校验
  -> data/graph/sample_extraction.json
  -> Neo4j 幂等写入
  -> 查询并打印样例实体的关系路径
```

模型输出若违反 Schema、缺少证据、引用不存在的实体或使用错误关系方向，将在写入 Neo4j 之前被拒绝。

## 运行 Day 2 批量抽取

先验证队友整理的原始语料：

```powershell
python -m scripts.validate_corpus
```

再逐文档调用 DeepSeek；成功结果默认保存在 `data/graph/by_document/`，运行报告保存在 `data/processed/batch_extraction_report.json`：

```powershell
python -m scripts.run_batch_extraction
```

批处理会隔离单篇失败、重试临时网络错误、对 Schema 错误进行一次纠错，并在二次纠错失败时保守删除非法关系。重复运行默认跳过已有合法结果；需要重新抽取全部资料时使用 `--force`。

完成后执行来源与证据审计：

```powershell
python -m scripts.audit_extractions
```

审计要求每份资料都有合法输出、实体包含当前文档来源、关系引用正确文档，并且关系证据逐字存在于原文。

## 构建和写入 Day 3 图谱 V1

使用受版本控制的人工消歧决策，将逐文档抽取合并为统一图谱：

```powershell
python -m scripts.build_graph_v1
```

该命令默认读取 `data/curated/entity_resolution_v1.json`，生成 `data/graph/knowledge_graph_v1.json` 和融合报告。构建过程会拒绝映射环、缺失目标、跨类型映射、删除后仍被关系引用的实体，以及来源或证据不合法的关系。

将统一图谱写入当前 `.env` 配置的 Neo4j Aura：

```powershell
python -m scripts.load_graph_v1
```

入库命令不会清空数据库。它会连续执行两次幂等写入，逐项检查实体和关系是否存在，并查询赵眜、南越文王墓和文帝行玺的核心路径。验收报告保存在 `data/processed/graph_v1_load_report.json`。

## Day 4 检索底座

Day 4 提供设备兼容的 RAG 与 KG 检索底座。默认 RAG 后端为纯 Python `lexical-tfidf-v1`，不依赖 GPU、FAISS 或本地模型下载；后续可以在保持返回模型不变的前提下替换为句向量 + FAISS 后端。

构建 RAG 索引：

```powershell
python -m scripts.build_rag_index
```

强制重建：

```powershell
python -m scripts.build_rag_index --force
```

验证文档检索：

```powershell
python -m scripts.verify_rag
```

验证 RAG + KG 检索：

```powershell
python -m scripts.verify_retrieval
```

RAG 索引产物位于 `data/processed/rag/`，本地图谱产物位于 `data/graph/knowledge_graph_v1.json`，二者均可重复生成且默认不提交到 Git。Neo4j Aura 不可用时，检索层可使用本地 JSON 图返回同构 `GraphHit` 结果。

## Day 5 Agent MVP

Day 5 提供 KG、RAG 和 Hybrid 三类工具路由，并生成带引用回答。默认使用离线抽取式回答生成器，不需要 DeepSeek；配置 `DEEPSEEK_API_KEY` 后可用 `--llm` 让 DeepSeek 只基于检索证据组织语言。

命令行提问：

```powershell
python -m scripts.ask "文帝行玺是什么材料？"
```

输出完整结构化结果：

```powershell
python -m scripts.ask "赵眜是谁？" --json
```

使用 DeepSeek 生成回答：

```powershell
python -m scripts.ask "讲讲丝缕玉衣的特点" --llm
```

运行 15 题 Agent 冒烟测试：

```powershell
python -m scripts.verify_agent
```

Agent 回答包含 `answer`、`citations`、`used_tools`、`route_reason` 和 `insufficient_evidence`。对实时客流、天气、停车、路线导航等超范围问题，Agent 会明确拒答。

## 项目结构

```text
app/                 Day 6 Streamlit 应用
data/raw/            原始资料及 Day 1 样例
data/curated/        受版本控制的人工消歧与审核决策
data/processed/      清洗和切分结果
data/graph/          经过校验的图谱数据
docs/                项目范围与 KG Schema
prompts/             LLM 抽取 Prompt
scripts/             云服务与完整链路验证脚本
src/config/          环境配置
src/extraction/      数据模型和 DeepSeek 抽取
src/graph/           Neo4j 入库与查询
src/rag/             Day 4 实现
src/agent/           Day 5 实现
tests/               离线测试
```

详细范围见 [docs/project_scope.md](docs/project_scope.md)，Schema 见 [docs/kg_schema.md](docs/kg_schema.md)。面向项目成员的成果解释、环境接收、分工和 Git 协作流程见 [Day 1 AI 工作交付与队友协作手册](docs/day1_handoff_manual.md)。

## Day 1 验收清单

- [x] 研究范围和非目标冻结。
- [x] Schema V1 文档与代码枚举一致。
- [x] Git 友好的目录、依赖和环境模板。
- [x] 非法抽取结果在入库前被拦截。
- [x] 使用个人凭据完成 DeepSeek 实际调用。
- [x] 使用个人 Aura 凭据完成 Neo4j 实际连接。
- [x] 运行完整样例并检查四条目标关系。

云端验收已于 2026-08-24 完成：DeepSeek 样例抽取、Neo4j 连接与幂等写入、端到端关系查询均通过。

## Day 2 验收结果

- [x] 36 份原始资料通过格式与重复 ID 校验。
- [x] 覆盖 25 份代表性文物资料。
- [x] 批量抽取支持失败隔离、临时错误重试和断点续跑。
- [x] 36 份资料全部生成 Schema V1 合法结果。
- [x] 关系证据和文档来源审计无遗留问题。
- [x] 人工抽查 10 份核心资料并收紧保守过滤规则。
- [x] 29 项离线测试全部通过。

详细统计和已知边界见 [Day 2 批量抽取与质量报告](docs/day2_extraction_report.md)。

## Day 3 验收结果

- [x] 12 个非规范实体 ID 按人工映射完成融合。
- [x] 删除 4 个误分类展览章节实体和 2 条证据不足关系。
- [x] 统一图谱包含 78 个实体、87 条关系，来源与证据审计问题为 0。
- [x] 图谱实际写入 Neo4j Aura，78 个实体和 87 条关系逐项验证无缺失。
- [x] 第二次写入前后均为 80 个节点、93 条关系，幂等性通过。
- [x] 36 项离线测试全部通过。

详细决策、验收数据和 Day 4 输入见 [Day 3 可靠知识图谱 V1 报告](docs/day3_graph_v1_report.md)。
