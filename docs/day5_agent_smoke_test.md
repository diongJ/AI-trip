# Day 5 Agent 冒烟测试记录

通过：15/15。

| 编号 | 问题 | 类型 | 工具 | 引用数 | 拒答 | 延迟 ms | 通过 |
|---|---|---|---|---:|---|---:|---|
| 1 | 文帝行玺是什么材料？ | kg_fact | search_kg | 6 | 否 | 0.7 | 是 |
| 2 | 赵眜和南越文王墓是什么关系？ | kg_fact | search_kg | 3 | 否 | 0.28 | 是 |
| 3 | 文帝行玺和赵眜有什么关系？ | kg_fact | search_kg | 3 | 否 | 0.14 | 是 |
| 4 | 丝缕玉衣反映了什么丧葬观念？ | kg_fact | search_kg | 3 | 否 | 0.21 | 是 |
| 5 | 船纹铜提筒反映了什么？ | kg_fact | search_kg | 3 | 否 | 0.23 | 是 |
| 6 | 介绍一下文帝行玺。 | document_description | hybrid_search | 6 | 否 | 0.46 | 是 |
| 7 | 讲讲丝缕玉衣的特点。 | document_description | hybrid_search | 6 | 否 | 0.3 | 是 |
| 8 | 南越王博物院王墓展区在哪里？ | document_description | search_documents | 5 | 否 | 0.26 | 是 |
| 9 | 南越国是谁建立的？ | document_description | search_kg | 2 | 否 | 0.1 | 是 |
| 10 | 犀角形玉杯有什么特点？ | document_description | hybrid_search | 6 | 否 | 0.21 | 是 |
| 11 | 赵眜是谁？请结合文物证据。 | hybrid | search_kg | 3 | 否 | 0.13 | 是 |
| 12 | 南越文王墓为什么重要？ | hybrid | hybrid_search | 6 | 否 | 0.23 | 是 |
| 13 | 文帝行玺为什么能证明墓主身份？ | hybrid | hybrid_search | 6 | 否 | 0.25 | 是 |
| 14 | 今天馆内有多少游客？ | out_of_scope | none | 0 | 是 | 0.02 | 是 |
| 15 | 广州哪里停车最方便？ | out_of_scope | none | 0 | 是 | 0.01 | 是 |
