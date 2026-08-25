# Day 5 Agent 冒烟测试记录

通过：16/16。

| 编号 | 问题 | 类型 | 预期工具 | 实际工具 | 内容正确 | 引用数 | 拒答 | 延迟 ms | 通过 |
|---|---|---|---|---|---|---:|---|---:|---|
| 1 | 文帝行玺是什么材料？ | kg_fact | search_kg | search_kg | 是 | 1 | 否 | 0.54 | 是 |
| 2 | 赵眜和南越文王墓是什么关系？ | kg_fact | search_kg | search_kg | 是 | 6 | 否 | 0.2 | 是 |
| 3 | 文帝行玺和赵眜有什么关系？ | kg_fact | search_kg | search_kg | 是 | 6 | 否 | 0.19 | 是 |
| 4 | 丝缕玉衣反映了什么丧葬观念？ | hybrid | hybrid_search | hybrid_search | 是 | 5 | 否 | 0.26 | 是 |
| 5 | 船纹铜提筒反映了什么？ | hybrid | hybrid_search | hybrid_search | 是 | 5 | 否 | 0.2 | 是 |
| 6 | 介绍一下文帝行玺。 | document_description | hybrid_search | hybrid_search | 是 | 6 | 否 | 0.24 | 是 |
| 7 | 讲讲丝缕玉衣的特点。 | document_description | hybrid_search | hybrid_search | 是 | 6 | 否 | 0.14 | 是 |
| 8 | 南越王博物院王墓展区在哪里？ | document_description | hybrid_search | hybrid_search | 是 | 5 | 否 | 0.16 | 是 |
| 9 | 南越国是谁建立的？ | hybrid | hybrid_search | hybrid_search | 是 | 6 | 否 | 0.25 | 是 |
| 10 | 犀角形玉杯有什么特点？ | document_description | hybrid_search | hybrid_search | 是 | 6 | 否 | 0.15 | 是 |
| 11 | 赵眜是谁？请结合文物证据。 | hybrid | hybrid_search | hybrid_search | 是 | 6 | 否 | 0.3 | 是 |
| 12 | 南越文王墓为什么重要？ | hybrid | hybrid_search | hybrid_search | 是 | 6 | 否 | 0.26 | 是 |
| 13 | 文帝行玺为什么能证明墓主身份？ | hybrid | hybrid_search | hybrid_search | 是 | 6 | 否 | 0.22 | 是 |
| 14 | 今天馆内有多少游客？ | out_of_scope | none | none | 是 | 0 | 是 | 0.01 | 是 |
| 15 | 广州哪里停车最方便？ | out_of_scope | none | none | 是 | 0 | 是 | 0.01 | 是 |
| 16 | 火星上的南越王墓是谁建的？ | false_premise | none | none | 是 | 0 | 是 | 0.0 | 是 |
