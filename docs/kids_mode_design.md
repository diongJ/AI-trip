# 儿童板块设计：小越的南越故事屋

> 设计日期：2026-08-28
> 目标：在不破坏现有"可靠资料、证据可溯、拒答边界"原则的前提下，为问答智能体增加儿童友好模式——讲故事、讲文物、日常聊天。
> 原则：**儿童模式不联网、不编造**。所有回答仍来自知识图谱与 RAG 证据，只是把语言改写成孩子听得懂的样子；实时信息与范围外问题仍拒答。

## 1. 产品概念

| 项 | 设计 |
|---|---|
| 板块名 | 「小越的南越故事屋」 |
| 角色 | 「小越」——南越王博物院的儿童讲解员。温和、好奇、鼓励式语气，自称"小越"，称呼访客"小朋友" |
| 头像 | 印章式「越」字圆形徽章（沿用博物馆视觉，不卡通化，符合设计规范） |
| 三大能力 | ① 听故事 ② 认识文物 ③ 聊聊天 |

三大能力说明：

1. **听故事**：把 KG 关系链 + RAG 证据组织成 3~5 句小故事。例：选实体「文帝行玺」→ 拉「出土于/属于/制作于」关系 → 按证据改写为"赵眜的小印章"故事。
2. **认识文物**：简化讲解，带比喻。例：丝缕玉衣 = "用 2291 片小玉片做的'魔法铠甲'"。长度 ≤ 4 句，句式短。
3. **聊聊天**：问候、自我介绍、推荐参观路线、回应"你是谁/你好/今天看什么"。闲聊里的事实仍以知识库为准，不生成虚构设定。

## 2. 后端设计（src/agent + app/api.py）

### 2.1 请求层

- `app/api.py` 的 `AskRequest` 增加字段：`audience: Literal["adult", "kids"] = "adult"`。
- 复用现有 `answer_mode`（kids 模式下 deep/brief 的差异可忽略，统一短句）。

### 2.2 Agent 层（src/agent/）

| 模块 | 改动 |
|---|---|
| `models.py` | 新增 `Audience` 枚举（ADULT / KIDS）；`RouteDecision` 增加 `kids_intent: Literal["story","relic","chat"] | None` |
| `router.py` | audience=kids 时，先识别儿童意图：故事类关键词（"故事/讲讲/猜猜"）→ story；文物/博物馆实体 + 描述问法 → relic；问候闲聊（"你好/你是谁/谢谢"）→ chat；其余走现有路由 |
| `tools.py` | 工具路由不变（search_kg / search_documents / hybrid_search）；**禁用 web_search 兜底** |
| `service.py` | 新增 kids 回答生成路径：抽取式生成器增加 kids 变体（证据 → 儿童化改写模板）；DeepSeek 模式使用 kids system prompt（只允许基于证据改写，禁止补事实）；`suggested_questions` 改为儿童风格 |
| `service.py` | 拒答语气儿童化：超范围/实时信息 → "这个问题要问博物馆的叔叔阿姨哦"，仍返回 `insufficient_evidence=true` 与拒答状态 |

### 2.3 证据与安全边界（不妥协项）

- 回答仍携带 `citations`（doc_id/标题/证据片段），前端可折叠为"给大人看的依据"。
- kids 模式永不启用联网补充；`web_sources` 恒为空。
- 拒绝不当内容（暴力、贬损、与学习无关的诱导）用统一温和话术。
- 不虚构"赵眜爷爷亲口说"等无来源情节；故事只是对真实证据的叙事化排列。

### 2.4 评测

- `tests/test_agent.py` 增加儿童模式用例（约 6 题）：
  - 故事：`请给小朋友讲讲文帝行玺的故事` → 断言 `audience=kids` 生效、答案含证据子串、citations 非空
  - 文物：`丝缕玉衣是什么？`（kids）→ 断言含"玉片"且长度限制生效
  - 聊天：`你好，你是谁？` → 断言回应含"小越"
  - 拒答：`今天馆里人多吗？`（kids）→ 断言 insufficient_evidence 且无 citations
- `scripts/verify_agent` 冒烟测试可扩展 3 题儿童模式用例。

## 3. 前端设计（website）

### 3.1 入口

问答区（`#qa`）标题旁加「大人 / 小朋友」切换（tab 或双态开关）。切换后问答区进入儿童面板，其余页面不变。

### 3.2 儿童面板（QADemo 的 kids 变体或独立组件 `KidsQASection`）

布局（自上而下）：

1. **欢迎语**：`小越：你好呀小朋友！我是小越，南越王博物院的讲解员。你想听故事、看文物，还是和我聊聊天？`
2. **三个大卡片入口**（横向，点击填入示例问题并自动提问）：
   - `听故事`（◆ 纹样图标）— 示例：`给我讲一个文帝行玺的小故事`
   - `认识文物`（玉璧纹样）— 示例：`丝缕玉衣是做什么用的？`
   - `聊聊天`（印章纹样）— 示例：`你是谁呀？`
3. **问答区**：大输入框（字号 ≥16px）、大按钮；回答分行短句；引用折叠为 `给大人看的依据`（默认收起）。
4. **风格**：沿用博物馆色板，圆角更大、留白更多；文字 18px+；头像为「越」字徽章。

### 3.3 与现有代码的衔接

- `website/src/lib/api.ts`：`ask()` 增加 `audience` 参数。
- 新增 `website/src/sections/KidsQA.tsx`（儿童面板），在 `QADemo.tsx` 里用 audience 状态切换，或独立区块。推荐：**独立区块**（`#kids` 章节 + 导航入口「故事屋」），问答区同时保留成人模式，互不干扰。

## 4. 可选：Streamlit 端

`app/pages/1_智能问答.py` 增加「儿童模式」开关，透传 `audience=kids` 给同一 `AppRuntime.ask()`，改动约 20 行。首期可不做。

## 5. 数据与语料（可选增强）

- 首期**不需要新语料**：现有 220 份资料（含 tourism 攻略、文物讲解、典故与儿童故事语料）足够支撑儿童改写。
- 可选二期：新增 5~10 份 `curated_guidance` 儿童故事语料（如《文帝行玺的小故事》《玉衣的秘密》《角形玉杯找朋友》），按现有语料格式入库，标注 `evidence_role=curated_guidance`，不进图谱。

## 6. 验收清单

- [ ] `pytest` 全绿（含新增儿童模式用例）
- [ ] `python -m scripts.verify_agent` 通过（含 kids 用例）
- [ ] 网站问答区可切换儿童模式；三种能力各自可用
- [ ] 儿童回答均带可折叠证据；kids 模式无 web_sources
- [ ] 拒答用例（实时信息/范围外）在儿童模式下仍正确拒答
- [ ] 移动端无溢出

## 7. 改动文件清单（预计）

后端：`src/agent/models.py`、`src/agent/router.py`、`src/agent/service.py`、`src/agent/tools.py`、`app/api.py`、`tests/test_agent.py`、`scripts/verify_agent.py`（可选）
前端：`website/src/lib/api.ts`、`website/src/sections/QADemo.tsx`（或新增 `KidsQA.tsx`）、`website/src/pages/Home.tsx`、`website/src/sections/Navbar.tsx`、`website/src/index.css`
文档：`docs/kids_mode_design.md`（本文件）、README 增补小节
