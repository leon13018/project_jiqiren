# EDD 回歸（skill-edd-regression workflow）

skill / reference 去噪後的回歸守門。對 Claude 說：

> 跑 skill-edd-regression，場景檔 resources/evals/<檔名>

主 agent 讀場景檔 → 以 `args:{scenarios}` 觸發 `.claude/workflows/skill-edd-regression.js`
（Navigate→Grade→Verdict；機制與 API 見 `resources/research/workflows_orchestration_research_2026-06-04.md`）。

## 場景檔

| 檔 | 內容 | 格式 |
|---|---|---|
| `evals.json` | 5 條內容覆蓋型場景（SDD / process / threading / sales / dormant 五 cluster） | 舊：`prompt` / `expectations` |
| `scenarios_workflow_routing.json` | 10 條協議路由場景（worktree / SDD / 派發 / Gotcha M / Pi 依賴與操作邊界 / workflow-authoring / memory 健檢；含 sonnet 對照 ×2） | 新：`task` / `asserts` |

harness 兩種格式都吃（`task||prompt`、`asserts||expectations`）；`model` 欄可選（`"sonnet"` = 降級對照，省略 = 跟 session）。新主題開新檔 `scenarios_<topic>.json`。

`baseline/` 與 `iteration-*/` 是歷史回歸紀錄（skill_reference_cleanup 時代），append 新輪結果時開 `iteration-N/`。

## 結果落檔（每跑必落）

跑完任一輪 EDD（全量或部分），主 agent 收到 workflow 回傳後**必須**落檔 `iteration-N/`（N 接續最大值；同一工作弧多次 run 共用同一 N）：

- 檔名：`<scope>-result.json`（例：full-regression / s10-graduation / s3-revalidation）
- schema：`{ "date": "YYYY-MM-DD", "run_id": "wf_…", "scope": "…", "scenario_ids": [...], "verdict": <原樣>, "graded": <原樣> }`
- 大局結論寫/併 `final-consolidated.md`（沿 iteration-2/3/4 慣例）

Why：跨輪聚合（每 assertion 跨輪 pass 率、抓非鑑別 assertion）的資料基礎——不落檔趨勢不可查。grader 自 2026-06-07 起回報 `weak_asserts`（非鑑別 assertion），聚合時一併看。
