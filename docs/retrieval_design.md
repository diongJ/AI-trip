# Day 4 检索设计

## 目标

Day 4 将 36 份官方资料和知识图谱 V1 封装成两个稳定工具：

- RAG 文档检索：返回原文片段、文档编号、标题、来源名称、来源 URL 和分数。
- KG 图谱检索：返回实体、关系、方向、`document_id` 和 `evidence`。

公开接口统一返回 Pydantic 模型，不暴露底层索引、FAISS 或 Neo4j 原始对象。

## 数据模型

- `DocumentChunk`：`chunk_id`、`text`、`doc_id`、`title`、`source_name`、`source_url`、`category`。
- `RetrievalHit`：`content`、`score`、`rank`、`backend`、`metadata`。
- `GraphHit`：`source_entity`、`relation`、`target_entity`、`direction`、`document_id`、`evidence`、`backend`。

`RetrievalHit` 会校验 metadata 中必须含有 `doc_id`、`title`、`source_name`、`source_url`、`category` 和 `chunk_id`。`GraphHit` 会拒绝缺失 `document_id` 或 `evidence` 的关系。

## RAG 切分规则

- 输入来自 `data/raw/**/*.json`，通过 `load_corpus()` 读取并校验。
- 优先按中文自然段切分。
- 长段落按 `。！？!?；;` 等句末标点切分。
- 默认 chunk 长度为 420 个字符。
- 默认 overlap 为 60 个字符。
- 空白、空行和过短片段会被清理。
- 一个 chunk 不跨文档。
- `chunk_id` 使用稳定格式：`DOC_001_CHUNK_001`。

## 默认索引后端

默认后端为 `lexical-tfidf-v1`，它是纯 Python 的轻量词法检索实现：

- 不需要 GPU。
- 不下载模型。
- 不依赖 FAISS。
- 可在 Windows、Linux 和普通云部署环境中稳定运行。

五日计划中的 FAISS/句向量方案可以作为后续增强后端接入；只要继续返回 `RetrievalHit`，Agent 和页面层不需要改接口。

## 索引产物

构建命令：

```powershell
python -m scripts.build_rag_index
```

强制重建：

```powershell
python -m scripts.build_rag_index --force
```

产物位于 `data/processed/rag/`：

- `chunks.json`：chunk metadata 和原文。
- `lexical_index.json`：词法倒排索引。
- `index_manifest.json`：构建参数和语料指纹。

`data/processed/**` 属于可重复生成产物，默认不进入 Git。

Manifest 字段：

- `created_at`
- `embedding_model`
- `chunk_size`
- `chunk_overlap`
- `document_count`
- `chunk_count`
- `index_file`
- `metadata_file`
- `source_fingerprint`

## RAG 检索行为

- 默认返回 Top-5。
- 支持可选 `category` 过滤。
- 按 `doc_id + text` 去重。
- 分数归一化到 0 到 1。
- 索引缺失时提示运行 `python -m scripts.build_rag_index`。
- metadata 与索引数量不一致时抛出清晰错误。
- 查询没有可匹配词项时返回空列表。

验证命令：

```powershell
python -m scripts.verify_rag
```

验证会保存 `docs/day4_retrieval_smoke_test.md`。

## KG 检索与降级

本地图构建命令：

```powershell
python -m scripts.build_graph_v1
```

默认输出：

```text
data/graph/knowledge_graph_v1.json
```

该文件是可重复生成产物，默认不进入 Git。

KG 检索支持：

- 实体名称和别名解析。
- 一跳关系查询。
- 受限两跳查询。
- 每条关系返回 `document_id` 和 `evidence`。

Neo4j 可用时可通过 `Neo4jGraphRetriever` 查询 Aura；Neo4j 不可用时使用 `LocalGraphRetriever` 读取本地 JSON 图。两种后端均返回 `GraphHit`。

综合验证命令：

```powershell
python -m scripts.verify_retrieval
```
