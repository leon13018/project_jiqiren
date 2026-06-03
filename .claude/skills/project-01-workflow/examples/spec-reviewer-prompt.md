# Spec-reviewer subagent prompt template

> **🎯 何時讀本檔**：SDD 三段迴圈第 2 段（spec compliance review）要派 spec-reviewer 時，複製本範本填空派發。流程 / 為何用 fresh-context subagent 見 [`../reference/sdd.md`](../reference/sdd.md) §三段 subagent 迴圈。

## 派發方式

`general-purpose` + `model: sonnet`（任務單純：對照 spec vs code，sonnet 已足）。

```python
Agent({
    subagent_type: "general-purpose",
    model: "sonnet",
    description: "Spec compliance review for <spec_name>",
    prompt: <下方範本>
})
```

## Prompt 範本（主 agent 複製 + 填空後派發）

```
你的工作是審查 sales-coder 對 <spec_name> 的實作是否符合 spec。

## Spec 檔
完整讀：`resources/specs/<spec_name>_spec.md`（如有 plan 檔也讀 `_plan.md`）
特別關注：§3 改檔範圍（每項是否實作）/ §3.3 測試清單 / §4 Out of scope（是否做了禁做的事）。

## Sales-coder 回報摘要
[主 agent paste sales-coder 的 DONE / DONE_WITH_CONCERNS 回報全文]

## Commit SHA 範圍
BASE: <pre-sales-coder SHA>　HEAD: <last sales-coder SHA>
跑 `git diff <BASE>..<HEAD> --stat`（改檔範圍）+ `git diff <BASE>..<HEAD>`（實際 diff）+ `git log <BASE>..<HEAD>`（commit 數 / 訊息一致性）。

## CRITICAL：不要信 sales-coder 的自報
它可能不完整 / 不準確（聲稱實作但 grep 不到）/ 過度樂觀。**必獨立 verify**：Read 每個改的 code、逐行對照 spec §3、找「extra 加料」與「grep 不到的假完成」。禁止接受它對「完整度」「spec 解讀」的宣告。

## 檢查 3 大類（每條附具體 file:line，不寫模糊描述）
- **Missing（漏做）**：spec §X.Y 規定 [...] 但 grep 不到 / 聲稱做了但 code 無對應改動。
- **Extra（加料）**：實作 spec 沒要求的 feature/param/flag、順手 refactor 鄰近 code（違 surgical）、加「未來可能需要」抽象（違 YAGNI）。
- **Misinterpreted（理解錯）**：spec §X.Y 意思 [...] 但實作成 [...] / 解決了錯的問題 / 對的 feature 用錯方法。

## 回報格式（嚴格 2 選 1）
- **✅ Spec compliant**：逐條列 spec §X.Y → file:line 的 commit、確認正確；無 extra/missing/misinterpreted。
- **❌ Issues found**：分 [Missing]/[Extra]/[Misinterpreted] 列，每條附 file:line 或 grep 命中行。
```
