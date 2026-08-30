# 公开 Demo 部署（Railway）

本项目以一个常在线 Railway 服务交付：FastAPI 同时提供 `/api/*` 和构建后的 React 页面，因此不需要单独的前端域名或 CORS 配置。

## 首次部署

1. 将 `codex/public-demo-release` 合入需要发布的分支并推送 GitHub。
2. 在 Railway 新建项目，选择仓库并使用根目录的 `Dockerfile`。
3. 选择付费常在线实例，并在服务变量中设置：

   ```dotenv
   DEEPSEEK_API_KEY=实际密钥
   SEMANTIC_RETRIEVAL_ENABLED=false
   DEMO_RATE_LIMIT_PER_MINUTE=12
   ```

   `PORT` 由 Railway 自动注入；不要配置或提交任何 `.env` 文件。Neo4j 变量可不填，服务会使用仓库内只读图谱。
4. 生成 Railway 默认域名后，访问 `/api/health`。它应返回 `status: ok`，并显示当前 `release`、DeepSeek 与离线后端状态。

## 发布验收

- 访问首页和 `/relic/wendi-seal`，确认刷新后仍正常显示。
- 连续发送 13 次问答，确认第 13 次返回 429 和 `Retry-After`；正常使用时问答、儿童模式、图谱查询均可用。
- 临时移除 `DEEPSEEK_API_KEY` 后重新部署，确认 `/api/health` 显示 `fallback_mode: true`，并且问答仍返回有引用的离线答案。
- 通过手机蜂窝网络检查网站、来源外链与页面首屏。

## 时效资料

`DOC_239` 的王宫展区暑期延长开放仅有效至 2026-08-31；检索器按上海时区自动在 9 月 1 日排除该公告。每次发布前仍需复核馆方公告中的开放、预约及研学规则；未核实的新规则不能写成确定事实。
