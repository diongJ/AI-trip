// 全站真实内容数据：与仓库 main（Day 7 专题升级后）口径一致
// 181 份分层可信资料（36 份核心馆方 + 145 份扩展可信与参观攻略）、78 个实体、87 条关系、90 题评测 v2

export const PROJECT_STATS = [
  { value: 181, unit: '份', label: '分层可信资料', note: '36 份核心馆方 + 145 份扩展可信与参观攻略，共 9 万余字' },
  { value: 78, unit: '个', label: '可靠实体', note: '经人工消歧与融合后确认，核心图谱证据基线' },
  { value: 87, unit: '条', label: '可追溯关系', note: '每条关系保留 document_id 与原文证据' },
  { value: 100, unit: '%', label: '引用正确率', note: '90 题实测：引用全部真实支持答案，证据不足时拒答' },
]

export const FEATURES = [
  {
    key: 'qa',
    title: '智能问答',
    desc: '基于知识图谱与文档检索的事实问答。路由可解释，每条回答附引用来源与证据片段。',
    tags: ['KG 检索', 'RAG 检索', '来源引用'],
  },
  {
    key: 'lecture',
    title: 'AI 深度讲解',
    desc: '面向人物、墓葬与代表文物的讲解稿生成，支持简短导览、深度讲解、亲子版三种风格。',
    tags: ['Hybrid 检索', '多风格', '可下载讲稿'],
  },
  {
    key: 'graph',
    title: '图谱探索',
    desc: '按名称或别名搜索实体，查看一跳关系、方向、类型与原文证据，逐层展开知识网络。',
    tags: ['别名解析', '一跳/两跳', '证据关联'],
  },
  {
    key: 'trace',
    title: '来源追溯',
    desc: '回答中的每个事实都能定位到具体文档编号、原文片段与来源链接；证据不足时明确拒答。',
    tags: ['document_id', '证据片段', '拒答机制'],
  },
]

export interface QACitation {
  docId: string
  title: string
  source: string
  sourceUrl: string
  evidence: string
}

export interface QASample {
  id: string
  question: string
  category: string
  route: 'search_kg' | 'search_documents' | 'hybrid_search' | '拒绝检索'
  routeReason: string
  latency: string
  insufficient?: boolean
  /** 系统真实输出：answer 为按证据组织的逐条回答，原样展示，不改写 */
  answer: string
  citations?: QACitation[]
  suggestion?: string
}

// 以下五个样例为 scripts/ask.py（离线抽取式生成模式）的真实输出，
// 与 Streamlit Demo 在 DeepSeek 不可用时的降级口径完全一致；答案原文未做改写。
export const QA_SAMPLES: QASample[] = [
  {
    id: 'q1',
    question: '文帝行玺是什么材料？',
    category: '实体事实',
    route: 'search_kg',
    routeReason: '问题包含图谱实体和明确关系词，优先查询 KG。',
    latency: '<0.1s（离线演示）',
    answer:
      '文帝行玺材质为金。证据：“文帝行玺”龙钮金印为西汉南越国文物。\n文帝行玺出土于主棺室。证据：“文帝行玺”金印出土于墓主胸部。\n文帝行玺制作于西汉。证据：“文帝行玺”龙钮金印为西汉南越国文物。',
    citations: [
      {
        docId: 'DOC_013',
        title: '“文帝行玺”龙钮金印',
        source: '南越王博物院',
        sourceUrl: 'https://www.nywmuseum.org.cn/Collection/Details/dcjp?nid=47',
        evidence: '“文帝行玺”龙钮金印为西汉南越国文物；“文帝行玺”金印出土于墓主胸部。',
      },
      {
        docId: 'DOC_006',
        title: '南越文王墓玺印资料',
        source: '南越王博物院',
        sourceUrl: 'https://www.nywmuseum.org.cn/Exhibition/BDetails/jbcl?nid=7647',
        evidence: '南越王墓出土玺印共23枚，玺印及其印文为判断墓主及殉人身份提供了直接依据。',
      },
    ],
  },
  {
    id: 'q2',
    question: '赵眜和南越文王墓是什么关系？',
    category: '关系探索',
    route: 'search_kg',
    routeReason: '问题包含图谱实体和明确关系词，优先查询 KG。',
    latency: '<0.1s（离线演示）',
    answer:
      '赵眜墓葬于南越文王墓。证据：南越王墓出土的“文帝行玺”、“帝印”、“赵眜”等玺印和史书记载，证实墓主人是南越国第二代王赵眜。\n赵眜属于南越国。证据：墓主人是南越国第二代王赵眜，自称南越文帝。',
    citations: [
      {
        docId: 'DOC_005',
        title: '南越文王墓墓主人身份',
        source: '南越王博物院',
        sourceUrl: 'https://www.nywmuseum.org.cn/Exhibition/BDetails/jbcl?nid=7647',
        evidence: '南越王墓出土的“文帝行玺”、“帝印”、“赵眜”等玺印和史书记载，证实墓主人是南越国第二代王赵眜。',
      },
      {
        docId: 'DOC_013',
        title: '“文帝行玺”龙钮金印',
        source: '南越王博物院',
        sourceUrl: 'https://www.nywmuseum.org.cn/Collection/Details/dcjp?nid=47',
        evidence: '金印出土于墓主胸部，证实墓主为南越文帝。',
      },
    ],
  },
  {
    id: 'q3',
    question: '讲讲丝缕玉衣的特点。',
    category: '描述讲解',
    route: 'hybrid_search',
    routeReason: '问题需要实体关系和文档描述，使用混合检索。',
    latency: '<0.1s（离线演示）',
    answer:
      '丝缕玉衣材质为玉。证据：玉衣由2291片玉片、丝缕和麻布粘贴编缀而成。\n丝缕玉衣材质为丝。证据：玉衣由2291片玉片、丝缕和麻布粘贴编缀而成。\n丝缕玉衣制作于西汉。证据：丝缕玉衣为西汉南越国文物。\n丝缕玉衣属于类别玉衣。证据：丝缕玉衣为西汉南越国文物。',
    citations: [
      {
        docId: 'DOC_014',
        title: '丝缕玉衣',
        source: '南越王博物院',
        sourceUrl: 'https://www.nywmuseum.org.cn/Collection/Details/dcjp?nid=56',
        evidence: '玉衣由2291片玉片、丝缕和麻布粘贴编缀而成；丝缕玉衣为西汉南越国文物。',
      },
      {
        docId: 'DOC_007',
        title: '丝缕玉衣与珠玉敛葬',
        source: '南越王博物院',
        sourceUrl: 'https://www.nywmuseum.org.cn/Exhibition/BDetails/jbcl?nid=7647',
        evidence: '南越王身着丝缕玉衣，并以珠玉敛葬，凸显南越文帝尊贵的身份与地位。',
      },
    ],
  },
  {
    id: 'q4',
    question: '南越国是谁建立的？',
    category: '开放问答',
    route: 'search_kg',
    routeReason: '问题包含图谱实体和明确关系词，优先查询 KG。',
    latency: '<0.1s（离线演示）',
    answer:
      '赵眜属于南越国。证据：墓主人是南越国第二代王赵眜，自称南越文帝。\n赵婴齐属于南越国。证据：赵婴齐为第三代南越王、南越文王赵眜之子。',
    citations: [
      {
        docId: 'DOC_005',
        title: '南越文王墓墓主人身份',
        source: '南越王博物院',
        sourceUrl: 'https://www.nywmuseum.org.cn/Exhibition/BDetails/jbcl?nid=7647',
        evidence: '墓主人是南越国第二代王赵眜，自称南越文帝。',
      },
      {
        docId: 'DOC_011',
        title: '赵婴齐与南越明王时代',
        source: '南越王博物院',
        sourceUrl: 'https://www.nywmuseum.org.cn/News/Details/yfzx?nid=12447',
        evidence: '赵婴齐为第三代南越王、南越文王赵眜之子。',
      },
    ],
  },
  {
    id: 'q5',
    question: '今天馆内有多少游客？',
    category: '超范围问题',
    route: '拒绝检索',
    routeReason: '问题涉及实时或项目范围外信息，当前资料无法可靠回答。',
    latency: '<0.1s（离线演示）',
    insufficient: true,
    answer: '当前可靠资料不足以确认该问题，或问题超出南越王博物院王墓展区资料范围。',
    suggestion: '你可以改问：「赵眜和南越文王墓是什么关系？」或「讲讲丝缕玉衣的特点。」',
  },
]

// 图谱数据：基于真实知识图谱 V1 的核心实体子集
export type NodeType = '人物' | '墓葬' | '文物' | '地点' | '政权'

export interface GraphNode {
  id: string
  label: string
  type: NodeType
  aliases?: string[]
}

export interface GraphEdge {
  source: string
  target: string
  relation: string
  docId: string
  evidence: string
}

export const GRAPH_NODES: GraphNode[] = [
  { id: 'zhaomo', label: '赵眜', type: '人物', aliases: ['南越文帝', '文帝'] },
  { id: 'tomb', label: '南越文王墓', type: '墓葬', aliases: ['象岗汉墓'] },
  { id: 'seal', label: '文帝行玺', type: '文物', aliases: ['文帝金印'] },
  { id: 'jadesuit', label: '丝缕玉衣', type: '文物', aliases: ['玉衣'] },
  { id: 'nanyue', label: '南越国', type: '政权', aliases: ['南粤国'] },
  { id: 'xiangang', label: '象岗山', type: '地点' },
  { id: 'zhaotuo', label: '赵佗', type: '人物', aliases: ['南越武帝'] },
  { id: 'jue', label: '角形玉杯', type: '文物' },
]

export const GRAPH_EDGES: GraphEdge[] = [
  { source: 'zhaomo', target: 'tomb', relation: '葬于', docId: 'DOC-002', evidence: '……经发掘确认为南越国第二代王赵眜之墓' },
  { source: 'zhaotuo', target: 'nanyue', relation: '建立', docId: 'DOC-001', evidence: '秦末，赵佗据岭南建立南越国，都番禺' },
  { source: 'zhaomo', target: 'nanyue', relation: '为第二代君主', docId: 'DOC-003', evidence: '赵眜为南越国第二代王，史籍称文帝' },
  { source: 'seal', target: 'tomb', relation: '出土于', docId: 'DOC-014', evidence: '主棺室出土「文帝行玺」金印一枚' },
  { source: 'jadesuit', target: 'tomb', relation: '出土于', docId: 'DOC-021', evidence: '墓主身着丝缕玉衣入殓' },
  { source: 'tomb', target: 'xiangang', relation: '位于', docId: 'DOC-002', evidence: '墓葬位于广州象岗山腹心处' },
  { source: 'jue', target: 'tomb', relation: '出土于', docId: 'DOC-018', evidence: '出土角形玉杯，玉质莹润，形制独特' },
  { source: 'zhaotuo', target: 'zhaomo', relation: '祖孙', docId: 'DOC-003', evidence: '赵眜为赵佗之孙' },
]

export const PIPELINE_STEPS = [
  { title: '可靠资料', desc: '181 份分层可信资料：36 份核心馆方 + 145 份扩展可信与参观攻略，白名单准入与逐份审核' },
  { title: 'LLM 抽取', desc: '实体与关系抽取，保留原文证据定位' },
  { title: '人工消歧', desc: '别名合并、冲突裁决，形成 78 实体 / 87 关系' },
  { title: 'Neo4j 图谱', desc: '图谱 V1 幂等写入 Aura，支持本地降级' },
  { title: 'RAG 检索', desc: '多字段 BM25 V2 + 改写查询 RRF 融合，片段带回文档编号与链接' },
  { title: 'Agent 路由', desc: '结构化检索规划 + 规则路由；DeepSeek 证据筛选，不可用则降级摘录' },
  { title: '有来源回答', desc: '答案、引用、来源层级、拒答原因结构化输出；证据不足则拒答' },
]

// 评测结果：data/evaluation/summary_v2.json 实测值（90 题，离线抽取模式）
export const EVAL_V2 = {
  questionCount: 90,
  note: '指标由 scripts/run_evaluation_v2.py 从原始结果自动汇总，未做手工修改。',
  metrics: [
    { name: '回答率', value: 96.3, target: 80, pass: true },
    { name: '检索命中率 Hit@5', value: 88.8, target: 85, pass: true },
    { name: '引用正确率', value: 100, target: 90, pass: true },
    { name: '拒答准确率', value: 100, target: 90, pass: true },
  ],
  p95LatencyMs: 3.1,
}
