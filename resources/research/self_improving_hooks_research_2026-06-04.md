# 自我改進型 Hook 與進階自動化 Stop Hook — 調研筆記（淨增量版）

> 日期：2026-06-04 ｜ 觸發：使用者要求調研「反思型 hook / continuous-improvement / prompt/agent 型 hook / CLAUDE.md 自動更新提議」。
> **定位**：本檔只寫**前三份筆記沒涵蓋的淨增量**。hook 事件清單／exit code／handler 5 類型／Stop hook fire 機制／8-block cap／`stop_hook_active`／async output／Slack/webhook 範例**已窮盡**，凡屬機制基本面一律標「→ 見主筆記 §x」不重述。
>   - 主筆記＝`CC_hooks_automation_best_practices_2026-06-03.md`
>   - 補充筆記＝`CC_hooks_automation_blog_supplement_2026-06-03.md`
>   - SDK 筆記＝`CC-hooks.md`（agent-sdk hooks-guide 全文）
> **本檔焦點**：把「反思 / 自我改進 / 模型型 hook」從前三份的「低優先 idea 一行帶過」升級為**可落地的官方範例 + 完整 prompt/agent 設計準則 + 防迴圈設計**。

---

## 0. 來源清單（本檔新引或深挖；標 ⭐ = 對五大問題最關鍵）

| # | 標題 | URL | 性質 | 對本檔貢獻 |
|---|---|---|---|---|
| ⭐R1 | Catch security issues as Claude writes code（security-guidance plugin） | code.claude.com/docs/en/security-guidance | **官方 docs** | **唯一一份官方「生產級反思 / 模型審查型 Stop hook」完整實作說明**——回答 Q1/Q2/Q5 的核心 |
| ⭐R2 | Best practices for Claude Code | code.claude.com/docs/en/best-practices | **官方 docs**（原 anthropic.com/engineering 已 308 轉址至此） | 官方明文「Claude can write hooks for you」+ CLAUDE.md 自我改進迭代 + `/goal` 條件 + Stop hook gate 四階——回答 Q3/Q4 |
| R3 | Automate actions with hooks（hooks-guide） | code.claude.com/docs/en/hooks-guide | 官方 docs | prompt/agent hook 完整 JSON 範例 + `"ok"/"reason"` 格式 + timeout/turn 上限——回答 Q2（主筆記 S1 同源，本檔補 prompt/agent 段全文） |
| R4 | Hooks reference（prompt/agent/additionalContext 段） | code.claude.com/docs/en/hooks | 官方 docs | prompt hook 的 `$ARGUMENTS`、`decision` 輸出、additionalContext 跨事件支援表——回答 Q2/Q4 |
| R5 | security-guidance plugin 源碼 | github.com/anthropics/claude-plugins-official/tree/main/plugins/security-guidance | 官方範例碼 | 官方點名「running a separate model call from a hook and feeding the result back—a working example」 |
| C1 | claude-meta：Self-improving CLAUDE.md | github.com/aviadr1/claude-meta | 社群 | 「reflect→abstract→generalize→write CLAUDE.md」+ **meta-rules 防膨脹**的具體 pattern（社群，非官方背書） |
| C2 | kaizen / continuous-learning SKILL / retro Stop hook | github.com/imadAttar/kaizen、affaan-m/everything-claude-code、egghead.io retro 等 | 社群 | 反思型 Stop hook 的社群實作生態（佐證概念，實作細節非權威） |

> ⚠️ **數字權威性**（延續前三份判定）：blog 仍見「8 hook types / 60s timeout」屬過時，官方 doc 為準（事件 25+、command 600s）。本檔所有官方數字均取自 R1–R4。社群來源（C1/C2）僅作「概念存在性」佐證，**其數字 / prompt 字串不當官方事實引用**。

---

## 1. ⭐官方唯一的「生產級反思型 Stop hook」實作 = security-guidance plugin（R1/R5）

> **這是本次調研最重要的發現**。前三份只把「反思型 Stop hook」當「未來低優先 idea」一行帶過（主筆記 §8.2）。官方其實**已出貨一個完整、可安裝、生產級的範例**，且 hooks-guide 明文指其源碼為「running a separate model call from a hook and feeding the result back to the session」的 working example（R3 §What you can automate）。

### 1.1 它是什麼
官方 plugin，安裝後 Claude **邊寫 code 邊自審安全漏洞並在同一 session 修掉**（R1 開頭）：
> "The security guidance plugin makes Claude review its own code changes for common vulnerabilities while it works and fix what it finds in the same session."

### 1.2 三層深度（核心架構——可直接套用到「反思 CLAUDE.md」場景）
官方明列「reviews Claude's work at three points, each at a different depth」（R1 §What the plugin checks）：

| 層 | hook 事件 | 機制 | 模型成本 |
|---|---|---|---|
| 1. 每次 edit | `PostToolUse`（`Edit`/`Write`/`NotebookEdit`） | **純字串/regex pattern match，無模型呼叫**；命中 → `additionalContext` 附警告到下一步；每 pattern/file/session 只 fire 一次（防洪水） | 0 |
| 2. **每 turn 結束** | **`Stop`** | 算出本 turn 全工作樹 git diff（含 edit tool / Bash / subagent 造成的變更）→ 丟給**另一個 fresh-context 的 Claude** 做 security review → **背景跑（不延遲回覆）** → 有發現就**re-prompt Claude 讓它當 follow-up 修掉** | 每改檔 turn 約 1 次 |
| 3. 每次 commit/push | `PostToolUse`（`Bash`，filtered to `git commit`/`git push`） | 更深的 **agentic** review，會讀周邊呼叫者/sanitizer/相關檔降誤報 | agentic、多 turn |

→ **對本專案的直接對照（Q1/Q5 答案）**：
- 「反思型 Stop hook 提議 CLAUDE.md 更新」的官方藍本 = **第 2 層**：Stop 事件 → 算 diff → 另起一個 fresh Claude 評估 → 把發現餵回。把「security review」換成「本 turn 是否踩到新 gotcha / 慣例 → 提議寫進 NOTES.md / CLAUDE.md」即得本專案的反思 hook。
- 第 1 層的「純 pattern match 無模型、命中才 additionalContext、每 session 去重一次」**完全免費**，是本專案最划算的起手式（例：偵測到 Claude 在 Windows 嘗試 import Pi-only SDK 的字串 pattern → 附提醒）。

### 1.3 防「自己改自己」偏誤 + 防迴圈（Q4 答案，官方明文）
R1 §Review independence and limits 直接點名兩個本專案 spec 該抄的設計：
> "The plugin does not ask the same Claude instance that wrote the code to grade itself... run as a separate Claude call with a fresh context and a security-focused prompt: the reviewer starts from the diff, has no investment in the original approach, and is instructed only to find problems."
- **fresh context 評審**：審查者只看 diff，對原方案無 sunk-cost → 比讓主 Claude 自評可靠。
- **不 block，只 re-prompt**：「None of the layers block writes or commits. Findings reach the writing Claude as instructions」——即**用 additionalContext / re-prompt 而非 decision:block**（呼應 Q4「何時 additionalContext 而非 block」）。
- **硬性迴圈上限**：
  > 第 2 層「fires at most **three times in a row** before yielding back to you」；「covers up to **30 changed files** per turn」。
  > 第 3 層「capped at **20 [reviews] per rolling hour**」。
- **env 旗標逐層關**：`ENABLE_PATTERN_RULES=0` / `ENABLE_STOP_REVIEW=0` / `ENABLE_COMMIT_REVIEW=0` / `ENABLE_CODE_SECURITY_REVIEW=0` / `SECURITY_GUIDANCE_DISABLE=1`。

### 1.4 模型與成本（Q2「成本控制」答案，官方明文）
- 兩個模型型 review **預設 Claude Opus 4.7**；可用 `SECURITY_REVIEW_MODEL`（end-of-turn）與 `SG_AGENTIC_MODEL`（commit）覆寫成更便宜模型。
- 成本：「Expect roughly one review call per turn that changes files and one deeper review per commit」——**只有改檔的 turn 才花錢**（無改動 turn 不觸發模型）。
- 失敗降級：Agent SDK 裝不起來時，commit review「falls back to a single-shot review instead of the agentic one」——**agentic → 單發 prompt 的優雅降級**思路值得借鏡。
- **Windows 註記**（對本專案關鍵）：「On Windows the virtual environment step is skipped, so the agentic commit review runs only if `claude-agent-sdk` is already importable and otherwise falls back」。本專案本機是 Windows → 若採此 plugin，agentic 層預設降級為單發 review。

### 1.5 可擴充點 = 把「安全 review」改寫成「任意規則 review」的鉤子
- `.claude/claude-security-guidance.md`（純語言寫 threat model / checklist）→ **模型型 review 把它當額外 context 載入**，combined cap 8 KB。
- → **對本專案**：這證明「**一份 markdown 規則檔 + 一個 Stop hook 模型 review**」就能做出領域版反思 hook，不必寫複雜程式。可仿作「`.claude/claude-review-guidance.md` 列本專案紅線（繁中、勿改 vendor SDK、勿 `git add -A`）→ Stop hook 模型 review 掃本 turn 是否違反 → additionalContext 提醒」。但**本專案紅線已有 PreToolUse 確定性 block，模型 review 屬第二道、非必要**。

---

## 2. prompt 型 vs agent 型 hook：完整官方設計準則（Q2，深挖 R3/R4）

> 主筆記 §3 已列 5 種 handler 與 timeout 表。本檔補 hooks-guide 的**完整 prompt/agent 段全文 + 選型決策樹 + 輸出格式**（前三份未展開）。

### 2.1 prompt 型 hook（`type:"prompt"`）— 單輪 LLM 判斷
官方定義（R3 §Prompt-based hooks）：
> "For decisions that require judgment rather than deterministic rules, use `type: "prompt"` hooks. Instead of running a shell command, Claude Code sends your prompt and the hook's input data to a Claude model (**Haiku by default**) to make the decision."

- **模型只回 yes/no JSON**：`{"ok": true}` 放行；`{"ok": false, "reason": "..."}` 依事件不同：
  - `Stop` / `SubagentStop`：reason 餵回 Claude **繼續做**。
  - `PreToolUse`：deny 該 tool call，reason 當 tool error 餵回讓它調整。
  - `PostToolUse` / `PostToolBatch` / `UserPromptSubmit` / `UserPromptExpansion`：**turn 結束**，reason 在 chat 顯為 warning 行。
- **config 欄位**（R4）：`prompt`（必填，可用 `$ARGUMENTS` 佔位 = hook 輸入 JSON 序列化字串）、`model`（選填，預設 fast model）、`timeout`（預設 **30s**）。
- 官方 Stop hook prompt 範例（R3，最小可用）：
```json
{ "hooks": { "Stop": [ { "hooks": [
  { "type": "prompt",
    "prompt": "Check if all tasks are complete. If not, respond with {\"ok\": false, \"reason\": \"what remains to be done\"}." }
] } ] } }
```
> ⚠️ R3 用 `{"ok":...}` 格式，R4 reference 另出現 `{"decision":"allow"/"deny"}` 格式（含 `$ARGUMENTS` + `model` 範例）。兩者並存於官方文檔，**以 hooks-guide R3 的 `ok/reason` 為 Stop/SubagentStop 的主格式**；tool 事件可能用 `decision`。實作前以 `/hooks` 與當前 reference 為準（experimental 區域，格式可能演進）。

### 2.2 agent 型 hook（`type:"agent"`，**experimental**）— 多輪 + 工具驗證
官方定義（R3 §Agent-based hooks，含明確 ⚠️ 警告）：
> "Agent hooks are experimental... For production workflows, prefer command hooks."
> "When verification requires inspecting files or running commands, use `type: "agent"` hooks. Unlike prompt hooks which make a single LLM call, agent hooks spawn a subagent that can read files, search code, and use other tools to verify conditions before returning a decision."

- 同 `ok/reason` 格式，但 **timeout 預設 60s、最多 50 tool-use turns**。
- 官方範例（驗證測試通過才准 stop，`$ARGUMENTS` 注入 hook 輸入）：
```json
{ "hooks": { "Stop": [ { "hooks": [
  { "type": "agent",
    "prompt": "Verify that all unit tests pass. Run the test suite and check the results. $ARGUMENTS",
    "timeout": 120 }
] } ] } }
```

### 2.3 ⭐選型決策樹（官方原則，三條一句話）
1. **永遠先試 command hook**（確定性、零模型成本、最可靠；experimental 警告只在 prompt/agent）。
2. 需要**判斷但 hook 輸入資料就夠** → `prompt`（單輪、預設 Haiku、30s、便宜）。官方：「Use prompt hooks when the hook input data alone is enough to make a decision.」
3. 需要**對照 codebase 實際狀態驗證**（讀檔/跑指令）→ `agent`（多輪、60s、50 turns、貴且 experimental）。官方：「Use agent hooks when you need to verify something against the actual state of the codebase.」

→ **對本專案對照**：
- 現有 `stop-check-sales-pytest`（command + flag 一次性 block）**維持現狀最優**——它是確定性、零成本、最多 block 1 次。若要「真的判斷 pytest 是否過」可升級為 §2.2 的 agent hook，但**多花模型錢 + experimental**，本專案 flag pattern 已足夠（主筆記 §3/§7.3 已下此結論，本檔以官方選型樹再確認）。
- 「反思提議 CLAUDE.md 更新」屬「需判斷、輸入(diff/transcript)就夠」→ 適合 **prompt 型**（便宜）；只有要它「去讀別的檔確認慣例」才升 agent。

---

## 3. ⭐官方明文：「Claude 自己寫 hook」（Q3，R2 確證）

> 前三份只在 blog 層面提過「ask Claude to create its own hook-based notifications」（補充筆記 B3，定位為 idea）。**官方 best-practices doc（R2）把它寫成正式建議，且給了逐字 prompt 範例**——這是 Q3 的權威答案。

R2 §Set up hooks 原文：
> "**Claude can write hooks for you.** Try prompts like *"Write a hook that runs eslint after every file edit"* or *"Write a hook that blocks writes to the migrations folder."* Edit `.claude/settings.json` directly to configure hooks by hand, and run `/hooks` to browse what's configured."

hooks-guide（R3）同樣三處重申：「You can also ask Claude to write the hook for you by describing what you want in the CLI」、「To add, modify, or remove hooks, edit your settings JSON directly **or ask Claude to make the change**」。

通知型 hook 的「自建」起手式（R3 §Get notified，含 Windows 版——對本專案可用）：
```json
{ "hooks": { "Notification": [ { "matcher": "", "hooks": [
  { "type": "command",
    "command": "powershell.exe -Command \"[System.Reflection.Assembly]::LoadWithPartialName('System.Windows.Forms'); [System.Windows.Forms.MessageBox]::Show('Claude Code needs your attention', 'Claude Code')\"" }
] } ] } }
```

→ **對本專案對照**：
- 本專案要新增任何 hook，**正規做法 = 直接叫 Claude 寫進 `.claude/settings.json` 再 `/hooks` review**（`/hooks` 唯讀，見主筆記 §4）。security 上：直接編設定檔需 review 才生效，防靜默注入（主筆記 §8.7）。
- 補充筆記 B3 的「Pi sync 完成播音效 / 桌面通知」低優先 idea → 官方 Windows `MessageBox` 範例即可直接用（本機是 Windows）。仍屬非必要。

---

## 4. CLAUDE.md 自我改進迭代：官方立場 vs 社群自動化 pattern（Q1 延伸）

### 4.1 官方立場（R2 §Write an effective CLAUDE.md / §Avoid common failure patterns）— **人在環中的迭代，非全自動**
官方把 CLAUDE.md 當「會隨時間複利的活文件」，但**強調的是 human-in-loop 的 review/prune，不是無人值守自動寫入**：
> "Treat CLAUDE.md like code: review it when things go wrong, prune it regularly, and test changes by observing whether Claude's behavior actually shifts."
> "The file compounds in value over time."
> 失敗模式「The over-specified CLAUDE.md」的 fix：「Ruthlessly prune. **If Claude already does something correctly without the instruction, delete it or convert it to a hook.**」
> tune 手段：「adding emphasis (e.g., "IMPORTANT" or "YOU MUST") to improve adherence」。

並重申主筆記 S4 已記的「每 3–6 個月 / 新模型後 review，舊限制可能反綁新模型」。

→ **關鍵判讀**：官方**沒有**提供「Stop hook 自動把學到的東西寫進 CLAUDE.md」的範例或背書。大型 codebase blog 的那句「a stop hook can reflect... and propose CLAUDE.md updates while the context is fresh」是**概念性可能（propose，非 auto-commit）**，官方至今未出對應實作範例（R2/R3 皆無）。最接近的官方實作是 §1 的 security-guidance（review→re-prompt 修 code），**它改的是 code 不是 CLAUDE.md**。

### 4.2 社群 pattern（C1 claude-meta，**非官方、僅佐證概念存在**）
- 「magic prompt」：**Reflect → Abstract → Generalize → Write to CLAUDE.md**（反思這次錯誤 → 抽象出通則 → 寫進 CLAUDE.md）。
- 防膨脹靠 **meta-rules**（CLAUDE.md 內含「如何寫 rule」的 META 段）：用 NEVER/ALWAYS 絕對句、先講 why（1–3 bullet）、附具體指令、每 code block 一例、bullet 優先；新增 detail rule 時必同步更新頂部 summary（兩層結構）。
- C1 未明說用 Stop hook 還是 slash command 觸發（多數社群實作是 **slash command `/reflect` 手動觸發**，非 Stop hook 全自動——避免噪音與無謂模型成本）。

→ **對本專案對照（重要，含風險警示）**：
- 本專案 root CLAUDE.md「📋 維護原則」**已內建 meta-rules**（每行自問「移掉會不會讓 Claude 出錯」、root ≤100 / 子層 ≤60 行、零重複、紅線只在 root）——與 C1 的 meta-rules 思路**獨立同源、已實踐**，無需引入外部 pattern。
- ⚠️ **不建議做「Stop hook 自動寫入 CLAUDE.md」**：(a) 官方無背書範例；(b) 與本專案「lean & layered、訊息密度優先、ruthlessly prune」直接衝突（自動寫入易膨脹）；(c) 自動編輯恆載核心檔風險高。**較安全的本專案版 = 反思 hook 只「提議」（additionalContext 提醒「本 turn 似乎該把 X 記進 NOTES.md」），由人決定寫不寫**——這也呼應使用者 memory「下了明確指令才動」的 step-by-step pace。

---

## 5. 防迴圈 / 防噪音設計準則彙整（Q4，跨來源去重）

> 機制基本面（8-block cap 數字、`stop_hook_active` 早退範例、exit2 vs JSON 不可混用）→ **見主筆記 §5.2/§7.3 與 SDK 筆記**。本檔只補**「何時 additionalContext 而非 block」的官方判準**與新證據。

1. **預設用 additionalContext（不 block）**：security-guidance 全三層**皆不 block**，只把發現當 instruction 餵回（§1.3）。官方範例 plugin 用行動證明「**側效果型 / 提醒型反思 hook 應 exit0 + additionalContext / re-prompt，不要 decision:block**」。
2. **只有「硬性 gate」才 block**：R2 §Give Claude a way to verify 把 Stop hook 定位為「**deterministic gate**：runs your check as a script and **blocks the turn from ending until it passes**」，並當場提醒「Claude Code overrides the hook and ends the turn after **8 consecutive blocks**」。→ block 專留給「驗證必須通過才准結束」（如測試 gate），不用於「順便提醒一下」。
3. **additionalContext 跨事件支援**（R4）：`Stop` / `SubagentStop` **都支援 additionalContext**（可不 block 純注入觀察）；亦可與 `decision:"block"` + `reason` 並用。`SessionStart`/`Setup` 的 plain stdout 也進 context。
4. **additionalContext 在 resume 會「replay 舊值」變 stale**（R4 新增細節，前三份未記）：mid-session 注入的 context 存進 transcript，`--continue`/`--resume` 時是**重播舊文字而非重跑 hook** → 故「需反映當前狀態」的提醒應放 `SessionStart`（resume 會以 `source:"resume"` 重跑刷新），而非 PostToolUse/Stop。
5. **硬上限要設**：security-guidance 的「3-in-a-row / 30 files / 20 per hour / 8-cap」是官方範例的具體數字模板（§1.3）。本專案任何反思 hook 應比照設「每 session 最多提醒 N 次 / 同主題去重一次」（呼應第 1 層「每 pattern/file/session fire 一次」防洪水）。

---

## 6. 旁支官方自我改進原語（前三份未列，記備查）

- **`/goal` 條件 = 官方內建的「每 turn 自評」迴圈**（R2 §Give Claude a way to verify）：
  > "set the check as a `/goal` condition. A separate evaluator re-checks it after every turn and Claude keeps working until it holds."
  → 這是**官方版的「prompt 型 Stop hook 自我改進」without 寫 hook**——把驗收條件設成 `/goal`，系統自動每 turn 用獨立 evaluator 檢查到滿足為止。本專案要「持續做到某條件」時，`/goal` 可能比自寫 Stop hook 更省事（待驗證其與本專案 SDD/Iron Law 的結合）。
- **官方四階「如何讓 stop 收斂」**（R2 同段，由鬆到緊）：① 同一 prompt 內叫它跑 check 並迭代 → ② `/goal` 條件（每 turn 自動 re-check）→ ③ Stop hook 確定性 gate（block until pass，8-cap）→ ④ verification subagent / dynamic workflow（fresh model 反駁自己的結果）。本專案現用 ③（pytest flag）+ ④（SDD reviewer），符合官方光譜。
- **`/code-review` bundled skill**（R2 §Add an adversarial review step）：fresh subagent 看 diff 找 bug 回報 session——本專案已有對應（superpowers / code-review skill）。
- **過度反思的反噬警告**（R2 Callout，重要去噪）：「A reviewer prompted to find gaps will usually report some, even when the work is sound... Chasing every finding leads to over-engineering.」→ **反思型 hook 同理會「為提議而提議」**，務必指示它「只報影響正確性/紅線的，其餘略過」，否則製造噪音。直接呼應使用者 memory 的 lean-doc / 訊號密度原則。

---

## 7. 對本專案的淨增益總結（去重後，含明確不建議事項）

**可落地（若日後要做反思 hook）**：
1. **官方藍本 = security-guidance plugin 的三層**（§1）：第 1 層純 pattern match 免費、第 2 層 Stop+fresh-Claude review+re-prompt、第 3 層 commit agentic review。要做本專案反思 hook 直接抄這結構。
2. **選型樹**（§2.3）：先 command；要判斷且輸入夠 → prompt（Haiku/30s/便宜）；要讀 codebase 驗證 → agent（60s/50turns/experimental/貴）。本專案反思提議屬 **prompt 型**。
3. **防迴圈/防噪音模板**（§5）：提醒型一律 **exit0 + additionalContext，不 block**；block 只留給硬 gate；設「每 session 最多 N 次 + 同主題去重」；需反映現況的提醒放 `SessionStart` 不放 Stop（avoid stale replay）。
4. **新增 hook 正規流程**（§3）：直接叫 Claude 寫進 `.claude/settings.json` → `/hooks` review。Windows `MessageBox` 通知範例可直接用。

**明確不建議（風險 > 收益）**：
- ❌ **不做「Stop hook 自動寫入/commit CLAUDE.md」**（§4.2）：官方無背書範例、與本專案 lean&layered + ruthlessly prune 衝突、自動改恆載核心檔風險高。要做也只「**提議**」交人定奪（合於使用者 step-by-step pace）。
- ❌ **不把 `stop-check-sales-pytest` 升級為 agent hook**（§2.3）：現 command+flag 已確定性、零成本、最多 block 1 次；agent 版多花錢且 experimental。

**已被官方/社群印證、無需改動**：
- 本專案 root CLAUDE.md「維護原則」= claude-meta 的 meta-rules 思路，已獨立實踐（§4.2）。
- 本專案紅線用 PreToolUse 確定性 block（非模型 review）= 官方「hard rule 用 hook、advisory 用 CLAUDE.md」分工（R2 §Set up hooks）正解。
- SDD reviewer + pytest gate = 官方「stop 收斂四階」的 ③+④（§6）。

---

## 8. 最重要的 3 個發現（給主 agent）

1. **官方其實已出貨一個生產級「反思型 / 模型審查型 Stop hook」完整範例 = `security-guidance` plugin**（§1）。它用 `Stop` 事件算本 turn diff → 丟給**另一個 fresh-context 的 Claude** 審 → **背景跑、不延遲、re-prompt 讓 Claude 同 session 修**，並硬性「3-in-a-row / 30 files / 20 per hour」防迴圈、全程**不 block 只 additionalContext/re-prompt**、預設 Opus 4.7 可換便宜模型、Agent SDK 不可用時降級單發。**這就是前三份「反思型 Stop hook」idea 的官方可抄藍本**，且 hooks-guide 明文指其源碼為官方 working example。

2. **「Claude 自己寫 hook」是官方正式建議、非僅 blog idea**（§3，R2 逐字）：「Claude can write hooks for you. Try prompts like 'Write a hook that runs eslint after every file edit'」。本專案新增任何 hook 的正規路徑 = 叫 Claude 寫進 `.claude/settings.json` → `/hooks` review。

3. **「Stop hook 自動更新 CLAUDE.md」官方至今無實作範例、且本檔評估為不建議**（§4）：官方對 CLAUDE.md 自我改進的立場是 **human-in-loop 的 review/prune/「correct→convert to hook」**，自動寫入與本專案 lean&layered 直接衝突。安全的本專案版 = 反思 hook 只「提議」（additionalContext），由人定奪——並務必指示它「只報影響正確性/紅線者」以免淪為噪音（R2 反噬警告，§6）。prompt vs agent 選型、`$ARGUMENTS`、`ok/reason` 格式、防迴圈判準均已在 §2/§5 備齊可直接落地。
