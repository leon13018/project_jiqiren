# EDD 回歸（skill-edd-regression workflow）

skill / reference 去噪後的回歸守門。對 Claude 說：

> 跑 skill-edd-regression，場景檔 resources/edd/scenarios_workflow_routing.json

主 agent 讀場景檔 → 以 `args:{scenarios}` 觸發 `.claude/workflows/skill-edd-regression.js`
（Navigate→Grade→Verdict；機制與 API 見 `resources/research/workflows_orchestration_research_2026-06-04.md`）。

## 場景檔格式（一主題一檔，命名 `scenarios_<topic>.json`）

```json
{ "scenarios": [ { "id": "...", "model": "sonnet（可省略=跟 session）",
                   "task": "任務情境", "asserts": ["機器可核對的斷言"] } ] }
```
