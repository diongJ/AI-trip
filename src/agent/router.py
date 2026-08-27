from __future__ import annotations

import re
from typing import Protocol

from src.agent.models import AnswerMode, QuestionType, RouteDecision, ToolName


class EntityResolver(Protocol):
    def list_entities(self, query: str = "", *, entity_type: str | None = None, limit: int = 100) -> list[object]: ...

    def resolve_entity_id(self, query: str) -> str | None: ...


REALTIME_OUT_OF_SCOPE_RE = re.compile(
    r"(今天|现在|实时|当前).*(游客|人数|客流|天气|交通|排队|开放|票价|门票|预约|余票)|"
    r"(实时价格|实时客流|当前排队|今日客流|今天客流|天气|预测)"
)
INCORRECT_PREMISE_RE = re.compile(
    r"(?:火星|月球|外星).*(?:南越王墓|南越文王墓)|(?:南越王墓|南越文王墓).*(?:火星|月球|外星)"
)
DOMAIN_OUT_OF_SCOPE_RE = re.compile(
    r"(路线导航|停车最方便|哪里停车|餐厅|酒店|公交换乘|地铁换乘|打车|机场|"
    r"智能手机|恐龙|航空母舰|火星|月球|外星)"
)
RELATION_RE = re.compile(r"(关系|谁|属于|出土|材料|材质|纹饰|制作|反映|关联|葬)")
DESCRIPTION_RE = re.compile(r"(介绍|讲讲|特点|意义|价值|如何|为什么|背景|过程|展示|展区)")
HYBRID_RE = re.compile(
    r"(结合.*(?:文物|资料|证据)|文物证据|建立|创建|创立|开国|反映|观念)"
)
COMPARISON_RE = re.compile(r"(比较|区别|异同|不同|相同|对比)")
EXPLANATION_RE = re.compile(r"(为什么|意义|价值|反映了什么|体现|如何理解|影响)")
TOURISM_RE = re.compile(
    r"(参观|游览|攻略|怎么逛|怎么玩|路线|动线|展厅|展区|开放时间|几点|门票|预约|地址|"
    r"交通|怎么去|讲解|导览|寄存|服务|拍照|无障碍|亲子|学生|老人|行程)"
)


class RuleBasedRouter:
    def __init__(self, resolver: EntityResolver | None = None) -> None:
        self.resolver = resolver

    def route(self, question: str) -> RouteDecision:
        normalized = question.strip()
        if not normalized:
            return RouteDecision(
                question_type=QuestionType.OUT_OF_SCOPE,
                tool=ToolName.NONE,
                reason="问题为空，无法检索可靠证据。",
                intent="clarification_needed",
                scope="out_of_scope",
            )
        if REALTIME_OUT_OF_SCOPE_RE.search(normalized):
            return RouteDecision(
                question_type=QuestionType.OUT_OF_SCOPE,
                tool=ToolName.NONE,
                reason="问题涉及实时信息，静态资料无法可靠确认。",
                intent="realtime_unavailable",
                scope="out_of_scope",
            )
        if INCORRECT_PREMISE_RE.search(normalized):
            return RouteDecision(
                question_type=QuestionType.OUT_OF_SCOPE,
                tool=ToolName.NONE,
                reason="可靠资料与问题中的地点前提不一致。",
                intent="incorrect_premise",
                scope="out_of_scope",
            )
        if DOMAIN_OUT_OF_SCOPE_RE.search(normalized):
            return RouteDecision(
                question_type=QuestionType.OUT_OF_SCOPE,
                tool=ToolName.NONE,
                reason="问题超出南越专题和馆内稳定信息范围。",
                intent="out_of_scope",
                scope="out_of_scope",
            )

        entity_query = self._find_entity_query(normalized)
        answer_mode = _default_answer_mode(normalized)
        explanation_intent = "comparison" if COMPARISON_RE.search(normalized) else (
            "explanation" if EXPLANATION_RE.search(normalized) else "description"
        )
        if entity_query and HYBRID_RE.search(normalized):
            return RouteDecision(
                question_type=QuestionType.DESCRIPTION,
                tool=ToolName.HYBRID_SEARCH,
                entity_query=entity_query,
                reason="问题需要结合结构化关系和文档证据，使用混合检索。",
                intent="hybrid_explanation" if explanation_intent == "description" else explanation_intent,
                entities=[entity_query],
                subqueries=[normalized],
                answer_mode=answer_mode,
            )
        if TOURISM_RE.search(normalized):
            return RouteDecision(
                question_type=QuestionType.DESCRIPTION,
                tool=ToolName.SEARCH_DOCUMENTS,
                entity_query=entity_query,
                reason="问题属于稳定参观攻略或游览信息，优先检索官方参观资料。",
                intent="visit_guidance",
                entities=[entity_query] if entity_query else [],
                subqueries=_visit_subqueries(normalized),
                answer_mode=answer_mode,
            )
        if entity_query and RELATION_RE.search(normalized):
            return RouteDecision(
                question_type=QuestionType.RELATION_EXPLORATION,
                tool=ToolName.SEARCH_KG,
                entity_query=entity_query,
                reason="问题包含图谱实体和明确关系词，优先查询 KG。",
                intent="relation_exploration",
                entities=[entity_query],
                subqueries=[normalized],
                answer_mode=answer_mode,
            )
        if entity_query and DESCRIPTION_RE.search(normalized):
            return RouteDecision(
                question_type=QuestionType.DESCRIPTION,
                tool=ToolName.HYBRID_SEARCH,
                entity_query=entity_query,
                reason="问题需要实体关系和文档描述，使用混合检索。",
                intent=explanation_intent,
                entities=[entity_query],
                subqueries=[normalized],
                answer_mode=answer_mode,
            )
        if entity_query:
            return RouteDecision(
                question_type=QuestionType.ENTITY_FACT,
                tool=ToolName.SEARCH_KG,
                entity_query=entity_query,
                reason="问题命中图谱实体，优先查询结构化事实。",
                intent="entity_fact",
                entities=[entity_query],
                subqueries=[normalized],
                answer_mode=answer_mode,
            )
        if DESCRIPTION_RE.search(normalized):
            return RouteDecision(
                question_type=QuestionType.DESCRIPTION,
                tool=ToolName.SEARCH_DOCUMENTS,
                reason="问题偏描述性，使用文档检索获取原文片段。",
                intent=explanation_intent,
                subqueries=[normalized],
                answer_mode=answer_mode,
            )
        return RouteDecision(
            question_type=QuestionType.DESCRIPTION,
            tool=ToolName.SEARCH_DOCUMENTS,
            reason="未命中明确实体，使用文档检索作为保守默认策略。",
            intent=explanation_intent,
            subqueries=[normalized],
            answer_mode=answer_mode,
        )

    def _find_entity_query(self, question: str) -> str | None:
        if self.resolver is None:
            return None
        listed = _entity_from_known_aliases(question, self.resolver)
        if listed:
            return listed
        candidates = _entity_candidates(question)
        for candidate in candidates:
            if self.resolver.resolve_entity_id(candidate):
                return candidate
        return None


def _entity_candidates(question: str) -> list[str]:
    clean = re.sub(r"[？?，,。！!：:；;、]", " ", question)
    tokens = [token.strip() for token in clean.split() if token.strip()]
    candidates = sorted(tokens, key=len, reverse=True)
    simplified = re.sub(
        r"(请|用|约|字|写|一段|清晰|适合|现场|参观|简短|导览|介绍一下|介绍|讲讲|"
        r"结合|文物证据|说明|所有判断|必须来自|当前|王墓展区|可靠资料|背景|特征|关系|文化意义|"
        r"生动语言|理解|提出|观察问题)",
        " ",
        question,
    )
    simplified = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9_]+", " ", simplified)
    candidates.extend(token.strip() for token in simplified.split() if token.strip())
    cjk_text = "".join(re.findall(r"[\u4e00-\u9fff]", question))
    for size in range(8, 1, -1):
        candidates.extend(cjk_text[index : index + size] for index in range(len(cjk_text) - size + 1))
    if question.strip() not in candidates:
        candidates.append(question.strip())
    return list(dict.fromkeys(candidate for candidate in candidates if candidate))


def _visit_subqueries(question: str) -> list[str]:
    return list(
        dict.fromkeys(
            [
                question,
                "南越王博物院 王墓展区 参观攻略 开放时间 预约",
                "南越王博物院 王墓展区 地址 交通 导览 服务",
                "南越文王墓 展厅 游览 动线 重点文物",
            ]
        )
    )


def _default_answer_mode(question: str) -> AnswerMode:
    if COMPARISON_RE.search(question) or EXPLANATION_RE.search(question):
        return AnswerMode.DEEP
    return AnswerMode.AUTO


def _entity_from_known_aliases(question: str, resolver: EntityResolver) -> str | None:
    if not hasattr(resolver, "list_entities"):
        return None
    try:
        entities = resolver.list_entities(limit=300)
    except Exception:
        return None
    aliases: list[str] = []
    for entity in entities:
        aliases.extend([entity.name, *entity.aliases])
    matches = [
        alias
        for alias in aliases
        if alias and len(alias) >= 2 and alias in question
    ]
    if not matches:
        return None
    return sorted(set(matches), key=lambda value: (-len(value), value))[0]
