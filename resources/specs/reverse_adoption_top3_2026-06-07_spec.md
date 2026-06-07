# 逆向採納候選 1-3 落實 — Spec（2026-06-07）

## 目標

落實 `skillcreator_claudemd_reverse_comparison_2026-06-07.md` §4 採納候選前三名（使用者已核可 1-7 全做、先做 1-3）：

1. **code_map 死引用檢查**（Currency 落地）——守「路徑單一事實來源」脫節風險
2. **grader 兼批 eval**（weak_asserts）——題庫自我改進訊號
3. **EDD 結果落檔協議**（iteration-N/<scope>-result.json）——跨輪聚合（候選 7）的資料基礎

## 元件

### 1. `skill scripts/codemap-health.ps1`（新）

- 掃全 repo 各層 `<層>/.claude/code_map.md`（排除 `.claude/worktrees/`），抽反引號 token 中「像路徑」的候選（結尾 `/`、含 `/`、或有副檔名；排除含空白/`<>`/`@`/`—`/`()`/`~` 開頭/磁碟機開頭），Test-Path 驗存活（支援 `settings*.json` 萬用字元）
- **三段解析 fallback**（對付行內巢狀與跨層引用）：本層 root → 同一行先前已解析成目錄的 token（新→舊）→ repo root；全失敗 = ❌ 死引用
- 介面：`-RepoRoot` 參數（預設 cwd）；只報告不改檔；exit 0/1/2（綠/僅警告/有死引用）；UTF-8 BOM
- 某份 code_map 解析不出任何候選 → ⚠️（格式異常訊號）
- 用法文檔落 `reference/pi-and-structure.md`（code_map 維護判準的權威家）新增小節；SKILL.md 既有「結構變動」路由列已覆蓋，不加列

### 2. `​.claude/workflows/skill-edd-regression.js` 增量

- `GRADE_SCHEMA`：required + properties 加 `weak_asserts`（string array；「即使導航錯也會 pass 的非鑑別 assertion，沒有就空陣列」）
- `gradePrompt` 末段加批題指令（依據 grader.md「weak assertion 的 pass 比沒有還糟」）
- `verdictPrompt` 加「彙整 graders 的 weak_asserts 進 summary 末尾」
- 順手修第 11 行過時註解 `resources/edd/` → `resources/evals/`

### 3. 結果落檔協議

- `resources/evals/README.md` 新增「結果落檔（每跑必落）」段：檔名 `iteration-N/<scope>-result.json`、schema `{date, run_id, scope, scenario_ids, verdict, graded}`、大局結論併 `final-consolidated.md`（沿 iteration-2/3/4 既有慣例）
- `reference/workflow-authoring.md` 本專案資產段 +1 行落檔提醒
- **Dogfood 回填**：把今天三輪 run（全量 14 場 `wf_48945bf8` / s3 復驗 `wf_7a62ecd9` / s10 graduation `wf_2d40d1cd`）從 task output 檔抽 result 落進 `iteration-5/`，附 `final-consolidated.md` 記 56/56 → 修復 → 復驗 6/6 → s10 3/3 的弧

## 驗收

1. codemap-health：fixture 注入（死引用/巢狀解析/跨層引用/萬用字元）各正確判定 + exit code 正確；對真實 repo 跑（主 checkout）——若抓到真死引用照實報告並修復 code_map
2. weak_asserts：graduation smoke（單場景）回傳含合法 weak_asserts 欄；verdict summary 有彙整
3. 落檔：iteration-5/ 三份 result.json schema 一致 + final-consolidated.md；README/workflow-authoring 協議可路由到

## 流程約束

- script + reference + SKILL.md（如需）+ workflow js → worktree 5 階段；README + iteration-5/ + 比對筆記 status 更新 → resources/ 直接 main
- 寫碼前 invoke karpathy-guidelines；workflow js 改動遵守 workflow-authoring.md 檢查清單
- 落實後更新比對筆記 §4 前三條 status（pending → adopted + 落實行）
