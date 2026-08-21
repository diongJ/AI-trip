# 南越王墓知识图谱 Schema V1

## 版本原则

Schema V1 于 Day 1 冻结。后续允许新增可选属性和向后兼容的实体或关系，不允许修改已有类型的语义或删除必填字段。实体标识、来源与证据必须贯穿抽取、融合和入库过程。

## 实体公共字段

| 字段 | 类型 | 必填 | 规则 |
|---|---|---:|---|
| `id` | string | 是 | 稳定且唯一，推荐 `类型小写:规范名称` |
| `name` | string | 是 | 去除首尾空白后的规范名称 |
| `type` | enum | 是 | 必须属于12种实体类型 |
| `aliases` | string[] | 是 | 默认空数组，不包含规范名称，不重复 |
| `description` | string | 是 | 可为空字符串，不得编造资料外信息 |
| `source_ids` | string[] | 是 | 至少一个来源文档 ID |
| `confidence` | number | 是 | 0 至 1，包含端点 |

实体类型：

| 类型 | 含义 | 示例 |
|---|---|---|
| `Person` | 历史人物 | 赵眜 |
| `Tomb` | 墓葬整体 | 南越文王墓 |
| `TombChamber` | 墓葬空间 | 主棺室 |
| `Relic` | 具体出土文物 | 文帝行玺 |
| `RelicCategory` | 文物类别 | 印章 |
| `Material` | 制作材料 | 金 |
| `Dynasty` | 朝代 | 西汉 |
| `State` | 历史政权 | 南越国 |
| `HistoricalEvent` | 历史事件 | 南越国建立 |
| `Culture` | 文化或文化影响 | 汉文化 |
| `Pattern` | 纹饰 | 龙纹 |
| `Exhibition` | 展览 | 南越藏珍 |

## 关系公共字段

| 字段 | 类型 | 必填 | 规则 |
|---|---|---:|---|
| `source_id` | string | 是 | 必须引用本批或图谱中存在的源实体 |
| `relation` | enum | 是 | 必须属于下表的关系类型 |
| `target_id` | string | 是 | 必须引用本批或图谱中存在的目标实体 |
| `evidence` | string | 是 | 非空原文证据，不允许只写推断结论 |
| `document_id` | string | 是 | 支持该关系的来源文档 ID |
| `confidence` | number | 是 | 0 至 1，包含端点 |

## 允许的关系组合

| 关系 | 源实体 | 目标实体 | 示例 |
|---|---|---|---|
| `BELONGS_TO_STATE` | Person | State | 赵眜 -> 南越国 |
| `BURIED_IN` | Person | Tomb | 赵眜 -> 南越文王墓 |
| `CONTAINS` | Tomb | TombChamber | 南越文王墓 -> 主棺室 |
| `EXCAVATED_FROM` | Relic | TombChamber | 文帝行玺 -> 主棺室 |
| `MADE_OF` | Relic | Material | 文帝行玺 -> 金 |
| `BELONGS_TO_CATEGORY` | Relic | RelicCategory | 文帝行玺 -> 印章 |
| `CREATED_IN` | Relic | Dynasty | 文帝行玺 -> 西汉 |
| `RELATED_TO_PERSON` | Relic | Person | 文帝行玺 -> 赵眜 |
| `REFLECTS_CULTURE` | Relic | Culture | 丝缕玉衣 -> 汉文化 |
| `HAS_PATTERN` | Relic | Pattern | 角形玉杯 -> 龙纹 |
| `INVOLVES_PERSON` | HistoricalEvent | Person | 墓主人身份判定 -> 赵眜 |
| `OCCURRED_IN` | HistoricalEvent | Dynasty | 南越国建立 -> 西汉 |

方向是 Schema 的组成部分。若资料表达反向事实，抽取结果仍应转换为表中的规范方向。

## 文档 Metadata

每份资料使用以下结构：

```json
{
  "doc_id": "DOC_001",
  "title": "资料标题",
  "source_url": "https://example.org/source",
  "source_type": "official",
  "category": "relic",
  "retrieved_at": "2026-08-21",
  "text": "资料正文"
}
```

`source_type` 初期允许 `official`、`academic`、`book`、`museum`、`other`。`category` 初期允许 `museum`、`tomb`、`person`、`relic`、`history`、`culture`、`exhibition`、`tourism`。

## 完整抽取示例

```json
{
  "entities": [
    {
      "id": "person:赵眜",
      "name": "赵眜",
      "type": "Person",
      "aliases": ["南越文王"],
      "description": "南越国第二代王",
      "source_ids": ["DOC_SAMPLE_001"],
      "confidence": 0.99
    },
    {
      "id": "tomb:南越文王墓",
      "name": "南越文王墓",
      "type": "Tomb",
      "aliases": [],
      "description": "赵眜的墓葬",
      "source_ids": ["DOC_SAMPLE_001"],
      "confidence": 0.99
    }
  ],
  "relations": [
    {
      "source_id": "person:赵眜",
      "relation": "BURIED_IN",
      "target_id": "tomb:南越文王墓",
      "evidence": "南越文王墓是南越国第二代王赵眜的墓葬。",
      "document_id": "DOC_SAMPLE_001",
      "confidence": 0.99
    }
  ]
}
```

## 入库约束

- Neo4j 中所有实体同时具有公共标签 `Entity` 和具体类型标签。
- `Entity.id` 建立唯一约束，实体写入统一使用 `MERGE`。
- 关系使用 Schema 中的枚举名称；创建前验证源、目标实体类型。
- 节点保存来源 ID 数组，关系保存证据、文档 ID 和置信度。
- 对无法确定的实体或关系不做猜测，应进入后续人工审核流程。

