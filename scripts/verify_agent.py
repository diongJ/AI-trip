from __future__ import annotations

import json
import time
from pathlib import Path

from scripts.verify_retrieval import _ensure_local_graph
from src.agent.service import AgentService
from src.agent.tools import AgentTools
from src.graph.retriever import LocalGraphRetriever
from src.rag.index import build_rag_index
from src.rag.retriever import RagRetriever


QUESTIONS = [
    ("文帝行玺是什么材料？", "kg_fact", False),
    ("赵眜和南越文王墓是什么关系？", "kg_fact", False),
    ("文帝行玺和赵眜有什么关系？", "kg_fact", False),
    ("丝缕玉衣反映了什么丧葬观念？", "kg_fact", False),
    ("船纹铜提筒反映了什么？", "kg_fact", False),
    ("介绍一下文帝行玺。", "document_description", False),
    ("讲讲丝缕玉衣的特点。", "document_description", False),
    ("南越王博物院王墓展区在哪里？", "document_description", False),
    ("南越国是谁建立的？", "document_description", False),
    ("犀角形玉杯有什么特点？", "document_description", False),
    ("赵眜是谁？请结合文物证据。", "hybrid", False),
    ("南越文王墓为什么重要？", "hybrid", False),
    ("文帝行玺为什么能证明墓主身份？", "hybrid", False),
    ("今天馆内有多少游客？", "out_of_scope", True),
    ("广州哪里停车最方便？", "out_of_scope", True),
]


def main() -> None:
    build_rag_index(force=True)
    _ensure_local_graph()
    service = AgentService(
        AgentTools(
            document_retriever=RagRetriever(),
            graph_retriever=LocalGraphRetriever(),
        )
    )
    rows = []
    passed = 0
    for index, (question, category, should_refuse) in enumerate(QUESTIONS, start=1):
        started = time.perf_counter()
        answer = service.answer(question)
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        ok = answer.insufficient_evidence if should_refuse else bool(answer.citations)
        passed += int(ok)
        rows.append(
            {
                "id": index,
                "question": question,
                "category": category,
                "used_tools": [tool.value for tool in answer.used_tools],
                "citation_count": len(answer.citations),
                "insufficient_evidence": answer.insufficient_evidence,
                "latency_ms": latency_ms,
                "passed": ok,
            }
        )

    report = {"questions": len(rows), "passed": passed, "items": rows}
    Path("docs/day5_agent_smoke_test.md").write_text(_markdown(report), encoding="utf-8")
    print(json.dumps({"questions": len(rows), "passed": passed}, ensure_ascii=False))
    if passed < len(rows):
        raise SystemExit("Agent smoke test failed")


def _markdown(report: dict[str, object]) -> str:
    lines = [
        "# Day 5 Agent 冒烟测试记录",
        "",
        f"通过：{report['passed']}/{report['questions']}。",
        "",
        "| 编号 | 问题 | 类型 | 工具 | 引用数 | 拒答 | 延迟 ms | 通过 |",
        "|---|---|---|---|---:|---|---:|---|",
    ]
    for item in report["items"]:
        lines.append(
            "| {id} | {question} | {category} | {tools} | {citations} | {refuse} | {latency} | {passed} |".format(
                id=item["id"],
                question=item["question"],
                category=item["category"],
                tools=", ".join(item["used_tools"]) or "none",
                citations=item["citation_count"],
                refuse="是" if item["insufficient_evidence"] else "否",
                latency=item["latency_ms"],
                passed="是" if item["passed"] else "否",
            )
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
