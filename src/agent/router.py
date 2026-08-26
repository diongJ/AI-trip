from __future__ import annotations

import re
from typing import Protocol

from src.agent.models import QuestionType, RouteDecision, ToolName


class EntityResolver(Protocol):
    def list_entities(self, query: str = "", *, entity_type: str | None = None, limit: int = 100) -> list[object]: ...

    def resolve_entity_id(self, query: str) -> str | None: ...


REALTIME_OUT_OF_SCOPE_RE = re.compile(
    r"(今天|现在|实时|当前).*(游客|人数|客流|天气|交通|排队|开放|票价|门票|预约|余票)|"
    r"(实时价格|实时客流|当前排队|今日客流|今天客流|天气|预测)"
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
                scope="out_of_scope",
            )
        if REALTIME_OUT_OF_SCOPE_RE.search(normalized) or DOMAIN_OUT_OF_SCOPE_RE.search(normalized):
            return RouteDecision(
                question_type=QuestionType.OUT_OF_SCOPE,
                tool=ToolName.NONE,
                reason="问题涉及实时或项目范围外信息，当前资料无法可靠回答。",
                scope="out_of_scope",
            )

        entity_query = self._find_entity_query(normalized)
        if entity_query and HYBRID_RE.search(normalized):
            return RouteDecision(
                question_type=QuestionType.DESCRIPTION,
                tool=ToolName.HYBRID_SEARCH,
                entity_query=entity_query,
                reason="问题需要结合结构化关系和文档证据，使用混合检索。",
                intent="hybrid_explanation",
                entities=[entity_query],
                subqueries=[normalized],
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
            )
        if entity_query and DESCRIPTION_RE.search(normalized):
            return RouteDecision(
                question_type=QuestionType.DESCRIPTION,
                tool=ToolName.HYBRID_SEARCH,
                entity_query=entity_query,
                reason="问题需要实体关系和文档描述，使用混合检索。",
                entities=[entity_query],
                subqueries=[normalized],
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
            )
        if DESCRIPTION_RE.search(normalized):
            return RouteDecision(
                question_type=QuestionType.DESCRIPTION,
                tool=ToolName.SEARCH_DOCUMENTS,
                reason="问题偏描述性，使用文档检索获取原文片段。",
                subqueries=[normalized],
            )
        return RouteDecision(
            question_type=QuestionType.DESCRIPTION,
            tool=ToolName.SEARCH_DOCUMENTS,
            reason="未命中明确实体，使用文档检索作为保守默认策略。",
            subqueries=[normalized],
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
