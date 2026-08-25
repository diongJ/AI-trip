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

- `data/processed/rag/**` 与 `data/graph/knowledge_graph_v1.json` 是可重复生成产物，不提交 Git。
- PowerShell 中文输出偶尔乱码，但 UTF-8 文件内容和 JSON 校验正常。
- 当前本地图谱是 Day 4 检索降级用核心图，不宣称替代 Day 3 完整 78/87 图谱口径。
