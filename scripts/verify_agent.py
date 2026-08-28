from __future__ import annotations

import json
import time
from pathlib import Path

from scripts.verify_retrieval import _ensure_local_graph
from src.agent.models import Audience
from src.agent.service import AgentService
from src.agent.tools import AgentTools
from src.graph.retriever import LocalGraphRetriever
from src.rag.index import build_rag_index
from src.rag.retriever import RagRetriever


QUESTIONS = [
    {"question": "文帝行玺是什么材料？", "category": "kg_fact", "tool": "search_kg", "terms": ["金"], "relation": "MADE_OF"},
    {"question": "赵眜和南越文王墓是什么关系？", "category": "kg_fact", "tool": "search_kg", "terms": ["赵眜", "南越文王墓"]},
    {"question": "文帝行玺和赵眜有什么关系？", "category": "kg_fact", "tool": "search_kg", "terms": ["文帝行玺", "赵眜"]},
    {"question": "丝缕玉衣反映了什么丧葬观念？", "category": "hybrid", "tool": "hybrid_search", "terms": ["丝缕玉衣", "玉衣"]},
    {"question": "船纹铜提筒反映了什么？", "category": "hybrid", "tool": "hybrid_search", "terms": ["船纹铜提筒", "船纹"]},
    {"question": "介绍一下文帝行玺。", "category": "document_description", "tool": "hybrid_search", "terms": ["文帝行玺"]},
    {"question": "讲讲丝缕玉衣的特点。", "category": "document_description", "tool": "hybrid_search", "terms": ["丝缕玉衣", "玉衣"]},
    {"question": "南越王博物院王墓展区在哪里？", "category": "visit_guidance", "tool": "search_documents", "terms": ["解放北路", "王墓展区"]},
    {"question": "南越国是谁建立的？", "category": "hybrid", "tool": "hybrid_search", "terms": ["赵佗"]},
    {"question": "犀角形玉杯有什么特点？", "category": "document_description", "tool": "hybrid_search", "terms": ["犀角形玉杯", "玉杯"]},
    {"question": "赵眜是谁？请结合文物证据。", "category": "hybrid", "tool": "hybrid_search", "terms": ["赵眜", "南越文帝"]},
    {"question": "南越文王墓为什么重要？", "category": "hybrid", "tool": "hybrid_search", "terms": ["南越文王墓", "南越王墓"]},
    {"question": "文帝行玺为什么能证明墓主身份？", "category": "hybrid", "tool": "hybrid_search", "terms": ["文帝行玺", "南越文帝"]},
    {"question": "第一次去王墓展区应该怎么看？", "category": "visit_guidance", "tool": "search_documents", "terms": ["王墓展区", "文帝行玺", "重点"]},
    {"question": "王墓展区开放时间和预约怎么安排？", "category": "visit_guidance", "tool": "search_documents", "terms": ["9:00-17:30", "预约", "官方"]},
    {"question": "带学生参观南越王博物院可以讲哪些问题？", "category": "visit_guidance", "tool": "search_documents", "terms": ["学生", "墓主人", "文帝行玺"]},
    {"question": "今天馆内有多少游客？", "category": "out_of_scope", "tool": "none", "refuse": True},
    {"question": "今天王墓展区还剩多少预约名额？", "category": "out_of_scope", "tool": "none", "refuse": True},
    {"question": "广州哪里停车最方便？", "category": "out_of_scope", "tool": "none", "refuse": True},
    {"question": "火星上的南越王墓是谁建的？", "category": "false_premise", "tool": "none", "refuse": True},
    {"question": "给我讲一个文帝行玺的小故事", "category": "kids_story", "audience": "kids", "tool": "search_kg", "terms": ["文帝行玺"]},
    {"question": "丝缕玉衣是做什么用的？", "category": "kids_relic", "audience": "kids", "tool": "search_kg", "terms": ["丝缕玉衣"]},
    {"question": "你是谁呀？", "category": "kids_chat", "audience": "kids", "chat": True, "tool": "none", "terms": ["小越"]},
    {"question": "今天馆内有多少游客？", "category": "kids_refuse", "audience": "kids", "tool": "none", "refuse": True},
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
    for index, case in enumerate(QUESTIONS, start=1):
        question = case["question"]
        started = time.perf_counter()
        answer = service.answer(
            question,
            audience=Audience.KIDS if case.get("audience") == "kids" else Audience.ADULT,
        )
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        actual_tools = [tool.value for tool in answer.used_tools]
        expected_tool = case["tool"]
        tool_ok = actual_tools == ([] if expected_tool == "none" else [expected_tool])
        if case.get("refuse", False):
            content_ok = answer.insufficient_evidence and not answer.citations
        elif case.get("chat", False):
            terms = case.get("terms", [])
            content_ok = (
                not answer.insufficient_evidence
                and any(term in answer.answer for term in terms)
            )
        else:
            searchable = "\n".join(
                [answer.answer, *[citation.evidence for citation in answer.citations]]
            )
            terms = case.get("terms", [])
            terms_ok = any(term in searchable for term in terms) if terms else True
            required_relation = case.get("relation")
            relation_ok = (
                any(hit.relation == required_relation for hit in answer.graph_facts)
                if required_relation
                else True
            )
            content_ok = (
                not answer.insufficient_evidence
                and bool(answer.citations)
                and terms_ok
                and relation_ok
            )
        ok = tool_ok and content_ok
        passed += int(ok)
        rows.append(
            {
                "id": index,
                "question": question,
                "category": case["category"],
                "expected_tool": expected_tool,
                "used_tools": actual_tools,
                "citation_count": len(answer.citations),
                "insufficient_evidence": answer.insufficient_evidence,
                "content_ok": content_ok,
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
        "| 编号 | 问题 | 类型 | 预期工具 | 实际工具 | 内容正确 | 引用数 | 拒答 | 延迟 ms | 通过 |",
        "|---|---|---|---|---|---|---:|---|---:|---|",
    ]
    for item in report["items"]:
        lines.append(
            "| {id} | {question} | {category} | {expected} | {tools} | {content} | {citations} | {refuse} | {latency} | {passed} |".format(
                id=item["id"],
                question=item["question"],
                category=item["category"],
                expected=item["expected_tool"],
                tools=", ".join(item["used_tools"]) or "none",
                content="是" if item["content_ok"] else "否",
                citations=item["citation_count"],
                refuse="是" if item["insufficient_evidence"] else "否",
                latency=item["latency_ms"],
                passed="是" if item["passed"] else "否",
            )
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
