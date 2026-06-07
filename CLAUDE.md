# Project_01 — 互動式銷售輔助機器人

人形機器人課程期末專題。Raspberry Pi 4 上的規則匹配點餐 / 收款模擬系統。

> **本檔＝root 層、全域恆載核心**：安全紅線 + 繁中 + skill 載入指標 + 導航指標。
> workflow 協議與 myProgram 領域知識在 **`project-01-workflow` skill**（用到才載）。
> 分層 / 各層 CLAUDE.md 內容分配標準 → 見文末「📋 維護原則」。

---

## ⛔ 絕對禁止（違反就壞東西）

1. **不要修改廠商 Hiwonder TonyPi SDK** 🔒 — `myProgram/vendor/ActionGroupControl.py` / `Board.py`，改了破壞硬體通訊。只能 `Read` 引用、`import` 使用。（Pi-only 依賴等局部細節見 `myProgram/vendor/CLAUDE.md`）
2. **不要在 Windows 本機安裝任何依賴**（`pip` / `npm` / `apt`）🔒 — 執行環境是 Pi，本機只負責編輯與 git。（pytest 已全域裝為例外）
3. **不要嘗試在 Windows import / 執行任何依賴廠商 SDK 的程式碼** — 必 ImportError。
4. **不要用 `git add -A` / `git add .`** 🔒 — 明確列出檔名，避免誤加。

> 🔒 = PreToolUse hook 自動 block（不靠自律）。hooks 行為文檔與 .ps1 踩坑 → skill `reference/hooks-system.md` / `hooks-gotchas.md`（路由見 SKILL.md）。

---

## 🌏 輸出語言規範

所有 **程式碼註解、字串輸出、文件、commit message、markdown 內的中文** 一律使用 **繁體中文**。即使使用者用簡體中文溝通也不影響此規則 — 最終成果在 **中國台灣** 展示。（對話回覆本身可簡繁混合，這條只規範**產出物**。簡繁對照細節見 skill `reference/conventions.md`。）

---

## 📐 工作流程與領域知識 → 載入 `project-01-workflow` skill

做**任何實作性工作前務必先載入 `project-01-workflow` skill**（即使任務看似簡單——規則會演進，重讀 reference 比憑記憶可靠），再依其 `SKILL.md` **router 表**選讀對應 `reference/`。**路由與領域細節都在 skill，本檔不重複。**

> 編寫 / 修改 code 前一律遵守 `andrej-karpathy-skills:karpathy-guidelines`——每輪實作自寫前都要 invoke，session 早期載過不算（sales-coder 已 frontmatter 預載）。

---

## ⚙️ 操作習慣

- **任何「檔案在哪 / 專案結構」問題 → 務必第一優先查 `.claude/code_map.md`**（本層索引，單一事實來源）。**逐層下沉導航**：要深入任何目錄 → 讀 `<該目錄>/.claude/code_map.md`（每層只索引自己那層、越深越細；某目錄無此檔 = 尚未建子索引，以上層說明為準）。讀子目錄 code_map 時 Claude Code 會自動載入該層 `CLAUDE.md`（按需）。
- 優先 `Read` / `Edit` / `Write` / `Glob` / `Grep` — Windows shell 只給 git 用。
- 規劃階段（還沒確定要做什麼）→ 暫停確認，不要先 commit。
- 任務完成回報：(1) 改了什麼 (2) 是否寫了 pineedtodo (3) Pi 是否同步成功 (4) 是否需使用者後續行動。

---

## 📋 維護原則

- **分層**：CLAUDE.md（核心紅線 + skill 載入指標）＋ **`code_map.md`（檔案路徑單一事實來源）** → `project-01-workflow` skill（router + `reference/` 細節）。
- **CLAUDE.md 跨層內容分配標準**（官方 lean & layered）：
  - **root**：全域大局 + critical gotchas（安全紅線）+ 全域指標。critical 一律留 root（∵ `/compact` 後 root 倖存、子層蒸發，且需恆載事先勸阻）。
  - **子層**：只放該層局部慣例（怎麼跑測試 / 該讀哪份 reference / 局部 pattern / 解釋性細節）+ 指回 root 的薄 pointer，**不重述紅線**。
  - **零重複解釋**：紅線權威版只在 root；hook 才是強制執行、CLAUDE.md 是 advisory，故 root 紅線寫精簡即可。
  - 每行自問「移掉會不會讓 Claude 出錯」，不會就刪；每檔目標 root ≤~100 行、子層 ≤~60 行。
- memory 只放「使用者特質 / 授權 / 節奏」這類無處可歸的事實；協議 / 領域 / 歷史在 skill + `resources/`。
- 新增 / 改協議 → 寫進 skill `reference/<topic>.md`（router 在 `SKILL.md`）；**新增 / 移動檔案 → 同步更新該層 `code_map.md`**。
