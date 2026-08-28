export interface Relic {
  slug: string
  name: string
  material: string
  period: string
  place: string
  theme: string
  imageLabel: string
  image: string
  importance: string
  relationSeed: string
  source: { docId: string; title: string; url: string; evidence: string }
}

export const RELICS: Relic[] = [
  {
    slug: 'wendi-seal', name: '文帝行玺', material: '金', period: '西汉南越国', place: '南越文王墓主棺室',
    theme: '王权', imageLabel: '金印', image: '/images/relics/wendi-seal.png', importance: '墓中同时出现“文帝行玺”“帝印”与“赵眜”印章，成为确认墓主人身份的重要证据。',
    relationSeed: '赵眜', source: { docId: 'DOC_013', title: '“文帝行玺”龙钮金印', url: 'https://www.nywmuseum.org.cn/Collection/Details/dcjp?nid=47', evidence: '“文帝行玺”龙钮金印为西汉南越国文物，金印出土于墓主胸部。' },
  },
  {
    slug: 'jade-suit', name: '丝缕玉衣', material: '玉、丝、麻布', period: '西汉南越国', place: '南越文王墓',
    theme: '丧葬', imageLabel: '玉衣', image: '/images/relics/jade-suit.png', importance: '2291 片玉片以丝缕和麻布粘贴编缀，留下南越王对身份、礼制与生死的想象。',
    relationSeed: '丝缕玉衣', source: { docId: 'DOC_014', title: '丝缕玉衣', url: 'https://www.nywmuseum.org.cn/Collection/Details/dcjp?nid=56', evidence: '玉衣由2291片玉片、丝缕和麻布粘贴编缀而成。' },
  },
  {
    slug: 'horn-cup', name: '角形玉杯', material: '玉', period: '西汉南越国', place: '南越文王墓',
    theme: '交流', imageLabel: '玉杯', image: '/images/relics/horn-cup.png', importance: '独特器形与温润玉质，提示南越与中原、海上世界之间多层次的文化交流。',
    relationSeed: '角形玉杯', source: { docId: 'DOC_018', title: '角形玉杯', url: 'https://www.nywmuseum.org.cn/', evidence: '出土角形玉杯，玉质莹润，形制独特。' },
  },
  {
    slug: 'jade-pendant', name: '组玉佩', material: '玉', period: '西汉南越国', place: '南越文王墓',
    theme: '礼制', imageLabel: '玉佩', image: '/images/relics/jade-pendant.png', importance: '多件玉器通过佩系与组合形成等级表达，是理解南越礼制的一条细小线索。',
    relationSeed: '南越文王墓', source: { docId: 'DOC_007', title: '丝缕玉衣与珠玉敛葬', url: 'https://www.nywmuseum.org.cn/', evidence: '南越王身着丝缕玉衣，并以珠玉敛葬，凸显尊贵的身份与地位。' },
  },
]

export const TIMELINE = [
  { year: '前214', title: '秦定岭南', text: '岭南被纳入秦帝国版图，南越故事的地理与制度背景由此展开。', target: '赵佗' },
  { year: '前203', title: '赵佗建立南越国', text: '秦末，赵佗据岭南建立南越国，都番禺。', target: '赵佗' },
  { year: '前137', title: '赵眜继位', text: '南越第二代王赵眜自称文帝，留下王权与汉越关系的复杂证据。', target: '赵眜' },
  { year: '西汉', title: '南越文王墓', text: '文帝行玺、丝缕玉衣等器物被安放于象岗山腹心的墓室。', target: '南越文王墓' },
  { year: '前111', title: '汉灭南越', text: '南越国的政治史告一段落，岭南与中原的联系进入新阶段。', target: '南越国' },
  { year: '1983', title: '王墓发现', text: '南越文王墓的发现，让两千年前的岭南王国再次被看见。', target: '南越文王墓' },
]

export const THEMES = [
  { title: '王权密码', intro: '从金印与墓主身份，理解南越王权的自我表达。', stops: ['赵眜', '文帝行玺', '帝印', '南越文王墓'] },
  { title: '玉之国', intro: '沿着玉衣、玉杯与佩饰，走近南越的礼制与日常。', stops: ['丝缕玉衣', '组玉佩', '角形玉杯', '南越文王墓'] },
  { title: '帝国与岭南', intro: '从秦统一到南越兴亡，理解岭南如何进入更广阔的历史。', stops: ['秦定岭南', '赵佗', '南越国', '汉越关系'] },
]
