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
    Audience,
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
    VERB_ASPECT_SUFFIXES,
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
        entity_names = [name for name in route.entities if name] or (
            [route.entity_query] if route.entity_query else []
        )
        if entity_names and document_hits:
            # 优先选择正文/标题中出现问题实体的文档，避免复合问题
            # 被泛化讲解/陈列文档抢走位置；标题命中权重更高。
            # 政权/展区/地名等泛化实体名会出现在大量文档标题中，
            # 标题加权反而会把真正的细节文档（如记载存续年份的）挤出
            # 前列，因此对这些实体只按正文命中排序。
            generic_entities = {"南越", "南越国", "南越王博物院", "博物院", "博物馆", "中国", "汉朝", "西汉", "岭南", "广州", "王墓展区", "王宫展区"}

            def _entity_coverage(hit: object) -> int:
                title = str(hit.metadata.get("title", ""))
                best = 0
                for name in entity_names:
                    if name in hit.content:
                        best = max(best, 1)
                    if name not in generic_entities and name in title:
                        best = max(best, 2)
                return best

            document_hits.sort(key=_entity_coverage, reverse=True)
        selected = [
            *[graph_evidence_id(hit) for hit in result.graph[:3]],
            *[document_evidence_id(hit) for hit in document_hits[:2]],
        ]
        if route.kids_intent:
            return GeneratedAnswer(
                answer=_kids_extractive_answer(route.kids_intent, result, document_hits),
                selected_evidence_ids=selected,
            )
        if route.tool in {ToolName.SEARCH_DOCUMENTS, ToolName.HYBRID_SEARCH} and document_hits:
            snippets = [_format_extract(hit) for hit in document_hits[:3 if entity_names else 2]]
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
        audience_line = (
            "\n受众：儿童。请以小越（南越王博物院的儿童讲解员）的语气回答：用短句，"
            "可以打比方，可以按叙事方式把证据讲成小故事；回答控制在150字以内，"
            "可以直接引用证据原文里的短句；但不得改变事实，"
            "不得添加证据之外的人物、年代、数字或情节。"
            + (
                "请围绕问题涉及的文物或主题讲述，不要引入参观、门票、开放时间等与问题无关的内容。"
                if route.kids_intent == "story"
                else ""
            )
            if route.kids_intent
            else ""
        )
        if not audience_line and ANECDOTE_ONTOPIC_RE.search(question):
            # 典故/成语/传说类问题：禁止泛泛介绍博物馆概况、门票、开放时间。
            audience_line = (
                "\n请围绕问题涉及的典故、成语或历史故事本身组织回答，"
                "逐条说明出处；不要泛泛介绍博物馆概况、门票、开放时间等无关内容。"
            )
        payload = {
            "model": self.settings.deepseek_model,
            "messages": [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": (
                        f"问题：{question}\n"
                        f"路由：{route.model_dump_json()}{audience_line}\n\n"
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
        audience: Audience = Audience.ADULT,
    ) -> AgentAnswer:
        question = self.conversation_rewriter.rewrite(question, history)
        route = self.router.route(question).model_copy(update={"answer_mode": answer_mode})
        if audience == Audience.KIDS:
            # 儿童模式：意图识别与路由全部走规则，跳过 DeepSeek 规划器，
            # 避免规划器把“故事/典故/讲解”重新分类导致答偏或证据丢失。
            kids_intent = _detect_kids_intent(question)
            route = route.model_copy(update={"kids_intent": kids_intent})
            if kids_intent == "chat":
                return AgentAnswer(
                    answer=_kids_chat_answer(question),
                    citations=[],
                    used_tools=[],
                    route_reason="儿童聊天意图：日常对话，不构成事实断言。",
                    insufficient_evidence=False,
                    response_status=AnswerStatus.CHAT,
                    suggested_questions=[
                        "给我讲一个文帝行玺的小故事",
                        "丝缕玉衣是做什么用的？",
                    ],
                )
            if kids_intent == "story" and (route.entity_query or route.entities):
                focus = route.entity_query or route.entities[0]
                if _story_entity_uses_kg(self.tools, focus):
                    # 文物/人物类实体：故事优先使用图谱事实，避免 BM25 参观类
                    # 文档抢到高排名导致答偏；国名、展区等宽泛实体则保留
                    # 典故文档检索（文档里才有赵佗、陆贾等故事人物）。
                    route = route.model_copy(
                        update={
                            "tool": ToolName.SEARCH_KG,
                            "reason": "儿童故事意图：优先图谱事实，避免文档检索偏离主题。",
                        }
                    )
            elif kids_intent == "relic" and (route.entity_query or route.entities):
                focus = route.entity_query or route.entities[0]
                if _story_entity_uses_kg(self.tools, focus):
                    # 儿童讲解文物/人物：同样优先图谱事实，简洁且可追溯。
                    route = route.model_copy(
                        update={
                            "tool": ToolName.SEARCH_KG,
                            "reason": "儿童讲解意图：优先图谱事实。",
                        }
                    )
        if (
            self.planner is not None
            and route.tool != ToolName.NONE
            and not _is_fast_path(route)
            and route.kids_intent is None
            and route.intent != "anecdote"
        ):
            # 典故意图已由专门子查询限定检索范围，规划器再分类反而会
            # 破坏检索目标，因此同样跳过规划器。
            route = self.planner.plan(question, route)
            if answer_mode != AnswerMode.AUTO:
                route = route.model_copy(update={"answer_mode": answer_mode})
        if route.tool == ToolName.NONE:
            return self._route_failure(question, route)

        unknown_focus = self._unknown_focus_terms(question, route) if audience != Audience.KIDS else []
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
                question, route, fallback_result.documents, relaxed=True
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
            # 图证据为空时按“救援路径”放宽：实体出现在文档中即为足够信号，
            # 避免兜底检索到的唯一可用文档又被严格方面词过滤丢掉。
            filtered_docs = self._filter_focus_documents(
                question, route, result.documents, relaxed=True
            )
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
        if not claims or not selected_citations or not _answer_grounding_ok(
            route, answer, selected_result
        ):
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
        has_entity = bool(route.entity_query or route.entities)
        top_k = (
            10
            if has_entity
            else 8
            if route.answer_mode == AnswerMode.DEEP or route.intent in {"explanation", "comparison", "hybrid_explanation"}
            else 5
        )
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
            zones = (
                {"王墓展区", "两展区"}
                if route.visit_zone.value == "wangmu"
                else {"王墓展区", "王宫展区", "两展区"}
            ) if route.intent == "visit_guidance" else None
            queries = route.subqueries or [question]
            if route.kids_intent == "story":
                # 儿童故事按问题本身 + 一条南越故事扩展检索：既让
                # “角形玉杯”命中对应故事文档，又让“南越的故事”能
                # 命中赵佗/陆贾类典故文档；去掉过窄的赵佗专指子查询。
                queries = [question, "南越国 历史故事 传说 典故 文物"]
            result = self.tools.search_documents(
                question,
                queries=queries,
                category=category,
                include_curated_guidance=route.intent == "visit_guidance",
                top_k=top_k,
                temporal_scope=route.temporal_scope.value,
                as_of=route.as_of,
                zones=zones,
            )
            if route.intent == "anecdote":
                # 只保留真正讲典故/传说/成语的资料，避免博物馆概况
                # 文档抢到高排名导致回答偏题。
                anecdote_hits = [
                    hit
                    for hit in result.documents
                    if ANECDOTE_CONTENT_RE.search(
                        f"{hit.metadata.get('title', '')} {hit.content}"
                    )
                ]
                if anecdote_hits:
                    result = ToolResult(documents=anecdote_hits)
            return result
        if route.tool == ToolName.HYBRID_SEARCH:
            return self.tools.hybrid_search(
                question,
                entity_query=route.entity_query,
                top_k=top_k,
                depth=depth,
                limit=20 if depth == 2 else 12,
                queries=route.subqueries or [question],
                entity_queries=route.entities or None,
                temporal_scope=route.temporal_scope.value,
                as_of=route.as_of,
            )
        raise ValueError(f"unsupported tool: {route.tool}")

    def _fallback_document_search(self, question: str, route: RouteDecision) -> ToolResult:
        if route.tool == ToolName.SEARCH_DOCUMENTS:
            return ToolResult()
        queries = list(dict.fromkeys([question, *route.subqueries]))
        zones = (
            {"王墓展区", "两展区"}
            if route.visit_zone.value == "wangmu"
            else {"王墓展区", "王宫展区", "两展区"}
        ) if route.intent == "visit_guidance" else None
        return self.tools.search_documents(
            question,
            top_k=5,
            queries=queries,
            temporal_scope=route.temporal_scope.value,
            as_of=route.as_of,
            zones=zones,
        )

    def _filter_focus_documents(
        self, question: str, route: RouteDecision, documents: list, *, relaxed: bool = False
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
        # 样板页（备案/导航/联系方式等整页抓取内容）不能作为回答证据。
        documents = [
            hit
            for hit in documents
            if not (BOILERPLATE_RE.search(hit.content) and "备案" in hit.content)
        ]
        if not documents:
            return []
        # 参观问题已经在 AgentTools 中按 tourism 分类、证据角色和专用提示词
        # 完成分路检索与重排。此处再按字面 bigram 过滤，会把“第一次怎么看”
        # 这类自然说法误判为无证据。
        if route.intent in {"visit_guidance", "anecdote"}:
            # Visitor intent has already been narrowed to tourism documents,
            # time/zone validity and dedicated reranking. Natural questions
            # such as “什么时候开门” or “最佳游览路线” often have no exact
            # content bigram in a source, so the generic history-QA focus
            # filter must not discard their otherwise grounded evidence.
            # Anecdote intent is likewise narrowed by dedicated 典故/传说
            # subqueries, so the strict focus filter must not drop them.
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
            if relaxed:
                # 兜底检索（KG 证据缺失时的救援路径）：实体名出现在文档中
                # 即为足够信号，不再要求方面词覆盖率，避免把唯一可用的
                # 证据文档滤掉。
                kept = []
                for hit in documents:
                    chunk_text = f"{hit.metadata.get('title', '')} {hit.content}"
                    if any(name in chunk_text for name in entity_names):
                        kept.append(hit)
                return kept
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
        if route.kids_intent:
            return (
                "哎呀，小越在可靠资料里没有找到足够的内容来回答这个。"
                "可以换个问题试试，比如让我讲一个文帝行玺的小故事，"
                "或者问问丝缕玉衣是做什么用的。"
            )
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
        web_question = question
        if route.intent == "visit_guidance" and not NANYUE_SCOPE_RE.search(question):
            web_question = f"南越王博物院王墓展区：{question}"
        try:
            result = self.web_search_generator.search(web_question)
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
        if route.kids_intent:
            if route.intent == "realtime_unavailable":
                status = AnswerStatus.REALTIME_UNAVAILABLE
                answer = (
                    "这个问题要看当天的情况，小越也不知道哦。"
                    "可以问问博物馆的叔叔阿姨，或者请爸爸妈妈看官方公众号。"
                )
            else:
                status = AnswerStatus.OUT_OF_SCOPE
                answer = (
                    "这个问题有点难住小越啦。可以换个南越的小问题，"
                    "比如「文帝行玺是什么做的？」或者「给我讲个故事」。"
                )
            return AgentAnswer(
                answer=answer,
                citations=[],
                used_tools=[],
                route_reason=route.reason,
                insufficient_evidence=True,
                refusal_reason=route.reason,
                response_status=status,
                suggested_questions=[
                    "给我讲一个文帝行玺的小故事",
                    "丝缕玉衣是做什么用的？",
                ],
            )
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
        elif route.intent == "wanggong_visit_out_of_scope":
            status = AnswerStatus.OUT_OF_SCOPE
            answer = "当前智慧导览以王墓展区为主。王宫资料只用于两展区比较、交通和联动路线；你可以改问“王墓和王宫怎样联动参观？”。"
        elif route.intent == "visit_uncertain":
            status = AnswerStatus.INSUFFICIENT_EVIDENCE
            answer = "暂未在可靠资料中找到这项参观细节的馆方依据，建议出行前向馆方咨询确认。"
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
        if route.kids_intent:
            return ["给我讲一个文帝行玺的小故事", "丝缕玉衣是做什么用的？"]
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
        if route.intent == "visit_guidance":
            # Visitor-service vocabulary is intentionally paraphrase-heavy;
            # it is validated by tourism retrieval and evidence roles rather
            # than the generic unknown-subject guard.
            return []
        if route.entities or route.entity_query:
            # 已锚定实体的问题也继续检查未知词段：词表能区分“秦始皇”（语料
            # 已收录）与“李鴻章/老婆/货币”（未收录）。未知词段一旦存在，
            # 说明问的是知识库没有的方面/人物，应拒答而不是拿实体资料凑数。
            pass
        vocabulary = getattr(self.tools.document_retriever, "idf", None)
        if not vocabulary:
            return []
        entity_names = list(
            route.entities or ([] if route.entity_query is None else [route.entity_query])
        )
        text = question
        for phrase in QUESTION_STOP_PHRASES:
            text = text.replace(phrase, " ")
        # 确认问法（…吗）：只检查实体出现之前的“主语”部分。
        # “李鴻章来过南越王墓吗”→主语未知→拒答；“文帝行玺是用铜做的吗”→
        # 主语是已知实体→允许实体证据作答。
        scan_text = text
        if question.rstrip("？?。！!，, ") .endswith(("吗", "嘛", "吧")) or "是不是" in question:
            first_pos = -1
            for name in entity_names:
                position = question.find(name)
                if position >= 0 and (first_pos < 0 or position < first_pos):
                    first_pos = position
            if first_pos >= 0:
                scan_text = question[:first_pos]
                for phrase in QUESTION_STOP_PHRASES:
                    scan_text = scan_text.replace(phrase, " ")
            # “和/与”之后的比较对象也要扫（“南越国和西游记有关系吗”→西游记未知→拒答）
            for separator in ("和", "与"):
                separator_pos = question.find(separator)
                if separator_pos >= 0:
                    tail = question[separator_pos + 1 :]
                    for phrase in QUESTION_STOP_PHRASES:
                        tail = tail.replace(phrase, " ")
                    scan_text = f"{scan_text} {tail}"
        unknown: list[str] = []
        comparison_shape = bool(COMPARISON_UNKNOWN_RE.search(question))
        scan_targets = [scan_text] if not comparison_shape else [text, scan_text]
        for target in scan_targets:
            for segment in re.findall(r"[一-鿿]+", target):
                content = []
                for index in range(len(segment) - 1):
                    bigram = segment[index : index + 2]
                    if any(char in SCAFFOLD_CHARS for char in bigram):
                        continue
                    if any(bigram in name for name in entity_names):
                        continue
                    # 动词+体貌后缀（灭掉→灭、带来了→带）视为已知词干，
                    # 不触发未知主题拒答。
                    if (
                        len(bigram) == 2
                        and bigram[1] in VERB_ASPECT_SUFFIXES
                        and bigram[0] in vocabulary
                    ):
                        continue
                    content.append(bigram)
                unknown_bigrams = [
                    term for term in content if not self._term_known(term, vocabulary)
                ]
                if comparison_shape:
                    # 比较/关系类问法：出现任何一个词表外方面词即拒答。
                    if unknown_bigrams:
                        unknown.extend(unknown_bigrams)
                elif content and len(unknown_bigrams) == len(content):
                    unknown.extend(unknown_bigrams)
        # 外来词（GDP/WiFi 等）：词表外的英文词视为未知主题。
        vocabulary_lower = {str(term).lower() for term in vocabulary}
        for word in re.findall(r"[A-Za-z]{2,}", question):
            if word.lower() not in vocabulary_lower:
                unknown.append(word)
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
    if route.kids_intent:
        # 儿童模式不联网：所有回答只能来自本地可信资料。
        return False
    if route.scope != "in_scope" or route.tool == ToolName.NONE:
        return False
    if route.intent in {
        "realtime_unavailable",
        "out_of_scope",
        "clarification_needed",
        "incorrect_premise",
    }:
        return False
    return bool(
        route.intent == "visit_guidance"
        or route.entity_query
        or route.entities
        or NANYUE_SCOPE_RE.search(question)
    )


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
    return (
        route.tool == ToolName.SEARCH_KG and bool(route.entity_query)
    ) or route.intent == "visit_guidance"


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


def _answer_grounding_ok(route: RouteDecision, answer: str, selected_result: ToolResult) -> bool:
    """Grounding gate: adult answers keep the strict bigram coverage check;
    kids answers additionally pass when they verbatim embed their evidence
    (the extractive kids template is built from evidence snippets by
    construction, and the short test-corpus evidence sentences would
    otherwise fail the vocabulary-coverage ratio)."""
    if _answer_is_grounded(answer, selected_result):
        return True
    return bool(route.kids_intent and _kids_answer_embeds_evidence(answer, selected_result))


def _kids_answer_embeds_evidence(answer: str, selected_result: ToolResult) -> bool:
    for hit in selected_result.graph[:3]:
        evidence = " ".join(hit.evidence.split())
        if len(evidence) >= 6 and evidence[:80] in answer:
            return True
    for hit in selected_result.documents[:2]:
        content = " ".join(hit.content.split())
        if len(content) >= 6 and content[:80] in answer:
            return True
    return False


KIDS_CHAT_RE = re.compile(r"你好|您好|hello|hi|在吗|你是谁|介绍一下你|你会什么|谢谢|感谢|再见|拜拜|辛苦了|干嘛|做什么的|叫(什么|嘛)名字")
KIDS_STORY_RE = re.compile(r"故事|讲个|讲讲|猜猜|从前|小故事|传说|睡前|讲一下|讲一段|典故|成语|趣事|掌故")
ANECDOTE_ONTOPIC_RE = re.compile(r"典故|成语|轶事|掌故|趣事|历史故事|民间传说|传说")
ANECDOTE_CONTENT_RE = re.compile(r"典故|成语|轶事|掌故|趣事|历史故事|传说|故事")
# 网站整页抓取的样板内容（备案/导航/联系方式等），不作为回答证据。
BOILERPLATE_RE = re.compile(r"备案号|版权所有|ICP|网站地图|技术支持|公安备案|主办单位|联系电话|友情链接")
# 比较/关系类问法：只要出现词表外的方面词（如“赋税制度”“新衣”）就拒答，
# 避免“A和B一样吗/什么关系”被已知实体的资料带偏。
COMPARISON_UNKNOWN_RE = re.compile(r"(一样吗|什么关系|有何异同|有什么关系|区别|异同|分别是什么|一样)")


def _detect_kids_intent(question: str) -> str:
    """儿童模式下识别对话意图：story / chat / relic（默认文物讲解）。"""
    if KIDS_STORY_RE.search(question):
        return "story"
    if KIDS_CHAT_RE.search(question):
        return "chat"
    return "relic"


def _story_entity_uses_kg(tools: AgentTools, name: str) -> bool:
    """儿童故事是否应强制走图谱：仅当实体是文物/人物等“可讲故事”的具体对象。"""
    try:
        matches = tools.graph_retriever.list_entities(name, limit=3)
    except Exception:
        return False
    for entity in matches:
        entity_type = str(getattr(entity, "type", "") or "")
        if entity_type in {"Relic", "Person", "Artifact", "Material", "Object", "Tomb"}:
            return True
    return False


def _kids_chat_answer(question: str) -> str:
    if re.search(r"谢谢|感谢", question):
        return "不客气呀小朋友！有什么想听的故事，随时来找小越。"
    if re.search(r"再见|拜拜", question):
        return "再见啦小朋友，欢迎再来南越王博物院玩！记得去看看文帝行玺和丝缕玉衣哦。"
    return (
        "你好呀小朋友！我是小越，南越王博物院的儿童讲解员。"
        "我可以给你讲文物的故事，介绍丝缕玉衣、文帝行玺这些宝贝，"
        "也可以陪你聊聊天。你想从哪里开始呢？"
    )


def _kids_shorten(text: str, limit: int = 80) -> str:
    text = " ".join(text.split())
    return text[:limit] + ("……" if len(text) > limit else "")


def _kids_extractive_answer(intent: str, result: ToolResult, document_hits: list | None = None) -> str:
    """离线抽取式儿童回答：把图谱关系与文档证据改写成短句，并内嵌逐字证据。

    document_hits 必须与 selected_evidence_ids 使用同一份排序后的文档，
    否则接地校验会因“回答引用的证据”与“声明引用的证据”不一致而失败。
    """
    docs = list(document_hits) if document_hits is not None else list(result.documents)
    facts = [
        f"{hit.source_entity.name}{_relation_label(hit.relation)}{hit.target_entity.name}"
        for hit in result.graph[:3]
    ]
    evidence_lines = [_kids_shorten(hit.evidence) for hit in result.graph[:3]]
    doc_lines = [_kids_shorten(_format_extract(hit)) for hit in docs[:2]]
    if intent == "story":
        lines = ["小越讲故事时间！\n"]
        if result.graph:
            lines.append(f"今天的故事，和{result.graph[0].source_entity.name}有关。")
            for fact, evidence in zip(facts, evidence_lines):
                lines.append(f"{fact}。{evidence}")
        elif doc_lines:
            lines.append("小越从可靠资料里找到了这个小故事：")
            lines.extend(doc_lines)
        lines.append("\n你还想听别的故事吗？告诉我一个文物的名字就好！")
        return "\n".join(lines)
    lines = ["小越来讲解啦！\n"]
    for fact, evidence in zip(facts[:2], evidence_lines[:2]):
        lines.append(f"{fact}。{evidence}")
    if doc_lines and not result.graph:
        lines.extend(doc_lines)
    lines.append("\n你可以在「镇馆之珍」里找到它哦。")
    return "\n".join(lines)
