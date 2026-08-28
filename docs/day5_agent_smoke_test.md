# Day 5 Agent 冒烟测试记录

通过：24/24。

| 编号 | 问题 | 类型 | 预期工具 | 实际工具 | 内容正确 | 引用数 | 拒答 | 延迟 ms | 通过 |
|---|---|---|---|---|---|---:|---|---:|---|
| 1 | 文帝行玺是什么材料？ | kg_fact | search_kg | search_kg | 是 | 1 | 否 | 1.21 | 是 |
| 2 | 赵眜和南越文王墓是什么关系？ | kg_fact | search_kg | search_kg | 是 | 3 | 否 | 6.17 | 是 |
| 3 | 文帝行玺和赵眜有什么关系？ | kg_fact | search_kg | search_kg | 是 | 2 | 否 | 4.5 | 是 |
| 4 | 丝缕玉衣反映了什么丧葬观念？ | hybrid | hybrid_search | hybrid_search | 是 | 2 | 否 | 4.87 | 是 |
| 5 | 船纹铜提筒反映了什么？ | hybrid | hybrid_search | hybrid_search | 是 | 3 | 否 | 1.42 | 是 |
| 6 | 介绍一下文帝行玺。 | document_description | hybrid_search | hybrid_search | 是 | 5 | 否 | 7.1 | 是 |
| 7 | 讲讲丝缕玉衣的特点。 | document_description | hybrid_search | hybrid_search | 是 | 4 | 否 | 6.58 | 是 |
| 8 | 南越王博物院王墓展区在哪里？ | visit_guidance | search_documents | search_documents | 是 | 2 | 否 | 15.1 | 是 |
| 9 | 南越国是谁建立的？ | hybrid | hybrid_search | hybrid_search | 是 | 4 | 否 | 8.57 | 是 |
| 10 | 犀角形玉杯有什么特点？ | document_description | hybrid_search | hybrid_search | 是 | 5 | 否 | 6.12 | 是 |
| 11 | 赵眜是谁？请结合文物证据。 | hybrid | hybrid_search | hybrid_search | 是 | 5 | 否 | 6.85 | 是 |
| 12 | 南越文王墓为什么重要？ | hybrid | hybrid_search | hybrid_search | 是 | 5 | 否 | 9.55 | 是 |
| 13 | 文帝行玺为什么能证明墓主身份？ | hybrid | hybrid_search | hybrid_search | 是 | 5 | 否 | 6.39 | 是 |
| 14 | 第一次去王墓展区应该怎么看？ | visit_guidance | search_documents | search_documents | 是 | 2 | 否 | 22.16 | 是 |
| 15 | 王墓展区开放时间和预约怎么安排？ | visit_guidance | search_documents | search_documents | 是 | 2 | 否 | 15.37 | 是 |
| 16 | 带学生参观南越王博物院可以讲哪些问题？ | visit_guidance | search_documents | search_documents | 是 | 2 | 否 | 21.51 | 是 |
| 17 | 今天馆内有多少游客？ | out_of_scope | none | none | 是 | 0 | 是 | 3.06 | 是 |
| 18 | 今天王墓展区还剩多少预约名额？ | out_of_scope | none | none | 是 | 0 | 是 | 1.83 | 是 |
| 19 | 广州哪里停车最方便？ | out_of_scope | none | none | 是 | 0 | 是 | 1.73 | 是 |
| 20 | 火星上的南越王墓是谁建的？ | false_premise | none | none | 是 | 0 | 是 | 0.34 | 是 |
| 21 | 给我讲一个文帝行玺的小故事 | kids_story | search_kg | search_kg | 是 | 3 | 否 | 0.62 | 是 |
| 22 | 丝缕玉衣是做什么用的？ | kids_relic | search_kg | search_kg | 是 | 2 | 否 | 0.64 | 是 |
| 23 | 你是谁呀？ | kids_chat | none | none | 是 | 0 | 否 | 2.55 | 是 |
| 24 | 今天馆内有多少游客？ | kids_refuse | none | none | 是 | 0 | 是 | 0.03 | 是 |
