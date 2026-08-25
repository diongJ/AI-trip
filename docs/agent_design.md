# Day 5 Agent 设计

## 目标

Day 5 提供可演示的 Agent MVP：用户问题先经过可解释路由，再调用 KG、RAG 或混合检索工具，最后只基于检索证据生成回答。证据不足或超出范围时拒答，不使用模型自身记忆补造事实。

## 问题类型

- `entity_fact`：实体直接事实，优先 KG。
- `relation_exploration`：实体间关系或属性追问，优先 KG。
- `description`：介绍、特点、意义、背景类问题，使用 RAG 或 Hybrid。
- `out_of_scope`：实时客流、天气、停车、酒店、路线导航等当前资料无法可靠回答的问题。

## 工具

- `search_kg`：按实体名或别名查询本地图谱/Neo4j 图谱的一跳关系。
- `search_documents`：从 RAG 索引返回 Top-K 原文片段和完整来源。
- `hybrid_search`：同时返回 KG 事实和 RAG 文档片段。

三种工具都返回统一 Pydantic 模型，页面和后续评测不依赖底层实现。

## 回答生成

默认生成器为 `ExtractiveAnswerGenerator`，无需 API Key，适合本地测试和无网络设备。它直接组织检索事实与片段，保证答案可追溯。

配置 `DEEPSEEK_API_KEY` 后，CLI 可使用 `--llm` 切换到 `DeepSeekAnswerGenerator`。LLM Prompt 要求只使用传入证据，并输出严格 JSON：

```json
{
  "answer": "直接回答"
}
```

如果 DeepSeek 不可用，默认离线生成器仍可运行。

## 引用

`AgentAnswer` 包含：

- `answer`
- `citations`
- `used_tools`
- `route_reason`
- `insufficient_evidence`
- `retrieved_documents`
- `graph_facts`

只要 `insufficient_evidence=false`，就必须有引用。KG 关系引用通过 `document_id` 回查 Day 2 语料，补齐标题、来源名称和来源 URL。

## 命令

离线提问：

```powershell
python -m scripts.ask "文帝行玺是什么材料？"
```

输出完整 JSON：

```powershell
python -m scripts.ask "赵眜是谁？" --json
```

使用 DeepSeek 组织语言：

```powershell
python -m scripts.ask "讲讲丝缕玉衣的特点" --llm
```

Day 5 冒烟测试：

```powershell
python -m scripts.verify_agent
```

验证记录保存到 `docs/day5_agent_smoke_test.md`。
