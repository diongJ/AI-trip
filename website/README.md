# 南越数字博物志前端

React/Vite 前端通过 `app.api` 调用与 Streamlit 共用的 Python 知识运行时；问答、图谱实体和关系证据不再使用静态演示数据。

## 本地演示

在仓库根目录启动 API：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.api:app --host 127.0.0.1 --port 8000
```

另开终端启动前端：

```powershell
cd website
npm ci
npm run dev
```

Vite 会将 `/api` 请求代理到 `127.0.0.1:8000`。部署到单独域名时，设置 `VITE_API_BASE_URL` 为 API 地址，并通过 `NANYUE_WEB_ORIGINS` 限制允许访问 API 的来源。

## 素材替换

当前文物视觉为统一的低饱和占位构图。正式替换前请参照 [ASSET_CHECKLIST.md](./ASSET_CHECKLIST.md)，并保留馆方来源、版权与署名信息。

## 校验

```powershell
npm run lint
npm run build
```
