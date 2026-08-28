"""离线问答评测基线。

用法：
    python -m scripts.evaluate_qa [--eval data/eval/qa_eval.json] [--verbose]

对 data/eval/qa_eval.json 中的每个用例运行离线 AgentService（抽取式生成器，
不调用 DeepSeek），判定规则：

- expect=answered：未拒答，且答案包含全部 must_contain 子串；
- expect=refused：insufficient_evidence 为 True 且无引用。

输出逐题结果与汇总指标（回答正确率、拒答正确率、总体准确率、平均答案长度）。
基线模式永远以 0 退出；传 --fail-under 0.9 可在准确率低于阈值时以 1 退出（CI 用）。
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from src.agent.service import AgentService
from src.agent.tools import AgentTools
from src.agent.models import Audience
from src.graph.retriever import LocalGraphRetriever
from src.rag.retriever import RagRetriever

DEFAULT_EVAL_PATH = Path("data/eval/qa_eval.json")
DEFAULT_INDEX_DIR = Path("data/processed/rag")
DEFAULT_GRAPH_PATH = Path("data/graph/knowledge_graph_v1.json")


@dataclass
class CaseResult:
    case_id: str
    question: str
    expect: str
    passed: bool
    insufficient: bool
    answer: str
    tools: list[str]
    note: str


def build_service() -> AgentService:
    return AgentService(
        AgentTools(
            document_retriever=RagRetriever(DEFAULT_INDEX_DIR),
            graph_retriever=LocalGraphRetriever(DEFAULT_GRAPH_PATH),
        )
    )


def run_case(service: AgentService, case: dict) -> CaseResult:
    audience = Audience.KIDS if case.get("audience") == "kids" else Audience.ADULT
    answer = service.answer(case["question"], audience=audience)
    expect = case["expect"]
    if expect == "answered":
        required = case.get("must_contain", [])
        passed = (
            not answer.insufficient_evidence
            and all(fragment in answer.answer for fragment in required)
        )
    else:
        passed = answer.insufficient_evidence and not answer.citations
    return CaseResult(
        case_id=case["id"],
        question=case["question"],
        expect=expect,
        passed=passed,
        insufficient=answer.insufficient_evidence,
        answer=answer.answer,
        tools=[tool.value for tool in answer.used_tools],
        note=case.get("note", ""),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="离线问答评测基线")
    parser.add_argument("--eval", default=str(DEFAULT_EVAL_PATH), help="评测集 JSON 路径")
    parser.add_argument("--verbose", action="store_true", help="打印每个用例的答案全文")
    parser.add_argument("--fail-under", type=float, default=None, help="总体准确率低于该值时以 1 退出")
    args = parser.parse_args()

    cases = json.loads(Path(args.eval).read_text(encoding="utf-8"))
    service = build_service()

    results = [run_case(service, case) for case in cases]

    answered = [r for r in results if r.expect == "answered"]
    refused = [r for r in results if r.expect == "refused"]
    answered_ok = sum(1 for r in answered if r.passed)
    refused_ok = sum(1 for r in refused if r.passed)
    total_ok = answered_ok + refused_ok
    accuracy = total_ok / len(results) if results else 0.0
    lengths = [len(r.answer) for r in results if not r.insufficient]

    for r in results:
        mark = "PASS" if r.passed else "FAIL"
        print(f"[{mark}] {r.case_id}｜{r.question}")
        print(f"      期望={r.expect} 实际={'拒答' if r.insufficient else '回答'} 工具={r.tools}")
        if args.verbose or not r.passed:
            preview = r.answer if args.verbose else r.answer[:120]
            print(f"      答案：{preview}")
        if r.note:
            print(f"      备注：{r.note}")

    print("=" * 60)
    print(f"回答类：{answered_ok}/{len(answered)} 通过")
    print(f"拒答类：{refused_ok}/{len(refused)} 通过")
    print(f"总体准确率：{accuracy:.1%}（{total_ok}/{len(results)}）")
    if lengths:
        print(f"已回答用例平均答案长度：{sum(lengths) / len(lengths):.0f} 字（最长 {max(lengths)}）")

    if args.fail_under is not None and accuracy < args.fail_under:
        print(f"准确率 {accuracy:.1%} 低于阈值 {args.fail_under:.1%}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
