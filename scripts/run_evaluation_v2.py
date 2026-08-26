from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

from scripts.verify_retrieval import _ensure_local_graph
from src.agent.service import AgentService, ExtractiveAnswerGenerator
from src.agent.tools import AgentTools
from src.graph.retriever import LocalGraphRetriever
from src.rag.index import build_rag_index
from src.rag.retriever import RagRetriever


def main() -> None:
    parser = argparse.ArgumentParser(description="运行南越专题 90 题可复算评测。")
    parser.add_argument("--questions", default="data/evaluation/questions_v2.json")
    parser.add_argument("--output-dir", default="data/evaluation")
    parser.add_argument("--baseline", help="可选的旧 summary JSON，用于计算指标变化")
    args = parser.parse_args()

    payload = json.loads(Path(args.questions).read_text(encoding="utf-8"))
    questions = payload["questions"]
    build_rag_index()
    _ensure_local_graph()
    service = AgentService(
        AgentTools(
            document_retriever=RagRetriever(),
            graph_retriever=LocalGraphRetriever(),
        ),
        generator=ExtractiveAnswerGenerator(),
    )
    rows = [_evaluate(case, service) for case in questions]
    summary = _summarize(rows)
    summary["targets"] = payload["targets"]
    summary["target_status"] = {
        metric: (
            summary[metric] <= target if metric.endswith("latency_ms") else summary[metric] >= target
        )
        for metric, target in payload["targets"].items()
        if metric in summary
    }
    if args.baseline:
        baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        summary["baseline_delta"] = {
            metric: round(summary[metric] - baseline[metric], 4)
            for metric in ("answer_rate", "hit_at_5", "citation_correctness", "refusal_accuracy")
            if metric in baseline
        }

    output = Path(args.output_dir)
    raw_dir = output / "raw_results"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "upgrade_v2.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output / "summary_v2.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _evaluate(case: dict[str, object], service: AgentService) -> dict[str, object]:
    started = time.perf_counter()
    answer = service.answer(str(case["question"]))
    latency_ms = round((time.perf_counter() - started) * 1000, 3)
    searchable = "\n".join(
        [
            answer.answer,
            *[hit.content for hit in answer.retrieved_documents[:5]],
            *[hit.evidence for hit in answer.graph_facts[:5]],
        ]
    )
    expected_terms = [str(term) for term in case.get("expected_terms", [])]
    hit = not expected_terms or any(term in searchable for term in expected_terms)
    citation_correct = all(
        citation.evidence in service.source_lookup[citation.doc_id].text
        for citation in answer.citations
        if citation.doc_id in service.source_lookup
    ) and all(citation.doc_id in service.source_lookup for citation in answer.citations)
    return {
        **case,
        "answer": answer.answer,
        "insufficient_evidence": answer.insufficient_evidence,
        "citation_count": len(answer.citations),
        "hit_at_5": hit,
        "citation_correct": citation_correct,
        "latency_ms": latency_ms,
        "used_tools": [tool.value for tool in answer.used_tools],
        "source_tiers": answer.source_tiers,
    }


def _summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    answerable = [row for row in rows if row["answerable"]]
    unanswerable = [row for row in rows if not row["answerable"]]
    answered = [row for row in answerable if not row["insufficient_evidence"]]
    cited = [row for row in answered if row["citation_count"]]
    latencies = sorted(float(row["latency_ms"]) for row in rows)
    p95_index = max(0, math.ceil(len(latencies) * 0.95) - 1)
    return {
        "question_count": len(rows),
        "answer_rate": round(len(answered) / len(answerable), 4),
        "hit_at_5": round(sum(bool(row["hit_at_5"]) for row in answerable) / len(answerable), 4),
        "citation_correctness": round(
            sum(bool(row["citation_correct"]) for row in cited) / len(cited), 4
        ) if cited else 0.0,
        "refusal_accuracy": round(
            sum(bool(row["insufficient_evidence"]) for row in unanswerable) / len(unanswerable), 4
        ),
        "p95_latency_ms": latencies[p95_index],
    }


if __name__ == "__main__":
    main()
