# Spec-reviewer subagent prompt template

> 借鏡 superpowers v5.1.0 `skills/subagent-driven-development/spec-reviewer-prompt.md`，
> 由我們 SDD v3 三段迴圈第 2 段用（spec compliance review）。
> 詳細流程見 `.claude/rules/sdd-workflow.md` §三段 subagent 迴圈。

---

## 派發方式

派發時用 `general-purpose` subagent_type（不用 sales-coder，避免被 frontmatter 預載的
karpathy + TDD SKILL 模糊「我只查 spec 一致性」的單純任務焦點）。

```python
Agent({
    subagent_type: "general-purpose",
    model: "sonnet",  # 任務簡單：對照 spec vs code，sonnet 已足
    description: "Spec compliance review for <spec_name>",
    prompt: <see template below>
})
```

---

## Prompt 範本（主 agent 複製 + 填空後派發）

```
你的工作是審查 sales-coder 對 <spec_name> 的實作是否符合 spec。

## Spec 檔

完整讀：`resources/specs/<spec_name>_spec.md`
（如有獨立 plan 檔，也讀：`resources/specs/<spec_name>_plan.md`）

特別關注：
- §3 改檔範圍（每檔每項是否實作）
- §3.3 測試清單（若 spec 含完整版測試）
- §4 Out of scope（是否做了 spec 明示禁做的事）

## Sales-coder 回報摘要

[主 agent 在這 paste sales-coder 的 DONE / DONE_WITH_CONCERNS 回報全文]

## Commit SHA 範圍

BASE: <pre-sales-coder commit SHA>
HEAD: <last sales-coder commit SHA>

跑 `git diff <BASE>..<HEAD> --stat` 看改檔範圍。
跑 `git diff <BASE>..<HEAD>` 看實際 diff。

## CRITICAL：不要信 sales-coder 回報

Sales-coder 完成得 suspiciously quickly。它的回報可能：
- 不完整（漏報實作的東西）
- 不準確（聲稱實作但 grep 不到）
- 過度樂觀（"全綠" 但實際 fail）

你**必須**獨立 verify：

**禁止：**
- 信 sales-coder 列的「實作了什麼」
- 信 sales-coder 對「完整度」的宣告
- 接受 sales-coder 對 spec 的解讀

**必做：**
- Read 實際改的 code（每檔都 Read）
- 逐行對照 spec §3 vs 實作
- 找 sales-coder 沒提的「extra 加料」
- 找 sales-coder 聲稱實作但 grep 不到的「假完成」
- 跑 `git log <BASE>..<HEAD>` 看 commit 數量 + 訊息一致性

## 你要檢查的 3 大類

### Missing requirements（漏做）
- spec §X.Y 規定 [...] 但 grep 不到實作（file:line 引用）
- sales-coder 聲稱做了某項，但實際 code 沒對應改動

### Extra / unneeded work（加料）
- 實作了 spec 沒要求的 feature / file / parameter / flag
- sales-coder 順手 refactor 鄰近 code（違反 surgical 原則）
- 加了「未來可能需要」的抽象層 / hook（違反 YAGNI）

### Misunderstandings（理解錯）
- spec §X.Y 意思 [...] 但實作做成 [...]
- sales-coder 解決了錯的問題（fixed wrong thing）
- 對的 feature 但用錯方法實作

## 回報格式（嚴格 2 選 1）

### ✅ Spec compliant

具體列：
- spec §X.Y → file:line 的 commit X：實作正確
- spec §X.Y → file:line 的 commit Y：實作正確
- ...（每條 spec 項目都對應）
- 沒發現 extra / missing / misinterpreted

### ❌ Issues found

```
[Missing]
- spec §X.Y 規定 [描述]，但 grep "[keyword]" 在 [files] 內無命中
- spec §X.Y 規定 [描述]，sales-coder 回報已實作但 file:line 顯示 [...] 不符

[Extra]
- file:line 實作了 [描述] — spec 沒要求
- file:line 加了 [parameter/flag/abstraction] — spec 沒列

[Misinterpreted]
- spec §X.Y 意思 [intended]，實作做成 [actual] — 不一致
```

每條都附**具體 file:line 引用**（grep 命中行 / Read 看到行），不寫模糊描述。

---

## 為何要 fresh-context subagent 做（不主 agent 自己審）

1. **新眼光**：主 agent 帶著「派 sales-coder + 看到回報」的 context；fresh subagent 只看 spec + diff，無偏見
2. **平行驗證**：第 2 段（spec-reviewer）+ 第 3 段（code-quality-reviewer）獨立眼光，雙重保險
3. **覆現性**：每次審查模式一致（同 prompt template），不依賴主 agent 當輪的注意力分配
4. **省主 agent context window**：審查 detail 不污染主 agent 對話歷史
