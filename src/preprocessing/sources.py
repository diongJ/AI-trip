from __future__ import annotations

import json
import re
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

from src.preprocessing.corpus import CorpusDocument, load_corpus


class WhitelistSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    domains: list[str]
    seed_urls: list[AnyHttpUrl]
    include_paths: list[str] = Field(default_factory=list)
    exclude_paths: list[str] = Field(default_factory=list)
    source_type: str = "official"
    source_tier: str = "extended"
    review_status: str = "approved"
    evidence_role: str = "factual"
    topic_tags: list[str] = Field(default_factory=list)
    follow_links: bool = False


class SourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relevance_keywords: list[str]
    sources: list[WhitelistSource]

    @classmethod
    def from_path(cls, path: str | Path) -> "SourceConfig":
        return cls.model_validate_json(Path(path).read_text(encoding="utf-8"))


class SyncReport(BaseModel):
    fetched: int = 0
    accepted: int = 0
    unchanged: int = 0
    rejected_irrelevant: int = 0
    rejected_duplicate: int = 0
    failed: int = 0
    written_doc_ids: list[str] = Field(default_factory=list)
    failures: list[dict[str, str]] = Field(default_factory=list)


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.links: list[str] = []
        self._text: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "svg", "noscript"}:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "svg", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        value = re.sub(r"\s+", " ", data).strip()
        if not value:
            return
        if self._in_title:
            self.title += value
        self._text.append(value)

    @property
    def text(self) -> str:
        return "\n".join(dict.fromkeys(self._text))


def sync_sources(
    config_path: str | Path,
    *,
    output_root: str | Path = "data/raw/extended",
    max_pages: int = 250,
    min_chars: int = 180,
    dry_run: bool = False,
    http_client: object | None = None,
) -> SyncReport:
    config = SourceConfig.from_path(config_path)
    output = Path(output_root)
    report = SyncReport()
    existing = load_corpus(output.parent) if output.parent.exists() else []
    by_url = {str(document.source_url): document for document in existing}
    existing_paths = {
        path.stem: path for path in output.parent.rglob("*.json")
    } if output.parent.exists() else {}
    hashes = {document.content_hash for document in existing}
    dedupe_hashes = {_dedupe_hash(document.text) for document in existing}
    next_id = max(
        [int(document.doc_id.split("_")[1]) for document in existing] or [99]
    ) + 1
    owns_client = http_client is None
    client = http_client or httpx.Client(
        timeout=20.0,
        follow_redirects=True,
        headers={"User-Agent": "NanyueKnowledgeBot/1.0 (educational project)"},
    )
    try:
        for source in config.sources:
            queue = deque(_normalize_url(str(url)) for url in source.seed_urls)
            queue.extend(
                url for url in by_url if _allowed(url, source) and url not in queue
            )
            visited: set[str] = set()
            with ThreadPoolExecutor(max_workers=8) as executor:
                while queue and len(visited) < max_pages:
                    batch: list[str] = []
                    while queue and len(batch) < 8 and len(visited) < max_pages:
                        url = queue.popleft()
                        if url in visited or not _allowed(url, source):
                            continue
                        visited.add(url)
                        batch.append(url)
                    futures = {
                        executor.submit(_fetch_page, client, url): url for url in batch
                    }
                    for future in as_completed(futures):
                        url = futures[future]
                        try:
                            parser = future.result()
                        except (httpx.HTTPError, UnicodeError, ValueError) as exc:
                            report.failed += 1
                            if len(report.failures) < 20:
                                report.failures.append(
                                    {"url": url, "error": f"{type(exc).__name__}: {exc}"}
                                )
                            continue
                        if parser is None:
                            continue
                        report.fetched += 1
                        if source.follow_links:
                            for href in parser.links:
                                candidate = _normalize_url(urljoin(url, href))
                                if candidate not in visited and _allowed(candidate, source):
                                    queue.append(candidate)
                        text = _clean_page_text(parser.text, parser.title)
                        collection_detail = (
                            source.name == "南越王博物院" and "/Collection/Details/" in url
                        )
                        if len(text) < (70 if collection_detail else min_chars) or not (
                            collection_detail or _is_relevant(text, config.relevance_keywords)
                        ):
                            report.rejected_irrelevant += 1
                            continue
                        digest = sha256(text.encode("utf-8")).hexdigest()
                        dedupe_digest = _dedupe_hash(text)
                        current = by_url.get(url)
                        if current and current.source_tier == "core":
                            # Core documents are the immutable evidence baseline for KG relations.
                            report.unchanged += 1
                            continue
                        if current and current.content_hash == digest:
                            report.unchanged += 1
                            continue
                        if dedupe_digest in dedupe_hashes and current is None:
                            report.rejected_duplicate += 1
                            continue
                        doc_id = current.doc_id if current else f"DOC_{next_id:03d}"
                        if current is None:
                            next_id += 1
                        document = CorpusDocument(
                            doc_id=doc_id,
                            title=_clean_title(parser.title, url, text),
                            source_name=source.name,
                            source_url=url,
                            source_type=current.source_type if current else source.source_type,
                            category=_infer_category(text),
                            retrieved_at=datetime.now(UTC).date().isoformat(),
                            text=text,
                            source_tier=current.source_tier if current else source.source_tier,
                            evidence_role=current.evidence_role if current else source.evidence_role,
                            topic_tags=_topic_tags(text, source.topic_tags),
                            content_hash=digest,
                            review_status=current.review_status if current else source.review_status,
                            version=(current.version + 1) if current else 1,
                        )
                        report.accepted += 1
                        report.written_doc_ids.append(doc_id)
                        hashes.add(document.content_hash)
                        dedupe_hashes.add(dedupe_digest)
                        if not dry_run:
                            target = existing_paths.get(doc_id) or output / document.category / f"{doc_id}.json"
                            target.parent.mkdir(parents=True, exist_ok=True)
                            target.write_text(document.model_dump_json(indent=2), encoding="utf-8")
    finally:
        if owns_client:
            client.close()
    return report


def _fetch_page(client: object, url: str) -> _PageParser | None:
    response = client.get(url)
    response.raise_for_status()
    if "text/html" not in response.headers.get("content-type", ""):
        return None
    parser = _PageParser()
    parser.feed(response.text)
    return parser


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, "", parsed.query, ""))


def _allowed(url: str, source: WhitelistSource) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or parsed.hostname not in source.domains:
        return False
    value = parsed.path + (f"?{parsed.query}" if parsed.query else "")
    if source.include_paths and not any(re.search(pattern, value) for pattern in source.include_paths):
        return False
    return not any(re.search(pattern, value) for pattern in source.exclude_paths)


def _clean_page_text(text: str, title: str = "") -> str:
    lines = [line.strip() for line in text.splitlines() if len(line.strip()) >= 2]
    footer_markers = {"官方微信", "官方微博", "粤ICP备"}
    footer_indexes = [
        index for index, line in enumerate(lines)
        if any(marker in line for marker in footer_markers)
    ]
    if footer_indexes:
        lines = lines[:min(footer_indexes)]
    boilerplate = {
        "首页", "资讯", "展览", "典藏", "教育", "视频", "关于", "返回顶部", "参观",
        "开放时间", "交通指引", "票务信息", "馆内服务", "参观须知", "院方资讯",
        "通知公告", "文博资讯", "党建工作", "财务预决算公开", "学习宣传贯彻党的二十大精神",
        "基本陈列", "临时展览", "遗址展示", "线上展厅", "明星文物", "典藏精品",
        "品牌活动", "特色活动", "服务建设", "志愿者", "短视频", "电视节目", "采访报道",
        "无障碍影像", "讲解视频", "博物院简介", "机构设置", "王宫展区", "王墓展区",
        "推荐文物", "EN", "南小越",
    }
    clean_title = re.sub(r"\s+", " ", title).strip()
    return "\n".join(
        line for line in lines
        if line not in boilerplate
        and line != clean_title
        and not re.fullmatch(r"查看（?\d+）?", line)
        and not line.startswith("网站访问量")
    )


def _is_relevant(text: str, keywords: list[str]) -> bool:
    keyword_matches = sum(1 for keyword in keywords if keyword in text)
    anchors = ("南越", "赵佗", "赵眜", "王墓", "宫署", "文帝行玺")
    anchor_mentions = sum(text.count(anchor) for anchor in anchors)
    return keyword_matches >= 2 and anchor_mentions >= 2


def _dedupe_hash(text: str) -> str:
    substantial = [line for line in text.splitlines() if len(line) >= 20]
    value = "\n".join(substantial) if substantial else text
    return sha256(value.encode("utf-8")).hexdigest()


def _clean_title(title: str, url: str, text: str = "") -> str:
    value = re.sub(r"\s+", " ", title).strip(" -_")
    generic = not value or value in {
        "南越王博物院", "南越王博物院-首页", "南越王博物院-典藏",
        "南越王博物院-展览", "南越王博物院-资讯", "南越王博物院-教育",
        "南越王博物院-关于", "南越王博物院-中文版",
    }
    if generic:
        for line in text.splitlines():
            candidate = line.strip()
            if 4 <= len(candidate) <= 80 and not candidate.startswith(("发布时间", "信息来源")):
                return candidate
    return value[:160] or urlparse(url).path.rsplit("/", 1)[-1] or "南越专题资料"


def _infer_category(text: str) -> str:
    candidates = {
        "relic": ("文物", "玉", "铜", "金印", "器"),
        "tomb": ("墓", "墓室", "墓葬"),
        "person": ("赵佗", "赵眜", "南越王"),
        "history": ("历史", "秦汉", "南越国", "制度"),
        "culture": ("文化", "交流", "海上丝绸之路", "工艺"),
        "museum": ("博物院", "展区", "遗址"),
        "exhibition": ("展览", "陈列"),
    }
    return max(candidates, key=lambda category: sum(text.count(term) for term in candidates[category]))


def _topic_tags(text: str, defaults: list[str]) -> list[str]:
    vocabulary = ["南越国", "王墓", "王宫", "考古", "文物", "工艺", "汉代", "文化交流", "海上丝绸之路"]
    return list(dict.fromkeys([*defaults, *[term for term in vocabulary if term in text]]))
