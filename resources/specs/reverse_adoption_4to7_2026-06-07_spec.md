# 逆向採納候選 4-7 落實 + s2 斷言改寫 — Spec（2026-06-07）

## 目標

接續 `reverse_adoption_top3_2026-06-07_spec.md`，落實比對筆記 §4 候選 4-7 + 處理 weak_asserts 首發訊號（s2 斷言 3 非鑑別性）。

## 元件

### 0. s2 斷言 3 改寫（weak_asserts 訊號處置）

`scenarios_workflow_routing.json` s2 斷言 3：
- 原：「git add 必須明列檔名（禁 -A / .）」（全域不變規則，無鑑別力）
- 新：「收尾計畫中 git add 明列的檔名恰為本次新增的那一個檔（非 -A/.、亦無夾帶無關檔）」（場景特定——考「對這個情境正確套用規則」而非「複述規則」）
- 改寫後須重畢業（併入候選 4 的驗證 run）

### 1. 候選 4：pass@k 變異數（workflow js 增量）

- args 加選用 `k`（正整數，預設 1 = 現行為零變化；正式守門輪用 3）
- 每場景 skill-variant 跑 k 次（trial 攤平進 pipeline，流式不變）；JS 內聚合：每 assertion 跨 trial pass 數 → `majority_pass`（≥⌈k/2⌉）與 `pass_rate`
- verdict 改吃聚合結構：overall_pass = 全部 majority_pass；summary 註明各場景 rate（k>1 時）；weak_asserts 取聯集
- k=1 時聚合退化為現行語意（單 trial 即 majority）

### 2. 候選 5：baseline 對照（選擇性場景）

- 場景物件加選用 `baseline: true` → 該場景額外跑 1 個 bare navigator（prompt 明令**不載入 skill、不讀 `.claude/skills/`**，僅憑一般工程常識作答）+ 同 grader 評分
- verdict 收 `baseline_graded`，summary 報 delta（with-skill vs bare 的 pass 數差 = skill 增益證明）
- baseline 不乘 k（對照組單跑即可）；預設不開（token ×2 只給「去噪有疑慮」場景）

### 3. 候選 6：CLAUDE.md 分層健檢（`scripts/claudemd-health.ps1`）

六維 rubric 改造後的**機器可判定子集**（語意維度——分層分配、零重複——留給 agent 對照 root 維護原則人工判，不硬塞）：
- **行數預算**：root CLAUDE.md >100 行 = ❌、>90 = ⚠️；子層 >60 = ❌、>54 = ⚠️（root 維護原則的軟目標轉硬 check）
- **Currency 死引用**：各 CLAUDE.md 反引號路徑 token 驗存活（解析：本檔所在層 → repo root；同 codemap-health 的白名單/排除啟發式）
- `-RepoRoot` 參數；只報告不改檔；exit 0/1/2；UTF-8 BOM；用法併入 pi-and-structure.md 健檢段（與 codemap-health 同居）

### 4. 候選 7：跨輪聚合（`scripts/aggregate-edd.ps1`）

- 掃 `resources/evals/iteration-*/` 下符合新 schema 的 `*-result.json`（缺 `verdict`/`graded`/`scenario_ids` 的舊檔靜默跳過並計數）
- 聚合輸出：每 (scenario, assertion) 跨輪 pass 率（<100% = flaky/退化訊號優先列出）、weak_asserts 出現頻次表、各輪 run 一覽
- 純分析報告，exit 恆 0；`-EvalsDir` 參數（預設 `resources/evals`）；用法落 workflow-authoring.md 資產段

## 驗收

1. **C4+斷言改寫**：k=3 跑改寫後 s2 → 聚合結構合法、majority/rate 正確、改寫斷言通過重畢業（≈7 agent）
2. **C5**：baseline:true 跑 s9（最專案特定，bare navigator 預期顯著落後）→ delta 呈現於 summary（≈5 agent）
3. **C6**：fixture（超預算/死引用/全綠）+ 真實 repo 跑（預期全綠：root 55 行、子層 7-9 行）
4. **C7**：對 iteration-5 實資料跑 → 正確解析 4 份新 schema、跳過舊檔、輸出聚合表
5. 兩輪驗證 run 落檔 `iteration-6/`（新工作弧）；比對筆記 §4 候選 4-7 status → adopted + 落實行

## 流程約束

- js + 2 scripts + reference → worktree；場景改寫 + iteration-6 + 筆記 status → resources/ 直接 main
- 寫碼前 invoke karpathy-guidelines；js 改動守 workflow-authoring 檢查清單（k 經 args 傳入不碰 Date.now；聚合純 JS 不觸檔案）
