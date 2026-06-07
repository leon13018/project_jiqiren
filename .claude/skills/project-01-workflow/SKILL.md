---
name: project-01-workflow
description: >-
  Project_01 人形銷售機器人專案（Raspberry Pi 規則匹配點餐 / 收款模擬系統）的工作流程協議與 myProgram 領域知識。
  **在本專案做任何實作性工作前都應載入本 skill**——包括改動 myProgram/ 下任何 .py code、派發 subagent / agent
  teams、走 SDD / worktree / git 收尾流程、判斷是否需 Pi 端操作、維護專案資料結構、或 debug 多線程難收斂問題。
  任務沾到上述任一情境即主動載入並讀對應 reference，即使使用者沒明說「載入 skill」。
---

# Project_01 工作流程與領域知識

Raspberry Pi 上的規則匹配點餐 / 收款機器人。本 skill 是專案所有 workflow 協議 + myProgram 領域知識的單一入口。**本檔只路由**——細節在 `reference/`，用到才 Read。

> 安全紅線（⛔ 不改 vendor / Windows 不裝依賴 / 不 import vendor SDK / 不用 `git add -A`）+ 繁中產出，由 CLAUDE.md + hook 確定性強制；本檔不重複但假設生效。
> **檔案位置**：repo 檔 → **巢狀 code_map**（root `.claude/code_map.md` + 各層 `<層>/.claude/code_map.md`，逐層下沉、第一優先查）；skill 內部 → 下方路由表 + `examples/`（SDD reviewer 範本）+ `scripts/`（`clean-pi-pycache.ps1`）。

## 路由表：要做 X → Read 哪個 reference（用到才載）

> **兩層觸發**：下表給**粗條件**命中候選 → 打開該 reference，其開頭 **🎯 何時讀本檔** 標頭給精確條件確認 / 細化是否深入（精確觸發條件留在各 reference，本表保持廣而短）。
> **複合任務跨多列**（如「實作＋部署到 Pi」「改 code＋git 收尾」）→ 命中的**每一列都要讀**，別只蓋主桶——次桶常藏跨檔 caveat（EDD 實測踩過：多線程任務漏讀 sync Pi 列的 pycache 坑）。

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
| 寫 / 改 dynamic workflow 腳本、spec 碼化判斷、跑 EDD 回歸 | `workflow-authoring.md` |
| memory 健檢 / 記憶整併 / 記憶維護 | `memory-management.md` |
| 反思/整併採納處理、踩雷轉 eval 場景、watch-list 重訪 / model 換代 | `harness-evolution.md` |
| 繁簡對照 / 環境 quirk / 跨任務原則 | `conventions.md` |

## 跨任務鐵則（細節見對應 reference）

- `myProgram/`、`tests/`、`.claude/` 改動走 **worktree 5 階段**；`resources/` 純文件新增 / 小修可直接 main（分層表 → `worktree.md`）。
- 改 `myProgram/{sales,main,tts,action,input_reader}.py` **必走 SDD**（spec/plan → approval → sales-coder → 三段 reviewer → Iron Law；小改動簡化條件 → `sdd.md`）。
- **中小以上改動派 sales-coder**；只有 ≤10 行純值替換主 agent 才自 patch，且先 invoke `karpathy-guidelines`（→ `dispatch.md`）。
- **派 subagent 後驗證 commit branch**（`git branch --contains <SHA>`，防落 main；→ `worktree.md`）。
- **Iron Law：沒跑驗證指令不得宣告完成**（→ `sdd.md`）。
- **編 / 改 code 前遵守 `karpathy-guidelines`**；看到不對立刻修，fix bug 主動 grep 同類一次掃完（→ `conventions.md`）。

## 維護原則

- 路由摘要留本檔，**協議細節寫進 `reference/<topic>.md`**，可執行碼放 `scripts/`。
- reference 間用相對路徑連結（`[worktree](worktree.md)`）。
- 新增 / 移動 reference / scripts / examples → **同步更新本檔路由表**，且新 reference 開頭加 **🎯 何時讀本檔** 自描述標頭；repo 結構變動 → 更新**該層**的 `.claude/code_map.md`（巢狀；判準見 `reference/pi-and-structure.md`）。
