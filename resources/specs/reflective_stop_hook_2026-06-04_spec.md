# 反思型 Stop Hook（手搓版）— Spec

> 日期：2026-06-04 ｜ 狀態：brainstorming 四題 + 方案 B 已核可
> 依據：`resources/research/self_improving_hooks_research_2026-06-04.md`（官方 security-guidance 三層藍本、prompt/agent 選型樹、防迴圈判準、反噬警告）＋ `CC_hooks_automation_best_practices_2026-06-03.md`（Stop hook 機制基本面）。
> 學習目標：**不裝現成 plugin**，依官方公開資訊手搓同形架構；完工後再逆向比對官方 plugin 找差距。
> 後續：plan → `resources/plans/reflective_stop_hook_2026-06-04_plan.md`。

## 1. 目標

每 turn 結束時自動反思「本輪有沒有值得固化的學習點」（踩到新坑 / 重複犯錯 / 學到新慣例），由 **fresh-context 的另一個 Claude**（headless `claude -p`，便宜 model）評審，產出**提議**到提議檔等人定奪——**絕不自動寫入** CLAUDE.md / NOTES / skill。

**成功標準**：(1) 有變動 turn 與每 X 輪定期統整都會觸發反思且 turn 零延遲；(2) 提議落地提議檔、下輪一行提示不漏不吵；(3) 防迴圈三件套（env 守衛 / session 上限 / 主題去重）可被手測證明；(4) 無 claude CLI 或呼叫失敗時 session 完全不受影響。

## 2. 設計原則（取自調研，違反即偏離藍本）

- **做事 / 評判分離**：反思者是 fresh context 的另一個 Claude，只看素材、無 sunk cost（security-guidance §1.3）。
- **不 block、零延遲**：hook 永遠 `exit 0` 無 decision；模型呼叫拋背景行程（同 §1.3「背景跑不延遲」）。
- **只提議、人定奪**：官方無「自動寫 CLAUDE.md」背書，且與本專案 lean & layered 衝突（調研 §4.2 明確不建議）。
- **抗反噬**：評審 prompt 明令「只報影響正確性 / 紅線 / 會重複發生的，無則回 NONE」（R2 反噬警告，調研 §6）。
- **硬上限**：仿官方「3-in-a-row / 30 files / 20 per hour」精神設本案三上限（§5）。

## 3. 組件

| 檔 | 職責 | git |
|---|---|---|
| `.claude/hooks/stop-reflect.ps1` | Stop hook 本體（輕）：守衛 → 觸發判斷 → 收集素材 → 拋背景 worker → 未讀提議一行提示 | tracked |
| `.claude/hooks/reflect-worker.ps1` | 背景行程：組 prompt → 呼 `claude -p` → 解析 → 去重 → append 提議檔 → 更新狀態 → log | tracked |
| `.claude/hooks/state/reflect/` | 狀態：`turn-count.txt`、`session-calls_<session_id>.txt`、`lock`、`last-notified.txt` | gitignored（state/ 既有 ignore） |
| `resources/reflections/proposals.md` | 提議檔（append-only；採納後人工清理） | **gitignored**（高頻變動，避免工作樹常駐 dirty 干擾收尾觸發） |
| `.claude/hooks/reflect.log` | worker 日誌（debug 用） | gitignored（`*.log` 既有 ignore） |
| `.claude/settings.json` | Stop 事件加掛 `stop-reflect.ps1`（與既有 stop-check / stop-sync 並行，互不依賴） | tracked |
| `.gitignore` | 加 `resources/reflections/` | tracked |

## 4. 資料流

```
turn 結束 → Stop fire → stop-reflect.ps1
  [守衛] CLAUDE_REFLECT_CHILD=1？→ exit 0（遞迴守衛）
         lock 存在？session 呼叫數 ≥ 上限？→ 跳過反思，仍做「未讀提示」
  [未讀提示] proposals.md pending 數 > last-notified → stdout JSON additionalContext
             「🪞 反思提議 +N 條待審（resources/reflections/proposals.md）」→ 更新 last-notified
  [觸發判斷]
     T1 變動觸發：git status --porcelain 非空 **或** HEAD ≠ 上次反思 marker（本專案 turn 內常已 commit，
                  純 status 會漏）→ 素材 = 未提交 diff + marker..HEAD 範圍 diff（cap：30 檔 / 400 行，
                  超出截斷並註記）；反思後更新 marker（state：`last-reflected-commit.txt`）
     T2 定期統整：turn-count ≥ X（預設 8）→ 素材 = transcript 尾段（stdin 的 transcript_path，
                  取最後 ~30 條 user/assistant 訊息、cap ~8KB；轉純文字）
     （T1 命中時優先 T1；任一觸發後 turn-count 歸零，否則 +1）
  [拋背景] 建 lock → Start-Process pwsh -NoProfile reflect-worker.ps1（detached，帶素材暫存檔路徑、
           session_id、觸發類型）→ 主 hook 立即 exit 0

reflect-worker.ps1（背景）
  [呼叫] $env:CLAUDE_REFLECT_CHILD=1 → claude -p <反思prompt> --model <REFLECT_MODEL，預設 haiku>
         （單發、禁工具；timeout 守 120s）
  [解析] 模型輸出 = NONE → 記 log、釋放 lock、結束
         否則逐條提議：{topic-slug｜內文 ≤3 行｜建議落地層 NOTES/CLAUDE.md/skill/memory}
  [去重] slug 已存在 proposals.md → 丟棄該條
  [落地] append proposals.md（格式：## <日期> <slug>｜T1/T2｜建議層 + 內文 + status:pending）
  [收尾] session-calls +1 → 釋放 lock → log 一行摘要
```

## 5. 防迴圈 / 防噪音三件套

1. **遞迴守衛**：`claude -p` 子行程會跑專案 hooks → worker 設 `CLAUDE_REFLECT_CHILD=1`；`stop-reflect.ps1` **與 `stop-sync-pi.ps1`、`stop-check-sales-pytest.ps1`** 開頭都加旗標早退（子 session 不 sync、不 block、不再反思）。
2. **session 上限**：每 session 模型呼叫 ≤ **10** 次（state 檔按 session_id 計）；達標後本 session 只做未讀提示。
3. **主題去重**：模型輸出必附 `topic-slug`（kebab-case），與 proposals.md 既有 slug 比對，重複即棄（仿第 1 層「每 pattern/session fire 一次」）。

補充：lock 檔防並發（前一 worker 未完成則本輪跳過反思）；lock 帶時間戳，> 10 分鐘視為殭屍自動清除。

## 6. 反思 prompt 要點（worker 內嵌，繁中）

- 角色：「你是 fresh-context 審計員，審另一個 agent 本輪工作的學習點，與其產出無利害關係。」
- 素材：T1 = diff + 檔清單；T2 = 對話尾段。
- 嚴格門檻：**只報「影響正確性 / 違反專案紅線 / 同類錯誤已出現 ≥2 次 / 使用者明確糾正過」的學習點**；風格喜好、一次性小失誤、模型本來就會做對的事一律不報；無 → 回 `NONE`。
- 輸出格式（機器可解析）：每條 `SLUG: <kebab>` / `LAYER: NOTES|CLAUDE.md|skill|memory` / `BODY: ≤3 行繁中`，條間以 `---` 分隔。
- 上限：每次最多 **3** 條。

## 7. 邊界 case

- **claude CLI 不存在 / 呼叫失敗 / timeout**：worker try/catch → log → 釋放 lock → 靜默結束；session 零感知。
- **worktree session**：proposals.md / state 一律錨定**主 checkout**（依既有 hook 慣例寫死 `$mainCheckout` 常數，同 stop-sync-pi），避免 worktree 寫入分裂副本。
- **resume / compact**：additionalContext 在 resume 會 stale replay（調研 §5.4）→ 未讀提示靠「每次 Stop 重算 pending 數」自然刷新，不依賴舊注入。
- **user 中斷 / API error**：Stop 不 fire（主筆記 §7.1）→ 該輪反思自然跳過，下輪補（turn-count 不丟）。
- **transcript 過大 / 格式變動**：T2 解析失敗 → log 後當作無素材跳過，不得拋錯。

## 8. 不做清單（YAGNI）

- ❌ 自動寫入 / 自動 commit 任何規範檔（只提議）。
- ❌ commit 級 agentic review（官方第 3 層）——先做第 2 層，逆向比對後再議。
- ❌ 免費 pattern-match 層（官方第 1 層）——紅線已有 PreToolUse 確定性 block，重複建設。
- ❌ proposals 的 UI / slash command 管理——直接開檔看。

## 9. 驗證計畫（Iron Law：逐項跑過才宣告完成）

1. **守衛測**：`$env:CLAUDE_REFLECT_CHILD='1'` 下 echo stdin 跑 stop-reflect → 立即 exit 0 無輸出。
2. **T1 手測**：working tree 製造假變動 + echo stdin → lock 出現、worker 被拋出、proposals.md 收到提議或 NONE log。
3. **T2 手測**：偽造 turn-count=X + 乾淨工作樹 → transcript 尾段路徑被讀、同上。
4. **去重測**：同 slug 二次注入 → 第二次被棄（log 可證）。
5. **上限測**：session-calls 偽造 =10 → 跳過反思、仍出未讀提示。
6. **真實 session 觀察**：一個正常開發 turn 後，turn 結束零延遲、下輪見一行提示。
7. **既有 hook 迴歸**：stop-sync-pi / stop-check-sales-pytest 在加守衛後行為不變（echo 手測 + 真實 turn 觀察 `Pi synced`）。

## 10. 實作與收尾規範

- 全部 hook 檔改動屬 `.claude/` → **強制 worktree 5 階段**；Meta-task（非 myProgram code）→ 主 agent 自實作（sdd.md 既有例外）。
- PS1 慣例跟既有 hook：`-NoProfile`、絕對路徑、try/catch + log、**UTF-8 with BOM**（實測修正：PS 5.1 對無 BOM 的繁中 .ps1 以 cp936 解析必爆 parse error；完整踩坑清單見 NOTES.md §12）。
- 完工同步：NOTES.md 新增本 hook 行為段（事件 / 觸發 / 上限 / 旗標）；settings.json 經 `/hooks` review 生效；繁中註解。
- 預設參數集中 PS1 頂部常數：`X=8`、`SESSION_CAP=10`、`REFLECT_MODEL='claude-haiku-4-5-20251001'`、`DIFF_CAP_FILES=30`、`DIFF_CAP_LINES=400`、`PROPOSAL_MAX=3`。
