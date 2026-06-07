# iteration-5 — 2026-06-07 全量回歸 + 跨桶路由修復 + s10 graduation

> 觸發背景：workflow-authoring.md 補落點判準（c1ee936）+ memory-management 新路由（03e48f0）後的全量守門。

## 弧

1. **全量 14 場景**（`full-regression-result.json`，wf_48945bf8）：55/56——唯一 fail 是場景 3 assert 4（Pi pycache 坑未 surface）。歸因：**跨桶路由弱點**——「實作＋部署」複合任務只蓋主桶（threading）漏次桶（sync Pi）的跨檔 caveat；非內容缺失、非自足性問題。
2. **修復**（`52ec1f4`）：threading-paths.md Part B 加部署提醒薄 pointer（實例修）+ SKILL.md 路由表頭加「複合任務跨多列每列都要讀」（類型修）。
3. **s3 復驗**（`s3-revalidation-result.json`，wf_7a62ecd9）：6/6——navigator 把 pycache 納入 pineedtodo 規劃，Part B pointer 生效。
4. **s10 graduation**（`s10-graduation-result.json`，wf_2d40d1cd）：sonnet 變體 3/3——s7 的「規則查表」敏感性以實證銷帳，邊界敘述在弱模型上扛得住，無需強化 reference 文字。

## 結論

- 題庫 10 場景（scenarios_workflow_routing s1-s10）+ 5 legacy（evals.json）全綠；回歸基線 = **56/56（修復後）**。
- 本輪首次完整演示「EDD 抓 fail → transcript 歸因 → 選層修 → 復驗畢業」閉環。
- 注意：本輪三份 result 的 graded 由 2026-06-07 前的 grader 產出（無 weak_asserts 欄）；該欄自 365f3a1 起生效。
