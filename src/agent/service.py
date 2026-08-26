from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Protocol

from src.agent.context import (
    build_grounded_context,
    citations_from_result,
    document_evidence_id,
    graph_evidence_id,
    load_source_lookup,
)
from src.agent.models import AgentAnswer, GeneratedAnswer, RouteDecision, ToolName, ToolResult
from src.agent.planner import QueryPlanner
from src.agent.router import RuleBasedRouter
from src.agent.tools import (
    AUDIENCE_HINTS,
    AgentTools,
    QUESTION_STOP_PHRASES,
    SCAFFOLD_CHARS,
    _content_term_matches,
    _question_content_bigrams,
    _relation_hint_matches,
    _relation_label,
)
from src.config.settings import ConfigurationError, Settings
from src.preprocessing import CorpusDocument

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - minimal offline installs use extractive mode
    httpx = None


class AnswerGenerationError(RuntimeError):
    pass


class AnswerGenerator(Protocol):
    def generate(self, question: str, route: RouteDecision, result: ToolResult) -> GeneratedAnswer: ...


class FallbackAnswerGenerator(Protocol):
    def generate_without_evidence(self, question: str, route: RouteDecision) -> str: ...


class ExtractiveAnswerGenerator:
    def generate(self, question: str, route: RouteDecision, result: ToolResult) -> GeneratedAnswer:
        selected = [
            *[graph_evidence_id(hit) for hit in result.graph[:3]],
            *[document_evidence_id(hit) for hit in result.documents[:2]],
        ]
        if route.tool in {ToolName.SEARCH_DOCUMENTS, ToolName.HYBRID_SEARCH} and result.documents:
            snippets = [hit.content for hit in result.documents[:2]]
            return GeneratedAnswer(answer="\n".join(snippets), selected_evidence_ids=selected)
        if result.graph:
            facts = [
                f"{hit.source_entity.name}{_relation_label(hit.relation)}{hit.target_entity.name}。证据：{hit.evidence}"
                for hit in result.graph[:3]
            ]
            return GeneratedAnswer(answer="\n".join(facts), selected_evidence_ids=selected)
        if result.documents:
            snippets = [hit.content for hit in result.documents[:2]]
            return GeneratedAnswer(answer="\n".join(snippets), selected_evidence_ids=selected)
        return GeneratedAnswer(
            answer="当前可靠资料不足以确认该问题。",
            supported=False,
            refusal_reason="检索结果为空",
        )


class DeepSeekAnswerGenerator:
    def __init__(
        self,
        settings: Settings,
        *,
        prompt_path: str | Path = "prompts/grounded_answer.txt",
        http_client: object | None = None,
    ) -> None:
        if httpx is None:
            raise ConfigurationError("httpx is required for DeepSeek answer generation.")
        settings.require_deepseek()
        self.settings = settings
        self.prompt_path = Path(prompt_path)
        self._owns_client = http_client is None
        self.client = http_client or httpx.Client(timeout=45.0)

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def generate(self, question: str, route: RouteDecision, result: ToolResult) -> GeneratedAnswer:
        context = build_grounded_context(result)
        if not context.strip():
            return GeneratedAnswer(
                answer="当前可靠资料不足以确认该问题。",
                supported=False,
                refusal_reason="没有可用证据",
            )
        prompt = self.prompt_path.read_text(encoding="utf-8")
        payload = {
            "model": self.settings.deepseek_model,
            "messages": [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": (
                        f"问题：{question}\n"
                        f"路由：{route.model_dump_json()}\n\n"
                        f"可用证据：\n{context}"
                    ),
                },
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        try:
            response = self.client.post(
                f"{self.settings.deepseek_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.deepseek_api_key.get_secret_value()}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(_strip_code_fence(content))
            generated = GeneratedAnswer.model_validate(parsed)
            if generated.supported and not generated.selected_evidence_ids:
                raise TypeError("supported answer must select at least one evidence id")
            return generated
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AnswerGenerationError(f"DeepSeek answer generation failed: {exc}") from exc


class DeepSeekFallbackAnswerGenerator:
    """Use DeepSeek general knowledge only after local retrieval fails."""

    def __init__(self, settings: Settings, *, http_client: object | None = None) -> None:
        if httpx is None:
            raise ConfigurationError("httpx is required for DeepSeek fallback generation.")
        settings.require_deepseek()
        self.settings = settings
        self._owns_client = http_client is None
        self.client = http_client or httpx.Client(timeout=45.0)

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def generate_without_evidence(self, question: str, route: RouteDecision) -> str:
        payload = {
            "model": self.settings.deepseek_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是南越王博物院王墓展区智慧导览助手。本次没有检索到本地知识库证据。"
                        "可以用模型自身知识给出谨慎、面向游客的回答，但必须控制在100字以内，"
                        "直接回答，不要重复问题，不要展开背景。"
                        "不要编造实时客流、余票、票价、临时闭馆、天气、停车空位或导航路径。"
                        "若问题需要实时信息，建议用户查看官方平台或地图服务。"
                    ),
                },
                {
                    "role": "user",
                    "content": f"问题：{question}\n本地路由：{route.model_dump_json()}",
                },
            ],
            "temperature": 0.2,
        }
        try:
            response = self.client.post(
                f"{self.settings.deepseek_base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.settings.deepseek_api_key.get_secret_value()}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            content = str(response.json()["choices"][0]["message"]["content"]).strip()
            if not content:
                raise ValueError("empty DeepSeek fallback response")
            return content + "\n（以上为通用知识回答，未引用本地资料）"
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
            raise AnswerGenerationError(f"DeepSeek fallback generation failed: {exc}") from exc


class AgentService:
    def __init__(
        self,
        tools: AgentTools,
        *,
        router: RuleBasedRouter | None = None,
        generator: AnswerGenerator | None = None,
        fallback_generator: FallbackAnswerGenerator | None = None,
        planner: QueryPlanner | None = None,
        source_lookup: dict[str, CorpusDocument] | None = None,
    ) -> None:
        self.tools = tools
        self.router = router or RuleBasedRouter(tools.graph_retriever)
        self.generator = generator or ExtractiveAnswerGenerator()
        self.fallback_generator = fallback_generator
        self.planner = planner
        self.source_lookup = source_lookup if source_lookup is not None else _safe_source_lookup()

    def answer(self, question: str) -> AgentAnswer:
        route = self.router.route(question)
        if self.planner is not None and route.tool != ToolName.NONE and not _is_fast_path(route):
            route = self.planner.plan(question, route)
        if route.tool == ToolName.NONE:
            return AgentAnswer(
                answer="当前可靠资料不足以确认该问题，或问题超出南越专题资料范围。",
                citations=[],
                used_tools=[],
                route_reason=route.reason,
                insufficient_evidence=True,
                refusal_reason=route.reason,
            )

        unknown_focus = self._unknown_focus_terms(question, route)
        if unknown_focus:
            deepseek_fallback = self._deepseek_fallback_answer(question, route)
            if deepseek_fallback:
                return deepseek_fallback
            return AgentAnswer(
                answer=self._unknown_focus_answer(question, unknown_focus),
                citations=[],
                used_tools=[],
                route_reason=f"{route.reason} 问题主题未收录于本地知识库。",
                insufficient_evidence=True,
                refusal_reason=f"本地资料未收录：{'、'.join(unknown_focus)}",
            )

        result = self._run_tool(question, route)
        citations = citations_from_result(result, source_lookup=self.source_lookup)
        if not result.has_evidence or not citations:
            fallback_result = self._fallback_document_search(question, route)
            filtered_docs = self._filter_focus_documents(
                question, route, fallback_result.documents
            )
            if filtered_docs:
                result = ToolResult(documents=filtered_docs)
                citations = citations_from_result(result, source_lookup=self.source_lookup)
            else:
                deepseek_fallback = self._deepseek_fallback_answer(question, route)
                if deepseek_fallback:
                    return deepseek_fallback
                return AgentAnswer(
                    answer=self._insufficient_answer(question, route),
                    citations=[],
                    used_tools=[route.tool],
                    route_reason=route.reason,
                    insufficient_evidence=True,
                    retrieved_documents=result.documents,
                    graph_facts=result.graph,
                    refusal_reason="检索未返回可引用证据",
                )

        if route.tool != ToolName.SEARCH_DOCUMENTS and result.documents and not result.graph:
            route = route.model_copy(
                update={
                    "tool": ToolName.SEARCH_DOCUMENTS,
                    "reason": f"{route.reason} 结构化图谱证据不足，已回退到文档证据。",
                }
            )

        if not result.has_evidence or not citations:
            return AgentAnswer(
                answer=self._insufficient_answer(question, route),
                citations=[],
                used_tools=[route.tool],
                route_reason=route.reason,
                insufficient_evidence=True,
                retrieved_documents=result.documents,
                graph_facts=result.graph,
                refusal_reason="检索未返回可引用证据",
            )

        if result.documents and not result.graph:
            filtered_docs = self._filter_focus_documents(question, route, result.documents)
            if not filtered_docs:
                deepseek_fallback = self._deepseek_fallback_answer(question, route)
                if deepseek_fallback:
                    return deepseek_fallback
                return AgentAnswer(
                    answer=self._insufficient_answer(question, route),
                    citations=[],
                    used_tools=[route.tool],
                    route_reason=route.reason,
                    insufficient_evidence=True,
                    retrieved_documents=result.documents,
                    graph_facts=result.graph,
                    refusal_reason="检索到的资料未覆盖问题主题",
                )
            result = ToolResult(documents=filtered_docs)
            citations = citations_from_result(result, source_lookup=self.source_lookup)

        generated = self.generator.generate(question, route, result)
        if not generated.supported:
            deepseek_fallback = self._deepseek_fallback_answer(question, route)
            if deepseek_fallback:
                return deepseek_fallback
            return AgentAnswer(
                answer=generated.answer,
                citations=[],
                used_tools=[route.tool],
                route_reason=route.reason,
                insufficient_evidence=True,
                retrieved_documents=result.documents,
                graph_facts=result.graph,
                refusal_reason=generated.refusal_reason or "证据不足",
            )
        selected_result = _select_evidence(result, generated.selected_evidence_ids)
        selected_citations = citations_from_result(
            selected_result, source_lookup=self.source_lookup
        )
        if not selected_citations:
            return AgentAnswer(
                answer="当前可靠资料不足以确认该问题。",
                citations=[],
                used_tools=[route.tool],
                route_reason=route.reason,
                insufficient_evidence=True,
                retrieved_documents=result.documents,
                graph_facts=result.graph,
                refusal_reason="模型未选择有效证据",
            )
        if not _answer_is_grounded(generated.answer, selected_result):
            deepseek_fallback = self._deepseek_fallback_answer(question, route)
            if deepseek_fallback:
                return deepseek_fallback
            return AgentAnswer(
                answer="当前可靠资料不足以确认该问题。",
                citations=[],
                used_tools=[route.tool],
                route_reason=route.reason,
                insufficient_evidence=True,
                retrieved_documents=result.documents,
                graph_facts=result.graph,
                refusal_reason="生成答案与所选证据一致性不足",
            )
        return AgentAnswer(
            answer=generated.answer,
            citations=selected_citations,
            used_tools=[route.tool],
            route_reason=route.reason,
            insufficient_evidence=False,
            retrieved_documents=result.documents,
            graph_facts=result.graph,
            selected_evidence_ids=generated.selected_evidence_ids,
            source_tiers=list(dict.fromkeys(citation.source_tier for citation in selected_citations)),
        )

    def _run_tool(self, question: str, route: RouteDecision) -> ToolResult:
        if route.tool == ToolName.SEARCH_KG:
            return self.tools.search_kg(
                question,
                entity_query=route.entity_query,
                entity_queries=route.entities or None,
            )
        if route.tool == ToolName.SEARCH_DOCUMENTS:
            category = "tourism" if route.intent == "visit_guidance" else None
            return self.tools.search_documents(
                question,
                queries=route.subqueries or [question],
                category=category,
            )
        if route.tool == ToolName.HYBRID_SEARCH:
            return self.tools.hybrid_search(
                question,
                entity_query=route.entity_query,
                queries=route.subqueries or [question],
                entity_queries=route.entities or None,
            )
        raise ValueError(f"unsupported tool: {route.tool}")

    def _fallback_document_search(self, question: str, route: RouteDecision) -> ToolResult:
        if route.tool == ToolName.SEARCH_DOCUMENTS:
            return ToolResult()
        queries = list(dict.fromkeys([question, *route.subqueries]))
        return self.tools.search_documents(question, top_k=5, queries=queries)

    def _filter_focus_documents(
        self, question: str, route: RouteDecision, documents: list
    ) -> list:
        """Keep only documents that actually address the question's content terms.

        - 邻接伪词（“玺出/越王”这类跨词边界 bigram）先剔除：两端的字都在词表
          中、组合却不在词表中的 bigram 不参与判断；
        - 问题锚定了实体时：只保留同一 chunk 同时包含实体名和至少一半方面词
          的文档（允许“灭掉→灭”词干命中），既拒绝答非所问，也把玉璧式
          凑数 chunk 从答案中过滤掉；
        - 未锚定实体时：方面词在证据中的覆盖率不低于 0.4，否则整体放弃；
        - 地址/开放/预约等参观方面词由 visit rerank 的同义提示处理，不参与字面覆盖。
        """
        if not documents:
            return []
        entity_names = list(
            route.entities or ([] if route.entity_query is None else [route.entity_query])
        )
        vocabulary = getattr(self.tools.document_retriever, "idf", None)
        # 地址/开放/预约/亲子等参观方面词由 visit rerank 的同义提示处理：
        # 先把命中的方面短语从问题中遮蔽，再提取焦点词，避免“址在”这类
        # 跨方面词边界的伪 bigram 误伤。
        masked_question = question
        for pattern, _hints in AUDIENCE_HINTS:
            masked_question = pattern.sub(" ", masked_question)
        focus = _question_content_bigrams(masked_question, entity_names, vocabulary)
        if entity_names and route.intent != "visit_guidance":
            if not focus:
                return list(documents)
            kept = []
            for hit in documents:
                chunk_text = f"{hit.metadata.get('title', '')} {hit.content}"
                if not any(name in chunk_text for name in entity_names):
                    continue
                matched = sum(
                    1 for term in focus if _content_term_matches(term, chunk_text)
                )
                if matched / len(focus) >= 0.5:
                    kept.append(hit)
            return kept
        # 整体覆盖规则：实体名本身也是有效覆盖信号，不从焦点词中剔除。
        blob_focus = _question_content_bigrams(masked_question, [], vocabulary)
        if not blob_focus:
            return list(documents)
        blob = "\n".join(
            f"{hit.metadata.get('title', '')} {hit.content}" for hit in documents
        )
        covered = sum(1 for term in blob_focus if _content_term_matches(term, blob))
        if covered / len(blob_focus) < 0.4:
            return []
        # 外来词（WiFi/GDP 等词表之外的词）必须逐个命中，防止被实体名稀释。
        foreign = [term for term in blob_focus if _is_foreign_term(term, vocabulary or {})]
        if foreign and not all(_content_term_matches(term, blob) for term in foreign):
            return []
        return list(documents)

    def _deepseek_fallback_answer(self, question: str, route: RouteDecision) -> AgentAnswer | None:
        if self.fallback_generator is None or route.scope == "out_of_scope":
            return None
        try:
            answer = self.fallback_generator.generate_without_evidence(question, route)
        except AnswerGenerationError:
            return None
        return AgentAnswer(
            answer=answer,
            citations=[],
            used_tools=[route.tool],
            route_reason=f"{route.reason} 本地证据不足，已启用 DeepSeek 通用兜底。",
            insufficient_evidence=True,
            refusal_reason="本地知识库无可引用证据，已使用 DeepSeek 通用回答",
        )

    def _insufficient_answer(self, question: str, route: RouteDecision) -> str:
        if route.intent == "visit_guidance":
            return (
                "我检索了馆内参观资料，但没有找到足以确认这个问题的可引用内容。"
                "可以换得更具体一些，例如“王墓展区开放时间”“墓室参观怎么预约”"
                "或“王墓展区有哪些重点文物”。"
            )
        suggestions = self._suggest_related_entities(question)
        if suggestions:
            topics = "、".join(f"“{name}”" for name in suggestions)
            return (
                "我检索了本地知识图谱和资料库，没有找到足以确认这个问题的可引用证据，不能贸然作答。"
                f"你或许想了解：{topics}？用更具体的名称再试一次。"
            )
        return (
            "我检索了本地知识图谱和资料库，没有找到足以确认这个问题的可引用证据，不能贸然作答。"
            "可以换用更具体的实体或主题词，例如“文帝行玺”“丝缕玉衣”“赵眜”或“南越文王墓”。"
        )

    def _suggest_related_entities(self, question: str, limit: int = 3) -> list[str]:
        suggestions: list[str] = []
        seen: set[str] = set()

        def collect(term: str) -> bool:
            try:
                matches = self.tools.graph_retriever.list_entities(term, limit=3)
            except Exception:
                return False
            for entity in matches:
                name = getattr(entity, "name", "")
                if name and name not in seen:
                    seen.add(name)
                    suggestions.append(name)
                if len(suggestions) >= limit:
                    return True
            return False

        terms = _question_terms(question)
        for term in terms:
            if collect(term):
                return suggestions
        if not suggestions:
            # 首字（姓氏）兜底：捕捉“赵高→赵佗”这类同姓/同首字混淆，
            # 让拒答能附上“你或许想问赵佗”的引导。
            for term in terms:
                if len(term) == 2 and collect(term[0]):
                    return suggestions
        return suggestions

    def _unknown_focus_terms(self, question: str, route: RouteDecision) -> list[str]:
        """Detect question subjects that the knowledge base has never heard of.

        After stripping interrogative scaffolding and already-matched entity
        names, a whole CJK segment whose content bigrams are absent from both
        the document vocabulary and the graph alias index marks an
        out-of-knowledge subject (e.g. 赵高). Retrieving near-name documents
        for such subjects is exactly the failure mode this guard prevents.
        """
        if _relation_hint_matches(question):
            # 材料/出土/纹饰等概念词由关系提示映射到 KG 关系，不要求字面命中词表。
            return []
        if route.entities or route.entity_query:
            # 已锚定到知识库实体的问题：未知词多为“方面”而非“主题”，
            # 交给 KG 方面过滤和文档焦点覆盖校验处理（如“灭掉→灭”）。
            return []
        vocabulary = getattr(self.tools.document_retriever, "idf", None)
        if not vocabulary:
            return []
        entity_names = list(
            route.entities or ([] if route.entity_query is None else [route.entity_query])
        )
        text = question
        for phrase in QUESTION_STOP_PHRASES:
            text = text.replace(phrase, " ")
        unknown: list[str] = []
        for segment in re.findall(r"[一-鿿]+", text):
            content = []
            for index in range(len(segment) - 1):
                bigram = segment[index : index + 2]
                if any(char in SCAFFOLD_CHARS for char in bigram):
                    continue
                if any(bigram in name for name in entity_names):
                    continue
                content.append(bigram)
            unknown_bigrams = [term for term in content if not self._term_known(term, vocabulary)]
            if content and len(unknown_bigrams) == len(content):
                unknown.extend(unknown_bigrams)
        return list(dict.fromkeys(unknown))

    def _term_known(self, term: str, vocabulary: dict) -> bool:
        if term in vocabulary:
            return True
        try:
            return bool(self.tools.graph_retriever.list_entities(term, limit=1))
        except Exception:
            return False

    def _unknown_focus_answer(self, question: str, unknown_focus: list[str]) -> str:
        focus = "、".join(f"“{term}”" for term in unknown_focus[:2])
        base = (
            f"本地知识库没有收录与{focus}直接相关的资料，"
            "它可能不在南越专题范围内，我不会用名称相近的资料冒充答案。"
        )
        suggestions = self._suggest_related_entities(question)
        if suggestions:
            topics = "、".join(f"“{name}”" for name in suggestions)
            return base + f"你或许想了解：{topics}？"
        return base + "可以换用南越专题内的具体名称再试，例如“文帝行玺”“丝缕玉衣”“赵眜”或“南越文王墓”。"


def create_deepseek_generator(settings: Settings) -> DeepSeekAnswerGenerator:
    try:
        return DeepSeekAnswerGenerator(settings)
    except ConfigurationError:
        raise


def _is_fast_path(route: RouteDecision) -> bool:
    return route.tool == ToolName.SEARCH_KG and bool(route.entity_query)


def _select_evidence(result: ToolResult, evidence_ids: list[str]) -> ToolResult:
    selected = set(evidence_ids)
    return ToolResult(
        documents=[hit for hit in result.documents if document_evidence_id(hit) in selected],
        graph=[hit for hit in result.graph if graph_evidence_id(hit) in selected],
    )


def _strip_code_fence(content: str) -> str:
    value = content.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        if len(lines) >= 3 and lines[-1].strip() == "```":
            return "\n".join(lines[1:-1]).strip()
    return value


def _is_foreign_term(term: str, vocabulary: dict) -> bool:
    """词表之外的外来词：ASCII 词，或含有词表外汉字的中文 bigram。
    两个字都在词表中但组合不在的（如“越王”）不算外来词。"""
    if term in vocabulary:
        return False
    if re.fullmatch(r"[一-鿿]{2}", term):
        return not (term[0] in vocabulary and term[1] in vocabulary)
    return True


def _question_terms(question: str) -> list[str]:
    """Extract CJK n-grams (4..2) from the question for fuzzy entity suggestion."""
    text = "".join(re.findall(r"[一-鿿]", question))
    terms: list[str] = []
    for size in (4, 3, 2):
        terms.extend(text[index : index + size] for index in range(len(text) - size + 1))
    return list(dict.fromkeys(terms))


# Minimum share of an answer's content bigrams that must appear in the
# selected evidence for the answer to count as grounded. Deliberately low:
# it catches wholesale hallucination while tolerating paraphrase.
MIN_GROUNDED_COVERAGE = 0.25


def _answer_is_grounded(answer: str, selected_result: ToolResult) -> bool:
    """Cheap faithfulness check: the answer must share vocabulary with its evidence."""
    blob_parts: list[str] = []
    for hit in selected_result.graph:
        blob_parts.append(
            " ".join([hit.source_entity.name, hit.target_entity.name, hit.evidence])
        )
    for hit in selected_result.documents:
        blob_parts.append(f"{hit.metadata.get('title', '')} {hit.content}")
    blob = "\n".join(blob_parts)
    if not blob.strip():
        return False
    text = answer
    for phrase in QUESTION_STOP_PHRASES:
        text = text.replace(phrase, " ")
    bigrams: set[str] = set()
    for segment in re.findall(r"[一-鿿]+", text):
        for index in range(len(segment) - 1):
            bigram = segment[index : index + 2]
            if any(char in SCAFFOLD_CHARS for char in bigram):
                continue
            bigrams.add(bigram)
    if not bigrams:
        return True
    covered = sum(1 for bigram in bigrams if bigram in blob)
    return covered / len(bigrams) >= MIN_GROUNDED_COVERAGE


def _safe_source_lookup() -> dict[str, CorpusDocument]:
    try:
        return load_source_lookup()
    except Exception:
        return {}
