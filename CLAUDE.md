# Project_01 — 互動式銷售輔助機器人

人形機器人課程期末專題。Raspberry Pi 4 上的規則匹配點餐 / 收款模擬系統。

> 本檔只放**不能延遲載入的核心**（安全紅線 + 繁中 + skill 觸發表）。所有 workflow 協議與 myProgram 領域知識
> 都在 **`project-01-workflow` skill**（progressive disclosure，用到才載）。
> **檔案路徑 / 專案結構不在本檔重複——一律以 `.claude/code_map.md` 為單一事實來源。**

---

## ⛔ 絕對禁止（違反就壞東西）

1. **不要修改廠商 Hiwonder TonyPi SDK** 🔒 — `myProgram/vendor/` 下、code_map 標 🔒 的檔（`ActionGroupControl.py` / `Board.py`），含 Pi-only 依賴（`pigpio` / `RPi.GPIO` / `BusServoCmd` / `PWMServo` / `smbus2`），改了破壞硬體通訊。只能 `Read` 引用、`import` 使用。
2. **不要在 Windows 本機安裝任何依賴**（`pip` / `npm` / `apt`）🔒 — 執行環境是 Pi，本機只負責編輯與 git。（pytest 已全域裝為例外）
3. **不要嘗試在 Windows import / 執行任何依賴廠商 SDK 的程式碼** — 必 ImportError。
4. **不要用 `git add -A` / `git add .`** 🔒 — 明確列出檔名，避免誤加。

> 🔒 = PreToolUse hook 自動 block（hooks 位置與完整文檔 → code_map `.claude/` 段 / `hooks/NOTES.md`），不依賴主 agent 自律。
> **push 後永遠手動跑 `& sync_pi.ps1`**（PostToolUse hook 會試著自動跑，但 background session 不可依賴；手動跑為 idempotent no-op）。
> 編 sales code 或對應測試（路徑見 code_map）後沒跑 pytest → Stop hook block 一次提醒。
> 每次新 session 注入 git / 測試數快照（SessionStart hook）；派 subagent 注入標準規範（SubagentStart hook）。
> 寫檔含簡體字 → PostToolUse hook 純警示（不擋流程）。

---

## 🌏 輸出語言規範

所有 **程式碼註解、字串輸出、文件、commit message、markdown 內的中文** 一律使用 **繁體中文**。即使使用者用簡體中文溝通也不影響此規則 — 最終成果在 **中國台灣** 展示。（對話回覆本身可簡繁混合，這條只規範**產出物**。簡繁對照細節見 skill `reference/conventions.md`。）

---

## 📐 工作流程與領域知識 → 載入 `project-01-workflow` skill

本專案所有協議與知識都在該 skill。**做下列任一類工作前務必先載入 skill**，再依其 `SKILL.md` router 表 Read 對應 `reference/<topic>.md`（即使任務看似簡單也載入——規則會演進，重讀 reference 比憑記憶可靠）。**所有檔案位置先查 code_map。**

| 情境 | 載入後讀 |
|---|---|
| 改 `myProgram/` 下任何 .py code（檔見 code_map） | 走 SDD 流程（`sdd.md`）+ 對應領域 reference |
| 編 myProgram 前理解廠商 SDK / 線程 / 路徑 / sales 設計 | `myprogram-vendor.md` / `myprogram-threading-paths.md` / `sales-dialog-design.md` / `sales-tts-ux.md` |
| 派 subagent / agent teams、判斷派發規模門檻 | `dispatch.md` |
| 編輯任何 tracked 檔 / worktree 隔離 / git 收尾 / sync Pi | `worktree.md` + `standard-workflow.md` |
| 判斷是否需 Pi 端操作 → 寫 pineedtodo / 結構變動更新 code_map / 部署資訊 | `pi-and-structure.md` |
| 架構多線程 + queue + 旗號難收斂 | `incremental-rebuild.md` |
| 新增 sales 業務邏輯（BDD+TDD，dormant） | `bdd-tdd.md` |
| 繁簡對照 / 環境 quirk / 跨任務工作原則 | `conventions.md` |

> 編寫 / 修改 code 前一律遵守 `andrej-karpathy-skills:karpathy-guidelines`（主 agent 自寫前 invoke；sales-coder 已 frontmatter 預載）。

---

## ⚙️ 操作習慣

- **任何「檔案在哪 / 專案結構」問題 → 務必第一優先查 `.claude/code_map.md`**（本層索引，單一事實來源）。**逐層下沉導航**：要深入任何目錄 → 讀 `<該目錄>/.claude/code_map.md`（每層只索引自己那層、越深越細；某目錄無此檔 = 尚未建子索引，以上層說明為準）。讀子目錄 code_map 時 Claude Code 會自動載入該層 `CLAUDE.md`（按需）。
- 優先 `Read` / `Edit` / `Write` / `Glob` / `Grep` — Windows shell 只給 git 用。
- 規劃階段（還沒確定要做什麼）→ 暫停確認，不要先 commit。
- 任務完成回報：(1) 改了什麼 (2) 是否寫了 pineedtodo (3) Pi 是否同步成功 (4) 是否需使用者後續行動。

---

## 📋 維護原則

- **分層**：CLAUDE.md（核心紅線 + skill 觸發表）＋ **`code_map.md`（檔案路徑單一事實來源）** → `project-01-workflow` skill（router + `reference/` 細節）。
- memory 只剩 `user_profile` + `user_step_by_step_pace`；其餘協議 / 領域 / 歷史都在 skill + `resources/`。
- 新增 / 改協議 → 寫進 skill `reference/<topic>.md`；**新增 / 移動檔案 → 同步更新 `code_map.md`**；CLAUDE.md 只在觸發表加一行。
