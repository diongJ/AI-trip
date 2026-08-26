from __future__ import annotations

from importlib.util import find_spec


REQUIRED_MODULES = ("httpx", "neo4j", "pydantic", "pydantic_settings")


def require_project_environment(streamlit_module: object) -> None:
    """Stop with an actionable message when Streamlit uses the wrong Python."""
    missing = [name for name in REQUIRED_MODULES if find_spec(name) is None]
    if not missing:
        return
    streamlit_module.error("当前 Streamlit 使用的不是项目虚拟环境。")
    streamlit_module.write("缺少依赖：" + "、".join(missing))
    streamlit_module.code(
        r".\.venv\Scripts\python.exe -m streamlit run app/Home.py",
        language="powershell",
    )
    streamlit_module.caption("请在项目根目录运行以上命令。")
    streamlit_module.stop()
