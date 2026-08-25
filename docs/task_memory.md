# 任务记忆

## 更新规则

- 每次任务完成后更新本文件。
- 只记录会影响后续协作的事实：分支状态、重要提交、PR 流向、验证结果、未完成事项。
- 已解决的误操作只保留简要结论和必要恢复步骤，不展开长过程。

## 2026-08-23 Day 2 数据集建设

### 当前状态

- 正确交付分支：`feature/data-corpus`
- 正确合并目标：`dev`
- `dev` 已通过 PR #3 合入 Day 2 数据。
- `main` 曾误合并 Day 2 PR #1，随后通过 revert PR #2 撤销；当前文件效果正常，不应再从 `main` 继续 Day 2 开发。
- 后续常规开发以 `dev` 为基线，需要新功能时从 `dev` 新建分支。

### 关键提交

- `133cec4`：新增南越王博物院 Day 2 初始语料。
- `d13f947`：新增语料生成、校验工具和测试。
- `97cee0c`：撤销误合并到 `main` 的 Day 2 内容。
- `6aa1fa8`：将 `feature/data-corpus` 正确合并到 `dev`。

### 已完成内容

- 新增 36 份 `data/raw/**` 标准化 JSON 资料。
- 覆盖 25 条代表性文物资料。
- 新增 `docs/data_sources.md` 数据来源记录。
- 新增 `src/preprocessing/` 语料校验模块。
- 新增 `scripts/build_day2_corpus.py` 和 `scripts/validate_corpus.py`。
- 新增 `tests/test_preprocessing.py`。

### 验证记录

- `python -m scripts.validate_corpus` 通过：36 docs，25 relic。
- `python -m pytest` 通过：16 passed。

### 注意事项

- PR 目标分支必须先确认：功能分支通常合入 `dev`，不要直接合入 `main`。
- 如果误合并到 `main`，优先用 revert PR 撤销，不要 `reset --hard` 或强推。
- Day 2 数据质量达标但仍可增强：优先补墓室结构、赵眜/赵佗人物资料、南越国用印制度、汉代丧葬制度等小批量高质量资料。

## 2026-08-25 Day 4 RAG 与 KG 检索底座

### 当前状态

- 工作分支：`feature/day4-retrieval`。
- 基线分支：`dev`。
- Day 4 默认 RAG 后端采用纯 Python `lexical-tfidf-v1`，保证无 GPU、无 FAISS、无模型下载时也可运行。
- Neo4j 检索为可选增强；Neo4j 包不可用或 Aura 不可用时，本地 JSON 图仍可返回同构 `GraphHit`。

### 已完成内容

- 新增 RAG 模型、中文切分、索引构建和检索器。
- 新增本地 KG 图构建、别名解析、一跳/受限两跳关系检索。
- 新增 RAG/KG 验证脚本和 Day 4 smoke test 记录。
- 更新 README 和 `docs/retrieval_design.md`。

### 验证记录

- `python -m scripts.validate_corpus` 通过：36 docs。
- `python -m scripts.build_rag_index --force` 通过：36 docs，36 chunks。
- `python -m scripts.build_graph_v1` 通过：30 entities，30 relations。
- `python -m scripts.verify_rag` 通过：9/10，其中 1 个为超范围低相关问题。
- `python -m scripts.verify_retrieval` 通过：核心实体别名解析、Graph evidence、RAG sources 均完整。
- `python -m pytest` 通过：25 passed。

### 注意事项

- `data/processed/rag/**` 是可重复生成产物，不提交 Git；`data/graph/knowledge_graph_v1.json` 作为后续阶段的版本化基线提交。
- PowerShell 中文输出偶尔乱码，但 UTF-8 文件内容和 JSON 校验正常。
- 当前本地图谱是 Day 4 检索降级用核心图，不宣称替代 Day 3 完整 78/87 图谱口径。

### 冲突修复记录

- `feature/day4-retrieval` 与最新 `origin/dev` 合并时，`README.md`、`scripts/build_graph_v1.py`、`src/graph/__init__.py` 出现冲突。
- 解决原则：保留 Day 3 正式融合图谱构建逻辑，Day 4 检索层只读取 `data/graph/knowledge_graph_v1.json`，不覆盖 78/87 的正式图谱口径。
- `src/graph/__init__.py` 同时导出 Day 3 fusion API 和 Day 4 retriever API，并延迟导入 `Neo4jKnowledgeGraph`。
- `scripts.verify_retrieval` 在缺少 `data/graph/by_document` 时允许使用已有本地图或 smoke-test fallback 图，保证轻量设备也能跑检索验证。

## 2026-08-25 Day 5 Agent MVP

### 当前状态

- 工作分支：`feature/day5-agent`。
- 分支基线：`feature/day4-retrieval`，因为 Day 5 依赖 Day 4 的 RAG/KG 检索接口。
- 后续 PR 应在 Day 4 合入 `dev` 后，以 `dev` 为 base；不要合入 `main`。

### 已完成内容

- 新增规则路由：实体事实、关系探索、描述讲解、超范围拒答。
- 新增工具封装：`search_kg`、`search_documents`、`hybrid_search`。
- 新增受证据约束回答服务：默认离线抽取式生成；配置 DeepSeek 后可用 LLM 组织语言。
- 新增引用聚合：KG 关系通过 `document_id` 回查 Day 2 语料，补齐标题、来源和 URL。
- 新增 CLI：`python -m scripts.ask "问题"`。
- 新增并加强为 16 题 Agent 冒烟测试，检查预期工具、答案要点、关键关系、引用和拒答。
- 新增 `docs/agent_design.md` 与 README Day 5 说明。

### 验证记录

- `python -m scripts.validate_corpus` 通过：36 docs。
- `python -m scripts.verify_rag` 通过：9/10，1 个为超范围低相关问题。
- `python -m scripts.verify_retrieval` 通过。
- `python -m scripts.verify_agent` 通过：16/16。
- `python -m pytest` 通过：54 passed。

### 注意事项

- 默认回答不依赖 DeepSeek，保证无网络/无 API Key 设备也能演示主链路。
- `--llm` 模式只允许基于检索上下文生成，不允许使用模型自身知识补事实。
- RAG 索引写入已改为临时文件原子替换，减少并发验证时读到半写入文件的风险。
