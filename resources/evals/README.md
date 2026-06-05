# EDD 回歸（skill-edd-regression workflow）

skill / reference 去噪後的回歸守門。對 Claude 說：

> 跑 skill-edd-regression，場景檔 resources/evals/<檔名>

主 agent 讀場景檔 → 以 `args:{scenarios}` 觸發 `.claude/workflows/skill-edd-regression.js`
（Navigate→Grade→Verdict；機制與 API 見 `resources/research/workflows_orchestration_research_2026-06-04.md`）。

## 場景檔

| 檔 | 內容 | 格式 |
|---|---|---|
| `evals.json` | 5 條內容覆蓋型場景（SDD / process / threading / sales / dormant 五 cluster） | 舊：`prompt` / `expectations` |
| `scenarios_workflow_routing.json` | 6 條協議路由場景（worktree / SDD / 派發 / Gotcha M / Pi 依賴；含 sonnet 對照） | 新：`task` / `asserts` |

harness 兩種格式都吃（`task||prompt`、`asserts||expectations`）；`model` 欄可選（`"sonnet"` = 降級對照，省略 = 跟 session）。新主題開新檔 `scenarios_<topic>.json`。

`baseline/` 與 `iteration-*/` 是歷史回歸紀錄（skill_reference_cleanup 時代），append 新輪結果時開 `iteration-N/`。
