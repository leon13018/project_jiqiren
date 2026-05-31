# Code-quality-reviewer subagent prompt template

> 借鏡 superpowers v5.1.0 `skills/subagent-driven-development/code-quality-reviewer-prompt.md`，
> 由我們 SDD v3 三段迴圈第 3 段用（code quality review）。
> **前提**：必先通過第 2 段 spec-reviewer ✅ 才派此 reviewer。
> 詳細流程見 `.claude/rules/sdd-workflow.md` §三段 subagent 迴圈。

---

## 派發方式

派發時用 `general-purpose` subagent_type + opus xhigh（任務需架構判斷，sonnet 不夠）。

```python
Agent({
    subagent_type: "general-purpose",
    model: "opus",
    description: "Code quality review for <spec_name>",
    prompt: <see template below>  # prompt 內塞 extended thinking + xhigh effort
})
```

---

## Prompt 範本（主 agent 複製 + 填空後派發）

```
你的工作是審查 sales-coder commit 的 code quality（已通過 spec compliance review，
現在純粹從 code 工程品質角度看）。請用 **extended thinking + xhigh effort** 仔細思考、
寧可慢、不要錯。

## 改動範圍

跑：
- `git diff <BASE>..<HEAD> --stat` 看每檔行數變化
- `git diff <BASE>..<HEAD>` 看完整 diff
- `git log <BASE>..<HEAD> --oneline` 看 commit 結構

BASE: <pre-sales-coder commit SHA>
HEAD: <last sales-coder commit SHA>

## Spec / Plan 參考（非審查重點）

`resources/specs/<spec_name>_spec.md`（已通過 spec-reviewer 確認符合）
（你不必再查 spec compliance — 那是上一段 reviewer 的工作）

## 審查重點（依 karpathy-guidelines + 本專案規範）

### 1. Karpathy 原則（最高優先）

- **Surgical**：只改了任務範圍內的檔？沒順手 refactor 鄰近 code？
- **No over-engineering**：沒為「未來可能需要」加抽象層 / flag / parameter / hook？
- **No premature abstraction**：3 條相似 line 不抽 helper；5 條以上才考慮 — 是否抽得過早？
- **Verifiable**：每個 commit 都對應可驗證的行為改變？
- **看到不對立刻修**：sales-coder 是否在 commit 內留了 TODO / 假裝 OK 的痕跡？

### 2. 檔案組織（依本專案規範）

- 每檔有清楚單一責任 + 介面 well-defined？
- 各 unit 可獨立 understood + tested？
- 改動後的檔有沒有「肥到失控」（>500 行 / 多責任混雜）？
- 命名清楚反映「做什麼」而非「怎麼做」？

### 3. 廠商 SDK 隔離（CLAUDE.md ⛔#1）

- sales/ code 是否誤 import 廠商 SDK（ActionGroupControl / Board）？
- vendor/ 下任何檔是否被改？（git diff 應該顯示無）

### 4. 多線程規範（threading-conventions）

- 任何 daemon thread 是否漏設 cleanup？
- vendor sticky 旗號是否誤呼叫（如 `Act.stopAction()` 空轉時）？
- Queue / Event 用法是否 thread-safe？

### 5. 繁中規範（output-language）

- 註解 / docstring / 字串輸出 / commit message 內中文是否全繁中？
- 簡體出現 → 標出 file:line

### 6. Git 操作規範

- commit message 結尾有 `Co-Authored-By: Claude Opus <noreply@anthropic.com>`？
- 沒用 `git add -A` / `git add .`（hook 會擋但 review 仍確認）？

### 7. 測試品質（若改動含 test）

- test 真的驗證行為（不是測 mock 行為）？
- test 用 inline lambda stub / callback 注入（依 testing-anti-patterns）？
- TDD 順序對（先 RED 才 GREEN，或屬 DEGRADED 容許的批次 fail 模式）？

## 回報格式

### Strengths（優點）

具體列：
- file:line — 做得好的設計決定（如：抽 helper 抽得剛好）
- file:line — 命名清晰反映意圖
- ...

### Issues（依嚴重度分類）

**Critical**（必修，否則拒收）：
- file:line — bug / 安全漏洞 / 規格違反
- file:line — 廠商 SDK 誤改 / 線程不安全

**Important**（強烈建議修，karpathy 違反等）：
- file:line — over-engineering 證據（為未來功能加 hook）
- file:line — premature abstraction（3 條 line 抽 helper）
- file:line — 順手 refactor 越界

**Minor**（小改善，主 agent 判決）：
- file:line — 命名可更精準（如 `clearLayers` vs `clearAllLayers`）
- file:line — 註解可更精簡
- file:line — 文案可口語化

### Assessment（總評）

選 1：
- ✅ Approved — Critical/Important 都無，Minor 可接受
- ⚠️ Approved with Minor concerns — Critical/Important 無，Minor 有建議
- ❌ Needs fixes — 有 Critical 或 Important，回 sales-coder 修

---

## 為何要 fresh-context subagent 做（不主 agent 自己審）

1. **與 spec-reviewer 雙重保險**：第 2 段查 spec compliance、第 3 段查 code quality，視角不同
2. **新眼光**：主 agent 跟 sales-coder 對話有「合作惯性」，fresh subagent 純粹從 code 看
3. **覆現性 + 平等**：每個 spec 都跑同樣 prompt，標準一致
4. **省主 agent context window**：detail review 不污染主對話

---

## 主 agent 處理 reviewer 回報

| Reviewer 回報 | 主 agent 動作 |
|---|---|
| ✅ Approved | 進階段 3b（projectStructure 更新）+ 收尾 |
| ⚠️ Approved with Minor concerns | 主 agent 判決：(a) 接受 Minor + 進階段 3b / (b) 自己 fix Minor / (c) 派 sales-coder fix Minor → re-review |
| ❌ Needs fixes | 派 sales-coder 帶 reviewer 的 Critical/Important 清單 fix → re-dispatch code-quality-reviewer 重審 |
