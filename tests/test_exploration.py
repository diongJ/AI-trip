import json
from pathlib import Path

import pytest

from app.exploration import ExplorationDataError, load_exploration_paths


def _write_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    paths = {
        "version": 1,
        "paths": [{
            "id": "seal",
            "title": "金印确认墓主",
            "intro": "沿证据核对",
            "conclusion": "证据互相印证",
            "steps": [
                {
                    "id": "one", "question": "为何？", "conclusion": "有关联", "bridge": "继续核对",
                    "source_entity": "文帝行玺", "relation": "RELATED_TO_PERSON", "target_entity": "赵眜",
                    "document_id": "DOC_001", "evidence": "金印证实墓主为赵眜", "ask_prompt": "证据是什么？",
                },
                {
                    "id": "two", "question": "葬于何处？", "conclusion": "葬于王墓", "bridge": "形成闭环",
                    "source_entity": "赵眜", "relation": "BURIED_IN", "target_entity": "南越文王墓",
                    "document_id": "DOC_001", "evidence": "赵眜葬于南越文王墓", "ask_prompt": "墓在哪里？",
                },
            ],
        }],
    }
    graph = {
        "entities": [
            {"id": "relic:seal", "name": "文帝行玺"},
            {"id": "person:zhao", "name": "赵眜"},
            {"id": "tomb:king", "name": "南越文王墓"},
        ],
        "relations": [
            {"source_id": "relic:seal", "relation": "RELATED_TO_PERSON", "target_id": "person:zhao", "document_id": "DOC_001", "evidence": "金印证实墓主为赵眜"},
            {"source_id": "person:zhao", "relation": "BURIED_IN", "target_id": "tomb:king", "document_id": "DOC_001", "evidence": "赵眜葬于南越文王墓"},
        ],
    }
    document = {
        "doc_id": "DOC_001", "title": "官方资料", "source_name": "博物院", "source_url": "https://example.com/source",
        "text": "金印证实墓主为赵眜；赵眜葬于南越文王墓", "evidence_role": "factual", "review_status": "approved",
    }
    paths_file = tmp_path / "paths.json"
    graph_file = tmp_path / "graph.json"
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    paths_file.write_text(json.dumps(paths, ensure_ascii=False), encoding="utf-8")
    graph_file.write_text(json.dumps(graph, ensure_ascii=False), encoding="utf-8")
    (raw_dir / "DOC_001.json").write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
    return paths_file, graph_file, raw_dir


def _mutate_json(path: Path, mutator) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutator(payload)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    load_exploration_paths.cache_clear()


def test_exploration_paths_are_enriched_with_labels_and_citations(tmp_path: Path):
    files = _write_fixture(tmp_path)
    payload = load_exploration_paths(*files)
    step = payload["paths"][0]["steps"][0]
    assert step["relation_label"] == "证实关联"
    assert step["citation"]["source_name"] == "博物院"


@pytest.mark.parametrize(
    "target,mutator,error",
    [
        (0, lambda data: data["paths"][0]["steps"][0].update(target_entity="未知人物"), "does not match graph evidence"),
        (0, lambda data: data["paths"][0]["steps"][0].update(relation="MADE_OF"), "does not match graph evidence"),
        (2, lambda data: data.update(evidence_role="curated_guidance"), "not approved factual evidence"),
    ],
)
def test_exploration_paths_reject_invalid_grounding(tmp_path: Path, target, mutator, error):
    files = _write_fixture(tmp_path)
    path = files[target] if target < 2 else files[2] / "DOC_001.json"
    _mutate_json(path, mutator)
    with pytest.raises(ExplorationDataError, match=error):
        load_exploration_paths(*files)


def test_exploration_paths_reject_unknown_document(tmp_path: Path):
    paths_file, graph_file, raw_dir = _write_fixture(tmp_path)
    _mutate_json(paths_file, lambda data: data["paths"][0]["steps"][0].update(document_id="DOC_999"))
    _mutate_json(graph_file, lambda data: data["relations"][0].update(document_id="DOC_999"))
    with pytest.raises(ExplorationDataError, match="unknown path document"):
        load_exploration_paths(paths_file, graph_file, raw_dir)
