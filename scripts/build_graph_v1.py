from __future__ import annotations

from pathlib import Path

from src.extraction.models import Entity, ExtractionResult, Relation


def main() -> None:
    output_path = Path("data/graph/knowledge_graph_v1.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = ExtractionResult(entities=_entities(), relations=_relations())
    output_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    print(
        f"Built local graph with {len(result.entities)} entities and "
        f"{len(result.relations)} relations: {output_path}"
    )


def _entities() -> list[Entity]:
    specs = [
        ("person:赵眜", "赵眜", "Person", ["南越文王", "南越文帝"], "DOC_005"),
        ("person:赵佗", "赵佗", "Person", [], "DOC_010"),
        ("person:赵婴齐", "赵婴齐", "Person", ["南越明王"], "DOC_011"),
        ("state:南越国", "南越国", "State", [], "DOC_009"),
        ("dynasty:西汉", "西汉", "Dynasty", [], "DOC_013"),
        ("tomb:南越文王墓", "南越文王墓", "Tomb", ["南越王墓"], "DOC_008"),
        ("tombchamber:主棺室", "主棺室", "TombChamber", [], "DOC_013"),
        ("tombchamber:西耳室", "西耳室", "TombChamber", [], "DOC_036"),
        ("relic:文帝行玺", "文帝行玺", "Relic", ["“文帝行玺”龙钮金印", "文帝行玺金印"], "DOC_013"),
        ("relic:丝缕玉衣", "丝缕玉衣", "Relic", [], "DOC_014"),
        ("relic:犀角形玉杯", "犀角形玉杯", "Relic", ["角形玉杯"], "DOC_015"),
        ("relic:铜承盘高足玉杯", "铜承盘高足玉杯", "Relic", ["承盘高足玉杯"], "DOC_016"),
        ("relic:错金铭文铜虎节", "错金铭文铜虎节", "Relic", [], "DOC_035"),
        ("relic:铜印花板模", "铜印花板模", "Relic", [], "DOC_036"),
        ("relic:船纹铜提筒", "船纹铜提筒", "Relic", [], "DOC_028"),
        ("material:金", "金", "Material", [], "DOC_013"),
        ("material:玉", "玉", "Material", ["青玉"], "DOC_014"),
        ("material:铜", "铜", "Material", [], "DOC_016"),
        ("material:丝", "丝", "Material", ["丝缕"], "DOC_014"),
        ("reliccategory:印章", "印章", "RelicCategory", ["玺印"], "DOC_006"),
        ("reliccategory:玉衣", "玉衣", "RelicCategory", [], "DOC_014"),
        ("reliccategory:玉器", "玉器", "RelicCategory", [], "DOC_015"),
        ("reliccategory:兵器", "兵器", "RelicCategory", [], "DOC_027"),
        ("culture:汉代丧葬制度", "汉代丧葬制度", "Culture", ["珠玉敛葬"], "DOC_007"),
        ("culture:南越用印制度", "南越用印制度", "Culture", ["用印制度"], "DOC_006"),
        ("culture:岭南水上交通", "岭南水上交通", "Culture", [], "DOC_028"),
        ("pattern:龙纹", "龙纹", "Pattern", ["游龙"], "DOC_013"),
        ("pattern:船纹", "船纹", "Pattern", [], "DOC_028"),
        ("exhibition:南越藏珍", "南越藏珍", "Exhibition", ["西汉南越王墓出土文物陈列"], "DOC_003"),
        ("historicalevent:南越国建立", "南越国建立", "HistoricalEvent", [], "DOC_010"),
    ]
    return [
        Entity(
            id=entity_id,
            name=name,
            type=entity_type,
            aliases=aliases,
            description="",
            source_ids=[doc_id],
            confidence=0.95,
        )
        for entity_id, name, entity_type, aliases, doc_id in specs
    ]


def _relations() -> list[Relation]:
    specs = [
        ("person:赵眜", "BELONGS_TO_STATE", "state:南越国", "DOC_005", "墓主人是南越国第二代王赵眜，自称南越文帝。"),
        ("person:赵眜", "BURIED_IN", "tomb:南越文王墓", "DOC_005", "南越王墓出土的“文帝行玺”、“帝印”、“赵眜”等玺印和史书记载，证实墓主人是南越国第二代王赵眜。"),
        ("person:赵婴齐", "BELONGS_TO_STATE", "state:南越国", "DOC_011", "赵婴齐为第三代南越王、南越文王赵眜之子。"),
        ("historicalevent:南越国建立", "INVOLVES_PERSON", "person:赵佗", "DOC_010", "赵佗为保岭南地区的安定和人民的安宁建立南越国。"),
        ("historicalevent:南越国建立", "OCCURRED_IN", "dynasty:西汉", "DOC_009", "汉武帝灭南越国后岭南正式纳入汉朝郡县版图。"),
        ("tomb:南越文王墓", "CONTAINS", "tombchamber:主棺室", "DOC_013", "“文帝行玺”金印出土于墓主胸部。"),
        ("tomb:南越文王墓", "CONTAINS", "tombchamber:西耳室", "DOC_036", "西耳室出土丝织品中发现了与印板图案相同的印花织物。"),
        ("relic:文帝行玺", "EXCAVATED_FROM", "tombchamber:主棺室", "DOC_013", "“文帝行玺”金印出土于墓主胸部。"),
        ("relic:文帝行玺", "MADE_OF", "material:金", "DOC_013", "“文帝行玺”龙钮金印为西汉南越国文物。"),
        ("relic:文帝行玺", "BELONGS_TO_CATEGORY", "reliccategory:印章", "DOC_006", "南越王墓出土玺印共23枚。"),
        ("relic:文帝行玺", "CREATED_IN", "dynasty:西汉", "DOC_013", "“文帝行玺”龙钮金印为西汉南越国文物。"),
        ("relic:文帝行玺", "RELATED_TO_PERSON", "person:赵眜", "DOC_013", "金印出土于墓主胸部，证实墓主为南越文帝。"),
        ("relic:文帝行玺", "HAS_PATTERN", "pattern:龙纹", "DOC_013", "印钮为S形游龙。"),
        ("relic:文帝行玺", "REFLECTS_CULTURE", "culture:南越用印制度", "DOC_006", "玺印及其印文为判断墓主及殉人身份提供了直接依据，也体现南越国独特的用印制度。"),
        ("relic:丝缕玉衣", "MADE_OF", "material:玉", "DOC_014", "玉衣由2291片玉片、丝缕和麻布粘贴编缀而成。"),
        ("relic:丝缕玉衣", "MADE_OF", "material:丝", "DOC_014", "玉衣由2291片玉片、丝缕和麻布粘贴编缀而成。"),
        ("relic:丝缕玉衣", "BELONGS_TO_CATEGORY", "reliccategory:玉衣", "DOC_014", "丝缕玉衣为西汉南越国文物。"),
        ("relic:丝缕玉衣", "CREATED_IN", "dynasty:西汉", "DOC_014", "丝缕玉衣为西汉南越国文物。"),
        ("relic:丝缕玉衣", "REFLECTS_CULTURE", "culture:汉代丧葬制度", "DOC_007", "南越王身着丝缕玉衣，并以珠玉敛葬，凸显南越文帝尊贵的身份与地位。"),
        ("relic:犀角形玉杯", "MADE_OF", "material:玉", "DOC_015", "玉杯为青玉质、半透明。"),
        ("relic:犀角形玉杯", "BELONGS_TO_CATEGORY", "reliccategory:玉器", "DOC_015", "犀角形玉杯为西汉南越国文物。"),
        ("relic:犀角形玉杯", "HAS_PATTERN", "pattern:龙纹", "DOC_015", "器身纹饰自口沿起为一立姿夔龙向后展开。"),
        ("relic:铜承盘高足玉杯", "MADE_OF", "material:铜", "DOC_016", "整器由金、银、玉、铜、木五种材料制成。"),
        ("relic:铜承盘高足玉杯", "MADE_OF", "material:玉", "DOC_016", "全器由高足青玉杯、托架和铜承盘三部分组成。"),
        ("relic:错金铭文铜虎节", "MADE_OF", "material:铜", "DOC_035", "错金铭文铜虎节为西汉南越国文物。"),
        ("relic:船纹铜提筒", "MADE_OF", "material:铜", "DOC_028", "船纹铜提筒为西汉南越国文物。"),
        ("relic:船纹铜提筒", "HAS_PATTERN", "pattern:船纹", "DOC_028", "铜提筒上刻有四组船纹。"),
        ("relic:船纹铜提筒", "REFLECTS_CULTURE", "culture:岭南水上交通", "DOC_028", "反映当时岭南地区较发达的水上交通。"),
        ("relic:铜印花板模", "EXCAVATED_FROM", "tombchamber:西耳室", "DOC_036", "西耳室出土丝织品中发现了与印板图案相同的印花织物。"),
        ("relic:铜印花板模", "MADE_OF", "material:铜", "DOC_036", "铜印花板模为西汉南越国文物。"),
    ]
    return [
        Relation(
            source_id=source_id,
            relation=relation,
            target_id=target_id,
            document_id=document_id,
            evidence=evidence,
            confidence=0.92,
        )
        for source_id, relation, target_id, document_id, evidence in specs
    ]


if __name__ == "__main__":
    main()
