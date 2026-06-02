# BDD + TDD 開發流程（新增 `myProgram/sales/` 業務邏輯時必走）

> **🎯 何時讀本檔**：要**新增** `myProgram/sales/` 業務邏輯（新商品 / 新對話分支 / 新 L 層）。⚠️ 目前 **DORMANT**。

## 目錄
- DORMANT 狀態 + 重啟條件
- 4 階段鳥瞰
- 已知 pitfall（dispatcher / DEGRADED / Iron Law 判定 / commit 範圍）
- 既有產出（regression net）+ 設計決策

## ⚠️ 狀態：DORMANT

sales/ L0-L5 全層 + wire-up 完成後**休眠**。看到 DORMANT 標記後**自行判斷本輪是否真要重啟**（純 bug fix / refactor 不需）。S2-S7（tts / 動作 / OpenCV / threading）/ HTML 等多走「Pi 實機測 → 回報 → 改 code」迴圈（見 [incremental-rebuild.md](incremental-rebuild.md)），重 IO/硬體耦合、不適用 BDD+TDD 純 unit test 模型。

### 重啟條件（任一成立 → 重啟）
- 新增 `myProgram/sales/` 任何業務邏輯（新商品 / 新對話分支 / 新 L 層）。
- 修改既有 L0-L5 規格書（`resources/plans/業務程式邏輯規劃/L?.md`）導致 prod 邏輯要動。

### 不重啟（仍跑既有 tests 當回歸網）
純 docstring/註解｜一行 bug fix（[incremental-rebuild.md](incremental-rebuild.md) 直接 patch）｜既有 prod 純 refactor｜`constants.py` 單純調數字｜廠商 SDK 整合測試（選項 C 範圍外，本流程不涵蓋）。

> 既有 sales/ tests 是 **regression net 絕不能刪**；總數以 SessionStart hook 注入快照為準（持續累加，勿在文件寫死精確數）。wire-up/refactor 前後跑 `python -m pytest tests/sales/ -v` 驗證沒誤動。

---

## 4 階段鳥瞰（每 L 層獨立一輪，禁跨層合併）

1. **主 agent 寫 BDD spec（不派 subagent）**：讀規格書對應層 → 在 `tests/spec/L?_<short>_scenarios.py` 寫**只含註解 + 空函數 `pass`** 的 BDD 骨架（Given/When/Then + scenario ID，依 A/B-1/B-2/B-3/C 鏈路）→ **AskUserQuestion 強制確認**涵蓋規格全行為才往下。**禁**：此階段 import prod code、test body 寫實作。
2. **主 agent plan mode 規劃 TDD + Implementation**：列會動哪些 prod 檔 / 測試放哪 / 需要哪些 fixture / 預估 scenarios + 輪數 → ExitPlanMode 審 → 通過進階段 3。
3. **派單一 subagent 走 TDD（Red-Green-Refactor）**：EnterWorktree；prompt 塞規範（dispatch 協議 + vendor 禁改/不 import SDK＝選項 C + threading + Linux 路徑 + 繁中 + karpathy + TDD skill + testing-anti-patterns + bdd 規範）；**同一個 subagent** 連續走完（拆兩個違反 Iron Law 的 watch-fail）；每 scenario RED（跑 pytest 見 FAIL、確認 feature missing 非 typo）→ GREEN（最小 prod code、舊測試仍綠）→ REFACTOR；全 scenarios 完一個 commit（message 列實作哪些 scenarios/prod 檔 + pytest 摘要，**git add 明列檔名**含可能 untracked 的 spec 檔）。
4. **主 agent 審查 + 收尾**：Read 改動對照 CLAUDE.md → **自己跑 `python -m pytest tests/sales/ -v` 確認全綠（Iron Law）** → 條件性 3a/3b（pineedtodo 通常不觸發；個別測試檔通常不動 code_map）→ ExitWorktree keep → ff-merge → push → sync → cleanup。

---

## 已知 pitfall

**Dispatcher / 狀態機型 prod code 的 RED 排程**：禁止在 ENTRY scenario 的 GREEN 一次寫完整路由骨架（會讓後續鏈路 scenarios 直接 PASS＝違反 Iron Law 順序）。正確：ENTRY GREEN 只寫最小可印選單 + q 退出，A/B/C 鏈路各自獨立 RED→GREEN。

**DEGRADED-TDD-PARTIAL 容許條款**（dispatcher 即使警告也常踩——「最小 prod」對 dispatcher 定義模糊 + 工程直覺想一次設計 + redo 不划算）：**僅限 L1-L5 業務鏈路層的 dispatcher**，主 agent **接受** DEGRADED 不退回，但 subagent 必須在 commit message 標 `[DEGRADED-TDD-PARTIAL-L?]` + 誠實列哪些 scenarios 違反；prompt 內仍要警告（偶爾會成功）。**仍嚴格不容許 DEGRADED**：純函式/純資料 prod（`nlu.py`/`cart.py`/`constants.py`）必須逐 scenario RED；寫測試前先寫 prod（純順序倒）；沒看見任何 fail 就寫 prod。

**Iron Law 判定**（核心是「prod code 前必先看見 fail」，非「每 scenario 各自獨立 RED」）：模組空白時一次 pytest 看到全部 `AttributeError`（同根因批次 fail）→ 算「精神有守」不標 DEGRADED；之後逐 scenario 親見 FAIL→PASS。純順序倒 / 硬塞「應該會過」/ ENTRY 一次寫完整路由 → 標 DEGRADED。subagent 跑不起來 pytest → 回報主 agent（主 agent 修 conftest/import path；都跑不起 → degraded mode 標 `[DEGRADED-TDD]`）。

**Commit 範圍**：主 agent 在 worktree 寫的 BDD spec 檔若 untracked，subagent commit 可能漏 add → prompt 內 git add 範圍明列 `tests/spec/L?_*.py`。

---

## 既有產出 + 設計決策（重啟才看細節）

- **產出**：BDD spec（`tests/spec/L0-L5_*.py`）+ TDD tests（`tests/sales/test_*.py`，regression net，總數見 SessionStart 快照）+ 6 個 `run_?` 函式（`myProgram/sales/states/`：`l0_subroutine_a`/`l1`/`l2_l3_dialog`/`l4`/`l5` + `_l2_l3_qty_followup`）。
- **選項 C**：sales/ 嚴格不 import 廠商 SDK（Windows 無法 import → 整合測試違反工作邊界），純 unit test + callback 注入；廠商整合靠 Pi 實機驗（incremental-rebuild S1-S7 精神）。
- **為何每 L 層獨立一輪**：incremental-rebuild「每步只一變數」+ step-by-step pace + 失敗範圍可控。
- **為何 dormant 而非全刪**：tests 是 regression 安全網（S2-S7 誤動 dispatch 立即可知）；playbook 已驗證可行、重啟即複用；CLAUDE.md 已縮到 1 行 dormant marker，平時 context 成本極低。

---

**相關**：[dispatch.md](dispatch.md) / [worktree.md](worktree.md) / [incremental-rebuild.md](incremental-rebuild.md)（S2-S7 主工作流）/ [sdd.md](sdd.md)（BDD=scenarios / TDD=測試先行 / SDD=實作前契約）/ [myprogram-vendor.md](myprogram-vendor.md)；BDD 規範 `resources/plans/bdd規範.txt` + 範例 `resources/examples/bdd-寫法範例.txt`；TDD SKILL `.claude/skills/test-driven-development/`；業務規格 `resources/plans/業務程式邏輯規劃/`。
