# 開發日誌：2026-06-02 ~ 06-07 — Harness Engineering 弧

> 主程式（S1-S6）凍結期間的開發基建工程：hooks 反思閉環、skill 路由體系、EDD 回歸 harness、memory 治理、自進化機制。本期結束時 harness 四件套互鎖成型，回歸主程式開發。

## 更新紀錄

| 日期 | 里程碑 |
|---|---|
| 2026-06-02 | **官方陷阱稽核**：對照官方 hooks 文檔 17 條陷阱逐一比對 10 支 hook——零踩雷、多條主動防禦。**官方指南筆記二連**：memory 機制（`memory_official_guide`）+ 大型程式庫（`large_codebases_official_guide`）。EDD 題庫初代（`evals.json` 5 場景，skill_reference_cleanup 守門）。 |
| 2026-06-03 | **Pi sync 改 Stop hook**（`stop-sync-pi.ps1` + marker 自我修正）——繞過 background session PostToolUse 非確定性（雙實證 live + headless 可靠）；`auto-sync-pi` 退役。**block-git-add 誤擋根治**：settings `if:"Bash(git add *)"` gate（`1f8c4f3`）。hooks 自動化最佳實踐調研 ×2。 |
| 2026-06-04 | **harness 調研五連發**（overview / workflows 編排 / agent 記憶管理 / agent 自進化 / self-improving hooks）。**scaffolding 盤點**：4 субagent 盤點 → A 刪 2、B 降 5（自 patch 門檻 ≤10 行、resources 純文件直 main 等）、C 留觀察 7。**stop-reflect 反思 hook 上線**（背景 claude -p 掃 turn diff → proposals.md 只提議不自寫）。 |
| 2026-06-05 | **security-guidance 逆向**（只 clone 不裝）：採納候選 1-3（marker 成功才前移 / `quotePath=false` 保中文檔名 / 1MB log 輪轉）+ 修 3 個 bonus bug——worker exit-code 誤判成功（`aa33a85`）、**Stop 無 hookSpecificOutput**（live 實證 schema 整包拒收，hint 改純 systemMessage `696c5e8`）、素材截斷加標注。反思 ledger 慣例定型（status + 落實行 + rejected 疫苗）。 |
| 2026-06-06 | **EDD 回歸永久化**：`.claude/workflows/skill-edd-regression.js`（navigator→對抗 grader→verdict；雙格式題庫）+ 6 條路由場景，全量 18/18。**memory 健檢+整併**：`memory-health.ps1`（6 項檢查）+ 六步整併流程 + `memory_ledger.md`；首輪定奪 memory 5→3 條（karpathy 每輪/Pi SSH 升層 `79ac6ad`）。skill 新增 workflow-authoring / memory-management 兩 reference。 |
| 2026-06-07 | **自進化閉環補完**：`harness-evolution.md`（錯誤→eval 三判準 + graduation）+ `watchlist.md` 13 條集中 + SessionStart model 換代偵測 hook + s7-s10 場景（全 graduation 過）。**EDD 抓真缺口**：全量 14 場 55/56 → 跨桶路由修復（`52ec1f4`）→ 復驗 6/6。 |
| 2026-06-07 | **scripts vs workflows 落點判準**：deep-research（105 agent、23 claim 三票確認）→「誰持有 plan + 誰做工」判準入 workflow-authoring.md（`c1ee936`）；確認 workflow 腳本僅 JS 子集、plugin manifest 無 workflows 欄位。 |
| 2026-06-07 | **skill-creator + claude-md-management 逆向** → 候選 1-7 全採納：`codemap-health.ps1` + `claudemd-health.ps1`（Currency 死引用 + 行數預算）、grader 兼批 eval（weak_asserts）、結果落檔協議（iteration-N/*-result.json）、pass@k（k 預設 1）、baseline 對照（s9 實證 skill 增益 3/3 vs 0/3）、`aggregate-edd.ps1` 跨輪聚合（`365f3a1`+`01684bf`）。8 條不採納疫苗在案。 |
| 2026-06-07 | **weak_asserts 維護循環實跑兩輪**：頻次表→語意聚類→人定奪→graduation——s2 斷言改寫、s9 拆條+順序/授權考點（5/5）、s11 複合場景（夾帶判斷）；順手修 aggregate bare 污染 + 兩支健檢「worktree 假全綠」bug。題庫 11 場景全綠。**反思 worker haiku→sonnet**（實證誤報率 2/5，`b8610b9`）。 |
| 2026-06-07 | **NOTES.md 去噪拆遷**（598→128 行）：`hooks-system.md` + `hooks-gotchas.md` 兩個可路由 reference + 墓碑指標；s3 復驗 3/3 證路由接通（`132ecd7`）。**官方 skills 指南 PDF 全文轉寫**（stdlib 手搓抽取器：CMap 解碼+雙欄重排，`dee7056`）。worktree.md 補「Edit 前先 Read 副本」。 |

## 期末狀態（2026-06-07）

- **harness 四件套互鎖**：hooks（3 擋 + 反思 + sync + 快照/換代提醒 + 健檢 ×4 script）→ skill（SKILL.md 路由 17 列 + 18 reference）→ workflow（EDD 回歸 + pass@k + baseline）→ memory（3 條精實 + 健檢迴圈）。
- **題庫**：11 路由場景 + 5 深度場景，回歸基線全綠；iteration-5/6 共 12 份 run 落檔。
- **帳本三本**：proposals（反思）/ memory_ledger（記憶）/ final-consolidated per-iteration（weak_asserts）——零欠帳。
- **watchlist**：12 open（訊號未亮）+ 1 closed。
- **下一步**：回主程式——STT / HTML UI / demo 準備（見 `resources/roadmap.md`）。
