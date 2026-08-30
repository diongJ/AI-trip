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

## 2026-08-26 Agent 与参观攻略优化

### 当前状态

- 工作分支：`codex/improve-agent-corpus`。
- 基线分支：`main` / `origin/main`，起点为 `8635f4e`。
- `docs/website_design_agent_prompt.md` 已加入 `.gitignore`，不纳入仓库。

### 已完成内容

- 新增 12 份 `tourism` 参观攻略语料：基础开放/预约边界、游览动线、重点文物、亲子学生讲解、一小时/两小时/半日安排、游客分层建议、动态信息边界。
- 新增 9 份历史、人物、文化、文物和展区辨析扩展资料，补强南越文王墓、赵眜、文帝行玺、丝缕玉衣、角形玉杯、船纹铜提筒、铜虎节等常问主题。
- 继续新增 20 份资料 `DOC_174-DOC_193`：文物 8 份、旅游攻略 4 份、场地资料 4 份、历史文化背景 4 份。
- 继续新增 40 份资料 `DOC_194-DOC_233`：文物 15 份、旅游攻略 10 份、场地资料 7 份、历史文化背景 8 份。
- 新增 `docs/knowledge_base_expansion.md`，记录扩充资料范围、来源边界和验证结果。
- Agent 路由区分稳定参观信息与实时动态信息：稳定开放时间、地址、预约边界、游览建议可检索回答；当天客流、余票、天气、停车空位、导航仍拒答。
- 实体识别先从图谱真实实体名和别名中匹配，避免长问题或讲解 prompt 把实体识别成整句。
- 文档检索新增多查询扩展和南越专题兜底；KG 关系过滤在过窄时回退到原图谱证据，减少“搜不到就无法回答”的情况。
- 参观攻略意图优先限制在 `tourism` 类资料，避免被泛化展览列表挤占。
- DeepSeek 模式新增通用兜底：本地无可引用证据时可调用 DeepSeek 自身回答，并明确标注“本地知识库未检索到可引用证据”；实时和范围外问题仍不启用该兜底。

### 验证记录

- `python -m scripts.validate_corpus` 通过：181 docs。
- `python -m scripts.build_rag_index --force` 通过：181 docs。
- `python -m scripts.verify_rag` 通过：9/10。
- `python -m scripts.verify_retrieval` 通过。
- `python -m scripts.verify_agent` 通过：20/20。
- `python -m scripts.verify_demo` 通过：5/5。
- `python -m pytest` 通过：72 passed，6 skipped。

## 2026-08-28 跟进同步与健康验证

### 当前状态

- 本地 `main` 由 `8635f4e` 快进同步至 `origin/main` `71691cd`，合入 PR #14（50 题评测基线）、PR #15（grounding 加固）与 PR #16（Day8++：网站重建为南越数字博物馆、游客导览 V2 扩充 DOC_234-DOC_262）。
- 清理了本地未跟踪的 `website/`（仅含 `dist/` 与 `node_modules/`，无源码，可由远程源码重新生成）；`docs/website_design_agent_prompt.md` 已被 `.gitignore` 忽略，保留在本地不入库。
- 本地 `.env` 仍为 `DEEPSEEK_MODEL=deepseek-chat`，README 新口径为 `deepseek-v4-flash`（个人凭据差异，不提交）。

### 验证记录

- 补齐 venv dev 依赖后 `python -m pytest` 通过：111 passed（较 08-26 的 72 passed + 6 skipped 新增 API 与游客导览 V2 测试）。
- 沙箱环境注意：`pip install` 与 `pytest` 的临时目录需显式指向工作区内路径（如 `.tmp-pip`），否则 Windows 上会因系统 Temp 写入受限报 PermissionError。

### 待办线索

- `docs/visitor_guidance/open_issues.md` B1：王宫展区暑期延长开放 2026-08-31 后失效，需按复查要求更新语料。
- `website/ASSET_CHECKLIST.md`：网站文物视觉仍为占位构图，待正式素材替换。

## 2026-08-28 儿童板块与典故知识库

### 当前状态

- 儿童板块「小越的南越故事屋」已实现并上线：后端 `Audience.KIDS`、儿童意图识别（story/relic/chat）、儿童化回答与拒答语气；网站独立区块 + 导航入口；Streamlit 智能问答页加「儿童模式」开关。
- 儿童模式**固定走离线证据生成**（`小越离线故事`）：DeepSeek 叙事化生成对儿童短句的接地校验不稳定，待提示词调优后按需启用。
- 典故知识库扩充 DOC_263-DOC_267（陆贾使越、任嚣授命、赵佗称帝归汉、和辑百越、文帝行玺僭号），路由新增 `anecdote` 意图并跳过规划器。
- 关键修复：故事/典故类问题在 `search_kg` 跳过离题过滤；儿童故事优先 KG 事实；典故文档检索后按关键词过滤，防止博物馆概况文档答偏。

### 验证记录

- `pytest` 全量通过（含 4 个儿童模式用例）。
- `/api/ask` 实测（Python httpx，注意 PowerShell 发中文体会乱码）：儿童聊天返回 `chat` 状态；「南越时期有什么典故」「文帝行玺有什么典故？」返回带引用的典故回答；儿童故事返回 KG 事实故事。
- 注意：沙箱环境下 pip/pytest/uvicorn 均需把临时目录指向工作区内 `.tmp-pip`；杀 uvicorn/streamlit 进程后需确认端口已释放再重启。

## 2026-08-28 七项体验与质量优化

- ① 儿童模式恢复 DeepSeek 智能故事：先生成、校验失败自动回退离线故事（实测返回 3 条引用的主题内回答）。
- ② 新增儿童故事语料 DOC_268-DOC_272（文帝行玺/玉衣/角形玉杯/组玉佩/儿童参观动线），语料 220 份。
- ③ 网站问答（QADemo 与 KidsQA）升级为多轮会话：保留最近 4 轮历史，追问可解析（实测「它出土在哪里？」正确指代文帝行玺）。
- ④ 图谱探索加入防抖实时搜索。
- ⑤ 语义检索未启用：沙箱无法访问 HuggingFace 下载 BGE 模型（torch 亦约 2GB），README 已有启用指引，留待正常网络环境。
- ⑥ 新增 `.github/workflows/ci.yml`：pytest + 评测门禁（≥90%）+ 冒烟 24 题 + 网站 lint/build。
- ⑦ 网站补全 OG/Twitter meta、theme-color，新增 404 页面；修复 SpotlightCard 的 `React.MouseEvent` 类型未导入问题（`npm run build` 的 tsc 通过）。
- 验证：pytest 全量通过；60 题评测 100%；24 题冒烟全过；`npm run build` 成功。

## 2026-08-28 智能体 IQ 优化（评测 60→120 题，全过）

- 评测集扩展至 **120 题**（多跳/比较/否定/复合/时效/人物辨析/典故/儿童/参观/域外），从 85.8% 优化到 **100%**。
- 核心改动（router/service/tools）：
  - 描述词路由扩展（自称/位于/多少/是什么/分别等 → 混合检索，不再纯 KG 空转）；
  - 实体候选限长 ≤6 字，修复"整句话被误当成实体"；
  - KG 证据缺失时文档兜底放宽（实体在文档中即够）+ 样板页（备案/导航）过滤；
  - "是…吗"确认问法：只扫实体前的未知主语（李鴻章拒答 / 用铜做的放行）；
  - 比较/关系类问法：词表外方面词即拒答（赋税/西游记/皇帝的新衣）；
  - 外来词（GDP）未知检查；动词+体貌后缀（灭掉→灭）不误判；
  - 王宫展区开放/预约/延长公告问题放行（走普通文档检索，不再误拒）；
  - 博物院/博物馆为主语时走文档检索，避免被解析成人物别名；
  - 复合问题按逗号/顿号拆分查询；多实体问题（A和B分别是什么）双实体混合检索；
  - 儿童故事/讲解对文物人物类实体强制 KG，儿童模式跳过未知词守卫；
  - 儿童答案与证据 ID 使用同一排序文档（修复接地校验不一致 bug）。
- 验证：120 题评测 100%、24 题冒烟全过、pytest 全量通过。

## 2026-08-28 本地推进检查与远端提交

- 当前本地工作在 `main`，相对 `origin/main` 超前 6 个已提交 commit：`9e4ab8f`、`fad9fb3`、`38b75d5`、`735dfbc`、`c1f9952`、`1791316`。
- 为避免直接推送覆盖远端 `main`，远端提交应推到独立分支后再发 PR。
- 本地验证结果：`scripts.validate_corpus` 通过，语料 220 份；`scripts.verify_agent` 通过 24/24；`scripts.verify_demo` 通过 5/5；`pytest` 通过 115 passed。
- 本机 `.venv` 的 Python 启动器路径已失效；可临时使用 bundled Python 并设置 `PYTHONPATH=.\\.venv\\Lib\\site-packages`。pytest 需要把 `--basetemp` 指向项目内 `.tmp-pytest`。

## 2026-08-30 公开 Demo 发布准备

- 发布分支：`codex/public-demo-release`，基线为 `origin/main` 的 `cc79216`。
- 新增同域发布工件：`Dockerfile` 多阶段构建 React/Vite 与 Python/FastAPI，`railway.toml` 提供 Railway 健康检查；FastAPI 直接提供构建后的前端并支持文物详情等 SPA 刷新路由。
- 线上默认关闭 BGE 语义模型，保留 BM25、本地图谱和 DeepSeek 异常时的离线证据回答；`DEEPSEEK_API_KEY` 只允许经 Railway Secrets 注入。
- `/api/ask` 增加每 IP 每分钟限流（默认 12，可用 `DEMO_RATE_LIMIT_PER_MINUTE` 配置），超限返回 429 与 `Retry-After`；`/api/health` 增加 RAG、语义、DeepSeek、Neo4j 与发布版本状态。
- 新增研究区系统架构图（SVG + Mermaid 源码），并纠正素材清单中已经接入的文物局部图状态。
- 时效规则已覆盖：`DOC_239` 在 2026-08-31 当日可检索，2026-09-01 起自动由上海时区过滤；每次上线前仍须复核馆方开放与研学公告。

### 验证记录

- `pytest -q --basetemp .tmp-pytest-full` 通过。
- `python -m scripts.evaluate_qa --fail-under 0.9`：120/120（100%）。
- `python -m scripts.verify_agent`：24/24；`python -m scripts.verify_demo`：5/5。
- 网站 `npm run lint` 与 `npm run build` 通过；同域首页、`/relic/wendi-seal`、架构图和未知 API 路由冒烟检查通过。
- 缺失 DeepSeek Key 的 `/api/health` 验证为 `fallback_mode=true`；配置 Key 时状态为 `deepseek_configured=true`。

### 待办线索

- 本机未安装 Docker，尚未进行容器运行验收。
- Railway 项目创建、Secrets 填写、常在线实例选择和公网 URL 验收需由拥有 Railway 账户的成员完成；步骤见 `docs/public_demo_deployment.md`。
