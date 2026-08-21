# 南越王博物院深度知识图谱与智慧导览

本项目面向南越王博物院王墓展区，将可靠资料通过大模型转换为可追溯的知识图谱，并在后续阶段结合 RAG 与 Agent，开发智能问答、AI 深度讲解和局部图谱探索功能。

Day 1 已提供以下技术底座：

- 冻结的研究范围与知识图谱 Schema V1。
- Pydantic 实体、关系、文档和抽取结果模型。
- DeepSeek 严格 JSON 抽取客户端。
- Neo4j Aura 约束、幂等写入和局部关系查询。
- DeepSeek、Neo4j 及端到端样例验证脚本。

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

## 项目结构

```text
app/                 Day 6 Streamlit 应用
data/raw/            原始资料及 Day 1 样例
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

详细范围见 [docs/project_scope.md](docs/project_scope.md)，Schema 见 [docs/kg_schema.md](docs/kg_schema.md)。

## Day 1 验收清单

- [x] 研究范围和非目标冻结。
- [x] Schema V1 文档与代码枚举一致。
- [x] Git 友好的目录、依赖和环境模板。
- [x] 非法抽取结果在入库前被拦截。
- [ ] 使用个人凭据完成 DeepSeek 实际调用。
- [ ] 使用个人 Aura 凭据完成 Neo4j 实际连接。
- [ ] 运行完整样例并检查四条目标关系。

最后三项需要在本地 `.env` 中配置真实云服务凭据后执行。

