# -*- coding: utf-8 -*-
"""游客导览资料扩充脚本（依据 docs/visitor_guidance_source_collection.md 任务书）。

生成内容：
1. data/raw/tourism/ 下新增语料文档 DOC_234 起（official 官方事实 + other 项目整理路线）。
2. docs/visitor_guidance/ 下采集表 visitor_sources.csv、结构化事实表、代表性文物表、FAQ。
3. docs/visitor_guidance/official_snapshots/ 官方页面采集快照。

所有 official 文档正文均摘自 2026-08-27 采集的南越王博物院官网页面，
curated（项目整理）文档明确标注“项目整理建议”，与官方事实分开。
"""
from __future__ import annotations

import csv
import json
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_TOURISM = ROOT / "data" / "raw" / "tourism"
OUT_DIR = ROOT / "docs" / "visitor_guidance"
SNAPSHOT_DIR = OUT_DIR / "official_snapshots"
RETRIEVED = "2026-08-27"

OFFICIAL = "official"
CURATED = "other"
CURATED_URL = "https://github.com/diongJ/AI-trip"
MUSEUM = "南越王博物院"

OFFICIAL_DOCS = [
    {
        "doc_id": "DOC_234",
        "title": "王墓展区参观指南（2026年版）",
        "source_url": "https://www.nywmuseum.org.cn/News/Details/tzgg?nid=12532",
        "published_at": None,
        "topic_tags": ["参观指南", "开放时间", "门票", "预约", "王墓展区", "交通", "行李寄存"],
        "text": (
            "王墓展区地址为广州市越秀区解放北路867号，地铁二号线越秀公园站E出口，"
            "公交越秀公园站、解放北路口站、盘福路站。开放时间为周二至周日9:00—17:30，"
            "17:00停止售票及进场；逢周一闭馆，遇国家法定假期正常开放。门票全票10元、"
            "半价票5元，门票不含南越文王墓墓室下层参观。所有观众无论购买何种票价类型，"
            "均须通过“南越王博物院”微信公众号菜单栏“王墓展区→门票讲解预约”实名制预约购票，"
            "或凭有效身份证件现场购票，凭身份证核验参观。半价票适用于全日制大学本科及以下"
            "学历学生、60周岁（含）至64周岁（含）人士，以及盲人、智力残疾人、双下肢残疾人"
            "和其他重度残疾人的1名陪护人员。免费票适用于65周岁（含）以上长者、18周岁（不含）"
            "以下未成年人、残障人士、现役军人、残疾军人、军队离退休干部、退役军人和三属、"
            "消防救援人员、无偿献血优待对象及民政部门确认的困难群体等，免费不免票，需凭相关"
            "证件线上预约或在人工窗口申领免费票。南越文王墓墓室下层参观票需另行免费预约，"
            "一人一票，可提前一天通过微信公众号“王墓展区→门票讲解预约→墓室下层参观”预约。"
            "展区提供自助行李寄存柜。咨询电话020-36182920（周二至周日9:00—17:30）。"
        ),
    },
    {
        "doc_id": "DOC_235",
        "title": "王宫展区参观指南",
        "source_url": "https://www.nywmuseum.org.cn/News/Details/tzgg?nid=12498",
        "published_at": None,
        "topic_tags": ["参观指南", "开放时间", "免费预约", "王宫展区", "交通", "出入口"],
        "text": (
            "王宫展区地址为广州市越秀区中山四路316号，地铁一、二号线公园前站F出口，"
            "公交财厅站、中山五路站。开放时间为周二至周日9:00—17:30，17:00停止进场；"
            "逢周一闭馆，遇国家法定假期正常开放。王宫展区免费预约参观，请通过“南越王博物院”"
            "官方微信公众号菜单栏“王宫展区→门票讲解预约”预约，成功预约后无需取票，中国大陆"
            "观众到闸机刷身份证入场，港澳台及海外观众刷二维码入场。参观流线为从王宫展区东门"
            "（中山四路316号，近城隍庙）进入展区，从王宫展区西门（北京路374号，近广东省财政厅）"
            "离开展区，入口与出口不同。展区提供咨询、受理投诉建议、应急医药箱、婴儿车和轮椅"
            "出借、免费行李寄存等服务。咨询电话020-83896501（周二至周日9:00—17:30）。"
        ),
    },
    {
        "doc_id": "DOC_236",
        "title": "南越文王墓墓室下层参观公告（预约限流）",
        "source_url": "https://www.nywmuseum.org.cn/News/Details/tzgg?nid=12469",
        "published_at": "2025-07-09",
        "topic_tags": ["墓室下层", "预约", "限流", "王墓展区", "古墓保护区", "讲解"],
        "text": (
            "据南越王博物院2025年7月9日公告：出于文物保护考量，南越文王墓室上、下层"
            "不再并行参观，调整为仅限上层参观；墓室下层暂时实行预约限流参观管理。墓室下层"
            "每日开放时间9:00—17:00，分时段动态管理，每小时参观人数上限50人。免费"
            "“墓室下层参观票”可提前一天在南越王博物院票务系统实名制预约，一人一票，每日"
            "00:00放票；预约成功后无需取票，凭身份证原件于墓原址区检票，严格按预约时段参观，"
            "每人墓室下层停留时间上限为20分钟。未满14周岁（含）的未成年人须在成年人陪同下"
            "参观。另有定制考古主题导赏活动，收费150元/人，时长90分钟（包含墓室下层讲解"
            "20分钟），与免费预约自行参观并行。如遇墓室原址文物维护期，下层参观暂停。"
            "咨询、投诉电话：020-36182920。"
        ),
    },
    {
        "doc_id": "DOC_237",
        "title": "南越文王墓原址展示区恢复对外开放公告",
        "source_url": "https://www.nywmuseum.org.cn/News/Details/tzgg?nid=12524",
        "published_at": "2025-12-16",
        "topic_tags": ["墓原址", "恢复开放", "王墓展区", "古墓保护区", "公告"],
        "text": (
            "据南越王博物院2025年12月16日公告：南越文王墓原址展示区域预防性保护施工"
            "已完成，2025年12月16日起墓原址展示区恢复对外开放。出于文物保护的考量，"
            "南越文王墓原址展示区分上下层，其中墓原址上层全面对外开放，下层实行预约限流参观"
            "管理，详情请参考《关于南越文王墓下层参观的公告》（2025年7月9日发布）。"
        ),
    },
    {
        "doc_id": "DOC_238",
        "title": "南越文王墓原址展示区暂停开放公告（历史记录，已恢复）",
        "source_url": "https://www.nywmuseum.org.cn/News/Details/tzgg?nid=12496",
        "published_at": "2025-09-21",
        "topic_tags": ["墓原址", "暂停开放", "历史公告", "王墓展区"],
        "text": (
            "【历史公告，已失效，仅保留变更记录】南越王博物院2025年9月21日公告：为履行"
            "文物保护职责，博物院对南越文王墓墓原址展示区域进行预防性保护施工，墓原址展示区"
            "自2025年10月9日起暂停对外开放，期间王墓展区其他区域仍正常开放。根据2025年"
            "12月16日公告，该展示区已于2025年12月16日起恢复对外开放，本条公告自此失效。"
        ),
    },
    {
        "doc_id": "DOC_239",
        "title": "王宫展区2026年暑期延长开放服务时间公告",
        "source_url": "https://www.nywmuseum.org.cn/News/Details/tzgg?nid=12596",
        "published_at": "2026-07-07",
        "topic_tags": ["暑期", "延长开放", "王宫展区", "开放时间", "临时公告"],
        "text": (
            "据南越王博物院2026年7月7日公告：2026年暑假期间（7月11日至8月31日），"
            "王宫展区延长开放服务时间，开放时间调整为9:00—18:00，17:00停止入场；"
            "王宫展区免费开放，逢周一闭馆（遇国家法定假期正常开放）。王墓展区开放时间不变，"
            "仍为9:00—17:30，17:00停止售票、入场，逢周一闭馆（遇国家法定假期正常开放）。"
            "王宫展区预约及进场均不收取任何费用，须通过“南越王博物院”官方微信公众号菜单栏"
            "“王宫展区→门票讲解预约”提前预约；预约成功后无需取票，中国大陆观众携本人有效"
            "身份证原件在预约时段内至王宫展区东门闸机刷身份证进馆，港澳台、持永居证及海外"
            "观众刷二维码检票进馆。该延时安排2026年8月31日后失效，此后恢复常规开放时间。"
        ),
    },
    {
        "doc_id": "DOC_240",
        "title": "台风“红霞”后恢复开放公告（2026年7月）",
        "source_url": "https://www.nywmuseum.org.cn/News/Details/tzgg?nid=12604",
        "published_at": "2026-07-27",
        "topic_tags": ["恢复开放", "台风", "临时公告", "闭馆"],
        "text": (
            "【一次性时效公告，已执行完毕】南越王博物院2026年7月27日公告：由于台风"
            "“红霞”影响减弱，全市台风预警信号均已解除，博物院自2026年7月28日（周二）"
            "9:00起恢复正常开放（逢周一闭馆），王墓展区、王宫展区均正常对外开放。"
            "本条说明台风等极端天气可能造成临时闭馆，出行前应查看官方公众号最新通知。"
        ),
    },
    {
        "doc_id": "DOC_241",
        "title": "规范社会人士及机构在展区内开展讲解研学活动秩序公告",
        "source_url": "https://www.nywmuseum.org.cn/News/Details/tzgg?nid=12609",
        "published_at": "2026-08-12",
        "topic_tags": ["研学", "讲解秩序", "社会机构", "申请备案", "公告"],
        "text": (
            "据南越王博物院2026年8月12日公告（自2026年9月1日起施行）：博物院在开放"
            "期间面向公众免费提供定时定点人工讲解、智慧导览、教育研学等公共服务。旅行社、"
            "教育培训机构、导游、研学讲师等社会人士及机构拟在展区内开展讲解、研学活动的，"
            "须提前3个工作日向院方提交书面申请；长期常态化开展活动的主体须每自然年更新备案；"
            "突发行程、临时组团可在现场办理临时登记并补齐材料。申请表与证明函可在博物院官网"
            "或微信公众号公告页面下载，材料发送至专用邮箱nanyuekingmuseum@126.com审核。"
            "审核通过后，申请人活动当天凭有效证件在服务台登记并换领《公共服务证》，活动期间"
            "全程佩戴。开展活动时不得在参观通道长时间停留，不得使用扩声设备、高声喧哗，不得"
            "在展区内开展售卖课程、推广产品、招揽客源等经营性活动。"
        ),
    },
    {
        "doc_id": "DOC_242",
        "title": "警惕院外无授权商铺消费风险公告",
        "source_url": "https://www.nywmuseum.org.cn/News/Details/tzgg?nid=12597",
        "published_at": "2026-07-07",
        "topic_tags": ["消费提示", "防骗", "官方渠道", "讲解", "文创"],
        "text": (
            "据南越王博物院2026年7月7日公告：场馆周边存在商铺未取得院方授权，擅自冒用"
            "博物院名义售卖文创纪念品、私自承揽付费讲解和票务代办。院方提醒：官方文创售卖、"
            "官方讲解导览、票务咨询等全部服务仅开设于展区内讲解服务中心及官方文创商店，"
            "场馆外商铺及摊位均未获授权；请勿轻信“官方独家授权”“限定内部文创”“馆内持证讲解”"
            "等宣传，不要在非官方渠道选购商品、预约服务。如遇虚假营销、消费骗局，请保存证据"
            "并拨打12315或110维权。"
        ),
    },
    {
        "doc_id": "DOC_243",
        "title": "馆内便民服务（行李寄存、租借、医药箱）",
        "source_url": "https://www.nywmuseum.org.cn/News/VisitIndex/Visit-0",
        "published_at": None,
        "topic_tags": ["便民服务", "行李寄存", "租借服务", "医药箱", "充电宝"],
        "text": (
            "南越王博物院馆内便民服务包括：行李寄存方面，王宫展区提供免费行李寄存服务，"
            "王墓展区提供自助行李寄存柜。服务台提供咨询、受理投诉处理和应急医药箱。租借服务"
            "提供老花镜、助听器、婴儿车、拐杖、轮椅和盲文简介。据博物院服务建设介绍，还提供"
            "充电宝租借、披肩出借和免费自助讲解器（含普通话、粤语、英语、日语、德语、西班牙语、"
            "韩语等多语种语音导览）、导览机等便民装置。以上服务内容以展区服务台当日提供为准。"
        ),
    },
    {
        "doc_id": "DOC_244",
        "title": "无障碍与爱心服务（手语导赏、轮椅租借、爱心预约）",
        "source_url": "https://www.nywmuseum.org.cn/News/Details/fwjs",
        "published_at": "2022-09-07",
        "topic_tags": ["无障碍", "手语导赏", "轮椅", "爱心服务", "婴儿车", "盲文"],
        "text": (
            "南越王博物院无障碍服务包括：需要无障碍服务的观众可提前2天电话预约入展区当日的"
            "爱心服务；租借服务提供轮椅、助听器、老花镜、拐杖、婴儿车和盲文简介；手语导赏需"
            "提前7个工作日扫码预约。据博物院服务建设介绍，展区内多处设有无障碍坡道，提供轮椅、"
            "助听器、手电筒及盲文导览手册，播出手语版宣传视频；博物院与广州导盲犬学校合作，"
            "成为导盲犬社会化训练场馆，并在展厅设有“追光主播讲解”二维码，扫码可收听无障碍"
            "讲解。无障碍设施覆盖情况以各展区现场为准。"
        ),
    },
    {
        "doc_id": "DOC_245",
        "title": "讲解与导览服务（免费定时讲解、收费讲解、语音导览）",
        "source_url": "https://www.nywmuseum.org.cn/News/VisitIndex/Visit-0",
        "published_at": None,
        "topic_tags": ["讲解服务", "语音导览", "定时讲解", "收费讲解", "多语种"],
        "text": (
            "南越王博物院讲解与导览服务包括：免费定时定点讲解服务，王墓展区每天9:30、王宫"
            "展区每天9:30各一场，限20人，额满即止，详询服务台；线上语音导览服务；免费自助"
            "讲解器含普通话、粤语、英语、日语、德语、西班牙语、韩语等多语种语音导览。收费人工"
            "讲解方面，王墓展区可于综合陈列楼一楼“收费讲解服务台”购买讲解服务产品，王宫展区"
            "可于南越宫苑馆一楼“收费讲解服务台”购买。南越文王墓墓室下层定制考古主题导赏"
            "150元/人，时长90分钟（含墓室下层讲解20分钟）。此外，讲解员于每天（除周一闭馆日外）"
            "15:00在哔哩哔哩“南越王博物院”官方账号开展线上直播讲解。收费、时间和名额可能调整，"
            "以现场公告为准。"
        ),
    },
    {
        "doc_id": "DOC_246",
        "title": "参观须知（全员实名预约制）",
        "source_url": "https://www.nywmuseum.org.cn/News/VisitIndex/Visit-0",
        "published_at": None,
        "topic_tags": ["参观须知", "实名预约", "入馆流程", "咨询投诉"],
        "text": (
            "南越王博物院实行全员预约参观制度：观众须关注微信服务号“南越王博物院”，点击"
            "“王墓展区”或“王宫展区”—“门票预约”进行实名制预约；预约成功后须按所预约的参观"
            "时段到达，非预约时段到达会给入场带来不便；到达后请配合现场工作人员指引，验票后"
            "有序进入展区。如有疑问可致电020-36182920（王墓展区）、020-83896501（王宫展区）。"
        ),
    },
    {
        "doc_id": "DOC_247",
        "title": "两展区地址与交通指引",
        "source_url": "https://www.nywmuseum.org.cn/News/VisitIndex/Visit-0",
        "published_at": None,
        "topic_tags": ["交通", "地址", "地铁", "公交", "出入口"],
        "text": (
            "南越王博物院由王墓展区和王宫展区组成，两展区不在同一地址，需分别前往。王宫展区"
            "地址为广州市越秀区中山四路316号，地铁一、二号线公园前站F出口，公交财厅站、"
            "中山五路站；入口为东门（近城隍庙），出口为西门（北京路374号，近广东省财政厅）。"
            "王墓展区地址为广州市越秀区解放北路867号，地铁二号线越秀公园站E出口，公交越秀公园站、"
            "解放北路口站、盘福路站。两展区之间可搭乘地铁二号线（越秀公园站—公园前站）往来。"
            "实时路况、打车价格和停车信息不属于馆内静态资料，请以导航软件实时信息为准。"
        ),
    },
    {
        "doc_id": "DOC_248",
        "title": "王墓展区空间构成与展览分布",
        "source_url": "https://www.nywmuseum.org.cn/About/Index/wmzq",
        "published_at": None,
        "topic_tags": ["空间分布", "主体陈列楼", "综合陈列楼", "古墓保护区", "展厅"],
        "text": (
            "王墓展区以南越文王墓为核心，由主体陈列楼、综合陈列楼和古墓保护区三部分组成。"
            "基本陈列包括南越王墓原址和“南越藏珍——西汉南越王墓出土文物陈列”，专题陈列有"
            "“杨永德伉俪捐赠藏枕专题陈列”。据馆方假期开放指南公布的展览地点：南越藏珍陈列"
            "位于主体陈列楼；杨永德伉俪捐赠藏枕专题陈列位于综合陈列楼二楼；临时展览位于综合"
            "陈列楼三楼临展厅；收费讲解服务台位于综合陈列楼一楼。古墓保护区内的南越文王墓"
            "原址分上下层，上层全面对外开放，下层实行预约限流参观。"
        ),
    },
    {
        "doc_id": "DOC_249",
        "title": "王宫展区空间构成与展览分布",
        "source_url": "https://www.nywmuseum.org.cn/About/Index/wgzq",
        "published_at": None,
        "topic_tags": ["空间分布", "王宫展区", "南越国宫署遗址", "陈列楼", "南越宫苑馆"],
        "text": (
            "王宫展区依托南越国宫署遗址，其中南越国时期的大型石构水池在岭南地区尚属首见，"
            "曲流石渠遗迹是迄今为止发现的年代最早、保存较为完好的秦汉王家宫苑实例，二者分别"
            "被评为1995年、1997年全国十大考古新发现之一。遗址于1996年被列为全国重点文物"
            "保护单位。据馆方假期开放指南公布的展览地点：基本陈列“岭南两千年中心地”位于陈列楼，"
            "陈列楼一楼设有南越工坊教育活动空间；南越宫苑馆二楼设临展厅，一楼设收费讲解服务台；"
            "南越宫苑二楼设有室外展示休闲区。展区入口为东门（中山四路316号，近城隍庙），出口"
            "为西门（北京路374号，近广东省财政厅）。"
        ),
    },
    {
        "doc_id": "DOC_250",
        "title": "南越藏珍陈列单元结构与官方重点文物表述",
        "source_url": "https://www.nywmuseum.org.cn/Exhibition/BDetails/jbcl?nid=7647",
        "published_at": None,
        "topic_tags": ["南越藏珍", "展览单元", "重点文物", "基本陈列", "主体陈列楼"],
        "text": (
            "“南越藏珍——西汉南越王墓出土文物陈列”位于王墓展区主体陈列楼，展出1983年发现的"
            "南越国第二代国王赵眜墓出土文物。该墓是岭南地区所发现的规模最大的唯一汉代彩绘石室墓，"
            "1996年被列为全国重点文物保护单位，出土文物1000多套、一万余件。陈列分为“南越文帝”"
            "“美玉大观”“兵器车马”“海路扬帆”“生活器具”“宫廷宴乐”六个单元。馆方明确表述："
            "“文帝行玺”金印、玉角杯、错金铭文虎节、印花铜板模、平板玻璃铜牌饰等文物具有重大"
            "历史、科学、艺术价值。墓中出土“文帝行玺”“帝印”“赵眜”等玺印共23枚，材质有金、铜、"
            "玉、水晶、玛瑙、绿松石和象牙等7种，为判断墓主及殉人身份提供直接依据。"
        ),
    },
]


CURATED_DOCS = [
    {
        "doc_id": "DOC_251",
        "title": "第一次参观王墓展区路线（项目整理）",
        "topic_tags": ["路线", "第一次参观", "王墓展区", "项目整理建议"],
        "text": (
            "【项目整理建议，非馆方官方路线】第一次参观王墓展区，建议预留约2小时，按"
            "“先墓葬、后文物”的顺序：起点为展区入口，第一站古墓保护区南越文王墓原址上层"
            "（约30分钟，全面开放；如下墓室下层需提前一天免费预约，限20分钟），建立对墓葬"
            "结构和墓主赵眜的整体认识；第二站主体陈列楼“南越藏珍”陈列（约60分钟），按"
            "“南越文帝→美玉大观→兵器车马→海路扬帆→生活器具→宫廷宴乐”单元顺序观看，"
            "重点停留文帝行玺、丝缕玉衣、角形玉杯、错金铭文铜虎节、船纹铜提筒；如赶上9:30"
            "免费定时讲解（限20人，额满即止）可先到服务台登记。结束可于综合陈列楼一楼服务台"
            "咨询。官方依据：王墓展区参观指南、墓室下层参观公告、南越藏珍陈列介绍。"
        ),
    },
    {
        "doc_id": "DOC_252",
        "title": "30分钟精华路线（项目整理）",
        "topic_tags": ["路线", "30分钟", "精华", "项目整理建议"],
        "text": (
            "【项目整理建议，非馆方官方路线】只有30分钟时，建议放弃墓原址，直奔主体陈列楼"
            "“南越藏珍”陈列，只看三件官方明确点名具有重大价值的文物：文帝行玺金印（约8分钟，"
            "南越文帝单元，确认墓主身份的关键证据）、丝缕玉衣（约8分钟，南越文帝单元，我国目前"
            "发现唯一一套形制完备的丝缕玉衣）、角形玉杯（约8分钟，美玉大观单元），剩余时间快速"
            "浏览错金铭文铜虎节。注意17:00停止售票及进场，请至少在停止入场前40分钟到馆。"
            "官方依据：南越藏珍陈列介绍中馆方点名的重点文物表述、王墓展区参观指南。"
        ),
    },
    {
        "doc_id": "DOC_253",
        "title": "1小时重点路线（项目整理）",
        "topic_tags": ["路线", "一小时", "重点文物", "项目整理建议"],
        "text": (
            "【项目整理建议，非馆方官方路线】1小时参观建议：主体陈列楼“南越藏珍”陈列为主。"
            "前40分钟按“南越文帝→美玉大观”顺序观看文帝行玺、帝印与赵眜印等玺印、丝缕玉衣、"
            "角形玉杯、透雕龙凤纹重环玉佩、铜承盘高足玉杯；后20分钟快速经过海路扬帆单元看"
            "船纹铜提筒，并浏览兵器车马单元的错金铭文铜虎节。若9:30到馆可先参加免费定时讲解"
            "（限20人）。官方依据：南越藏珍陈列介绍、讲解服务说明、王墓展区参观指南。"
        ),
    },
    {
        "doc_id": "DOC_254",
        "title": "2小时深度路线（项目整理）",
        "topic_tags": ["路线", "两小时", "深度", "项目整理建议"],
        "text": (
            "【项目整理建议，非馆方官方路线】2小时深度参观：第一站古墓保护区墓原址上层"
            "（约30分钟）；第二站主体陈列楼“南越藏珍”陈列完整走一遍六个单元（约70分钟），"
            "重点文物各停留3—5分钟；第三站综合陈列楼二楼“杨永德伉俪捐赠藏枕专题陈列”"
            "（约20分钟）。已提前一天预约墓室下层参观票的观众，按预约时段前往墓原址区检票，"
            "墓室下层停留上限20分钟，需相应压缩藏枕陈列时间。官方依据：王墓展区空间构成、"
            "墓室下层参观公告、假期开放指南中的展览地点信息。"
        ),
    },
    {
        "doc_id": "DOC_255",
        "title": "半日王墓展区路线（项目整理）",
        "topic_tags": ["路线", "半日", "王墓展区", "项目整理建议"],
        "text": (
            "【项目整理建议，非馆方官方路线】半日（约3.5—4小时）安排：9:00开馆即入场，"
            "先到服务台确认9:30免费定时讲解名额（限20人，额满即止）；跟随讲解或按墓原址上层"
            "→主体陈列楼“南越藏珍”→综合陈列楼二楼藏枕专题陈列→三楼临展厅的顺序参观，"
            "中午前结束。已预约墓室下层的观众按预约时段插入墓原址区参观（限20分钟）。如对考古"
            "发掘细节感兴趣，可在综合陈列楼一楼收费讲解服务台咨询收费人工讲解或150元/人的"
            "定制考古主题导赏（90分钟，含墓室下层讲解20分钟）。官方依据：墓室下层参观公告、"
            "讲解服务说明、王墓展区参观指南。"
        ),
    },
    {
        "doc_id": "DOC_256",
        "title": "王墓、王宫两展区联动路线（项目整理）",
        "topic_tags": ["路线", "两展区", "联动", "王宫展区", "项目整理建议"],
        "text": (
            "【项目整理建议，非馆方官方路线】两展区联动建议安排一整天：上午王墓展区"
            "（解放北路867号，需购门票10元并实名预约），按墓原址上层→南越藏珍→藏枕专题陈列"
            "顺序参观约3小时；下午乘地铁二号线从越秀公园站到公园前站，步行至王宫展区"
            "（中山四路316号，免费但须预约，东门进、西门出），参观南越国宫署遗址、陈列楼"
            "“岭南两千年中心地”约2小时，从西门出可顺路逛北京路。注意两展区均需分别预约，"
            "王宫展区刷身份证或二维码直接入场。官方依据：两展区参观指南、王宫展区介绍。"
        ),
    },
    {
        "doc_id": "DOC_257",
        "title": "亲子观察路线（项目整理）",
        "topic_tags": ["路线", "亲子", "儿童", "观察任务", "项目整理建议"],
        "text": (
            "【项目整理建议，非馆方官方路线】亲子参观建议控制在1.5—2小时，以“找一找”"
            "观察任务组织：在主体陈列楼找一找金印上的龙钮（文帝行玺）、玉衣上的玉片和丝线"
            "（丝缕玉衣）、像犀牛角的杯子（角形玉杯）、老虎形状的凭证（错金铭文铜虎节）、"
            "刻有船的大铜筒（船纹铜提筒）。未满18周岁观众免票但需凭证预约领票；婴儿车可在"
            "服务台租借；未满14周岁（含）儿童进入墓室下层须成人陪同。建议避开孩子疲劳时段，"
            "中途在休息区调整。官方依据：王墓展区参观指南票务细则、墓室下层参观公告、"
            "便民服务介绍。"
        ),
    },
    {
        "doc_id": "DOC_258",
        "title": "学生研学证据链路线（项目整理）",
        "topic_tags": ["路线", "研学", "学生", "证据链", "项目整理建议"],
        "text": (
            "【项目整理建议，非馆方官方路线】学生研学可围绕“如何证明墓主是赵眜”组织证据链："
            "第一站墓原址上层观察石室墓结构（墓葬形制证据）；第二站南越文帝单元观察“文帝行玺”"
            "金印、“帝印”“赵眜”等玺印（文字与印章证据，墓中玺印共23枚、7种材质）；第三站"
            "观察丝缕玉衣与珠玉敛葬（丧葬制度证据）；最后结合史书记载得出结论。全日制大学本科"
            "及以下学历学生可购5元半价票。注意：自2026年9月1日起，机构组织研学讲解活动须提前"
            "3个工作日向院方书面申请备案，个人参观者不受影响。官方依据：南越藏珍陈列介绍、"
            "票务细则、规范讲解研学活动秩序公告。"
        ),
    },
    {
        "doc_id": "DOC_259",
        "title": "老人与少走路路线（项目整理）",
        "topic_tags": ["路线", "老人", "少走路", "项目整理建议"],
        "text": (
            "【项目整理建议，非馆方官方路线】老年游客建议：65周岁（含）以上长者免费不免票，"
            "需凭证件线上预约或在人工窗口申领免费票；路线以主体陈列楼“南越藏珍”陈列为主，"
            "重点看南越文帝、美玉大观两个单元（约60分钟），视体力决定是否前往墓原址和综合"
            "陈列楼；服务台可租借轮椅、拐杖和老花镜；建议9:30到馆跟随免费定时讲解，减少自行"
            "阅读展签的负担；避开节假日高峰。官方依据：王墓展区参观指南票务细则、便民服务"
            "介绍、讲解服务说明。"
        ),
    },
    {
        "doc_id": "DOC_260",
        "title": "无障碍参观路线（项目整理）",
        "topic_tags": ["路线", "无障碍", "轮椅", "爱心服务", "项目整理建议"],
        "text": (
            "【项目整理建议，非馆方官方路线】行动不便观众建议：提前2天电话预约入展区当日的"
            "爱心服务（王墓展区020-36182920，王宫展区020-83896501）；服务台可租借轮椅、"
            "助听器，展区内多处设有无障碍坡道；盲人、智力残疾人、双下肢残疾人和其他重度残疾人"
            "的1名陪护人员可购半价票，残障人士本人免费；视障观众可索取盲文简介、扫码收听"
            "“追光主播讲解”，听障观众可提前7个工作日扫码预约手语导赏。路线以主体陈列楼为主，"
            "墓原址及墓室下层的轮椅可达性未获官方明确说明，建议预约时向服务台电话确认。"
            "官方依据：无障碍与爱心服务资料、票务细则。"
        ),
    },
    {
        "doc_id": "DOC_261",
        "title": "雨天室内优先路线（项目整理）",
        "topic_tags": ["路线", "雨天", "室内", "项目整理建议"],
        "text": (
            "【项目整理建议，非馆方官方路线】雨天建议以室内陈列为主：优先主体陈列楼"
            "“南越藏珍”陈列（全程室内，约70—90分钟），再看综合陈列楼二楼藏枕专题陈列和三楼"
            "临展厅；墓原址位于古墓保护区，需短距离室外通行，雨势大时可跳过或缩短停留；"
            "王墓展区提供自助行李寄存柜，可先寄存雨具和背包轻装参观。台风等极端天气可能造成"
            "临时闭馆，出行前请查看官方公众号最新通知。官方依据：王墓展区空间构成、便民服务"
            "介绍、台风恢复开放公告所反映的临时闭馆机制。"
        ),
    },
    {
        "doc_id": "DOC_262",
        "title": "四条主题参观路线（项目整理）",
        "topic_tags": ["路线", "主题", "墓主身份", "丧葬观念", "工艺", "海上交流", "项目整理建议"],
        "text": (
            "【项目整理建议，非馆方官方路线】四条主题路线均以主体陈列楼“南越藏珍”六个单元"
            "为基础组织。墓主身份线：墓原址→南越文帝单元，重点看文帝行玺、帝印、赵眜印等玺印。"
            "丧葬观念线：南越文帝单元，重点看丝缕玉衣、珠玉敛葬与组玉佩，了解玉衣敛葬与殉人"
            "制度。工艺技术线：美玉大观、生活器具、宫廷宴乐单元，重点看角形玉杯、透雕龙凤纹"
            "重环玉佩、八节铁芯龙虎玉带钩、铜烤炉与印花铜板模。海上交流线：海路扬帆单元，"
            "重点看船纹铜提筒，并联想平板玻璃铜牌饰等域外因素器物；时间充裕可延伸参观王宫"
            "展区，了解海上丝绸之路形成发展的遗址见证。官方依据：南越藏珍陈列介绍、王宫展区"
            "介绍。"
        ),
    },
]


# ---------------------------------------------------------------------------
# 采集表扩展字段（按任务书第5节模板，CorpusDocument 尚未包含的字段记录在采集表）
# doc_id -> dict(zone, floor, visitor_types, recommended_duration, evidence_role,
#                effective_from, effective_until, volatility)
META = {
    "DOC_234": dict(zone="王墓展区", floor=None, visitor_types=["first_time", "family", "senior", "student"],
                    recommended_duration=None, evidence_role="factual", effective_from=None,
                    effective_until=None, volatility="monthly_check"),
    "DOC_235": dict(zone="王宫展区", floor=None, visitor_types=["first_time", "family", "senior", "student"],
                    recommended_duration=None, evidence_role="factual", effective_from=None,
                    effective_until=None, volatility="monthly_check"),
    "DOC_236": dict(zone="王墓展区", floor=None, visitor_types=["first_time", "student"],
                    recommended_duration=20, evidence_role="factual", effective_from="2025-07-09",
                    effective_until=None, volatility="monthly_check"),
    "DOC_237": dict(zone="王墓展区", floor=None, visitor_types=["first_time"],
                    recommended_duration=None, evidence_role="factual", effective_from="2025-12-16",
                    effective_until=None, volatility="stable"),
    "DOC_238": dict(zone="王墓展区", floor=None, visitor_types=[],
                    recommended_duration=None, evidence_role="factual", effective_from="2025-10-09",
                    effective_until="2025-12-16", volatility="expired"),
    "DOC_239": dict(zone="王宫展区", floor=None, visitor_types=["family", "student"],
                    recommended_duration=None, evidence_role="factual", effective_from="2026-07-11",
                    effective_until="2026-08-31", volatility="weekly_check"),
    "DOC_240": dict(zone="两展区", floor=None, visitor_types=[],
                    recommended_duration=None, evidence_role="factual", effective_from="2026-07-28",
                    effective_until="2026-07-28", volatility="expired"),
    "DOC_241": dict(zone="两展区", floor=None, visitor_types=["student", "group"],
                    recommended_duration=None, evidence_role="factual", effective_from="2026-09-01",
                    effective_until=None, volatility="stable"),
    "DOC_242": dict(zone="两展区", floor=None, visitor_types=["first_time"],
                    recommended_duration=None, evidence_role="factual", effective_from="2026-07-07",
                    effective_until=None, volatility="stable"),
    "DOC_243": dict(zone="两展区", floor=None, visitor_types=["family", "senior", "disabled"],
                    recommended_duration=None, evidence_role="factual", effective_from=None,
                    effective_until=None, volatility="monthly_check"),
    "DOC_244": dict(zone="两展区", floor=None, visitor_types=["disabled", "senior"],
                    recommended_duration=None, evidence_role="factual", effective_from=None,
                    effective_until=None, volatility="monthly_check"),
    "DOC_245": dict(zone="两展区", floor=None, visitor_types=["first_time", "foreign"],
                    recommended_duration=None, evidence_role="factual", effective_from=None,
                    effective_until=None, volatility="monthly_check"),
    "DOC_246": dict(zone="两展区", floor=None, visitor_types=["first_time"],
                    recommended_duration=None, evidence_role="factual", effective_from=None,
                    effective_until=None, volatility="monthly_check"),
    "DOC_247": dict(zone="两展区", floor=None, visitor_types=["first_time"],
                    recommended_duration=None, evidence_role="factual", effective_from=None,
                    effective_until=None, volatility="quarterly_check"),
    "DOC_248": dict(zone="王墓展区", floor=None, visitor_types=["first_time"],
                    recommended_duration=None, evidence_role="factual", effective_from=None,
                    effective_until=None, volatility="quarterly_check"),
    "DOC_249": dict(zone="王宫展区", floor=None, visitor_types=["first_time"],
                    recommended_duration=None, evidence_role="factual", effective_from=None,
                    effective_until=None, volatility="quarterly_check"),
    "DOC_250": dict(zone="王墓展区", floor=None, visitor_types=["first_time", "student"],
                    recommended_duration=None, evidence_role="factual", effective_from=None,
                    effective_until=None, volatility="quarterly_check"),
}
for _n, _doc in enumerate(CURATED_DOCS):
    META[_doc["doc_id"]] = dict(
        zone="王墓展区" if _doc["doc_id"] != "DOC_256" else "两展区",
        floor=None, visitor_types=[], recommended_duration=None,
        evidence_role="curated_guidance", effective_from=None,
        effective_until=None, volatility="review_on_official_change",
    )

# ---------------------------------------------------------------------------
# 结构化事实表：展区 → 建筑 → 楼层 → 展厅/展览单元 → 文物/服务设施
SPACE_FACTS = [
    # zone, building, floor, space, type, content, source, confidence, notes
    ("王墓展区", "主体陈列楼", "", "南越藏珍——西汉南越王墓出土文物陈列", "基本陈列",
     "展出南越文王墓出土文物1000多套、一万余件", "DOC_248/DOC_250", "官方", "展览地点见馆方假期开放指南"),
    ("王墓展区", "主体陈列楼", "", "南越文帝（单元）", "展览单元",
     "文帝行玺金印、帝印、赵眜印等玺印；丝缕玉衣与珠玉敛葬", "DOC_250", "官方+项目推断", "单元归属依陈列介绍上下文推断，待导览图核实"),
    ("王墓展区", "主体陈列楼", "", "美玉大观（单元）", "展览单元",
     "角形玉杯、透雕龙凤纹重环玉佩、组玉佩等玉器", "DOC_250", "项目推断", "待官方导览图核实"),
    ("王墓展区", "主体陈列楼", "", "兵器车马（单元）", "展览单元", "铜弩机、错金铭文铜虎节等", "DOC_250", "项目推断", "待官方导览图核实"),
    ("王墓展区", "主体陈列楼", "", "海路扬帆（单元）", "展览单元", "船纹铜提筒等", "DOC_250", "项目推断", "待官方导览图核实"),
    ("王墓展区", "主体陈列楼", "", "生活器具（单元）", "展览单元", "铜釜甑、铜烤炉等", "DOC_250", "项目推断", "待官方导览图核实"),
    ("王墓展区", "主体陈列楼", "", "宫廷宴乐（单元）", "展览单元", "宴乐相关器物", "DOC_250", "项目推断", "待官方导览图核实"),
    ("王墓展区", "综合陈列楼", "1F", "收费讲解服务台", "服务设施", "购买收费人工讲解、墓室下层导赏", "DOC_245", "官方", ""),
    ("王墓展区", "综合陈列楼", "2F", "杨永德伉俪捐赠藏枕专题陈列", "专题陈列", "藏枕专题陈列", "DOC_248", "官方", ""),
    ("王墓展区", "综合陈列楼", "3F", "临展厅", "临时展览", "临展举办场地（如“尼罗河的赠礼”展曾设于此）", "DOC_248", "官方", ""),
    ("王墓展区", "古墓保护区", "上层", "南越文王墓原址上层", "遗址展示", "全面对外开放", "DOC_237/DOC_248", "官方", ""),
    ("王墓展区", "古墓保护区", "下层", "南越文王墓墓室下层", "遗址展示",
     "预约限流参观：每小时上限50人、每人停留上限20分钟、提前一天00:00放票、14周岁（含）以下须成人陪同",
     "DOC_236", "官方", "维护期暂停"),
    ("王墓展区", "（展区内）", "", "自助行李寄存柜", "服务设施", "自助寄存", "DOC_234", "官方", "具体位置未注明"),
    ("王墓展区", "（展区内）", "", "服务台", "服务设施", "咨询、投诉、医药箱、租借（老花镜/助听器/婴儿车/拐杖/轮椅/盲文简介）",
     "DOC_243", "官方", ""),
    ("王宫展区", "（遗址区）", "", "南越国宫署遗址", "遗址展示", "大型石构水池、曲流石渠（1995/1997全国十大考古新发现）", "DOC_249", "官方", ""),
    ("王宫展区", "陈列楼", "", "岭南两千年中心地", "基本陈列", "广州两千年城市史主题陈列", "DOC_249", "官方", ""),
    ("王宫展区", "陈列楼", "1F", "南越工坊", "教育活动空间", "手工活动场地", "DOC_249", "官方", ""),
    ("王宫展区", "南越宫苑馆", "1F", "收费讲解服务台", "服务设施", "购买收费人工讲解", "DOC_245", "官方", ""),
    ("王宫展区", "南越宫苑馆", "2F", "临展厅", "临时展览", "临展举办场地", "DOC_249", "官方", ""),
    ("王宫展区", "南越宫苑", "2F室外", "室外展示休闲区", "展示休闲区", "户外展示与休息", "DOC_249", "官方", ""),
    ("王宫展区", "（展区内）", "", "免费行李寄存", "服务设施", "免费寄存行李", "DOC_235", "官方", ""),
    ("王宫展区", "东门", "", "入口", "出入口", "中山四路316号，近城隍庙", "DOC_235", "官方", ""),
    ("王宫展区", "西门", "", "出口", "出入口", "北京路374号，近广东省财政厅", "DOC_235", "官方", ""),
]

# ---------------------------------------------------------------------------
# 代表性文物表
# name, aliases, zone, building, floor, unit, unit_confidence, official_reason,
# core_questions, minutes, visitor_types, related, source
RELICS = [
    ("“文帝行玺”龙钮金印", "文帝行玺金印", "王墓展区", "主体陈列楼", "", "南越文帝", "推断",
     "馆方明确表述其具有重大历史、科学、艺术价值；为判断墓主身份提供直接依据",
     "墓主是谁？金印证明什么？", 5, "first_time,student,history",
     "帝印、赵眜印、丝缕玉衣", "DOC_013/DOC_250"),
    ("丝缕玉衣", "玉衣", "王墓展区", "主体陈列楼", "", "南越文帝", "推断",
     "我国目前发现唯一一套形制完备的丝缕玉衣，凸显南越文帝身份地位",
     "玉衣怎么做的？为什么用玉衣下葬？", 6, "first_time,family,craft",
     "墓主人组玉佩、右夫人组玉佩", "DOC_014/DOC_250"),
    ("角形玉杯（犀角形玉杯）", "玉角杯", "王墓展区", "主体陈列楼", "", "美玉大观", "推断",
     "馆方明确表述玉角杯具有重大历史、科学、艺术价值",
     "杯子为什么是角形？玉料从哪来？", 4, "first_time,craft",
     "铜承盘高足玉杯、玉盒", "DOC_015/DOC_250"),
    ("船纹铜提筒", "铜提筒", "王墓展区", "主体陈列楼", "", "海路扬帆", "推断",
     "筒身船纹反映岭南水上交通与海上交流，是海丝关联的重要物证",
     "船纹画了什么？说明什么？", 4, "student,history",
     "平板玻璃铜牌饰", "DOC_028/DOC_250"),
    ("错金铭文铜虎节", "铜虎节、虎节", "王墓展区", "主体陈列楼", "", "兵器车马", "推断",
     "馆方明确表述错金铭文虎节具有重大历史、科学、艺术价值",
     "虎节是干什么用的？铭文写了什么？", 4, "first_time,craft",
     "铜弩机", "DOC_035/DOC_250"),
    ("铜印花板模", "印花铜板模", "王墓展区", "主体陈列楼", "", "待核实", "待核实",
     "馆方明确表述印花铜板模具有重大历史、科学、艺术价值",
     "古代怎么批量印花？", 3, "craft,study",
     "铜虎节", "DOC_036/DOC_250"),
    ("平板玻璃铜牌饰", "玻璃牌饰", "王墓展区", "主体陈列楼", "", "待核实", "待核实",
     "馆方明确表述平板玻璃铜牌饰具有重大历史、科学、艺术价值",
     "汉代哪来的玻璃？和海外贸易有关吗？", 3, "student,history",
     "船纹铜提筒", "DOC_197/DOC_250"),
    ("“赵眜”玉印等墓主印章组合", "帝印、赵眜印", "王墓展区", "主体陈列楼", "", "南越文帝", "推断",
     "出土玺印共23枚、7种材质，为判断墓主及殉人身份提供直接依据",
     "靠哪几枚印章确认墓主？", 4, "student,history",
     "文帝行玺", "DOC_203/DOC_250"),
    ("墓主人组玉佩", "组玉佩", "王墓展区", "主体陈列楼", "", "美玉大观", "推断",
     "墓主生前佩挂的大型玉佩组合，反映礼制与工艺",
     "组玉佩由哪些件组成？怎么佩戴？", 4, "craft,family",
     "右夫人组玉佩、透雕龙凤纹重环玉佩", "DOC_022/DOC_250"),
    ("透雕龙凤纹重环玉佩", "龙凤纹玉佩", "王墓展区", "主体陈列楼", "", "美玉大观", "推断",
     "院方典藏精品页重点推介的玉器代表作",
     "透雕工艺难在哪？", 3, "craft",
     "墓主人组玉佩、圆雕玉舞人", "DOC_017/DOC_250"),
    ("铜承盘高足玉杯", "承盘高足玉杯", "王墓展区", "主体陈列楼", "", "美玉大观", "推断",
     "金玉铜多材质复合器物，工艺价值高",
     "这件器物由几种材料组成？", 3, "craft",
     "角形玉杯、鎏金铜框玉盖杯", "DOC_016/DOC_250"),
    ("圆雕玉舞人", "玉舞人", "王墓展区", "主体陈列楼", "", "美玉大观", "推断",
     "立体圆雕人物玉器，体现南越玉雕水平",
     "玉舞人在做什么动作？", 3, "family,craft",
     "透雕龙凤纹重环玉佩", "DOC_021/DOC_250"),
]

# ---------------------------------------------------------------------------
# 参观 FAQ：question, intent, zone, related_docs, note
FAQ = [
    ("南越王博物院几点开门？", "query_opening_hours", "两展区", "DOC_234/DOC_235", ""),
    ("王墓展区下午几点停止入场？", "query_last_entry", "王墓展区", "DOC_234", "17:00停止售票及进场"),
    ("王宫展区几点关门？", "query_opening_hours", "王宫展区", "DOC_235/DOC_239", "暑期延至18:00"),
    ("周一能去参观吗？", "query_monday_closed", "两展区", "DOC_234/DOC_235", "逢周一闭馆，法定节假日除外"),
    ("国庆节开馆吗？", "query_holiday_opening", "两展区", "DOC_234", "法定假期照常开放"),
    ("暑假开放时间有变化吗？", "query_summer_hours", "王宫展区", "DOC_239", "2026年7月11日-8月31日王宫延至18:00"),
    ("台风天会不会临时闭馆？", "query_temporary_closure", "两展区", "DOC_240", "以官方公众号通知为准"),
    ("墓室下层几点开放？", "query_tomb_lower_hours", "王墓展区", "DOC_236", "9:00-17:00分时段"),
    ("王墓展区门票多少钱？", "query_ticket_price", "王墓展区", "DOC_234", "全票10元、半价5元"),
    ("王宫展区要门票吗？", "query_ticket_price", "王宫展区", "DOC_235", "免费预约参观"),
    ("学生票怎么买？", "query_half_ticket", "王墓展区", "DOC_234", "全日制本科及以下半价5元"),
    ("老人参观免费吗？", "query_free_ticket", "王墓展区", "DOC_234", "65周岁（含）以上免费不免票"),
    ("小孩要买票吗？", "query_free_ticket", "王墓展区", "DOC_234", "18周岁（不含）以下免费不免票"),
    ("60岁有优惠吗？", "query_half_ticket", "王墓展区", "DOC_234", "60-64周岁（含）半价"),
    ("门票怎么预约？", "query_reservation", "两展区", "DOC_234/DOC_235/DOC_246", "微信公众号实名预约"),
    ("不预约能进吗？", "query_reservation_required", "两展区", "DOC_246", "全员预约制"),
    ("没带身份证怎么办？", "query_id_requirement", "两展区", "DOC_234/DOC_235", "凭身份证核验，详询服务台"),
    ("墓室下层怎么预约？", "query_tomb_lower_reservation", "王墓展区", "DOC_236", "提前一天公众号免费预约"),
    ("墓室下层参观票几点放票？", "query_tomb_lower_release", "王墓展区", "DOC_236", "每日00:00放票"),
    ("墓室下层能待多久？", "query_tomb_lower_duration", "王墓展区", "DOC_236", "每人上限20分钟"),
    ("小孩能进墓室下层吗？", "query_tomb_lower_children", "王墓展区", "DOC_236", "14周岁（含）以下须成人陪同"),
    ("墓室下层一次进多少人？", "query_tomb_lower_quota", "王墓展区", "DOC_236", "每小时上限50人"),
    ("大门票包含墓室下层吗？", "query_ticket_scope", "王墓展区", "DOC_234/DOC_236", "不含，需另行预约"),
    ("王墓展区怎么走？", "query_transport", "王墓展区", "DOC_234/DOC_247", "地铁二号线越秀公园站E出口"),
    ("王宫展区地铁哪个出口？", "query_transport", "王宫展区", "DOC_235/DOC_247", "公园前站F出口"),
    ("坐公交到王墓展区哪站下？", "query_transport_bus", "王墓展区", "DOC_234", "越秀公园、解放北路口、盘福路站"),
    ("王墓和王宫展区是同一个地方吗？", "query_zone_difference", "两展区", "DOC_247", "两个地址，相距约两站地铁"),
    ("两个展区能一起参观吗？", "query_two_zone_trip", "两展区", "DOC_256", "需分别预约"),
    ("王宫展区从哪个门进？", "query_entrance_exit", "王宫展区", "DOC_235", "东门进、西门出"),
    ("有免费讲解吗？", "query_free_guide", "两展区", "DOC_245", "每天9:30定时定点讲解"),
    ("免费讲解几点开始？怎么参加？", "query_free_guide_time", "两展区", "DOC_245", "限20人额满即止，详询服务台"),
    ("收费讲解在哪里买？", "query_paid_guide", "两展区", "DOC_245", "综合陈列楼一楼/南越宫苑馆一楼服务台"),
    ("有英文讲解吗？", "query_multilingual_guide", "两展区", "DOC_243/DOC_245", "自助讲解器含英语等多语种"),
    ("有没有语音导览？", "query_audio_guide", "两展区", "DOC_245", "线上语音导览+自助讲解器"),
    ("手语导赏怎么预约？", "query_sign_language", "两展区", "DOC_244", "提前7个工作日扫码预约"),
    ("墓室下层的考古讲解多少钱？", "query_tomb_tour_price", "王墓展区", "DOC_236", "150元/人90分钟"),
    ("旅行社能带团进馆讲解吗？", "query_third_party_guide", "两展区", "DOC_241", "2026-09-01起须提前3个工作日申请"),
    ("行李可以寄存吗？", "query_luggage", "两展区", "DOC_243", "王宫免费寄存、王墓自助寄存柜"),
    ("有轮椅租吗？", "query_wheelchair", "两展区", "DOC_244", "服务台租借"),
    ("婴儿车可以租吗？", "query_stroller", "两展区", "DOC_243/DOC_244", "服务台租借"),
    ("有老花镜、助听器吗？", "query_accessibility_loan", "两展区", "DOC_243/DOC_244", "服务台租借"),
    ("馆里有充电宝吗？", "query_powerbank", "两展区", "DOC_243", "充电宝租借"),
    ("有母婴室吗？", "query_baby_care", "两展区", "DOC_243", "官网未明示，列入待核实"),
    ("咨询电话是多少？", "query_contact_phone", "两展区", "DOC_234/DOC_235", "王墓020-36182920、王宫020-83896501"),
    ("丢东西了找谁？", "query_lost_found", "两展区", "DOC_243", "服务台咨询，失物招领流程待核实"),
    ("馆内可以拍照吗？", "query_photography", "两展区", "DOC_246", "官网未明示，列入待核实"),
    ("能带食物进馆吗？", "query_food_rules", "两展区", "DOC_246", "官网未明示，列入待核实"),
    ("馆外商铺的讲解靠谱吗？", "query_unauthorized_guide", "两展区", "DOC_242", "院外商铺均未获授权"),
    ("门口卖的文创是正品吗？", "query_unauthorized_shop", "两展区", "DOC_242", "认准展区内官方文创商店"),
    ("研学机构怎么报备？", "query_research_registration", "两展区", "DOC_241", "官网下载申请表发邮箱审核"),
    ("第一次去看什么？", "route_first_time", "王墓展区", "DOC_251", ""),
    ("只有半小时看哪些文物？", "route_30min", "王墓展区", "DOC_252", ""),
    ("一小时怎么逛？", "route_60min", "王墓展区", "DOC_253", ""),
    ("两小时深度游怎么安排？", "route_120min", "王墓展区", "DOC_254", ""),
    ("半天能把王墓展区看完吗？", "route_halfday", "王墓展区", "DOC_255", ""),
    ("带孩子怎么参观？", "route_family", "王墓展区", "DOC_257", ""),
    ("学生研学怎么做？", "route_student", "王墓展区", "DOC_258", ""),
    ("老人参观怎么省力？", "route_senior", "王墓展区", "DOC_259", ""),
    ("坐轮椅能参观吗？", "route_wheelchair", "两展区", "DOC_260", "墓原址可达性待核实"),
    ("下雨天怎么安排？", "route_rainy", "王墓展区", "DOC_261", ""),
    ("最值得看的文物有哪些？", "relic_highlights", "王墓展区", "DOC_250", "官方点名：文帝行玺、玉角杯、错金铭文虎节、印花铜板模、平板玻璃铜牌饰"),
    ("镇馆之宝是什么？", "relic_ranking", "王墓展区", "DOC_250", "馆方无官方排名，介绍代表性文物"),
    ("文帝行玺在哪个展厅？", "relic_location", "王墓展区", "DOC_250", "主体陈列楼南越藏珍陈列"),
    ("丝缕玉衣在哪里能看到？", "relic_location", "王墓展区", "DOC_250", "主体陈列楼南越藏珍陈列"),
]


def _hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def build_doc(spec: dict, source_type: str) -> dict:
    doc = {
        "doc_id": spec["doc_id"],
        "title": spec["title"],
        "source_name": MUSEUM if source_type == OFFICIAL else "AI-trip 项目整理",
        "source_url": spec["source_url"] if source_type == OFFICIAL else CURATED_URL,
        "source_type": source_type,
        "category": "tourism",
        "retrieved_at": RETRIEVED,
        "text": spec["text"],
        "source_tier": "extended",
        "topic_tags": spec["topic_tags"],
        "published_at": spec.get("published_at"),
        "content_hash": _hash(spec["text"]),
        "review_status": "approved",
        "version": 1,
    }
    return doc


def write_corpus_docs() -> list[dict]:
    RAW_TOURISM.mkdir(parents=True, exist_ok=True)
    docs = [build_doc(s, OFFICIAL) for s in OFFICIAL_DOCS]
    docs += [build_doc(s, CURATED) for s in CURATED_DOCS]
    for doc in docs:
        path = RAW_TOURISM / f"{doc['doc_id']}.json"
        if path.exists():
            raise SystemExit(f"拒绝覆盖已存在文件: {path}")
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return docs


def write_sources_csv(docs: list[dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    fields = ["doc_id", "title", "source_name", "source_url", "source_type", "source_tier",
              "evidence_role", "category", "published_at", "retrieved_at", "effective_from",
              "effective_until", "last_checked_at", "volatility", "zone", "floor",
              "visitor_types", "recommended_duration", "topic_tags", "review_status",
              "version", "content_hash"]
    with (OUT_DIR / "visitor_sources.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for doc in docs:
            meta = META[doc["doc_id"]]
            writer.writerow({
                "doc_id": doc["doc_id"], "title": doc["title"],
                "source_name": doc["source_name"], "source_url": doc["source_url"],
                "source_type": doc["source_type"], "source_tier": doc["source_tier"],
                "evidence_role": meta["evidence_role"], "category": doc["category"],
                "published_at": doc["published_at"] or "", "retrieved_at": doc["retrieved_at"],
                "effective_from": meta["effective_from"] or "",
                "effective_until": meta["effective_until"] or "",
                "last_checked_at": RETRIEVED, "volatility": meta["volatility"],
                "zone": meta["zone"], "floor": meta["floor"] or "",
                "visitor_types": "|".join(meta["visitor_types"]),
                "recommended_duration": meta["recommended_duration"] or "",
                "topic_tags": "|".join(doc["topic_tags"]),
                "review_status": doc["review_status"], "version": doc["version"],
                "content_hash": doc["content_hash"],
            })


def write_space_facts_csv() -> None:
    with (OUT_DIR / "structured_space_facts.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["展区", "建筑", "楼层", "空间/展厅", "类型", "内容", "来源文档", "置信度", "备注"])
        writer.writerows(SPACE_FACTS)


def write_relics_csv() -> None:
    with (OUT_DIR / "representative_relics.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["文物名称", "常见别名", "展区", "建筑", "楼层", "展览单元", "单元置信度",
                         "官方推荐理由", "能回答的核心问题", "建议停留(分钟)",
                         "适合人群", "相关文物", "来源文档"])
        writer.writerows(RELICS)


def write_faq_csv() -> None:
    with (OUT_DIR / "visitor_faq.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["编号", "游客问法", "标准意图", "展区", "关联文档", "备注"])
        for i, row in enumerate(FAQ, 1):
            writer.writerow([f"FAQ_{i:03d}", *row])


def main() -> None:
    docs = write_corpus_docs()
    write_sources_csv(docs)
    write_space_facts_csv()
    write_relics_csv()
    write_faq_csv()
    print(f"已生成语料文档 {len(docs)} 个（official {len(OFFICIAL_DOCS)} + curated {len(CURATED_DOCS)}）")
    print(f"采集表/事实表/文物表/FAQ 已写入 {OUT_DIR}")


if __name__ == "__main__":
    main()
