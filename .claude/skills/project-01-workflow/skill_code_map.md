# project-01-workflow skill — 內部導航索引（skill_code_map）

> skill 自己的檔案索引：要讀哪個 reference 先查這裡 / `SKILL.md` router。
> **repo 檔案位置（myProgram / tests / resources / .claude）一律見 `.claude/code_map.md`，本檔只管 skill 內部。**

## 入口
- `SKILL.md` — 路由表（任務情境 → 該讀哪個 reference）+ 跨任務鐵則

## reference/（用到才 Read）
| 檔 | 一行涵蓋 |
|---|---|
| `sdd.md` | myProgram code 改動的 SDD 流程（spec→plan→approval→implement→三段 reviewer→Iron Law） |
| `worktree.md` | tracked 檔改動的 worktree 5 階段 |
| `standard-workflow.md` | git 收尾 5 步 + Pi pycache |
| `dispatch.md` | subagent / agent teams 派發門檻、sales-coder |
| `myprogram-vendor.md` | 廠商 SDK / 動作組 API / silent fail |
| `myprogram-threading-paths.md` | 多線程 / Linux 路徑 / S6 非阻塞 input |
| `sales-dialog-design.md` | sales 對話狀態機 / 跨層流程 |
| `sales-tts-ux.md` | TTS / 計時倒數 / UX 過場 |
| `pi-and-structure.md` | Pi 端操作判斷 / pineedtodo / 結構變動維護（code_map） |
| `incremental-rebuild.md` | 多線程+queue+旗號難收斂的漸進重建 |
| `bdd-tdd.md` | 新增 sales 業務邏輯（BDD+TDD，dormant） |
| `conventions.md` | 繁簡對照 / 環境 quirk / 跨任務原則 |

## examples/
- `spec-reviewer-prompt.md` / `code-quality-reviewer-prompt.md` — SDD reviewer 範本

## scripts/
- `clean-pi-pycache.ps1` — 清 Pi __pycache__
