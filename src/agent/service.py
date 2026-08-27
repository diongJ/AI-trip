from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import urlsplit

from src.agent.context import (
    build_grounded_context,
    citations_from_result,
    document_evidence_id,
    graph_evidence_id,
    load_source_lookup,
)
from src.agent.models import (
    AgentAnswer,
    AnswerClaim,
    AnswerMode,
    AnswerStatus,
    ClaimType,
    ConversationTurn,
    GeneratedAnswer,
    RouteDecision,
    ToolName,
    ToolResult,
    WebSearchResult,
    WebSource,
)
from src.agent.planner import QueryPlanner
from src.agent.router import RuleBasedRouter
from src.agent.tools import (
    AUDIENCE_HINTS,
    FIRST_VISIT_RE,
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


class WebSearchAnswerGenerator(Protocol):
    def search(self, question: str) -> WebSearchResult: ...


class ClaimVerifier(Protocol):
    def verify(
        self, question: str, answer: str, claims: list[AnswerClaim], result: ToolResult
    ) -> list[AnswerClaim]: ...


class ConversationRewriter:
    """Resolve short follow-ups deterministically without treating history as evidence."""

    FOLLOW_UP_RE = re.compile(r"^(它|这[件个座]|那[件个座]|其|为什么|那为什么|它们|两者|这个)(.*)$")

    def __init__(self, resolver: object) -> None:
        self.resolver = resolver

    def rewrite(self, question: str, history: list[ConversationTurn] | None) -> str:
        if not history or not self.FOLLOW_UP_RE.search(question.strip()):
            return question
        # Known entity names are the safest antecedents. Scan user questions only:
        # previous assistant prose must never become an unverified source of facts.
        try:
            entities = self.resolver.list_entities(limit=300)
        except Exception:
            return question
        entity = ""
        for turn in reversed(history[-4:]):
            candidates = [
                entity.name
                for entity in entities
                if getattr(entity, "name", "") and getattr(entity, "name", "") in turn.question
            ]
            if candidates:
                entity = sorted(set(candidates), key=lambda value: (-len(value), value))[0]
                break
        if not entity:
            return question
        match = self.FOLLOW_UP_RE.match(question.strip())
        assert match is not None
        suffix = match.group(2).strip()
        if question.startswith(("为什么", "那为什么")):
            return f"{entity}为什么{suffix}" if suffix else f"{entity}为什么重要？"
        if question.startswith("两者"):
            return f"{entity}与前述对象{suffix}"
        return f"{entity}{suffix}" if suffix else f"介绍一下{entity}。"


class ExtractiveAnswerGenerator:
    def generate(self, question: str, route: RouteDecision, result: ToolResult) -> GeneratedAnswer:
        document_hits = list(result.documents)
        if route.intent == "visit_guidance":
            factual = [
                hit for hit in document_hits if hit.metadata.get("evidence_role") == "factual"
            ]
            curated = [
                hit
                for hit in document_hits
                if hit.metadata.get("evidence_role") == "curated_guidance"
            ]
            document_hits = [*factual[:1], *curated[:1]] or document_hits
        selected = [
            *[graph_evidence_id(hit) for hit in result.graph[:3]],
            *[document_evidence_id(hit) for hit in document_hits[:2]],
        ]
        if route.tool in {ToolName.SEARCH_DOCUMENTS, ToolName.HYBRID_SEARCH} and document_hits:
            snippets = [_format_extract(hit) for hit in document_hits[:2]]
            if route.intent == "visit_guidance" and re.search(r"学生|研学", question):
                snippets.insert(0, "面向学生研学，可以按以下证据线索组织参观：")
            return GeneratedAnswer(answer="\n".join(snippets), selected_evidence_ids=selected)
        if result.graph:
            facts = [
                f"{hit.source_entity.name}{_relation_label(hit.relation)}{hit.target_entity.name}。证据：{hit.evidence}"
                for hit in result.graph[:3]
            ]
            return GeneratedAnswer(answer="\n".join(facts), selected_evidence_ids=selected)
        if document_hits:
            snippets = [_format_extract(hit) for hit in document_hits[:2]]
            return GeneratedAnswer(answer="\n".join(snippets), selected_evidence_ids=selected)
        return GeneratedAnswer(
            answer="暂未在可靠资料中找到足够依据，因此不想给出可能不准确的答案。",
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
                answer="暂未在可靠资料中找到足够依据，因此不想给出可能不准确的答案。",
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


class DeepSeekClaimVerifier:
    """A second, evidence-only pass that removes unsupported generated claims."""

    def __init__(self, settings: Settings, *, http_client: object | None = None) -> None:
        if httpx is None:
            raise ConfigurationError("httpx is required for claim verification.")
        settings.require_deepseek()
        self.settings = settings
        self._owns_client = http_client is None
        self.client = http_client or httpx.Client(timeout=30.0)

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def verify(
        self, question: str, answer: str, claims: list[AnswerClaim], result: ToolResult
    ) -> list[AnswerClaim]:
        if not claims:
            return []
        prompt = (
            "你是证据核验器。只根据给定证据判断每条结论是否可保留。"
            "direct_fact 必须被所列证据明确支持；synthesis 必须引用至少两条证据，"
            "且不能添加证据中没有的人物、年代、数字或确定因果。"
            "只输出 JSON：{\\\"kept_claim_indexes\\\":[0,1]}。"
        )
        payload = {
            "model": self.settings.deepseek_model,
            "messages": [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": (
                        f"问题：{question}\\n回答：{answer}\\n"
                        f"结论：{json.dumps([claim.model_dump(mode='json') for claim in claims], ensure_ascii=False)}\\n\\n"
                        f"证据：\\n{build_grounded_context(result, max_chars=6000)}"
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
            raw = json.loads(_strip_code_fence(response.json()["choices"][0]["message"]["content"]))
            indexes = raw.get("kept_claim_indexes", [])
            if not isinstance(indexes, list):
                raise ValueError("kept_claim_indexes must be a list")
            return [claims[index] for index in indexes if isinstance(index, int) and 0 <= index < len(claims)]
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise AnswerGenerationError(f"claim verification failed: {exc}") from exc


class DeepSeekWebSearchAnswerGenerator:
    """Run a real server-side DeepSeek web search and keep only traceable results."""

    def __init__(self, settings: Settings, *, http_client: object | None = None) -> None:
        if httpx is None:
            raise ConfigurationError("httpx is required for DeepSeek web search.")
        settings.require_deepseek()
        self.settings = settings
        self._owns_client = http_client is None
        self.client = http_client or httpx.Client(timeout=45.0)

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def search(self, question: str) -> WebSearchResult:
        payload = {
            "model": self.settings.deepseek_search_model,
            "instructions": (
                "你是南越专题资料检索助手。必须先执行联网搜索，只根据搜索结果回答。"
                "优先博物馆、政府文物部门、考古研究机构和学术机构来源。"
                "用中文简洁回答；无法确认时明确说明，不得虚构来源、网址或实时信息。"
            ),
            "input": question,
            "tools": [{"type": "web_search"}],
            "tool_choice": {"type": "web_search"},
            "reasoning": {"effort": "low"},
            "max_output_tokens": 900,
        }
        try:
            response = self.client.post(
                f"{self.settings.deepseek_base_url.rstrip('/')}/responses",
                headers={
                    "Authorization": f"Bearer {self.settings.deepseek_api_key.get_secret_value()}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            raw = response.json()
            output = raw["output"]
            searched = any(
                item.get("type") == "web_search_call" and item.get("status") == "completed"
                for item in output
                if isinstance(item, dict)
            )
            if not searched:
                raise ValueError("response did not complete a web search call")
            answer = "\n".join(_response_output_texts(output)).strip()
            sources = _web_sources_from_payload(output)
            if not answer or not sources:
                raise ValueError("web search returned no answer or traceable source")
            return WebSearchResult(answer=answer, sources=sources)
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise AnswerGenerationError(f"DeepSeek web search failed: {exc}") from exc


class AgentService:
    def __init__(
        self,
        tools: AgentTools,
        *,
        router: RuleBasedRouter | None = None,
        generator: AnswerGenerator | None = None,
        web_search_generator: WebSearchAnswerGenerator | None = None,
        claim_verifier: ClaimVerifier | None = None,
        planner: QueryPlanner | None = None,
        source_lookup: dict[str, CorpusDocument] | None = None,
    ) -> None:
        self.tools = tools
        self.router = router or RuleBasedRouter(tools.graph_retriever)
        self.generator = generator or ExtractiveAnswerGenerator()
        self.web_search_generator = web_search_generator
        self.claim_verifier = claim_verifier
        self.planner = planner
        self.source_lookup = source_lookup if source_lookup is not None else _safe_source_lookup()
        self.conversation_rewriter = ConversationRewriter(tools.graph_retriever)

    def answer(
        self,
        question: str,
        *,
        history: list[ConversationTurn] | None = None,
        answer_mode: AnswerMode = AnswerMode.AUTO,
    ) -> AgentAnswer:
        question = self.conversation_rewriter.rewrite(question, history)
        route = self.router.route(question).model_copy(update={"answer_mode": answer_mode})
        if self.planner is not None and route.tool != ToolName.NONE and not _is_fast_path(route):
            route = self.planner.plan(question, route)
            if answer_mode != AnswerMode.AUTO:
                route = route.model_copy(update={"answer_mode": answer_mode})
        if route.tool == ToolName.NONE:
            return self._route_failure(question, route)

        unknown_focus = self._unknown_focus_terms(question, route)
        if unknown_focus:
            web_answer = self._web_search_response(
                question,
                route,
                used_tools=[],
                reason=f"本地资料未收录：{'、'.join(unknown_focus)}",
            )
            if web_answer is not None:
                return web_answer
            return AgentAnswer(
                answer=self._unknown_focus_answer(question, unknown_focus),
                citations=[],
                used_tools=[],
                route_reason=f"{route.reason} 问题主题未收录于本地知识库。",
                insufficient_evidence=True,
                refusal_reason=f"本地资料未收录：{'、'.join(unknown_focus)}",
                response_status=AnswerStatus.CLARIFICATION_NEEDED,
                suggested_questions=self._suggested_questions(question, route),
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
                return self._insufficient_response(
                    question,
                    route,
                    used_tools=[route.tool],
                    retrieved_documents=result.documents,
                    graph_facts=result.graph,
                    reason="检索未返回可引用证据",
                )

        if route.tool != ToolName.SEARCH_DOCUMENTS and result.documents and not result.graph:
            route = route.model_copy(
                update={
                    "tool": ToolName.SEARCH_DOCUMENTS,
                    "reason": f"{route.reason} 结构化图谱证据不足，已回退到文档证据。",
                }
            )

        if not result.has_evidence or not citations:
            return self._insufficient_response(
                question,
                route,
                used_tools=[route.tool],
                retrieved_documents=result.documents,
                graph_facts=result.graph,
                reason="检索未返回可引用证据",
            )

        if result.documents and not result.graph:
            filtered_docs = self._filter_focus_documents(question, route, result.documents)
            if not filtered_docs:
                return self._insufficient_response(
                    question,
                    route,
                    used_tools=[route.tool],
                    retrieved_documents=result.documents,
                    graph_facts=result.graph,
                    reason="检索到的资料未覆盖问题主题",
                )
            result = ToolResult(documents=filtered_docs)
            citations = citations_from_result(result, source_lookup=self.source_lookup)

        generated = self.generator.generate(question, route, result)
        if not generated.supported:
            return self._insufficient_response(
                question,
                route,
                used_tools=[route.tool],
                retrieved_documents=result.documents,
                graph_facts=result.graph,
                reason=generated.refusal_reason or "证据不足",
            )
        claims = _normalized_claims(generated)
        initial_claims = list(claims)
        initial_evidence_ids = list(
            dict.fromkeys(
                [*generated.selected_evidence_ids, *[evidence_id for claim in claims for evidence_id in claim.evidence_ids]]
            )
        )
        selected_result = _select_evidence(result, initial_evidence_ids)
        if not citations_from_result(selected_result, source_lookup=self.source_lookup):
            return self._insufficient_response(
                question,
                route,
                used_tools=[route.tool],
                retrieved_documents=result.documents,
                graph_facts=result.graph,
                reason="模型未选择有效证据",
            )
        verified = False
        if self.claim_verifier is not None:
            try:
                claims = self.claim_verifier.verify(question, generated.answer, claims, selected_result)
                verified = True
            except AnswerGenerationError:
                # A verifier outage must not make the application unusable; retain the
                # conservative local faithfulness check as a safe fallback.
                verified = False
        claims = _locally_valid_claims(claims, selected_result)
        evidence_ids = list(dict.fromkeys(evidence_id for claim in claims for evidence_id in claim.evidence_ids))
        selected_result = _select_evidence(result, evidence_ids)
        selected_citations = citations_from_result(selected_result, source_lookup=self.source_lookup)
        answer = generated.answer
        if claims != initial_claims:
            # Once a verifier removes a claim, rebuild from the surviving statements
            # so unsupported prose cannot remain in the final response.
            answer = "\n".join(claim.text for claim in claims)
        if not claims or not selected_citations or not _answer_is_grounded(answer, selected_result):
            return self._insufficient_response(
                question,
                route,
                used_tools=[route.tool],
                retrieved_documents=result.documents,
                graph_facts=result.graph,
                reason="生成答案与所选证据一致性不足",
            )
        answer_text = _label_curated_guidance(answer, selected_result)
        return AgentAnswer(
            answer=answer_text,
            citations=selected_citations,
            used_tools=[route.tool],
            route_reason=route.reason,
            insufficient_evidence=False,
            retrieved_documents=result.documents,
            graph_facts=result.graph,
            selected_evidence_ids=evidence_ids,
            claims=claims,
            claims_verified=verified,
            source_tiers=list(dict.fromkeys(citation.source_tier for citation in selected_citations)),
            response_status=AnswerStatus.ANSWERED,
        )

    def _run_tool(self, question: str, route: RouteDecision) -> ToolResult:
        depth = 2 if route.intent in {"explanation", "comparison", "hybrid_explanation"} or route.answer_mode == AnswerMode.DEEP else 1
        top_k = 8 if route.answer_mode == AnswerMode.DEEP or route.intent in {"explanation", "comparison", "hybrid_explanation"} else 5
        if route.tool == ToolName.SEARCH_KG:
            return self.tools.search_kg(
                question,
                entity_query=route.entity_query,
                entity_queries=route.entities or None,
                depth=depth,
                limit=20 if depth == 2 else 12,
            )
        if route.tool == ToolName.SEARCH_DOCUMENTS:
            category = "tourism" if route.intent == "visit_guidance" else None
            return self.tools.search_documents(
                question,
                queries=route.subqueries or [question],
                category=category,
                include_curated_guidance=route.intent == "visit_guidance",
                top_k=top_k,
            )
        if route.tool == ToolName.HYBRID_SEARCH:
            return self.tools.hybrid_search(
                question,
                entity_query=route.entity_query,
                top_k=top_k,
                depth=depth,
                limit=20 if depth == 2 else 12,
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
        # 参观问题已经在 AgentTools 中按 tourism 分类、证据角色和专用提示词
        # 完成分路检索与重排。此处再按字面 bigram 过滤，会把“第一次怎么看”
        # 这类自然说法误判为无证据。
        if route.intent == "visit_guidance" and FIRST_VISIT_RE.search(question):
            return list(documents)
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

    def _insufficient_answer(self, question: str, route: RouteDecision) -> str:
        if route.intent == "visit_guidance":
            return (
                "暂未在馆方资料和项目整理建议中找到足够依据，因此不想给出可能不准确的答案。"
                "你可以补充具体展区、参观时长或游客类型后再试。"
            )
        suggestions = self._suggest_related_entities(question)
        if suggestions:
            topics = "、".join(f"“{name}”" for name in suggestions)
            return (
                "暂未在可靠资料中找到足够依据，因此不想给出可能不准确的答案。"
                f"你或许想了解：{topics}？"
            )
        return (
            "暂未在可靠资料中找到足够依据，因此不想给出可能不准确的答案。"
            "可以补充具体人物、文物、展区或时间范围后再试。"
        )

    def _insufficient_response(
        self,
        question: str,
        route: RouteDecision,
        *,
        used_tools: list[ToolName],
        reason: str,
        retrieved_documents: list | None = None,
        graph_facts: list | None = None,
    ) -> AgentAnswer:
        web_answer = self._web_search_response(
            question,
            route,
            used_tools=used_tools,
            reason=reason,
            retrieved_documents=retrieved_documents,
            graph_facts=graph_facts,
        )
        if web_answer is not None:
            return web_answer
        return AgentAnswer(
            answer=self._insufficient_answer(question, route),
            citations=[],
            used_tools=used_tools,
            route_reason=route.reason,
            insufficient_evidence=True,
            retrieved_documents=retrieved_documents or [],
            graph_facts=graph_facts or [],
            refusal_reason=reason,
            response_status=AnswerStatus.INSUFFICIENT_EVIDENCE,
            suggested_questions=self._suggested_questions(question, route),
        )

    def _web_search_response(
        self,
        question: str,
        route: RouteDecision,
        *,
        used_tools: list[ToolName],
        reason: str,
        retrieved_documents: list | None = None,
        graph_facts: list | None = None,
    ) -> AgentAnswer | None:
        if self.web_search_generator is None or not _web_search_allowed(question, route):
            return None
        try:
            result = self.web_search_generator.search(question)
        except AnswerGenerationError:
            return None
        return AgentAnswer(
            answer=result.answer,
            citations=[],
            web_sources=result.sources,
            used_tools=[*used_tools, ToolName.WEB_SEARCH],
            route_reason=f"{route.reason} {reason}，已使用 DeepSeek 联网搜索补充。",
            insufficient_evidence=False,
            retrieved_documents=retrieved_documents or [],
            graph_facts=graph_facts or [],
            source_tiers=["web"],
            response_status=AnswerStatus.WEB_SEARCH_ANSWERED,
        )

    def _route_failure(self, question: str, route: RouteDecision) -> AgentAnswer:
        if route.intent == "realtime_unavailable":
            status = AnswerStatus.REALTIME_UNAVAILABLE
            answer = (
                "这类信息可能随时变化，我无法依据静态知识库可靠确认。"
                "建议查看南越王博物院官方公告、预约页面或实时服务。"
            )
        elif route.intent == "clarification_needed":
            status = AnswerStatus.CLARIFICATION_NEEDED
            answer = "我还不能确定你想了解什么。请补充具体人物、文物、展区或时间范围。"
        elif route.intent == "incorrect_premise":
            status = AnswerStatus.INSUFFICIENT_EVIDENCE
            answer = (
                "可靠资料与问题中的前提不一致，因此我不能沿用这个前提作答。"
                "你可以改问该人物、文物或墓葬在可靠资料中的实际情况。"
            )
        else:
            status = AnswerStatus.OUT_OF_SCOPE
            answer = (
                "我目前主要提供南越历史、考古、人物、文物和馆内稳定信息。"
                "这个问题暂不在可靠资料范围内。"
            )
        return AgentAnswer(
            answer=answer,
            citations=[],
            used_tools=[],
            route_reason=route.reason,
            insufficient_evidence=True,
            refusal_reason=route.reason,
            response_status=status,
            suggested_questions=self._suggested_questions(question, route),
        )

    def _suggested_questions(self, question: str, route: RouteDecision) -> list[str]:
        if route.intent == "visit_guidance":
            return ["王墓展区有哪些重点文物？", "第一次参观王墓展区可以怎么安排？"]
        suggestions = self._suggest_related_entities(question, limit=2)
        if suggestions:
            return [f"请介绍一下{name}。" for name in suggestions[:2]]
        return ["南越文王墓为什么重要？", "文帝行玺反映了什么？"]

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


NANYUE_SCOPE_RE = re.compile(
    r"南越|王墓|王宫|博物院|博物馆|赵佗|赵眜|赵胡|文帝行玺|丝缕玉衣|"
    r"南越文王墓|番禺|象岗|墓室|墓葬|岭南|汉代|秦汉"
)


def _web_search_allowed(question: str, route: RouteDecision) -> bool:
    if route.scope != "in_scope" or route.tool == ToolName.NONE:
        return False
    if route.intent in {
        "realtime_unavailable",
        "out_of_scope",
        "clarification_needed",
        "incorrect_premise",
    }:
        return False
    return bool(route.entity_query or route.entities or NANYUE_SCOPE_RE.search(question))


def _response_output_texts(output: list[object]) -> list[str]:
    texts: list[str] = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for part in item.get("content", []):
            if isinstance(part, dict) and part.get("type") == "output_text":
                value = str(part.get("text", "")).strip()
                if value:
                    texts.append(value)
    return texts


def _web_sources_from_payload(output: list[object]) -> list[WebSource]:
    accessed_at = datetime.now().astimezone().isoformat(timespec="seconds")
    candidates: dict[str, str] = {}

    def visit(value: object) -> None:
        if isinstance(value, dict):
            raw_url = next(
                (
                    str(value[key]).strip()
                    for key in ("url", "uri", "page_url", "source_url")
                    if value.get(key)
                ),
                "",
            )
            if raw_url.startswith(("https://", "http://")):
                title = str(
                    value.get("title")
                    or value.get("name")
                    or urlsplit(raw_url).netloc
                    or "联网来源"
                ).strip()
                current = candidates.get(raw_url)
                domain = urlsplit(raw_url).netloc
                if current is None or (current == domain and title != domain):
                    candidates[raw_url] = title
            for nested in value.values():
                visit(nested)
        elif isinstance(value, list):
            for nested in value:
                visit(nested)

    visit(output)
    sources: list[WebSource] = []
    seen: set[str] = set()
    for url, title in candidates.items():
        if url in seen:
            continue
        seen.add(url)
        try:
            sources.append(WebSource(title=title, url=url, accessed_at=accessed_at))
        except ValueError:
            continue
        if len(sources) >= 6:
            break
    return sources


def _is_fast_path(route: RouteDecision) -> bool:
    return route.tool == ToolName.SEARCH_KG and bool(route.entity_query)


def _select_evidence(result: ToolResult, evidence_ids: list[str]) -> ToolResult:
    selected = set(evidence_ids)
    return ToolResult(
        documents=[hit for hit in result.documents if document_evidence_id(hit) in selected],
        graph=[hit for hit in result.graph if graph_evidence_id(hit) in selected],
    )


def _normalized_claims(generated: GeneratedAnswer) -> list[AnswerClaim]:
    """Keep legacy and offline generators compatible with claim-level answers."""
    if generated.claims:
        return generated.claims
    if not generated.selected_evidence_ids:
        return []
    return [
        AnswerClaim(
            text=generated.answer,
            claim_type=ClaimType.DIRECT_FACT,
            evidence_ids=generated.selected_evidence_ids,
        )
    ]


def _locally_valid_claims(claims: list[AnswerClaim], result: ToolResult) -> list[AnswerClaim]:
    """Validate evidence wiring even when the optional LLM verifier is unavailable."""
    available = {
        *[graph_evidence_id(hit) for hit in result.graph],
        *[document_evidence_id(hit) for hit in result.documents],
    }
    valid: list[AnswerClaim] = []
    for claim in claims:
        evidence_ids = list(dict.fromkeys(claim.evidence_ids))
        if not evidence_ids or not set(evidence_ids).issubset(available):
            continue
        if claim.claim_type == ClaimType.SYNTHESIS:
            if len(evidence_ids) < 2 or "结合" not in claim.text:
                continue
        valid.append(claim.model_copy(update={"evidence_ids": evidence_ids}))
    return valid


def _format_extract(hit: object) -> str:
    if hit.metadata.get("evidence_role") == "curated_guidance":
        return f"项目整理建议：{hit.content}"
    return hit.content


def _label_curated_guidance(answer: str, selected_result: ToolResult) -> str:
    has_curated = any(
        hit.metadata.get("evidence_role") == "curated_guidance"
        for hit in selected_result.documents
    )
    if not has_curated or "项目整理建议" in answer:
        return answer
    return f"项目整理建议：{answer}"


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
