# Code-quality-reviewer subagent prompt template

> SDD 三段迴圈第 3 段（code quality review）。**前提**：先通過第 2 段 spec-reviewer ✅。流程與「為何用 fresh-context subagent」見 [`../reference/sdd.md`](../reference/sdd.md) §三段 subagent 迴圈。

## 派發方式

`general-purpose` + `model: "opus"`（需架構判斷，sonnet 不夠）。**effort 不寫死 → 繼承 session effort**（Agent 工具無 effort 參數可傳，亦不在 prompt 內強制 xhigh；session 是高 effort 時自然會深入）。

```python
Agent({
    subagent_type: "general-purpose",
    model: "opus",
    description: "Code quality review for <spec_name>",
    prompt: <下方範本>
})
```

## Prompt 範本（主 agent 複製 + 填空後派發）

```
你審查 sales-coder commit 的 code quality（已過 spec compliance，現純從工程品質看）。寧可慢不要錯、仔細逐項審查。

## 改動範圍
`git diff <BASE>..<HEAD> --stat` / `git diff <BASE>..<HEAD>` / `git log <BASE>..<HEAD> --oneline`
BASE: <pre-sales-coder SHA>　HEAD: <last SHA>
Spec（已過 spec-reviewer、不必再查 compliance）：`resources/specs/<spec_name>_spec.md`

## 審查 7 類
1. **Karpathy（最高優先）**：surgical（沒順手 refactor 鄰近）/ no over-engineering（沒為未來加抽象 flag hook）/ no premature abstraction（3 條相似 line 不抽 helper，5+ 才考慮）/ verifiable / 看到不對立刻修（無 TODO 假裝 OK）。
2. **檔案組織**：單一責任、介面清楚、可獨立測；改動後沒「肥到失控」（>500 行/多責任）；命名反映「做什麼」非「怎麼做」。
3. **廠商 SDK 隔離（CLAUDE.md ⛔#1）**：sales/ 沒誤 import ActionGroupControl/Board；vendor/ 沒被改（git diff 應為空）。
4. **多線程**：daemon thread 有 cleanup；vendor sticky 旗號沒誤呼叫（如空轉時 stopAction）；Queue/Event thread-safe。
5. **繁中**：註解/docstring/字串/commit 中文全繁體；簡體 → 標 file:line。
6. **Git**：commit 結尾有 `Co-Authored-By: Claude Opus <noreply@anthropic.com>`；沒用 `git add -A`/`.`。
7. **測試品質（若含 test）**：測行為非測 mock；用 inline lambda stub/callback 注入；TDD 順序對（先 RED）。

## 回報格式
- **Strengths**：具體 file:line 列做得好的設計決定。
- **Issues 分級**：**Critical**（必修否則拒收：bug/安全/規格違反/廠商誤改/線程不安全）｜**Important**（強烈建議：over-engineering/premature abstraction/越界 refactor）｜**Minor**（命名/註解/文案，主 agent 判決）。每條附 file:line。
- **Assessment 選 1**：✅ Approved（無 Critical/Important）｜⚠️ Approved with Minor concerns｜❌ Needs fixes（有 Critical/Important，回 sales-coder 修）。
```

## 主 agent 處理 reviewer 回報

| 回報 | 動作 |
|---|---|
| ✅ Approved | 進階段 3c（code_map 更新）+ 收尾 |
| ⚠️ Minor concerns | 判決：接受 + 進 3c / 自己 fix / 派 sales-coder fix 後 re-review |
| ❌ Needs fixes | 派 sales-coder 帶 Critical/Important 清單 fix → 重派 code-quality-reviewer 重審 |
