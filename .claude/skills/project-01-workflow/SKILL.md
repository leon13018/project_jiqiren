---
name: project-01-workflow
description: >-
  Project_01 人形機器人銷售機器人專案（Raspberry Pi 上的規則匹配點餐 / 收款模擬系統）的所有工作流程協議與
  myProgram 領域知識。**只要在這個專案內做任何實作性工作就務必載入本 skill**——包括：改動 myProgram/ 下任何 .py
  code、派發 subagent / agent teams、走 git 收尾 / worktree / SDD 流程、判斷是否需要 Pi 端操作、維護專案資料結構、
  或 debug 多線程架構難收斂問題。即使使用者沒明說「載入 skill」，只要任務沾到上述任一情境就該主動載入並讀對應 reference。
---

# Project_01 工作流程與領域知識

Raspberry Pi 上的規則匹配點餐 / 收款機器人。本 skill 是專案所有 workflow 協議 + myProgram 領域知識的單一入口。**本檔只路由**——細節在 `reference/`，用到才 Read（progressive disclosure，省常駐 context）。

> 安全紅線（⛔ 不改 vendor / Windows 不裝依賴 / 不 import vendor SDK / 不用 `git add -A`）+ 繁中產出，由 CLAUDE.md + hook 確定性強制；本檔不重複但假設生效。
> **檔案位置**：repo 檔（myProgram / tests / resources / .claude）→ `.claude/code_map.md`；skill 內部 → 下方路由表 + `examples/`（SDD reviewer 範本）+ `scripts/`（`clean-pi-pycache.ps1`）。

## 路由表：要做 X → Read 哪個 reference（用到才載）

| 要做… | Read `reference/` |
|---|---|
| 改 `myProgram/` 任何 .py code（走 SDD） | `sdd.md` + `examples/` reviewer 範本 |
| 廠商 SDK / 動作組 API / silent fail | `myprogram-vendor.md` |
| 多線程 / Linux 路徑 / S6 非阻塞 input | `myprogram-threading-paths.md` |
| sales 對話狀態機 / 跨層流程（cancel / service confirm / C-2 / L4） | `sales-dialog-design.md` |
| sales TTS / 計時倒數 / UX 過場 | `sales-tts-ux.md` |
| 派 subagent / 派發門檻 / sales-coder | `dispatch.md` |
| 進 worktree / 編 tracked 檔 / 收尾 merge | `worktree.md` |
| git 收尾 5 步 / push / sync Pi | `standard-workflow.md` |
| Pi 端操作 → pineedtodo / 結構變動 / 部署 | `pi-and-structure.md` |
| 多線程 + queue + 旗號難收斂 | `incremental-rebuild.md` |
| 新增 sales 業務邏輯（BDD+TDD，dormant） | `bdd-tdd.md` |
| 繁簡對照 / 環境 quirk / 跨任務原則 | `conventions.md` |

## 跨任務鐵則（細節見對應 reference）

- tracked 檔改動走 **worktree 5 階段**；**push 後永遠手動 `& sync_pi.ps1`**（→ `worktree.md` / `standard-workflow.md`）。
- 改 `myProgram/{sales,main,tts,action,input_reader}.py` **必走 SDD**（spec/plan → approval → sales-coder → 三段 reviewer → Iron Law；→ `sdd.md`）。
- **中小以上改動派 sales-coder**；只有 ≤3 行純值替換主 agent 才自 patch，且先 invoke `karpathy-guidelines`（→ `dispatch.md`）。
- **派 subagent 後驗證 commit branch**（`git branch --contains <SHA>`，防落 main；→ `worktree.md`）。
- **Iron Law：沒跑驗證指令不得宣告完成**（→ `sdd.md`）。
- **編 / 改 code 前遵守 `karpathy-guidelines`**；看到不對立刻修，fix bug 主動 grep 同類一次掃完（→ `conventions.md`）。

## 維護原則

- 取代舊 `.claude/rules/` + 大部分 memory（2026-06-01 遷移）。路由摘要留本檔，**協議細節寫進 `reference/<topic>.md`**，可執行碼放 `scripts/`。
- reference 間用相對路徑連結（`[worktree](worktree.md)`）。
- 新增 / 移動 reference / scripts / examples → **同步更新本檔路由表**；repo 結構變動 → 更新 `.claude/code_map.md`。
