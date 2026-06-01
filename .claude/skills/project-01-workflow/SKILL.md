---
name: project-01-workflow
description: >-
  Project_01 人形機器人銷售機器人專案（Raspberry Pi 上的規則匹配點餐 / 收款模擬系統）的所有工作流程協議與
  myProgram 領域知識。**只要在這個專案內做任何實作性工作就務必載入本 skill**——包括：改動 myProgram/ 下任何 .py
  code、派發 subagent / agent teams、走 git 收尾 / worktree / SDD 流程、判斷是否需要 Pi 端操作、維護專案資料結構、
  或 debug 多線程架構難收斂問題。即使使用者沒明說「載入 skill」，只要任務沾到上述任一情境就該主動載入並讀對應 reference。
---

# Project_01 工作流程與領域知識

人形機器人課程期末專題。Raspberry Pi 4 上的規則匹配點餐 / 收款模擬系統。本 skill 是專案所有 workflow 協議 +
myProgram 領域知識的單一入口。**SKILL.md 本體只負責路由**——細節全在 `references/`，用到哪個才 Read 哪個（progressive
disclosure，省常駐 context）。

> 安全紅線（⛔ 不改 vendor / Windows 不裝依賴 / 不 import vendor SDK / 不用 `git add -A`）與繁體中文產出規範，
> 由 CLAUDE.md 常駐 + hook 確定性強制；本 skill 不重複，但執行任何步驟時都假設它們生效。

---

## 路由表：當我要做 X → Read 哪個 reference

| 當我要… | Read |
|---|---|
| 改 `myProgram/` 下任何 .py code（走 SDD 流程） | [`references/sdd.md`](references/sdd.md) + [`examples/`](examples/) reviewer 範本 |
| 編 myProgram 前理解廠商 SDK / 動作組 API / silent fail | [`references/myprogram-vendor.md`](references/myprogram-vendor.md) |
| 編 myProgram 多線程 / Linux 路徑規範 / S6 非阻塞 input | [`references/myprogram-threading-paths.md`](references/myprogram-threading-paths.md) |
| 改 sales 對話狀態機 / 跨層流程（cancel / service confirm / C-2 / L4） | [`references/sales-dialog-design.md`](references/sales-dialog-design.md) |
| 改 sales TTS / 計時倒數 / UX 過場設計 | [`references/sales-tts-ux.md`](references/sales-tts-ux.md) |
| 派 subagent / 判斷派發規模門檻 / sales-coder | [`references/dispatch.md`](references/dispatch.md) |
| 進 worktree / 編輯 tracked 檔 / 收尾 merge | [`references/worktree.md`](references/worktree.md) |
| git 收尾 5 步 / push / sync Pi | [`references/standard-workflow.md`](references/standard-workflow.md) |
| 判斷 Pi 端操作 → 寫 pineedtodo / 更新 projectStructure / 部署細節 | [`references/pi-and-structure.md`](references/pi-and-structure.md) |
| 架構多線程 + queue + 旗號交互難收斂 | [`references/incremental-rebuild.md`](references/incremental-rebuild.md) |
| 新增 sales 業務邏輯（BDD+TDD，目前 dormant） | [`references/bdd-tdd.md`](references/bdd-tdd.md) |
| 繁簡對照 / 環境 quirk / 跨任務工作原則 | [`references/conventions.md`](references/conventions.md) |

---

## 跨任務鐵則（一行摘要，細節見對應 reference）

- **tracked 檔改動一律走 worktree 5 階段**（EnterWorktree → 編輯+commit → 審查 → ff-merge+push+sync → cleanup）。→ `worktree.md`
- **push 後永遠手動跑 `& sync_pi.ps1`**（不分 session 類型；hook 自動跑時為 idempotent no-op）。→ `standard-workflow.md`
- **改 `myProgram/{sales,main,tts,action,input_reader}.py` 必走 SDD**（spec/plan → user approval → sales-coder → 三段 reviewer 迴圈 → Iron Law 驗證）。→ `sdd.md`
- **中小以上改動派 sales-coder**；只有「超級小」（≤3 行純值替換）主 agent 才自 patch，且必先 invoke `karpathy-guidelines`。→ `dispatch.md`
- **派 subagent 後驗證 commit branch**（`git branch --contains <SHA>`，防 Gotcha M 落 main）。→ `worktree.md`
- **Iron Law：沒跑驗證指令不得宣告完成**（pytest / branch verify 要有 fresh evidence）。→ `sdd.md`
- **編寫 / 改 code 前遵守 `karpathy-guidelines`**（surgical / verifiable / no over-engineering / no premature abstraction）。
- **看到不對立刻修；fix 一條 bug 主動 grep 同類路徑一次掃完**。→ `conventions.md`

---

## 維護原則

本 skill 取代舊的 `.claude/rules/` + 大部分 memory（2026-06-01 遷移；設計見
`resources/specs/claude_md_to_skill_migration_2026-06-01_spec.md`）。新增 / 修改協議內容時：

- 路由型摘要留 SKILL.md，**具體協議內容寫進對應 `references/<topic>.md`**。
- 可執行代碼放 `scripts/`，用 `${CLAUDE_SKILL_DIR}/scripts/...` 引用。
- reference 之間用相對路徑連結（如 `[worktree](worktree.md)`），不要用舊的 `[[memory-slug]]` 語法。
