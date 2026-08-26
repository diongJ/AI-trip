# Day 4 检索设计

## 目标

检索层将 100 份分层可信资料和知识图谱 V1 封装成两个稳定工具：

- RAG 文档检索：返回原文片段、文档编号、标题、来源名称、来源 URL 和分数。
- KG 图谱检索：返回实体、关系、方向、`document_id` 和 `evidence`。

公开接口统一返回 Pydantic 模型，不暴露底层索引、FAISS 或 Neo4j 原始对象。

## 数据模型

- `DocumentChunk`：除原有来源字段外，包含 `source_tier`、主题标签、采集日期、发布日期和内容哈希。
- `RetrievalHit`：`content`、`score`、`rank`、`backend`、`metadata`。
- `GraphHit`：`source_entity`、`relation`、`target_entity`、`direction`、`document_id`、`evidence`、`backend`。

`RetrievalHit` 会额外校验来源层级、采集日期和融合分数。`GraphHit` 会拒绝缺失 `document_id` 或 `evidence` 的关系。

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

默认后端为 `multi-field-bm25-v2`，它是纯 Python 的轻量 BM25 检索实现：

- 不需要 GPU。
- 不下载模型。
- 不依赖 FAISS。
- 可在 Windows、Linux 和普通云部署环境中稳定运行。

标题、主题标签和正文采用不同权重，并加入标题双字词覆盖加分。多查询通过倒数排名融合合并，在不增加向量模型的情况下改善口语、同义表达和复杂问题召回。

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
- 支持 `core` 与 `extended` 来源层级过滤。
- 支持 `search_many()` 多查询融合与稳定去重。
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

该文件可以通过 Day 3 流程重复生成，同时作为后续检索、Agent 和 Demo 的版本化基线进入 Git。

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
