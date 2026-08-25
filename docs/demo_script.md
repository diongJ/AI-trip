# Day 6 演示脚本

## 演示准备

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m streamlit run app/Home.py
```

不要省略 `.\.venv\Scripts\python.exe -m`。这可确保 Streamlit、Pydantic 与项目代码来自同一个虚拟环境。

首次启动会加载本地只读图谱并检查 RAG 索引；索引缺失时自动从 36 份语料重建。侧边栏应显示 36 份资料、78 个实体和 87 条关系。DeepSeek 不可用时页面会明确提示并自动使用离线证据摘录。

## 五条固定路径

1. **首页**：确认项目目标、三项数据规模、可靠性原则、范围提示和三个功能入口均可见。
2. **事实问答**：进入“智能问答”，点击“文帝行玺是什么材料？”。确认工具为 `search_kg`，答案包含“金”，并展开 `DOC_013` 引用。
3. **混合问答**：提问“丝缕玉衣反映了什么丧葬观念？”。确认工具为 `hybrid_search`，回答同时展示来源和路由原因。
4. **深度讲解**：选择一个文物与“亲子版”，生成讲解；确认存在来源，并下载 Markdown 讲解稿。
5. **图谱探索**：搜索别名“南越文王”，打开“赵眜”，沿相邻节点进入“南越文王墓”，再展开一条关系证据与来源链接。

## 验收命令

```powershell
python -m scripts.verify_demo
python -m scripts.verify_agent
pytest
```

在桌面宽屏和约 390px 宽的浏览器视口各执行一次以上路径。窄屏下关系卡片应改为纵向排列，页面不应出现水平溢出或不可操作控件。
