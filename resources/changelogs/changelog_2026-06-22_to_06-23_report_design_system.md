# 報告設計系統 + 雙生 skill 重構弧（2026-06-22 ~ 06-23）

> 不改產品碼。承接上一弧（深色霓虹圖工具化 `architecture-diagram`），本弧把報告視覺**改宗 Anthropic 淺色編輯 + 手繪蠟筆風**，並把製作工具重構成「**風格權威 + production 產線**」雙生 skill。全程走 worktree；commit/push/codemap-health 全綠。
> commits：`c06eb1f`（report-design-system 誕生）→ `eaf4273`（architecture-diagram 改宗）→ `626b2a5`（QA 迴圈硬化）→ `28b98c4`（蠟筆 render caveat）→ `e795664`（diagrams 重組）→ `4ad3649`（共用 deps 預放）。

## 1. `report-design-system` skill 誕生（`c06eb1f`）

把 `resources/report/design-system.md`（Anthropic 淺色編輯風：報告 PDF §0–8,10 + 系統圖手繪蠟筆 §9）做成**完全自足、可打包帶走**的 skill：
- spec 搬進 `reference/{report-pdf.md, diagram-crayon.md}`，**原 `design-system.md` 改薄 pointer**（單一事實來源移入 skill）。
- `reference/render-and-qa.md`：蒸餾 render / 截圖 / SVG 匯出 / 視覺 critical gotchas（自足、不依賴 architecture-diagram）。
- vendored `assets/rough.js`（Rough.js hachure 填色）+ `assets/fonts/jason8.ttf`（清松手寫⑧塗鴉標題字）。
- `assets/benchmarks/`：圖①②③ 三張**定版對照基準**（HTML+PNG+SVG，淺色蠟筆 gold standard；HTML 引用 skill 內 `../rough.js`/`../fonts/jason8.ttf`、可就地 render；PNG=1× 給 `Read` 看、SVG=內嵌 2×PNG 供報告引用）。
- 唯一外部依賴＝ web font 走 Google Fonts CDN（render 需網路；可離線化但本 session 定 CDN）。
- skill-creator 流程：使用者選 **author-only**（視覺主觀 skill、不跑量化 eval）；PNG/SVG 格式經兩輪確認。

## 2. `architecture-diagram` 改宗淺色（`eaf4273`）

- **刪深色霓虹預設主題**，視覺風格**完全指向 `report-design-system`**；保留嚴謹流程（讀實際碼鐵則 / SDD / opus 實作 / 3-QA-panel）。
- `reference/visual-system.md` 挖空成 pointer；`assets/skeleton.html` 改**淺色自足起手式**（內聯 tokens + 3 蠟筆濾鏡 + Rough.js loader、平放依賴引用）；`render-pipeline.md` 保留 render 機制、風格/gotchas 指向 report-design-system。
- **雙生 skill 分工**（雙向 cross-ref）：`report-design-system` = 風格權威（+ 報告 PDF + 三基準）；`architecture-diagram` = 從頭畫圖的嚴謹 production（單向吃前者風格、不反向依賴）。深色 `theme/` + 深色圖 ①–⑤ 標 legacy。

## 3. QA 迴圈硬化（處理 pending 反思的真 bug，`626b2a5` + `28b98c4`）

反思揪出 architecture-diagram 的 QA 迴圈指令**其實跑不起來**，全修：
- 具名 implementer `impl-NN` + 缺陷用 `SendMessage(to: impl-NN)` 回送（不再 `Agent()` 開新 subagent 丟 context）。
- **render 全歸 orchestrator 序列獨占**（新增 step 5.5），implementer 只寫 HTML 不 render（解多圖並行撞單一共享瀏覽器）。
- QA 只讀靜態檔、不 render/不 GetPixel；**QA-B 比 dump `arrowSamples[]` 像素**（解「GetPixel ⊥ no-render」矛盾）；`render-pipeline.md §5.5` 加 dump schema 欄位 + §5.5b orchestrator render 後補像素取樣。
- QA loop **N=3 收斂上限**；**QA-C 讀對應 `.py` 稽核**（非只 spec、防 spec 本身已錯）；**step8 從 snapshots 搬已驗 PNG、禁重 render**；backlog/code_map 索引只在三式 commit 後改。
- 蠟筆 render caveat（`28b98c4`）：`file://` 自足只對 rough.js/jason8.ttf 成立、**web font 仍需網路**（離線 fallback）；`#crayon` 用 userSpaceOnUse、region 綁 `.stage` 尺寸 → 放大畫布要同步加大。

## 4. 反思全處理 + 歸檔（gitignored ledger）

- 20 條 pending（含 session 中反思機制新 append 的 2 條）→ **17 採納 + 3 否決**；連同上批 14 條已 adopted+落實 = **34 條歸檔** `reflections/archive/proposals_archived_2026-06-23.md`，`proposals.md` 收乾淨。轉 eval 一律否（皆 skill 指令/協議文字修正，非 navigator transcript 可客觀判定）。

## 5. `resources/architecture/diagrams/` 重組（`e795664` + `4ad3649`）

為「之後淺色圖生成不跟深色混亂」整理：
- **深色歸檔 `_legacy-dark/`**：深色 `theme/` + 深色圖 ①–⑤ 三式（保留為淺色重畫的來源素材，尤其無淺色版的 ④⑤；相對 theme link 完整）。
- **淺色交付主層**：①②③ png+svg（從基準複製；**html 源留基準**、零依賴/字型重複）。
- **共用 render 依賴預放**：`diagrams/rough.js` + `diagrams/jason8.ttf`（同層平放）→ 未來 ⑥–⑪ 淺色 html 落主層直接同層引用、不必再複製。
- `specs/00-diagram-backlog` + `01` spec 去過時（改宗淺色 pivot）；resources code_map + skill 路徑（theme→`_legacy-dark/theme/`）同步。
- `_archive/` 舊願景保留（使用者選）；5 個架構 .md（README/00/10/20/30）未動（本就整齊）。

## 狀態 / 下一步

- 雙生 skill 定版、6 commits 全 push、codemap-health 全綠、4 個 worktree 全清。
- **圖**：淺色 ①②③ 已交付（`diagrams/` png+svg）；**④⑤ 待淺色重畫**（深色源在 `_legacy-dark/`、取 layout/座標起手 + report-design-system 風格 + 三基準對照）；⑥–⑪ 待畫（淺色）。
- **下一步（使用者指定，新 session）＝載 `architecture-diagram` skill、把圖④⑤ 轉淺色。**
