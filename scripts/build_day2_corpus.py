from __future__ import annotations

import json
import shutil
from pathlib import Path


RETRIEVED_AT = "2026-08-23"
SOURCE_NAME = "南越王博物院"


DOCUMENTS = [
    {
        "doc_id": "DOC_001",
        "title": "王墓展区介绍",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/About/Index/wmzq",
        "source_type": "official",
        "category": "museum",
        "text": "王墓展区以南越文王墓为核心，由主体陈列楼、综合陈列楼和古墓保护区三部分组成。基本陈列包括南越王墓原址和“南越藏珍——西汉南越王墓出土文物陈列”，专题陈列有“杨永德伉俪捐赠藏枕”。",
    },
    {
        "doc_id": "DOC_002",
        "title": "王墓展区参观信息",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/News/VisitIndex/Visit",
        "source_type": "official",
        "category": "museum",
        "text": "王墓展区地址为广州市越秀区解放北路867号，周二至周日9:00-17:30开放，17:00停止领票及进场。王墓展区购票进场，南越文王墓墓室下层参观票需另行预约。",
    },
    {
        "doc_id": "DOC_003",
        "title": "南越藏珍——西汉南越王墓出土文物陈列",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Exhibition/BDetails/jbcl?nid=7647",
        "source_type": "official",
        "category": "exhibition",
        "text": "“南越藏珍——西汉南越王墓出土文物陈列”以1983年发现的南越国第二代国王赵眜之墓为基础。该墓是岭南地区发现的规模最大的唯一汉代彩绘石室墓，1996年被列为全国重点文物保护单位。",
    },
    {
        "doc_id": "DOC_004",
        "title": "南越文王墓出土规模",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Exhibition/BDetails/jbcl?nid=7647",
        "source_type": "official",
        "category": "tomb",
        "text": "南越文王墓中出土文物1000多套、一万余件，其中“文帝行玺”金印、玉角杯、错金铭文虎节、印花铜板模、平板玻璃铜牌饰等文物具有重大历史、科学、艺术价值。",
    },
    {
        "doc_id": "DOC_005",
        "title": "南越文王墓墓主人身份",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Exhibition/BDetails/jbcl?nid=7647",
        "source_type": "official",
        "category": "person",
        "text": "南越王墓出土的“文帝行玺”、“帝印”、“赵眜”等玺印和史书记载，证实墓主人是南越国第二代王赵眜，自称南越文帝。",
    },
    {
        "doc_id": "DOC_006",
        "title": "南越文王墓玺印资料",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Exhibition/BDetails/jbcl?nid=7647",
        "source_type": "official",
        "category": "relic",
        "text": "南越王墓出土玺印共23枚，材质有金、铜、玉、水晶、玛瑙、绿松石和象牙等7种。这些玺印及其印文为判断墓主及殉人身份提供了直接依据，也体现南越国独特的用印制度。",
    },
    {
        "doc_id": "DOC_007",
        "title": "丝缕玉衣与珠玉敛葬",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Exhibition/BDetails/jbcl?nid=7647",
        "source_type": "official",
        "category": "culture",
        "text": "南越王身着丝缕玉衣，并以珠玉敛葬，凸显南越文帝尊贵的身份与地位。南越文王墓还发现有15个殉人，体现了南越独特的丧葬文化。",
    },
    {
        "doc_id": "DOC_008",
        "title": "南越文王墓原址",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/News/Details/djgz?nid=11319",
        "source_type": "official",
        "category": "tomb",
        "text": "南越文王墓原址为1983年发掘的南越国第二代王赵眜之墓，是岭南地区发现规模最大、随葬品最丰富、墓主人等级最高的汉代彩绘石室墓。",
    },
    {
        "doc_id": "DOC_009",
        "title": "秦汉南疆——南越国历史专题陈列",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/News/Details/yfzx?nid=8083",
        "source_type": "official",
        "category": "history",
        "text": "“秦汉南疆——南越国历史专题陈列”讲述秦朝末期赵佗为保岭南地区安定建立南越国，以及汉武帝灭南越国后岭南正式纳入汉朝郡县版图的历史过程。",
    },
    {
        "doc_id": "DOC_010",
        "title": "赵佗与南越国建立",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/News/Details/yfzx?nid=8083",
        "source_type": "official",
        "category": "person",
        "text": "南越国历史专题陈列中，“守疆营土”重点讲述秦朝末期，赵佗为保岭南地区的安定和人民的安宁建立南越国。历代南越统治者的经营推动岭南政治、经济、文化、民族融合和海外交流发展。",
    },
    {
        "doc_id": "DOC_011",
        "title": "赵婴齐与南越明王时代",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/News/Details/yfzx?nid=12447",
        "source_type": "official",
        "category": "person",
        "text": "赵婴齐为第三代南越王、南越文王赵眜之子。本展览从“南越王子”“长安为质”“南越明王”“南越鸿门宴”四个部分呈现赵婴齐及其时代。",
    },
    {
        "doc_id": "DOC_012",
        "title": "王墓展区文物特展合作公告中的王墓定位",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/News/Details/tzgg?nid=12589",
        "source_type": "official",
        "category": "tomb",
        "text": "王墓展区以南越文王墓为核心，通过墓中出土的一千余件套出土文物集中展现岭南地区政治、经济和文化的发展状况。南越文王墓被列入全国重点文物保护单位，入选“百年百大考古发现”。",
    },
    {
        "doc_id": "DOC_013",
        "title": "“文帝行玺”龙钮金印",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Collection/Details/dcjp?nid=47",
        "source_type": "official",
        "category": "relic",
        "text": "“文帝行玺”龙钮金印为西汉南越国文物，印面长3.1厘米、宽3厘米，南越文王墓出土。印面阴刻小篆“文帝行玺”四字，印钮为S形游龙，金印出土于墓主胸部，证实墓主为南越文帝。",
    },
    {
        "doc_id": "DOC_014",
        "title": "丝缕玉衣",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Collection/Details/dcjp?nid=56",
        "source_type": "official",
        "category": "relic",
        "text": "丝缕玉衣为西汉南越国文物，全长173厘米，南越文王墓出土。玉衣由2291片玉片、丝缕和麻布粘贴编缀而成，主要由头套、上身衣、袖筒、手套、裤筒和鞋套六部分组成。",
    },
    {
        "doc_id": "DOC_015",
        "title": "犀角形玉杯",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Collection/Details/dcjp?nid=97",
        "source_type": "official",
        "category": "relic",
        "text": "犀角形玉杯为西汉南越国文物，长18.4厘米、口径5.8-6.7厘米，南越文王墓出土。玉杯为青玉质、半透明，仿犀角形，中空，器身纹饰自口沿起为一立姿夔龙向后展开。",
    },
    {
        "doc_id": "DOC_016",
        "title": "铜承盘高足玉杯",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Collection/Details/dcjp?nid=98",
        "source_type": "official",
        "category": "relic",
        "text": "铜承盘高足玉杯为西汉南越国文物，通高17厘米，南越文王墓出土。全器由高足青玉杯、托架和铜承盘三部分组成，整器由金、银、玉、铜、木五种材料制成。",
    },
    {
        "doc_id": "DOC_017",
        "title": "透雕龙凤纹重环玉佩",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Collection/Details/dcjp?nid=95",
        "source_type": "official",
        "category": "relic",
        "text": "透雕龙凤纹重环玉佩为西汉南越国文物，直径10.6厘米，南越文王墓出土。玉佩出土于墓主右眼位置，内圈透雕游龙，外圈透雕凤鸟，龙凤相对。",
    },
    {
        "doc_id": "DOC_018",
        "title": "玉盒",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Collection/Details/dcjp?nid=100",
        "source_type": "official",
        "category": "relic",
        "text": "玉盒为西汉南越国文物，高7.7厘米、口径9.8厘米，南越文王墓出土。玉盒由青玉雕成，盒身深圆圜底，下附小圈足，盖中央隆起，有桥形纽。",
    },
    {
        "doc_id": "DOC_019",
        "title": "八节铁芯龙虎玉带钩",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Collection/Details/dcjp?nid=102",
        "source_type": "official",
        "category": "relic",
        "text": "八节铁芯龙虎玉带钩为西汉南越国文物，长19.5厘米，南越文王墓出土。带钩为青玉质，通体圆雕，龙虎并体形，由八节合成，当中六节有圆孔贯通，用一根铁芯串联。",
    },
    {
        "doc_id": "DOC_020",
        "title": "虎头金钩扣龙形玉佩",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Collection/Details/dcjp?nid=101",
        "source_type": "official",
        "category": "relic",
        "text": "虎头金钩扣龙形玉佩为西汉南越国文物，通长14.4厘米，南越文王墓出土。该器由青玉镂雕玉龙和金质虎头带钩组合而成，钩首和钩尾均作虎头形。",
    },
    {
        "doc_id": "DOC_021",
        "title": "圆雕玉舞人",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Collection/Details/dcjp?nid=99",
        "source_type": "official",
        "category": "relic",
        "text": "圆雕玉舞人为西汉南越国文物，高3.5厘米、宽3.5厘米，南越文王墓出土。舞者穿右衽长袖衣，扭胯并膝而跪，两面均以线刻表现衣纹，头顶端有小孔贯穿。",
    },
    {
        "doc_id": "DOC_022",
        "title": "墓主人组玉佩",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Collection/Details/?nid=103",
        "source_type": "official",
        "category": "relic",
        "text": "墓主人组玉佩为西汉南越国文物，南越文王墓出土。南越文王墓共出土组玉佩十一套，其中墓主这一套最为华丽，由双凤涡纹玉璧、龙凤涡纹玉璧、犀形玉璜等饰件组成。",
    },
    {
        "doc_id": "DOC_023",
        "title": "右夫人组玉佩（A组）",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Collection/Details/dcjp?nid=104",
        "source_type": "official",
        "category": "relic",
        "text": "右夫人组玉佩（A组）为西汉南越国文物，南越文王墓出土。墓中右夫人随葬有两套组玉佩，均出于其棺位及玺印附近；A组由20个饰件组成。",
    },
    {
        "doc_id": "DOC_024",
        "title": "右夫人组玉佩（B组）",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Collection/Details/dcjp?nid=105",
        "source_type": "official",
        "category": "relic",
        "text": "右夫人组玉佩（B组）为西汉南越国文物，南越文王墓出土。这套组玉佩由7个饰件组成，包含玉环、玉璜、玉管各2件和玉舞人1件。",
    },
    {
        "doc_id": "DOC_025",
        "title": "鎏金铜框玉盖杯",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Collection/Details/dcjp?nid=107",
        "source_type": "official",
        "category": "relic",
        "text": "鎏金铜框玉盖杯为西汉南越国文物，高16厘米，南越文王墓出土。杯体呈八棱筒形，杯身为铜铸窗棂形框架，分上下两截嵌入青玉片，盖顶镶一整块青玉。",
    },
    {
        "doc_id": "DOC_026",
        "title": "鎏金铜框玉卮",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Collection/Details/dcjp?nid=108",
        "source_type": "official",
        "category": "relic",
        "text": "鎏金铜框玉卮为西汉南越国文物，高14厘米，南越文王墓出土。卮身由九块玉片嵌在鎏金铜框上，整器呈九棱圆筒形，下附兽首形三短足。",
    },
    {
        "doc_id": "DOC_027",
        "title": "铜弩机",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Collection/Details/dcjp?nid=111",
        "source_type": "official",
        "category": "relic",
        "text": "铜弩机为西汉南越国文物，郭长14.5厘米，南越文王墓出土。弩机装有“廓”，中有“牙”用来钩弦，上有望山作为瞄准器，牙下有“悬刀”即扳机。",
    },
    {
        "doc_id": "DOC_028",
        "title": "船纹铜提筒",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Collection/Details/dcjp?nid=115",
        "source_type": "official",
        "category": "relic",
        "text": "船纹铜提筒为西汉南越国文物，高40.7厘米，南越文王墓出土。铜提筒上刻有四组船纹，描绘大型作战船队凯旋场景，反映当时岭南地区较发达的水上交通。",
    },
    {
        "doc_id": "DOC_029",
        "title": "四连体铜熏炉",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Collection/Details/?nid=116",
        "source_type": "official",
        "category": "relic",
        "text": "四连体铜熏炉为西汉南越国文物，高16.4厘米，南越文王墓出土。炉体由四个方口圜底小盒组成，平面呈“田”字形。熏炉是燃熏香料的器具。",
    },
    {
        "doc_id": "DOC_030",
        "title": "朱雀鎏金铜顶饰",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Collection/Details/dcjp?nid=117",
        "source_type": "official",
        "category": "relic",
        "text": "朱雀鎏金铜顶饰为西汉南越国文物，高26.4厘米，南越文王墓出土。此为漆木屏风构件之一，朱雀昂首展翅，伫立在方座之上。",
    },
    {
        "doc_id": "DOC_031",
        "title": "双面兽首鎏金铜顶饰",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Collection/Details/dcjp?nid=118",
        "source_type": "official",
        "category": "relic",
        "text": "双面兽首鎏金铜顶饰为西汉南越国文物，高16.7厘米、宽56.3厘米，南越文王墓出土。此为漆木屏风构件之一，正中为兽面，通体鎏金。",
    },
    {
        "doc_id": "DOC_032",
        "title": "人操蛇鎏金铜托座",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Collection/Details/dcjp?nid=120",
        "source_type": "official",
        "category": "relic",
        "text": "人操蛇鎏金铜托座为西汉南越国文物，高31.5厘米，南越文王墓出土。此为漆木屏风右下角折叠构件，跪坐力士俑口衔两头蛇，两手各操一蛇。",
    },
    {
        "doc_id": "DOC_033",
        "title": "铜釜甑",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Collection/Details/dcjp?nid=124",
        "source_type": "official",
        "category": "relic",
        "text": "铜釜甑为西汉南越国文物，南越文王墓出土。釜小口直唇、大圆腹、平底；甑为敞口、窄平沿，腹较深，圈足，甑底有箅，透气孔作图案形。",
    },
    {
        "doc_id": "DOC_034",
        "title": "铜烤炉",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Collection/Details/dcjp?nid=125",
        "source_type": "official",
        "category": "relic",
        "text": "铜烤炉为西汉南越国文物，高11厘米、长61厘米、宽52.5厘米，南越文王墓出土。烤炉平面略呈长方形，四角微翘，底设四个带轴轮的足，可以推动。",
    },
    {
        "doc_id": "DOC_035",
        "title": "错金铭文铜虎节",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Collection/Details/?nid=49",
        "source_type": "official",
        "category": "relic",
        "text": "错金铭文铜虎节为西汉南越国文物，最高11.6厘米、长19厘米，南越文王墓出土。全器铸成蹲踞状老虎，正面有错金铭文“王命命车驲”，并镶以金箔片作虎斑纹。",
    },
    {
        "doc_id": "DOC_036",
        "title": "铜印花板模",
        "source_name": SOURCE_NAME,
        "source_url": "https://www.nywmuseum.org.cn/Collection/Details/zyzb?nid=54",
        "source_type": "official",
        "category": "relic",
        "text": "铜印花板模为西汉南越国文物，南越文王墓出土。这两件印板是在丝织物上印染图案的工具，西耳室出土丝织品中发现了与印板图案相同的印花织物。",
    },
]


def write_json(path: Path, payload: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    raw_root = Path("data/raw")
    for category in [
        "tomb",
        "relic",
        "person",
        "history",
        "culture",
        "exhibition",
        "museum",
    ]:
        category_path = raw_root / category
        if category_path.exists():
            shutil.rmtree(category_path)
        category_path.mkdir(parents=True, exist_ok=True)

    rows = []
    for document in DOCUMENTS:
        payload = {**document, "retrieved_at": RETRIEVED_AT}
        path = raw_root / payload["category"] / f"{payload['doc_id']}.json"
        write_json(path, payload)
        rows.append(
            "| {doc_id} | {title} | {category} | {source_name} | {source_url} |".format(
                **payload
            )
        )

    docs_path = Path("docs/data_sources.md")
    docs_path.write_text(
        "# 数据来源\n\n"
        "| doc_id | 标题 | 类别 | 来源 | URL |\n"
        "|---|---|---|---|---|\n"
        + "\n".join(rows)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
