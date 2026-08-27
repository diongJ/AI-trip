from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from src.agent.models import ToolResult
from src.rag.models import GraphHit, RetrievalHit


class DocumentRetriever(Protocol):
    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        category: str | None = None,
        min_score: float = 0.0,
        evidence_role: str | None = None,
        temporal_scope: str = "all",
        as_of: str | None = None,
        zones: set[str] | None = None,
    ) -> list[RetrievalHit]: ...

    def search_many(
        self,
        queries: list[str],
        *,
        top_k: int = 8,
        per_query_k: int = 12,
        category: str | None = None,
        source_tier: str | None = None,
        evidence_role: str | None = None,
        temporal_scope: str = "all",
        as_of: str | None = None,
        zones: set[str] | None = None,
    ) -> list[RetrievalHit]: ...


class GraphRetriever(Protocol):
    def list_entities(
        self,
        query: str = "",
        *,
        entity_type: str | None = None,
        limit: int = 100,
    ) -> list[GraphEntity]: ...

    def resolve_entity_id(self, query: str) -> str | None: ...

    def get_neighbors(
        self,
        entity_query: str,
        *,
        depth: int = 1,
        limit: int = 20,
    ) -> list[GraphHit]: ...


RELATION_HINTS: tuple[tuple[re.Pattern[str], frozenset[str]], ...] = (
    (re.compile(r"材料|材质"), frozenset({"MADE_OF"})),
    (re.compile(r"纹饰|图案"), frozenset({"HAS_PATTERN"})),
    (re.compile(r"出土"), frozenset({"EXCAVATED_FROM"})),
    (re.compile(r"埋葬|墓葬|葬于"), frozenset({"BURIED_IN"})),
    (re.compile(r"类别|种类"), frozenset({"BELONGS_TO_CATEGORY"})),
    (re.compile(r"朝代|时期|年代|制作于"), frozenset({"CREATED_IN"})),
    (re.compile(r"文化|反映"), frozenset({"REFLECTS_CULTURE"})),
    (re.compile(r"属于哪国|哪个国家|所属国家"), frozenset({"BELONGS_TO_STATE"})),
)
VISIT_HINT_RE = re.compile(
    r"(参观|游览|攻略|怎么逛|怎么玩|开放时间|几点|门票|预约|地址|交通|导览|讲解|服务|展厅|展区|动线|行程|"
    r"寄存|轮椅|婴儿车|无障碍|手语|多语种|语音|英语|英文|老人|分钟|小时|雨天|食物|母婴|"
    r"开门|开馆|营业|关门|闭馆|最[佳优]|推荐|建议|值得看|看什么|怎么安排|怎么走|逛多久|多久能逛完|半天)"
)
VISIT_QUERIES = [
    "南越王博物院 王墓展区 参观攻略 开放时间 预约",
    "南越王博物院 王墓展区 地址 交通 导览 服务",
    "南越文王墓 展厅 游览 动线 重点文物",
]
FIRST_VISIT_RE = re.compile(r"第一次|初次|首次|第一次去|应该怎么看|参观重点|重点看")
ROUTE_REQUEST_RE = re.compile(r"(路线|动线|行程|最[佳优]|推荐|建议|怎么安排|怎么逛|怎么玩|逛多久|多久能逛完|半天|小时|分钟)")
BOUNDARY_REQUEST_RE = re.compile(r"(实时|当天|今天|边界|官网|确认|公告)")
VISIT_AUDIENCE_QUERIES: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = (
    (
        FIRST_VISIT_RE,
        (
            "第一次参观 王墓展区 重点 文帝行玺 丝缕玉衣 墓主人",
            "王墓展区 初次参观 代表文物 墓主人身份 参观动线",
            "南越文王墓 参观重点 文帝行玺 重要文物",
        ),
    ),
    (
        re.compile(r"学生|研学|课程|作业"),
        (
            "学生 研学 讲解问题 墓主人 文帝行玺 王墓展区",
            "亲子 学生 参观建议 墓主人 文帝行玺 丝缕玉衣",
            "王墓展区 学生参观 历史证据链 文帝行玺 墓主人",
        ),
    ),
    (
        re.compile(r"亲子|孩子|儿童|小朋友|家庭"),
        (
            "亲子 观察任务 文帝行玺 丝缕玉衣 船纹铜提筒",
            "孩子 儿童 王墓展区 观察问题 代表文物",
        ),
    ),
    (
        re.compile(r"讲解|导览"),
        (
            "王墓展区 讲解问题 墓主人 赵眜 文帝行玺",
            "南越文王墓 导览 代表文物 讲解线索",
        ),
    ),
    (
        re.compile(r"老人|长者|老年"),
        (
            "老人 长者 王墓展区 轻松参观 路线 休息 建议",
            "王墓展区 老年观众 参观时长 无障碍 服务",
        ),
    ),
    (
        re.compile(r"轮椅|无障碍|婴儿车"),
        (
            "王墓展区 轮椅 婴儿车 无障碍 服务台 租借",
            "南越王博物院 无障碍 轮椅 参观服务",
        ),
    ),
    (
        re.compile(r"寄存|行李"),
        (
            "王墓展区 行李 寄存柜 服务",
        ),
    ),
    (
        re.compile(r"手语|多语种|英语|英文|语音"),
        (
            "南越王博物院 英语 多语种 语音导览 手语导赏 服务",
        ),
    ),
    (
        re.compile(r"下雨|雨天|降雨"),
        (
            "雨天参观 王墓展区 室内展陈 行程建议",
            "下雨 王墓展区 参观攻略 天气 信息边界",
        ),
    ),
    (
        re.compile(r"两展区|王墓.*王宫|王宫.*王墓|一起参观|联动|展区.*区别"),
        (
            "王墓 王宫 两展区 联动参观 路线 预约 交通",
            "王墓展区 王宫展区 区别 一天参观 建议",
        ),
    ),
)
AUDIENCE_HINTS: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = (
    (
        FIRST_VISIT_RE,
        ("第一次", "初次", "重点", "文帝行玺", "丝缕玉衣", "墓主人", "代表文物", "动线"),
    ),
    (
        re.compile(r"开放时间|几点|开门|开馆|营业|关门|闭馆|入馆|官方|购票"),
        ("开放时间", "9:00-17:30", "17:00", "开门", "闭馆", "预约", "官方", "门票", "入馆"),
    ),
    (
        re.compile(r"地址|交通|怎么去|在哪|地铁|公交"),
        ("地址", "解放北路", "越秀", "交通", "地铁", "公交", "位于"),
    ),
    (
        re.compile(r"学生|研学|课程|作业"),
        ("学生", "研学", "任务", "问题", "证据", "墓主人", "文帝行玺", "学生参观", "证据链"),
    ),
    (re.compile(r"亲子|孩子|儿童|小朋友|家庭"), ("亲子", "孩子", "儿童", "观察", "任务")),
    (re.compile(r"老人|长者|老年"), ("老人", "长者", "轻松", "休息", "路线", "服务")),
    (re.compile(r"半小时|一小时|两小时|半日|小时|分钟|路线|动线|行程|最[佳优]|推荐|建议|怎么安排|逛多久|多久能逛完"), ("半小时", "一小时", "两小时", "半日", "路线", "动线", "建议")),
    (re.compile(r"讲解|导览"), ("讲解", "导览", "提问", "问题", "线索")),
    (re.compile(r"寄存|行李"), ("寄存", "行李", "服务", "入馆")),
    (re.compile(r"轮椅|无障碍|婴儿车"), ("轮椅", "无障碍", "婴儿车", "服务", "咨询")),
    (re.compile(r"手语|多语种|英语|英文|语音"), ("手语", "多语种", "英语", "导览", "服务")),
    (re.compile(r"下雨|雨天|降雨"), ("雨天", "下雨", "降雨", "室内展陈", "天气", "信息边界")),
    (re.compile(r"两展区|王墓.*王宫|王宫.*王墓|一起参观|联动|展区.*区别"), ("两展区", "王墓", "王宫", "联动", "路线", "预约")),
)

# Generic interrogative scaffolding: stripped before measuring whether a
# question asks about a specific aspect of an entity.
QUESTION_STOP_PHRASES = (
    "介绍一下", "介绍", "讲讲", "说一下", "怎么样", "如何", "为什么", "是谁",
    "哪些", "哪个", "什么", "怎么", "怎样", "请问", "一下", "哪里", "哪儿",
    "多大", "多少", "多久", "被谁", "关系", "来过", "样子",
    # 生成式指令 scaffolding（讲解提示词模板、用户粘贴的指令句）
    "请用约", "用约", "写一段", "请结合", "文物证据", "所有判断", "必须来自", "可靠资料",
)
SCAFFOLD_CHARS = frozenset("是什么怎吗呢哪的了吗有和与或及何如请谁")
# 动词词尾：匹配方面词时允许“灭掉”→“灭”这类词干命中。
VERB_ASPECT_SUFFIXES = frozenset("掉了过着")
# “讲讲/介绍/说明 X”这类泛描述请求：实体的全部邻居关系都算相关，
# 不做方面词过滤（否则指令词会被误当作“方面”把证据全部滤掉）。
GENERIC_DESCRIPTION_RE = re.compile(
    r"(介绍|讲讲|讲解|导览|说明|特点|意义|价值|背景|过程|如何|为什么|怎么样)"
)


@dataclass
class AgentTools:
    document_retriever: DocumentRetriever
    graph_retriever: GraphRetriever

    def search_documents(
        self,
        query: str,
        *,
        top_k: int = 5,
        category: str | None = None,
        queries: list[str] | None = None,
        include_curated_guidance: bool = False,
        temporal_scope: str = "all",
        as_of: str | None = None,
        zones: set[str] | None = None,
    ) -> ToolResult:
        expanded_queries = _expand_document_queries(query, queries)
        should_rerank_visit = bool(VISIT_HINT_RE.search(query))
        search_top_k = _visit_candidate_limit(query, top_k) if should_rerank_visit else top_k
        factual = (
            self.document_retriever.search_many(
                expanded_queries,
                top_k=search_top_k,
                category=category,
                evidence_role="factual",
                temporal_scope=temporal_scope,
                as_of=as_of,
                zones=zones,
            )
            if hasattr(self.document_retriever, "search_many")
            else self.document_retriever.search(
                query,
                top_k=search_top_k,
                category=category,
                evidence_role="factual",
                temporal_scope=temporal_scope,
                as_of=as_of,
                zones=zones,
            )
        )
        if not factual and category is not None:
            factual = (
                self.document_retriever.search_many(
                    expanded_queries,
                    top_k=search_top_k,
                    evidence_role="factual",
                    temporal_scope=temporal_scope,
                    as_of=as_of,
                    zones=zones,
                )
                if hasattr(self.document_retriever, "search_many")
                else self.document_retriever.search(
                    query,
                    top_k=search_top_k,
                    evidence_role="factual",
                    temporal_scope=temporal_scope,
                    as_of=as_of,
                    zones=zones,
                )
            )
        if not factual:
            fallback_queries = _fallback_document_queries(query)
            factual = (
                self.document_retriever.search_many(
                    fallback_queries,
                    top_k=search_top_k,
                    evidence_role="factual",
                    temporal_scope=temporal_scope,
                    as_of=as_of,
                    zones=zones,
                )
                if hasattr(self.document_retriever, "search_many")
                else self.document_retriever.search(
                    fallback_queries[0],
                    top_k=search_top_k,
                    evidence_role="factual",
                    temporal_scope=temporal_scope,
                    as_of=as_of,
                    zones=zones,
                )
            )
        if should_rerank_visit:
            factual = _rerank_visit_documents(query, factual)
        curated: list[RetrievalHit] = []
        if include_curated_guidance:
            curated = (
                self.document_retriever.search_many(
                    expanded_queries,
                    top_k=search_top_k,
                    category="tourism",
                    evidence_role="curated_guidance",
                    temporal_scope=temporal_scope,
                    as_of=as_of,
                    zones=zones,
                )
                if hasattr(self.document_retriever, "search_many")
                else self.document_retriever.search(
                    query,
                    top_k=search_top_k,
                    category="tourism",
                    evidence_role="curated_guidance",
                    temporal_scope=temporal_scope,
                    as_of=as_of,
                    zones=zones,
                )
            )
            curated = _rerank_visit_documents(query, curated)
        documents = _combine_visit_documents(factual, curated, top_k)
        return ToolResult(documents=documents)

    def search_kg(
        self,
        query: str,
        *,
        entity_query: str | None = None,
        depth: int = 1,
        limit: int = 12,
        entity_queries: list[str] | None = None,
    ) -> ToolResult:
        hits: list[GraphHit] = []
        seen: set[tuple[str, str, str, str]] = set()
        for candidate in entity_queries or [entity_query or query]:
            for hit in self.graph_retriever.get_neighbors(candidate, depth=depth, limit=limit):
                key = (hit.source_entity.id, hit.relation, hit.target_entity.id, hit.document_id)
                if key not in seen:
                    seen.add(key)
                    hits.append(hit)
        hits = _filter_relevant_relations(query, hits)
        if hits and not _relation_hint_matches(query) and not GENERIC_DESCRIPTION_RE.search(query):
            entity_names = [name for name in (entity_queries or [entity_query]) if name]
            vocabulary = getattr(self.document_retriever, "idf", None)
            hits = _filter_offtopic_hits(query, hits, entity_names, vocabulary)
        return ToolResult(graph=hits)

    def hybrid_search(
        self,
        query: str,
        *,
        entity_query: str | None = None,
        top_k: int = 5,
        depth: int = 1,
        limit: int = 12,
        queries: list[str] | None = None,
        entity_queries: list[str] | None = None,
        temporal_scope: str = "all",
        as_of: str | None = None,
        zones: set[str] | None = None,
    ) -> ToolResult:
        graph = self.search_kg(
            query,
            entity_query=entity_query,
            entity_queries=entity_queries,
            depth=depth,
            limit=limit,
        ).graph if (entity_query or entity_queries) else []
        documents = self.search_documents(
            query,
            top_k=top_k,
            queries=queries,
            temporal_scope=temporal_scope,
            as_of=as_of,
            zones=zones,
        ).documents
        return ToolResult(documents=documents, graph=graph)


def _relation_hint_matches(query: str) -> bool:
    return any(pattern.search(query) for pattern, _relations in RELATION_HINTS)


def _filter_relevant_relations(query: str, hits: list[GraphHit]) -> list[GraphHit]:
    expected: set[str] = set()
    for pattern, relations in RELATION_HINTS:
        if pattern.search(query):
            expected.update(relations)
    if not expected:
        return hits
    # 严格过滤：用户问的是特定关系而图谱没有该关系时，不得倒出其他关系凑数；
    # 返回空列表让上层回退到文档检索（原文中往往有答案）。
    return [hit for hit in hits if hit.relation in expected]


def _filter_offtopic_hits(
    query: str,
    hits: list[GraphHit],
    entity_names: list[str],
    vocabulary: dict | None = None,
) -> list[GraphHit]:
    """Drop neighbor relations that share no content vocabulary with the question.

    A plain "tell me about X" question keeps every neighbor; a question that
    asks about a specific aspect (e.g. 赋税制度) only keeps relations whose
    text mentions that aspect. When nothing matches, an empty list lets the
    service fall through to the insufficient-evidence path instead of
    dumping every neighbor as if it were an answer.
    """
    content_bigrams = _question_content_bigrams(query, entity_names, vocabulary)
    if not content_bigrams:
        return hits
    filtered: list[GraphHit] = []
    for hit in hits:
        searchable = " ".join(
            [
                hit.source_entity.name,
                hit.target_entity.name,
                _relation_label(hit.relation),
                hit.evidence,
            ]
        )
        if any(_content_term_matches(bigram, searchable) for bigram in content_bigrams):
            filtered.append(hit)
    return filtered


def _content_term_matches(term: str, searchable: str) -> bool:
    if term in searchable:
        return True
    # 动词词干命中：“灭掉”可命中“汉武帝灭南越国”中的“灭”。
    if len(term) == 2 and term[1] in VERB_ASPECT_SUFFIXES and term[0] in searchable:
        return True
    return False


def _question_content_bigrams(
    query: str,
    entity_names: list[str],
    vocabulary: dict | None = None,
) -> set[str]:
    text = query
    for phrase in QUESTION_STOP_PHRASES:
        text = text.replace(phrase, " ")
    bigrams: set[str] = set()
    for segment in re.findall(r"[一-鿿]+", text):
        chain = [segment[index : index + 2] for index in range(len(segment) - 1)]
        for index, bigram in enumerate(chain):
            if any(char in SCAFFOLD_CHARS for char in bigram):
                continue
            if any(bigram in name for name in entity_names):
                continue
            if vocabulary is not None and bigram not in vocabulary:
                # 邻接伪词：左右相邻 bigram 都在词表中、自己却不在，
                # 说明只是跨词边界的分词产物（如“玺出”“衣出”），剔除。
                left = chain[index - 1] if index > 0 else None
                right = chain[index + 1] if index < len(chain) - 1 else None
                if left in vocabulary and right in vocabulary:
                    continue
            bigrams.add(bigram)
    # ASCII 词（GDP、WiFi 等）同样参与方面匹配，避免英文主题词漏判。
    for word in re.findall(r"[A-Za-z0-9]+", text.lower()):
        if len(word) >= 2 and not any(word in name.lower() for name in entity_names):
            bigrams.add(word)
    return bigrams


def _relation_label(relation: str) -> str:
    labels = {
        "BELONGS_TO_STATE": "属于",
        "BURIED_IN": "墓葬于",
        "CONTAINS": "包含",
        "EXCAVATED_FROM": "出土于",
        "MADE_OF": "材质为",
        "BELONGS_TO_CATEGORY": "属于类别",
        "CREATED_IN": "制作于",
        "RELATED_TO_PERSON": "关联人物为",
        "REFLECTS_CULTURE": "反映",
        "HAS_PATTERN": "具有纹饰",
        "INVOLVES_PERSON": "涉及人物",
        "OCCURRED_IN": "发生于",
    }
    return labels.get(relation, f" {relation} ")


def _expand_document_queries(query: str, queries: list[str] | None) -> list[str]:
    expanded = [query, *(queries or [])]
    if VISIT_HINT_RE.search(query):
        expanded.extend(VISIT_QUERIES)
        for pattern, audience_queries in VISIT_AUDIENCE_QUERIES:
            if pattern.search(query):
                expanded.extend(audience_queries)
    return list(dict.fromkeys(item.strip() for item in expanded if item.strip()))


def _fallback_document_queries(query: str) -> list[str]:
    if VISIT_HINT_RE.search(query):
        expanded = [query, *VISIT_QUERIES]
        for pattern, audience_queries in VISIT_AUDIENCE_QUERIES:
            if pattern.search(query):
                expanded.extend(audience_queries)
        return list(dict.fromkeys(expanded))
    # 非参观类问题不再注入泛化的南越查询：检索不到就返回空，
    # 让上层的“证据不足”分支正常触发，避免用泛泛资料强行作答。
    return [query]


def _visit_candidate_limit(query: str, top_k: int) -> int:
    has_audience_hint = any(pattern.search(query) for pattern, _ in AUDIENCE_HINTS)
    if not has_audience_hint:
        return top_k
    return max(top_k, 12)


def _combine_visit_documents(
    factual: list[RetrievalHit], curated: list[RetrievalHit], top_k: int
) -> list[RetrievalHit]:
    if not curated:
        return factual[:top_k]
    factual_limit = max(1, top_k - 2)
    combined = [*factual[:factual_limit], *curated[:2]]
    if len(combined) < top_k:
        combined.extend(factual[factual_limit : factual_limit + top_k - len(combined)])
    if len(combined) < top_k:
        combined.extend(curated[2 : 2 + top_k - len(combined)])
    return [
        hit.model_copy(
            update={
                "rank": rank,
                "metadata": {**hit.metadata, "fusion_score": hit.score},
            }
        )
        for rank, hit in enumerate(combined[:top_k], start=1)
    ]


def _rerank_visit_documents(query: str, documents: list[RetrievalHit]) -> list[RetrievalHit]:
    hints: list[str] = []
    for pattern, values in AUDIENCE_HINTS:
        if pattern.search(query):
            hints.extend(values)
    if not hints:
        return documents

    scored: list[tuple[float, RetrievalHit]] = []
    for hit in documents:
        searchable = " ".join(
            [
                hit.content,
                str(hit.metadata.get("title", "")),
                " ".join(str(tag) for tag in hit.metadata.get("topic_tags", [])),
            ]
        )
        bonus = sum(0.28 for hint in hints if hint in searchable)
        topic_tags = {str(tag) for tag in hit.metadata.get("topic_tags", [])}
        # “参观前准备/信息边界”对用户问路线、时长、亲子时只是辅助提醒，
        # 不能压过实际的路线或服务证据。
        if "信息边界" in topic_tags and not BOUNDARY_REQUEST_RE.search(query):
            bonus -= 0.8
        if ROUTE_REQUEST_RE.search(query):
            if hit.metadata.get("evidence_role") == "curated_guidance":
                bonus += 0.45
            if "路线" in " ".join(topic_tags) or "动线" in " ".join(topic_tags):
                bonus += 0.35
        scored.append((hit.score + bonus, hit))

    scored.sort(key=lambda item: (-item[0], item[1].rank, str(item[1].metadata.get("doc_id", ""))))
    reranked: list[RetrievalHit] = []
    for rank, (score, hit) in enumerate(scored, start=1):
        metadata = {**hit.metadata, "fusion_score": round(min(1.0, score), 6)}
        reranked.append(
            hit.model_copy(
                update={
                    "rank": rank,
                    "score": round(min(1.0, score), 6),
                    "metadata": metadata,
                }
            )
        )
    return reranked
