# Day 1 AI 工作交付与队友协作手册

## 1. 这份手册解决什么问题

这份手册用于帮助项目成员理解第一天到底完成了什么、代码如何工作、哪些内容还需要人工配置，以及第二天怎样在不破坏现有结构的前提下继续协作。

项目名称为：

> 基于大模型与智能体的南越王博物院深度知识图谱构建与智慧导览应用

第一天完成的不是最终产品，而是后续数据采集、知识抽取、Neo4j 图谱、RAG 和 Agent 都要共同使用的技术底座。

## 2. 一句话理解当前成果

当前系统已经具备以下流程的代码基础：

```text
输入一段南越王墓资料
        ↓
DeepSeek 提取实体和关系
        ↓
Pydantic 按 Schema 检查结果
        ↓
合格数据写入 Neo4j
        ↓
查询并返回实体之间的关系
```

例如，输入资料中明确提到赵眜、南越文王墓、主棺室和文帝行玺后，系统预期形成：

```text
赵眜 → BURIED_IN → 南越文王墓
南越文王墓 → CONTAINS → 主棺室
文帝行玺 → EXCAVATED_FROM → 主棺室
文帝行玺 → RELATED_TO_PERSON → 赵眜
```

## 3. AI 已经完成的工作

### 3.1 冻结研究边界

研究对象被限制为南越王博物院王墓展区，重点覆盖南越文王墓、赵眜、墓室、30 至 50 件代表文物及其直接相关历史文化。

明确不做王宫展区、全馆所有藏品、广州旅游助手、票务、实时客流和路线导航。这样可以防止九天项目无限扩张。

完整边界记录在 `docs/project_scope.md`。

### 3.2 冻结知识图谱 Schema V1

Schema 可以理解为知识图谱的“统一语言和数据合同”。它规定系统允许出现哪些实体、哪些关系以及每条知识必须保存哪些字段。

当前定义了12类实体，例如人物、墓葬、墓室、文物、材料、朝代和历史事件；同时定义了12类有方向的关系。例如只能是：

```text
Person -BURIED_IN-> Tomb
Relic -EXCAVATED_FROM-> TombChamber
```

如果大模型把方向写反、使用未定义类型、置信度超过范围或没有原文证据，程序会拒绝该结果，不会直接写入数据库。

完整定义记录在 `docs/kg_schema.md`，对应代码位于 `src/extraction/models.py`。

### 3.3 建立 DeepSeek 知识抽取接口

`src/extraction/deepseek.py` 负责：

- 读取抽取 Prompt。
- 将资料文本和文档编号发送给 DeepSeek。
- 要求 DeepSeek 只返回 JSON。
- 解析返回结果并交给 Schema 校验。
- 将网络错误、格式错误和 Schema 错误转换成可读提示。

抽取规则写在 `prompts/knowledge_extraction.txt`。修改 Prompt 时不能自行增加实体或关系类型，除非先兼容性升级 Schema。

### 3.4 建立 Neo4j 图谱接口

`src/graph/repository.py` 负责：

- 连接 Neo4j Aura。
- 为实体 `id` 创建唯一约束。
- 使用 `MERGE` 幂等写入，重复运行不会重复创建同一实体。
- 合并同一实体来自不同资料的别名和来源编号。
- 保存关系的原文证据、文档编号和置信度。
- 查询指定实体附近的关系路径。

“可溯源”是项目的重要特点：回答中的图谱知识后续可以追溯到 `document_id` 和 `evidence`。

### 3.5 建立测试与验证脚本

当前包含13项离线测试，验证：

- 实体名称不能为空。
- 实体和关系类型必须合法。
- 置信度只能处于0到1之间。
- 关系两端实体必须存在。
- 关系方向必须符合 Schema。
- DeepSeek 返回的 JSON 必须能通过数据模型校验。
- 缺少密钥时给出明确提示且不泄露敏感值。

本地测试已全部通过。真实 DeepSeek 和 Neo4j 云端连接尚需项目成员提供个人凭据。

## 4. 目录和文件怎么理解

| 路径 | 当前作用 | 谁会主要使用 |
|---|---|---|
| `README.md` | 安装、配置和运行入口 | 所有人 |
| `docs/project_scope.md` | 项目范围、非目标和九天里程碑 | 项目负责人、PPT负责人 |
| `docs/kg_schema.md` | 实体、关系和字段标准 | 数据、图谱、Agent开发者 |
| `prompts/knowledge_extraction.txt` | DeepSeek 抽取规则 | 抽取开发者 |
| `data/raw/` | 原始资料和 Day 1 示例 | 数据负责人 |
| `data/processed/` | 后续清洗和切分结果 | 数据负责人 |
| `data/graph/` | 通过校验的图谱 JSON | 图谱负责人 |
| `src/config/` | 读取环境变量 | 所有后端模块 |
| `src/extraction/` | 数据模型与 LLM 抽取 | 抽取负责人 |
| `src/graph/` | Neo4j 写入和查询 | 图谱负责人 |
| `src/rag/` | Day 4 开发文档检索 | RAG负责人 |
| `src/agent/` | Day 5 开发工具路由 | Agent负责人 |
| `scripts/` | 服务验证和完整样例命令 | 所有人 |
| `tests/` | 防止修改破坏已有功能 | 所有开发者 |

`app/`、`src/rag/` 和 `src/agent/` 目前只是预留目录。它们为空不是遗漏，而是九天计划中的后续工作。

## 5. 新成员如何接收项目

### 5.1 获取代码

队友从 GitHub 仓库克隆代码，不要通过微信反复传压缩包：

```powershell
git clone <GitHub仓库地址>
cd nanyue-kg-agent
```

如果已经克隆过，则执行：

```powershell
git switch main
git pull origin main
```

### 5.2 建立个人环境

每个成员都在自己的电脑上创建虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

`.venv` 是每台电脑自己的依赖环境，不需要传给队友，也不能上传 GitHub。

### 5.3 配置个人凭据

每个人只在自己的 `.env` 中填写凭据：

```dotenv
DEEPSEEK_API_KEY=个人的真实Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
NEO4J_URI=Neo4j Aura连接地址
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=Neo4j真实密码
NEO4J_DATABASE=neo4j
```

禁止把真实密钥写入 `.env.example`、README、聊天截图、测试文件或代码。需要共享账号时，通过私密渠道分别发送凭据，不要放入 Git。

### 5.4 验证接收成功

依次执行：

```powershell
pytest
python -m scripts.verify_deepseek
python -m scripts.verify_neo4j
python -m scripts.run_sample_pipeline
```

成功标准：

- `pytest` 显示13项测试通过。
- DeepSeek 脚本输出实体和关系 JSON。
- Neo4j 脚本报告连接、写入、查询和幂等性通过。
- 完整样例在 Neo4j 中生成赵眜、南越文王墓、主棺室和文帝行玺相关关系。

## 6. 推荐的队友分工

第二天建议这样交接：

### 项目负责人：架构与质量

- 维护 Schema 和代码主线。
- 优化知识抽取 Prompt。
- 审核资料来源和抽取结果。
- 维护测试、README 和每日验收记录。
- 负责合并队友代码，保证 `main` 始终可运行。

### 队友：资料与图谱数据

- 按 `docs/project_scope.md` 收集30至50份可靠资料。
- 为每份资料建立 `DocumentMetadata`。
- 优先整理30至50件代表性文物，不扩展到全馆藏品。
- 使用现有 Schema 检查实体和关系，不自行创造类型。
- 对不确定实体放入人工审核清单，不强行合并。

队友当天至少应交付：资料来源表、原始资料文件、文档编号规则、5篇试抽取结果和错误记录。

## 7. Git 协作约定

开始工作前：

```powershell
git switch main
git pull origin main
git switch -c feature/data-corpus
```

完成一个小任务后提交：

```powershell
git status
git add <本次需要提交的文件>
git commit -m "data: add first batch of museum sources"
git push -u origin feature/data-corpus
```

协作要求：

- 不直接在 `main` 上堆积未经验证的大改动。
- 一次提交只处理一个清晰任务。
- 提交前运行 `pytest`。
- 不提交 `.env`、`.venv`、缓存或真实密钥。
- 不用聊天软件覆盖传递整个项目目录。
- 每晚将通过测试的内容合并到 `main`，保证第二天有稳定起点。

## 8. 当前完成与未完成边界

### 已完成

- 项目范围与九天主线。
- Schema V1 文档和代码约束。
- DeepSeek 抽取接口。
- Neo4j 幂等入库与关系查询接口。
- Day 1 示例资料和完整链路脚本。
- 离线测试、环境模板、Git 忽略规则和 README。
- GitHub 仓库发布与 `main` 分支同步。

### 仍需人工完成

- 创建个人 `.env` 并填入 DeepSeek 和 Neo4j Aura 凭据。
- 运行三条真实云服务验证命令。
- 在 Neo4j Browser 中检查四条样例关系是否正确。
- 把实际验证结果和截图保存到后续项目文档。

### 后续日期完成

- 大规模可靠资料采集与 Metadata。
- 批量抽取、实体融合与人工审核。
- FAISS 文档检索。
- Agent 工具路由和带来源回答。
- Streamlit Demo、部署、评测、PPT和演示视频。

## 9. 常见问题

### 为什么不能直接相信大模型输出？

大模型可能使用错误类型、写反关系或补充原文没有的信息。因此系统先使用 Pydantic 校验，再写 Neo4j；证据不足的数据必须拒绝或人工审核。

### 为什么每条关系都要保存证据？

后续问答需要说明答案来自哪里。`document_id` 指向资料，`evidence` 保存支持关系的原文，这是区别于普通聊天机器人的关键设计。

### 为什么重复运行不会产生很多相同节点？

实体 `id` 在 Neo4j 中具有唯一约束，写入使用 `MERGE`。同一实体再次出现时会更新并合并别名和来源，而不是创建新节点。

### 为什么目前还看不到聊天页面？

Day 1 只负责技术底座。RAG、Agent 和 Streamlit 分别安排在后续日期开发，提前做页面会分散对数据质量和完整链路的注意力。

## 10. 交接确认清单

交给队友前，双方共同确认：

- [ ] 队友能够打开 GitHub 仓库并克隆代码。
- [ ] 队友理解项目只覆盖王墓展区。
- [ ] 队友阅读了 Schema 的实体和关系方向。
- [ ] 队友本机 `pytest` 全部通过。
- [ ] 双方明确 `.env` 和密钥不能上传。
- [ ] 双方能够分别验证 DeepSeek 和 Neo4j。
- [ ] 队友知道 Day 2 应提交哪些资料和 Metadata。
- [ ] 新功能通过独立分支提交，合并前必须测试。

完成上述确认后，Day 1 的技术成果才算真正完成团队交付。

